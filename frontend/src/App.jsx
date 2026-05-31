import React, { useEffect, useMemo, useRef, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_BASE ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

const RUN_VIEWS = [
  { key: "create", label: "运行创建" },
  { key: "monitor", label: "实时监控" },
  { key: "items", label: "逐题结果" },
  { key: "timeline", label: "多轮时间线" },
  { key: "bank", label: "题库浏览" },
  { key: "models", label: "模型接入" },
  { key: "history", label: "历史 Runs" },
  { key: "reports", label: "报告" },
];

const MODULE_OPTIONS = [
  "A1", "A2", "A3", "A4", "A5",
  "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
  "C1", "C2", "C3", "C4",
];

const PROTOCOL_OPTIONS = [
  { value: "anthropic_compatible", label: "Anthropic-compatible" },
  { value: "openai_compatible", label: "OpenAI-compatible" },
  { value: "gemini", label: "Gemini" },
  { value: "mock", label: "Mock" },
];

const AUTH_SCHEME_OPTIONS = [
  "x_api_key",
  "bearer",
  "x_goog_api_key",
  "none",
];

const MODEL_LOOKUP_OPTIONS = [
  "skip",
  "get_single",
  "list_contains",
];

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

async function apiFetch(path, options = {}) {
  try {
    const headers = { ...(options.headers || {}) };
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(`${API_BASE}${path}`, {
      headers,
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      let detail = text || `HTTP ${response.status}`;
      try {
        const parsed = JSON.parse(text);
        detail = parsed?.detail || detail;
      } catch {
        // Keep raw text fallback.
      }
      throw new Error(String(detail));
    }
    return response.json();
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(`无法连接后端接口：${API_BASE}。请确认后端服务已启动。`);
    }
    throw error;
  }
}

async function fetchReportUntilReady(runId, attempts = 8, delayMs = 1200) {
  let lastError = null;
  for (let index = 0; index < attempts; index += 1) {
    try {
      return await apiFetch(`/api/reports/${runId}`);
    } catch (error) {
      lastError = error;
      if (index < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }
  throw lastError || new Error("读取报告失败");
}

function asPrettyJson(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return JSON.stringify(value, null, 2);
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return value.toFixed(4).replace(/\.?0+$/, "");
  }
  return String(value);
}

function briefText(text, maxLen = 90) {
  if (!text) {
    return "-";
  }
  const compact = String(text).replace(/\s+/g, " ").trim();
  return compact.length > maxLen ? `${compact.slice(0, maxLen)}...` : compact;
}

function getRunCounts(run) {
  const progress = run?.progress || {};
  const totals = run?.totals || {};
  const total = progress.items_total ?? totals.items_total ?? 0;
  const processed = progress.items_processed ?? progress.items_completed ?? totals.items_processed ?? totals.items_completed ?? 0;
  const failed = progress.items_failed ?? totals.items_failed ?? 0;
  const succeeded = progress.items_succeeded ?? totals.items_succeeded ?? Math.max(0, processed - failed);
  const inflight = progress.items_inflight ?? Math.max(0, total - processed);
  return { total, processed, succeeded, failed, inflight };
}

function slugifyAlias(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

function humanizeError(message) {
  const text = String(message || "");
  if (text.includes("model_alias is required")) {
    return "需要填写 model_alias。建议填写一个稳定的英文别名，例如 `claude_3_5_sonnet`。";
  }
  if (text.includes("provider_id is required")) {
    return "需要填写 provider_id。";
  }
  if (text.includes("auth_env is required")) {
    return "当前认证方式需要填写环境变量名，例如 `OPENAI_API_KEY`。";
  }
  if (text.includes("Cannot delete provider with existing models")) {
    return "该 Provider 下面还有 Model Alias，需先删除或迁移这些模型后再删除 Provider。";
  }
  if (text.includes("Duplicate provider_id")) {
    return "provider_id 已存在，请换一个唯一 ID。";
  }
  if (text.includes("Duplicate model_alias")) {
    return "model_alias 已存在，请换一个唯一别名。";
  }
  return text;
}

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "" || value === false) {
      return;
    }
    search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function ScoreCard({ title, value, tone = "neutral" }) {
  return (
    <div className={`score-card score-card-${tone}`}>
      <div className="score-label">{title}</div>
      <div className="score-value">{value ?? "-"}</div>
    </div>
  );
}

function MiniTrendBar({ label, value, total, tone = "warm" }) {
  const pct = total > 0 ? Math.max(0, Math.min(100, (value / total) * 100)) : 0;
  return (
    <div className="mini-bar-row">
      <div className="mini-bar-head">
        <span>{label}</span>
        <strong>{formatValue(value)}</strong>
      </div>
      <div className="mini-bar-track">
        <div className={`mini-bar-fill mini-bar-${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ReportCharts({ reportData }) {
  if (!reportData?.summary) {
    return null;
  }
  const moduleRows = reportData.module_rows || [];
  const maxModuleScore = Math.max(1, ...moduleRows.map((row) => row.score || 0));
  const failureRows = Object.entries(reportData.failure_counts || {});
  const failureTotal = failureRows.reduce((sum, [, count]) => sum + count, 0);
  const statusCounts = reportData.status_counts || {};
  const processed = reportData.summary?.totals?.items_processed || 0;
  const succeeded = reportData.summary?.totals?.items_succeeded || 0;
  const failed = reportData.summary?.totals?.items_failed || 0;
  return (
    <div className="report-dashboard">
      <div className="report-grid">
        <div className="detail-card report-chart-card">
          <SectionTitle title="模块得分" meta={`共 ${moduleRows.length} 个模块`} />
          {moduleRows.length ? moduleRows.map((row) => (
            <MiniTrendBar key={row.module} label={row.module} value={row.score} total={maxModuleScore} tone="warm" />
          )) : <div className="muted-text">当前没有可视化模块分。</div>}
        </div>
        <div className="detail-card report-chart-card">
          <SectionTitle title="状态分布" meta={`Processed ${processed}`} />
          <MiniTrendBar label="Succeeded" value={succeeded} total={Math.max(processed, 1)} tone="ok" />
          <MiniTrendBar label="Failed" value={failed} total={Math.max(processed, 1)} tone="failed" />
          <div className="report-stat-grid">
            <SummaryMiniCard label="Retry Runs" value={reportData.lineage?.filter((item) => item.run_kind === "retry").length || 0} />
            <SummaryMiniCard label="Canonical Items" value={reportData.summary?.totals?.items_total || 0} />
          </div>
        </div>
      </div>
      <div className="report-grid">
        <div className="detail-card report-chart-card">
          <SectionTitle title="失败类型分布" meta={`共 ${failureTotal} 次失败`} />
          {failureRows.length ? failureRows.map(([failureType, count]) => (
            <MiniTrendBar key={failureType} label={failureType} value={count} total={Math.max(failureTotal, 1)} tone="failed" />
          )) : <div className="muted-text">当前没有失败类型。</div>}
        </div>
        <div className="detail-card report-chart-card">
          <SectionTitle title="运行链路" meta={`共 ${reportData.lineage?.length || 0} 个 run`} />
          <div className="lineage-list">
            {(reportData.lineage || []).map((row) => (
              <div className="lineage-row" key={row.run_id}>
                <div>
                  <div className="config-row-title mono">{row.run_id}</div>
                  <div className="config-row-subtitle">{row.run_kind} / parent {row.parent_run_id || "-"}</div>
                </div>
                <span className={`chip ${row.status === "completed" ? "chip-ok" : "chip-failed"}`}>{row.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function renderInlineMarkdown(text, keyPrefix = "md") {
  const chunks = String(text || "").split(/(`[^`]+`)/g);
  return chunks.map((chunk, index) => {
    if (chunk.startsWith("`") && chunk.endsWith("`")) {
      return <code key={`${keyPrefix}-${index}`}>{chunk.slice(1, -1)}</code>;
    }
    return <React.Fragment key={`${keyPrefix}-${index}`}>{chunk}</React.Fragment>;
  });
}

function MarkdownPreview({ content }) {
  const lines = String(content || "").split(/\r?\n/);
  const blocks = [];
  let listBuffer = [];

  function flushList() {
    if (!listBuffer.length) return;
    blocks.push(
      <ul className="markdown-list" key={`list-${blocks.length}`}>
        {listBuffer.map((item, index) => (
          <li key={`list-item-${index}`}>{renderInlineMarkdown(item, `list-${index}`)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  }

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      return;
    }
    if (trimmed.startsWith("- ")) {
      listBuffer.push(trimmed.slice(2));
      return;
    }
    flushList();
    if (trimmed.startsWith("### ")) {
      blocks.push(<h4 className="markdown-h4" key={`h4-${blocks.length}`}>{renderInlineMarkdown(trimmed.slice(4), `h4-${blocks.length}`)}</h4>);
      return;
    }
    if (trimmed.startsWith("## ")) {
      blocks.push(<h3 className="markdown-h3" key={`h3-${blocks.length}`}>{renderInlineMarkdown(trimmed.slice(3), `h3-${blocks.length}`)}</h3>);
      return;
    }
    if (trimmed.startsWith("# ")) {
      blocks.push(<h2 className="markdown-h2" key={`h2-${blocks.length}`}>{renderInlineMarkdown(trimmed.slice(2), `h2-${blocks.length}`)}</h2>);
      return;
    }
    blocks.push(<p className="markdown-p" key={`p-${blocks.length}`}>{renderInlineMarkdown(trimmed, `p-${blocks.length}`)}</p>);
  });
  flushList();

  if (!blocks.length) {
    return <div className="muted-text">暂无报告内容。</div>;
  }
  return <div className="markdown-preview">{blocks}</div>;
}

function SectionTitle({ title, meta }) {
  return (
    <div className="section-head">
      <div className="panel-title">{title}</div>
      {meta ? <div className="section-meta">{meta}</div> : null}
    </div>
  );
}

function EmptyState({ title, description, actionLabel, onAction }) {
  return (
    <div className="empty-state">
      <div className="empty-title">{title}</div>
      {description ? <div className="muted-text">{description}</div> : null}
      {actionLabel && onAction ? (
        <button className="action-button secondary" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function InfoBanner({ tone = "neutral", title, body }) {
  return (
    <div className={`info-banner info-banner-${tone}`}>
      <div className="info-banner-title">{title}</div>
      <div className="info-banner-body">{body}</div>
    </div>
  );
}

function StatusPill({ configured, envName }) {
  return (
    <span className={`status-pill ${configured ? "status-pill-ok" : "status-pill-warn"}`}>
      {configured ? `已配置 ${envName || ""}`.trim() : `待配置 ${envName || "环境变量"}`.trim()}
    </span>
  );
}

function RunArtifactStatus({ ready, label }) {
  return (
    <span className={`status-pill ${ready ? "status-pill-ok" : "status-pill-neutral"}`}>
      {ready ? `${label} 就绪` : `${label} 未生成`}
    </span>
  );
}

function PathList({ title, paths }) {
  const rows = Object.entries(paths || {}).filter(([, value]) => value);
  if (!rows.length) {
    return null;
  }
  return (
    <div className="detail-section">
      <div className="detail-title">{title}</div>
      <div className="path-list">
        {rows.map(([key, value]) => (
          <div className="path-row" key={key}>
            <span className="path-key">{key}</span>
            <div className="path-value-wrap">
              <code className="path-value" title={String(value)}>{String(value)}</code>
              <CopyButton value={value} label="复制路径" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryMiniCard({ label, value }) {
  return (
    <div className="mini-stat">
      <div className="mini-stat-label">{label}</div>
      <div className="mini-stat-value">{value}</div>
    </div>
  );
}

function CopyButton({ value, label = "复制" }) {
  async function handleCopy(event) {
    event.stopPropagation();
    if (!value) return;
    try {
      await navigator.clipboard.writeText(String(value));
    } catch {
      // Best-effort copy only.
    }
  }
  return (
    <button className="mini-button" type="button" onClick={handleCopy} disabled={!value}>
      {label}
    </button>
  );
}

function ModalDialog({ open, title, subtitle, onClose, children }) {
  if (!open) {
    return null;
  }
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <div className="modal-title">{title}</div>
            {subtitle ? <div className="modal-subtitle">{subtitle}</div> : null}
          </div>
          <button className="modal-close" type="button" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}

function PaginationBar({ page, pageSize, total, onPageChange, onPageSizeChange }) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / pageSize));
  return (
    <div className="pagination-bar">
      <div className="pagination-meta">
        <span>共 {total} 条</span>
        <span>第 {page} / {totalPages} 页</span>
      </div>
      <div className="pagination-actions">
        <label className="pagination-size">
          每页
          <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
            {PAGE_SIZE_OPTIONS.map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </label>
        <button className="mini-button" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          上一页
        </button>
        <button className="mini-button" type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          下一页
        </button>
      </div>
    </div>
  );
}

function renderResponseText(response) {
  if (!response) return "暂无响应";
  if (response.mode === "single_turn") return response.text || "空响应";
  if (Array.isArray(response.turn_results)) {
    return response.turn_results
      .map((turn) => `Turn ${turn.turn_index}\n[Prompt]\n${turn.prompt || ""}\n\n[Response]\n${turn.text || ""}`)
      .join("\n\n----------------\n\n");
  }
  if (response.scenario_results) {
    return Object.entries(response.scenario_results)
      .map(([branch, turns]) =>
        `Branch ${branch}\n${turns
          .map((turn) => `Turn ${turn.turn_index}\n[Prompt]\n${turn.prompt || ""}\n\n[Response]\n${turn.text || ""}`)
          .join("\n\n")}`,
      )
      .join("\n\n================\n\n");
  }
  return asPrettyJson(response);
}

function ToggleModule({ selected, onToggle }) {
  return (
    <div className="module-grid">
      {MODULE_OPTIONS.map((module) => (
        <button
          key={module}
          type="button"
          className={selected.includes(module) ? "module-pill active" : "module-pill"}
          onClick={() => onToggle(module)}
        >
          {module}
        </button>
      ))}
    </div>
  );
}

function PromptBlock({ bankItem }) {
  if (!bankItem) {
    return <div className="muted-text">暂无题目内容。</div>;
  }
  if (bankItem.item_format === "single_turn") {
    return <pre className="detail-pre">{bankItem.prompt_template || "无题面"}</pre>;
  }
  return (
    <div className="turn-list">
      {(bankItem.turn_script || []).map((turn, idx) => (
        <div className="detail-block" key={`${bankItem.question_id}-${turn.branch_key || "default"}-${turn.turn_index}-${idx}`}>
          <div className="detail-subtitle">
            Turn {turn.turn_index} / {turn.branch_key || "default"} / {turn.speaker}
          </div>
          <pre className="detail-pre">{turn.content_template}</pre>
        </div>
      ))}
    </div>
  );
}

function DetailCard({ title, item, timelineData }) {
  const bank = item?.bank_item || item;
  const hasScoreContext = Boolean(item?.bank_item);
  return (
    <div className="detail-card">
      <SectionTitle title={title} />
      {!item && !bank ? (
        <div className="muted-text">选择一条记录后查看详情。</div>
      ) : (
        <>
          <div className="chip-row">
            <span className="chip">{bank.question_id}</span>
            <span className="chip">{bank.module}</span>
            <span className="chip">{bank.subtype || "-"}</span>
            {item?.status ? (
              <span className={`chip ${item.status === "ok" ? "chip-ok" : "chip-failed"}`}>{item.status}</span>
            ) : null}
            {item?.primary_score !== undefined ? (
              <span className="chip">score {formatValue(item.primary_score)}</span>
            ) : null}
          </div>

          <div className="detail-section">
            <div className="detail-title">原题内容</div>
            <PromptBlock bankItem={bank} />
          </div>

          <div className="detail-section">
            <div className="detail-title">标准答案与评分</div>
            <div className="meta-grid">
              <div>
                <div className="detail-subtitle">Ground Truth</div>
                <pre className="detail-pre">
                  {typeof bank.ground_truth === "string" ? bank.ground_truth : asPrettyJson(bank.ground_truth)}
                </pre>
              </div>
              <div>
                <div className="detail-subtitle">Scoring</div>
                <pre className="detail-pre">{asPrettyJson({
                  method: bank.scoring_method || item?.score_method,
                  params: bank.scoring_params,
                })}</pre>
              </div>
            </div>
          </div>

          {hasScoreContext ? (
            <>
              <div className="detail-section">
                <div className="detail-title">模型输出</div>
                <pre className="detail-pre">{renderResponseText(item.response)}</pre>
              </div>

              <div className="detail-section">
                <div className="detail-title">评分细节</div>
                <pre className="detail-pre">{asPrettyJson(item.score_details)}</pre>
              </div>

              {timelineData ? (
                <div className="detail-section">
                  <div className="detail-title">完整时间线</div>
                  <div className="timeline-list">
                    {(timelineData.timeline || []).map((step, idx) => (
                      <div className="timeline-item" key={`${step.branch_key || "default"}-${step.turn_index}-${idx}`}>
                        <div className="timeline-head">
                          <span>Turn {step.turn_index || idx + 1}</span>
                          <span>{step.branch_key || "default"}</span>
                          <span>{step.step_type}</span>
                        </div>
                        <div className="timeline-grid">
                          <div>
                            <div className="detail-subtitle">Prompt</div>
                            <pre className="detail-pre">{step.prompt || "-"}</pre>
                          </div>
                          <div>
                            <div className="detail-subtitle">Response</div>
                            <pre className="detail-pre">{step.response || step.error || "-"}</pre>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="detail-section">
                <div className="detail-title">运行信息</div>
                <pre className="detail-pre">{asPrettyJson({
                  failure_type: item.failure_type,
                  latency_ms: item.latency_ms,
                  attempt_run_id: item.attempt_run_id,
                  source_run_id: item.source_run_id,
                  error: item.error,
                })}</pre>
              </div>
            </>
          ) : null}

          <div className="detail-section">
            <div className="detail-title">来源信息</div>
            <pre className="detail-pre">{asPrettyJson(bank.provenance)}</pre>
          </div>
        </>
      )}
    </div>
  );
}

function App() {
  const bankRequestSeq = useRef(0);
  const runRequestSeq = useRef(0);
  const [view, setView] = useState("create");
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [connections, setConnections] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runItems, setRunItems] = useState([]);
  const [selectedQuestionId, setSelectedQuestionId] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [report, setReport] = useState(null);
  const [bankRows, setBankRows] = useState([]);
  const [bankTotal, setBankTotal] = useState(0);
  const [runItemsTotal, setRunItemsTotal] = useState(0);
  const [bankFacets, setBankFacets] = useState({ total: 0, modules: [], subtypes: [], item_formats: [] });
  const [systemPaths, setSystemPaths] = useState(null);
  const [selectedBankQuestionId, setSelectedBankQuestionId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingBank, setLoadingBank] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingRunItems, setLoadingRunItems] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [editingModelAlias, setEditingModelAlias] = useState(null);
  const [editingConnectionId, setEditingConnectionId] = useState(null);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [showModelForm, setShowModelForm] = useState(false);
  const [showConnectionForm, setShowConnectionForm] = useState(false);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [itemPage, setItemPage] = useState(1);
  const [itemPageSize, setItemPageSize] = useState(20);
  const [bankPage, setBankPage] = useState(1);
  const [bankPageSize, setBankPageSize] = useState(20);
  const [selectedHistoryRunIds, setSelectedHistoryRunIds] = useState([]);

  const [runForm, setRunForm] = useState({
    provider_id: "",
    model_alias: "",
    model_connection_id: "",
    modules: [],
    smoke: false,
    timeout: 45,
    concurrency_limit: 1,
    max_items: "",
  });

  const [itemFilters, setItemFilters] = useState({
    module: "",
    status: "",
    failure_type: "",
    question_id: "",
    search: "",
    canonical_only: false,
  });

  const [bankFilters, setBankFilters] = useState({
    module: "",
    subtype: "",
    item_format: "",
    keyword: "",
  });

  const [providerForm, setProviderForm] = useState({
    provider_id: "",
    display_name: "",
    protocol: "anthropic_compatible",
    base_url: "",
    auth_scheme: "x_api_key",
    auth_env: "",
    headers_template_text: "{}",
    model_lookup_mode: "skip",
    enabled: true,
  });

  const [modelForm, setModelForm] = useState({
    model_alias: "",
    provider_id: "minimax_anthropic",
    display_name: "",
    model_name: "",
    default_timeout: 45,
    default_max_tokens: 512,
    supports_multi_turn: true,
    enabled: true,
  });

  const [connectionForm, setConnectionForm] = useState({
    connection_id: "",
    vendor_name: "",
    note: "",
    homepage_url: "",
    display_name: "",
    protocol: "anthropic_compatible",
    base_url: "",
    auth_scheme: "x_api_key",
    auth_env: "MINIMAX_API_KEY",
    api_key: "",
    model_name: "",
    default_timeout: 45,
    default_max_tokens: 512,
    supports_multi_turn: true,
    enabled: true,
    headers_template_text: "{}",
    model_lookup_mode: "skip",
  });

  useEffect(() => {
    refreshProviders();
    refreshRuns();
    loadSystemPaths();
    loadBankFacets();
    loadBankItems();
  }, []);

  const runIsActive = useMemo(() => {
    const status = selectedRun?.execution_status || selectedRun?.status;
    return ["queued", "running"].includes(status);
  }, [selectedRun]);

  useEffect(() => {
    if (view !== "monitor" || !selectedRunId || !runIsActive) {
      return undefined;
    }
    const timer = setInterval(() => {
      refreshRuns();
      refreshRun(selectedRunId);
    }, 3000);
    return () => clearInterval(timer);
  }, [view, selectedRunId, itemFilters.canonical_only, runIsActive]);

  useEffect(() => {
    if (selectedRunId) {
      refreshRun(selectedRunId);
    }
  }, [
    selectedRunId,
    itemFilters.module,
    itemFilters.status,
    itemFilters.failure_type,
    itemFilters.question_id,
    itemFilters.search,
    itemFilters.canonical_only,
    itemPage,
    itemPageSize,
  ]);

  useEffect(() => {
    setRunItems([]);
    setRunItemsTotal(0);
    setSelectedQuestionId(null);
    setTimelineData(null);
  }, [selectedRunId]);

  useEffect(() => {
    setSelectedBankQuestionId(null);
    setBankRows([]);
    setBankTotal(0);
    const timer = setTimeout(() => {
      loadBankItems();
    }, 250);
    return () => clearTimeout(timer);
  }, [bankFilters.module, bankFilters.subtype, bankFilters.item_format, bankFilters.keyword, bankPage, bankPageSize]);

  useEffect(() => {
    setItemPage(1);
  }, [itemFilters.module, itemFilters.status, itemFilters.failure_type, itemFilters.question_id, itemFilters.search, itemFilters.canonical_only, selectedRunId]);

  useEffect(() => {
    setBankPage(1);
  }, [bankFilters.module, bankFilters.subtype, bankFilters.item_format, bankFilters.keyword]);

  const selectedRunSummary = useMemo(() => selectedRun?.summary_metrics || {}, [selectedRun]);
  const selectedRunCounts = useMemo(() => getRunCounts(selectedRun), [selectedRun]);
  const selectedConnection = useMemo(
    () => connections.find((connection) => connection.connection_id === runForm.model_connection_id) || null,
    [connections, runForm.model_connection_id],
  );
  const modelsForProvider = useMemo(
    () => models.filter((model) => model.provider_id === runForm.provider_id && model.enabled !== false),
    [models, runForm.provider_id],
  );
  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.provider_id === runForm.provider_id) || null,
    [providers, runForm.provider_id],
  );
  const selectedModelProvider = useMemo(
    () => providers.find((provider) => provider.provider_id === modelForm.provider_id) || null,
    [providers, modelForm.provider_id],
  );

  const selectedRunItem = useMemo(() => {
    if (!runItems.length) return null;
    return runItems.find((item) => item.question_id === selectedQuestionId) || runItems[0];
  }, [runItems, selectedQuestionId]);

  const selectedBankItem = useMemo(() => {
    if (!bankRows.length) return null;
    return bankRows.find((item) => item.question_id === selectedBankQuestionId) || bankRows[0];
  }, [bankRows, selectedBankQuestionId]);

  const availableBankSubtypes = useMemo(() => {
    const subtypes = bankFacets.subtypes || [];
    if (!bankFilters.module) {
      return subtypes;
    }
    return subtypes.filter((item) => (item.modules || []).includes(bankFilters.module));
  }, [bankFacets.subtypes, bankFilters.module]);

  const providerSummary = useMemo(() => {
    const configured = providers.filter((provider) => provider.configured).length;
    const enabled = providers.filter((provider) => provider.enabled !== false).length;
    return { total: providers.length, configured, enabled };
  }, [providers]);

  const modelSummary = useMemo(() => {
    const enabled = models.filter((model) => model.enabled !== false).length;
    const multiTurn = models.filter((model) => model.supports_multi_turn).length;
    return { total: models.length, enabled, multiTurn };
  }, [models]);

  const connectionSummary = useMemo(() => {
    const enabled = connections.filter((connection) => connection.enabled !== false).length;
    const configured = connections.filter((connection) => connection.configured).length;
    return { total: connections.length, enabled, configured };
  }, [connections]);
  const historySelection = useMemo(() => new Set(selectedHistoryRunIds), [selectedHistoryRunIds]);
  const selectedHistoryRuns = useMemo(
    () => runs.filter((run) => historySelection.has(run.run_id)),
    [runs, historySelection],
  );
  const historySummary = useMemo(() => ({
    total: runs.length,
    reportReady: runs.filter((run) => run.report_ready).length,
    retry: runs.filter((run) => (run.run_kind || "base") === "retry").length,
  }), [runs]);
  const reportCandidates = useMemo(
    () => runs.filter((run) => run.report_ready || run.report_path || (run.execution_status || run.status) === "completed"),
    [runs],
  );
  const visibleError = useMemo(() => (
    error && !/question or run not found/i.test(error) ? error : ""
  ), [error]);
  const reportSummaryMetrics = useMemo(() => report?.summary?.summary_metrics || report?.summary_metrics || {}, [report]);

  useEffect(() => {
    if (selectedRunItem?.question_id && selectedRunItem.question_id !== selectedQuestionId) {
      setSelectedQuestionId(selectedRunItem.question_id);
    }
  }, [selectedRunItem, selectedQuestionId]);

  useEffect(() => {
    if (selectedBankItem?.question_id && selectedBankItem.question_id !== selectedBankQuestionId) {
      setSelectedBankQuestionId(selectedBankItem.question_id);
    }
  }, [selectedBankItem, selectedBankQuestionId]);

  useEffect(() => {
    if (bankFilters.subtype && !availableBankSubtypes.some((item) => item.value === bankFilters.subtype)) {
      setBankFilters((prev) => ({ ...prev, subtype: "" }));
    }
  }, [availableBankSubtypes, bankFilters.subtype]);

  useEffect(() => {
    setSelectedHistoryRunIds((prev) => prev.filter((runId) => runs.some((run) => run.run_id === runId)));
  }, [runs]);

  useEffect(() => {
    const itemBelongsToSelectedRun = selectedRunItem && (!selectedRunItem.run_id || selectedRunItem.run_id === selectedRunId);
    const itemHasTimelineData = selectedRunItem && ["ok", "failed"].includes(selectedRunItem.status || "");
    const runHasProcessedItems = !runIsActive || selectedRunCounts.processed > 0;
    if (selectedRunId && selectedRunItem?.question_id && itemBelongsToSelectedRun && itemHasTimelineData && runHasProcessedItems) {
      loadTimeline(selectedRunId, selectedRunItem.question_id, itemFilters.canonical_only);
    } else {
      setTimelineData(null);
    }
  }, [selectedRunId, selectedRunItem, itemFilters.canonical_only, runIsActive, selectedRunCounts.processed]);

  useEffect(() => {
    const shouldLock = showProviderForm || showModelForm || showConnectionForm;
    const previousOverflow = document.body.style.overflow;
    if (shouldLock) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [showProviderForm, showModelForm, showConnectionForm]);

  useEffect(() => {
    if (view !== "reports" || report || loadingReport) {
      return;
    }
    const readyCandidate = reportCandidates.find((item) => item.report_ready);
    const candidateRunId = (selectedRun && selectedRun.report_ready ? selectedRun.run_id : readyCandidate?.run_id) || null;
    if (candidateRunId) {
      handlePreviewReport(candidateRunId, { generateIfMissing: false });
    }
  }, [view, report, loadingReport, selectedRun, reportCandidates]);

  async function refreshProviders() {
    setLoadingProviders(true);
    try {
      const data = await apiFetch("/api/providers");
      const nextProviders = data.providers || [];
      const nextModels = data.models || [];
      const nextConnections = data.model_connections || [];
      setProviders(nextProviders);
      setModels(nextModels);
      setConnections(nextConnections);
      if ((!runForm.model_connection_id || !nextConnections.some((item) => item.connection_id === runForm.model_connection_id)) && nextConnections.length) {
        setRunForm((prev) => ({
          ...prev,
          model_connection_id: nextConnections[0].connection_id,
          provider_id: nextConnections[0].provider_id,
          model_alias: nextConnections[0].model_alias,
          timeout: nextConnections[0].default_timeout || prev.timeout,
        }));
      } else if ((!runForm.model_alias || !nextModels.some((item) => item.model_alias === runForm.model_alias)) && nextModels.length) {
        setRunForm((prev) => ({
          ...prev,
          provider_id: nextModels[0].provider_id,
          model_alias: nextModels[0].model_alias,
        }));
      }
      if ((!modelForm.provider_id || !nextProviders.some((item) => item.provider_id === modelForm.provider_id)) && nextProviders.length) {
        setModelForm((prev) => ({ ...prev, provider_id: nextProviders[0].provider_id }));
      }
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setLoadingProviders(false);
    }
  }

  async function refreshRuns() {
    setLoadingRuns(true);
    try {
      const data = await apiFetch("/api/runs");
      setRuns(data.runs || []);
      if (!selectedRunId && data.runs?.length) {
        setSelectedRunId(data.runs[0].run_id);
      }
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setLoadingRuns(false);
    }
  }

  async function refreshRun(runId) {
    setLoadingRunItems(true);
    const requestId = ++runRequestSeq.current;
    try {
      const query = buildQuery({
        module: itemFilters.module,
        status: itemFilters.status,
        failure_type: itemFilters.failure_type,
        question_id: itemFilters.question_id,
        keyword: itemFilters.search,
        canonical_only: itemFilters.canonical_only,
        include_bank: true,
        offset: (itemPage - 1) * itemPageSize,
        limit: itemPageSize,
      });
      const [runData, itemsData] = await Promise.all([
        apiFetch(`/api/runs/${runId}`),
        apiFetch(`/api/runs/${runId}/items${query}`),
      ]);
      if (requestId !== runRequestSeq.current) {
        return;
      }
      setSelectedRun(runData);
      setRunItems(itemsData.items || []);
      setRunItemsTotal(itemsData.total || 0);
      setError("");
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      if (requestId === runRequestSeq.current) {
        setLoadingRunItems(false);
      }
    }
  }

  async function loadTimeline(runId, questionId, canonicalOnly = false) {
    try {
      const query = buildQuery({ canonical_only: canonicalOnly });
      const data = await apiFetch(`/api/runs/${runId}/timeline/${questionId}${query}`);
      setTimelineData(data);
    } catch (err) {
      setTimelineData(null);
      const message = humanizeError(err?.message || err);
      if (/question or run not found/i.test(message)) {
        return;
      }
      setError(message);
    }
  }

  async function loadBankItems() {
    setLoadingBank(true);
    const requestId = ++bankRequestSeq.current;
    try {
      const query = buildQuery({ ...bankFilters, offset: (bankPage - 1) * bankPageSize, limit: bankPageSize });
      const data = await apiFetch(`/api/bank/items${query}`);
      if (requestId !== bankRequestSeq.current) {
        return;
      }
      setBankRows(data.items || []);
      setBankTotal(data.total || 0);
      setSelectedBankQuestionId((data.items || [])[0]?.question_id || null);
    } catch (err) {
      setError(humanizeError(err?.message || err));
      if (requestId === bankRequestSeq.current) {
        setBankRows([]);
        setSelectedBankQuestionId(null);
      }
    } finally {
      if (requestId === bankRequestSeq.current) {
        setLoadingBank(false);
      }
    }
  }

  async function loadBankFacets() {
    try {
      const data = await apiFetch("/api/bank/facets");
      setBankFacets(data);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    }
  }

  async function loadSystemPaths() {
    try {
      const data = await apiFetch("/api/system/paths");
      setSystemPaths(data);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    }
  }

  function toggleRunModule(module) {
    setRunForm((prev) => ({
      ...prev,
      modules: prev.modules.includes(module)
        ? prev.modules.filter((item) => item !== module)
        : [...prev.modules, module],
    }));
  }

  function resetBankFilters() {
    setBankFilters({
      module: "",
      subtype: "",
      item_format: "",
      keyword: "",
    });
  }

  async function handleCreateRun(event) {
    event?.preventDefault?.();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const connection = selectedConnection;
      const payload = {
        provider_id: connection?.provider_id || runForm.provider_id,
        model_alias: connection?.model_alias || runForm.model_alias,
        model_connection_id: connection?.connection_id || runForm.model_connection_id || null,
        modules: runForm.modules.length ? runForm.modules : null,
        smoke: runForm.smoke,
        timeout: Number(runForm.timeout || connection?.default_timeout) || null,
        concurrency_limit: Number(runForm.concurrency_limit) || 1,
        max_items: runForm.max_items ? Number(runForm.max_items) : null,
      };
      const run = await apiFetch("/api/runs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      runRequestSeq.current += 1;
      setRunItems([]);
      setRunItemsTotal(0);
      setTimelineData(null);
      setSelectedRunId(run.run_id);
      setSelectedQuestionId(null);
      setSelectedRun(run);
      setNotice(`已创建评测任务 ${run.run_id}`);
      setView("monitor");
      await refreshRuns();
      await refreshRun(run.run_id);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryFailures() {
    if (!selectedRunId) return;
    setBusy(true);
    setNotice("");
    try {
      const retryRun = await apiFetch(`/api/runs/${selectedRunId}/retry-failures`, {
        method: "POST",
        body: JSON.stringify({ concurrency_limit: 1, timeout: 30 }),
      });
      runRequestSeq.current += 1;
      setRunItems([]);
      setRunItemsTotal(0);
      setTimelineData(null);
      setSelectedRunId(retryRun.run_id);
      setSelectedRun(retryRun);
      setNotice(`已基于 ${selectedRunId} 创建失败题重试 run：${retryRun.run_id}`);
      setView("monitor");
      await refreshRuns();
      await refreshRun(retryRun.run_id);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateReport() {
    if (!selectedRunId) return;
    setBusy(true);
    setLoadingReport(true);
    setError("");
    setNotice("");
    try {
      await apiFetch(`/api/runs/${selectedRunId}/report`, { method: "POST" });
      const reportData = await fetchReportUntilReady(selectedRunId);
      setReport(reportData);
      setNotice(`报告已生成：${reportData.report_path}`);
      setView("reports");
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
      setLoadingReport(false);
    }
  }

  async function handlePreviewReport(runId, { generateIfMissing = false } = {}) {
    if (!runId) return;
    setBusy(true);
    setLoadingReport(true);
    setError("");
    setNotice("");
    try {
      if (generateIfMissing) {
        await apiFetch(`/api/runs/${runId}/report`, { method: "POST" });
      }
      const reportData = await fetchReportUntilReady(runId);
      setReport(reportData);
      setSelectedRunId(runId);
      setView("reports");
      setNotice(`已加载报告：${reportData.report_path}`);
      await refreshRun(runId);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
      setLoadingReport(false);
    }
  }

  async function handleConnectionSubmit(event) {
    event.preventDefault();
    const normalizedDisplay = connectionForm.display_name.trim();
    const normalizedVendor = connectionForm.vendor_name.trim();
    const normalizedBaseUrl = connectionForm.base_url.trim();
    const normalizedModelName = connectionForm.model_name.trim();
    const secretConfigured = String(systemPaths?.secret_master_configured || "") === "true";
    if (!normalizedVendor || !normalizedDisplay || !normalizedModelName) {
      setError("请填写供应商名称、显示名称和模型名称。");
      return;
    }
    if (connectionForm.auth_scheme !== "none" && connectionForm.api_key.trim() && !secretConfigured) {
      setError(`后端尚未配置 ${systemPaths?.secret_master_env || "QUESTION_BANK_SECRET_KEY"}，暂时不能安全保存 API Key。`);
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        connection_id: connectionForm.connection_id || undefined,
        vendor_name: normalizedVendor,
        note: connectionForm.note.trim() || undefined,
        homepage_url: connectionForm.homepage_url.trim() || undefined,
        display_name: normalizedDisplay,
        protocol: connectionForm.protocol,
        base_url: normalizedBaseUrl,
        auth_scheme: connectionForm.auth_scheme,
        auth_env: connectionForm.auth_env.trim(),
        api_key: connectionForm.api_key.trim() || undefined,
        model_name: normalizedModelName,
        default_timeout: Number(connectionForm.default_timeout) || 45,
        default_max_tokens: Number(connectionForm.default_max_tokens) || 512,
        supports_multi_turn: connectionForm.supports_multi_turn,
        enabled: connectionForm.enabled,
        headers_template: JSON.parse(connectionForm.headers_template_text || "{}"),
        model_lookup_mode: connectionForm.model_lookup_mode,
        keep_existing_secret: editingConnectionId ? !connectionForm.api_key.trim() : true,
      };
      const endpoint = editingConnectionId ? `/api/model-connections/${editingConnectionId}` : "/api/model-connections";
      const method = editingConnectionId ? "PATCH" : "POST";
      const saved = await apiFetch(endpoint, { method, body: JSON.stringify(payload) });
      setNotice(`模型接入已保存：${saved.display_name}`);
      resetConnectionForm();
      await refreshProviders();
      setRunForm((prev) => ({
        ...prev,
        model_connection_id: saved.connection_id,
        provider_id: saved.provider_id,
        model_alias: saved.model_alias,
        timeout: saved.default_timeout,
      }));
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleTestConnection(connectionId) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiFetch(`/api/model-connections/${connectionId}/test`, { method: "POST" });
      setNotice(`连通性测试通过：${result.model_name}`);
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteRun(run) {
    const warning = run.run_kind === "base"
      ? `确认删除 run "${run.run_id}"？这会同时删除该 run 及其 retry 链路、SQLite 记录和运行目录。`
      : `确认删除 retry run "${run.run_id}"？这会删除该 run 的 SQLite 记录和运行目录，并使 root run 的 canonical/report 失效，需重新生成。`;
    if (!window.confirm(warning)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiFetch(`/api/runs/${run.run_id}`, { method: "DELETE" });
      if (selectedRunId && result.deleted_run_ids?.includes(selectedRunId)) {
        setSelectedRunId(null);
        setSelectedRun(null);
        setRunItems([]);
        setReport(null);
      }
      setNotice(`已删除 ${result.deleted_run_ids?.length || 1} 个 run`);
      await refreshRuns();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelectedRuns() {
    if (!selectedHistoryRunIds.length) {
      return;
    }
    const roots = selectedHistoryRuns.filter((run) => (run.run_kind || "base") === "base").length;
    const retries = selectedHistoryRunIds.length - roots;
    const warning = `确认删除所选 ${selectedHistoryRunIds.length} 个 run 吗？其中 base ${roots} 个、retry ${retries} 个。删除会同步清理 SQLite 记录和运行目录。`;
    if (!window.confirm(warning)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiFetch("/api/runs/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ run_ids: selectedHistoryRunIds }),
      });
      if (selectedRunId && result.deleted_run_ids?.includes(selectedRunId)) {
        setSelectedRunId(null);
        setSelectedRun(null);
        setRunItems([]);
        setReport(null);
      }
      setSelectedHistoryRunIds([]);
      setNotice(`已删除 ${result.deleted_run_ids?.length || 0} 个 run`);
      await refreshRuns();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleProviderSubmit(event) {
    event.preventDefault();
    const normalizedProviderId = providerForm.provider_id.trim();
    const normalizedBaseUrl = providerForm.base_url.trim();
    const normalizedAuthEnv = providerForm.auth_env.trim();
    if (!normalizedProviderId) {
      setError("请先填写 provider_id。");
      return;
    }
    if (providerForm.protocol !== "mock" && !normalizedBaseUrl) {
      setError("请先填写 base_url。");
      return;
    }
    if (providerForm.auth_scheme !== "none" && !normalizedAuthEnv) {
      setError("当前认证方式需要填写环境变量名，例如 `OPENAI_API_KEY`。");
      return;
    }
    if (providerForm.auth_scheme !== "none" && (normalizedAuthEnv.startsWith("sk-") || normalizedAuthEnv.length > 80 || !/^[A-Z][A-Z0-9_]*$/.test(normalizedAuthEnv))) {
      setError("这里要填写环境变量名，例如 `MINIMAX_API_KEY`，不要填写明文 API Key。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const payload = {
        provider_id: normalizedProviderId,
        display_name: providerForm.display_name,
        protocol: providerForm.protocol,
        base_url: normalizedBaseUrl,
        auth_scheme: providerForm.auth_scheme,
        auth_env: normalizedAuthEnv,
        headers_template: JSON.parse(providerForm.headers_template_text || "{}"),
        model_lookup_mode: providerForm.model_lookup_mode,
        enabled: providerForm.enabled,
      };
      await apiFetch(editingProviderId ? `/api/providers/${editingProviderId}` : "/api/providers", {
        method: editingProviderId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setProviderForm({
        provider_id: "",
        display_name: "",
        protocol: "anthropic_compatible",
        base_url: "",
        auth_scheme: "x_api_key",
        auth_env: "",
        headers_template_text: "{}",
        model_lookup_mode: "skip",
        enabled: true,
      });
      setEditingProviderId(null);
      setShowProviderForm(false);
      await refreshProviders();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleModelSubmit(event) {
    event.preventDefault();
    const normalizedModelName = modelForm.model_name.trim();
    const derivedAlias = slugifyAlias(modelForm.model_alias || normalizedModelName || modelForm.display_name);
    if (!derivedAlias) {
      setError("请先填写 model_alias，或至少填写 model_name 以便自动生成别名。");
      return;
    }
    if (!normalizedModelName) {
      setError("请先填写 model_name。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (modelForm.model_alias !== derivedAlias) {
        setModelForm((prev) => ({ ...prev, model_alias: derivedAlias }));
      }
      const payload = {
        model_alias: derivedAlias,
        provider_id: modelForm.provider_id,
        display_name: modelForm.display_name,
        model_name: normalizedModelName,
        default_timeout: Number(modelForm.default_timeout) || 45,
        default_max_tokens: Number(modelForm.default_max_tokens) || 512,
        supports_multi_turn: modelForm.supports_multi_turn,
        enabled: modelForm.enabled,
      };
      await apiFetch(editingModelAlias ? `/api/models/${editingModelAlias}` : "/api/models", {
        method: editingModelAlias ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setModelForm((prev) => ({
        ...prev,
        model_alias: "",
        display_name: "",
        model_name: "",
        default_timeout: 45,
        default_max_tokens: 512,
        supports_multi_turn: true,
        enabled: true,
      }));
      setEditingModelAlias(null);
      setShowModelForm(false);
      await refreshProviders();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  function beginEditProvider(provider) {
    setEditingProviderId(provider.provider_id);
    setShowProviderForm(true);
    setProviderForm({
      provider_id: provider.provider_id,
      display_name: provider.display_name,
      protocol: provider.protocol,
      base_url: provider.base_url,
      auth_scheme: provider.auth_scheme,
      auth_env: provider.auth_env || "",
      headers_template_text: JSON.stringify(provider.headers_template || {}, null, 2),
      model_lookup_mode: provider.model_lookup_mode || "skip",
      enabled: provider.enabled !== false,
    });
  }

  function beginEditModel(model) {
    setEditingModelAlias(model.model_alias);
    setShowModelForm(true);
    setModelForm({
      model_alias: model.model_alias,
      provider_id: model.provider_id,
      display_name: model.display_name,
      model_name: model.model_name,
      default_timeout: model.default_timeout,
      default_max_tokens: model.default_max_tokens,
      supports_multi_turn: model.supports_multi_turn,
      enabled: model.enabled !== false,
    });
  }

  function beginEditConnection(connection) {
    setEditingConnectionId(connection.connection_id);
    setShowConnectionForm(true);
    setConnectionForm({
      connection_id: connection.connection_id,
      vendor_name: connection.vendor_name || "",
      note: connection.note || "",
      homepage_url: connection.homepage_url || "",
      display_name: connection.display_name || "",
      protocol: connection.protocol || "anthropic_compatible",
      base_url: connection.base_url || "",
      auth_scheme: connection.auth_scheme || "x_api_key",
      auth_env: connection.auth_env || "",
      api_key: "",
      model_name: connection.model_name || "",
      default_timeout: connection.default_timeout || 45,
      default_max_tokens: connection.default_max_tokens || 512,
      supports_multi_turn: connection.supports_multi_turn !== false,
      enabled: connection.enabled !== false,
      headers_template_text: JSON.stringify(connection.headers_template || {}, null, 2),
      model_lookup_mode: connection.model_lookup_mode || "skip",
    });
  }

  function resetProviderForm() {
    setEditingProviderId(null);
    setShowProviderForm(false);
    setProviderForm({
      provider_id: "",
      display_name: "",
      protocol: "anthropic_compatible",
      base_url: "",
      auth_scheme: "x_api_key",
      auth_env: "",
      headers_template_text: "{}",
      model_lookup_mode: "skip",
      enabled: true,
    });
  }

  function resetModelForm() {
    setEditingModelAlias(null);
    setShowModelForm(false);
    setModelForm((prev) => ({
      ...prev,
      model_alias: "",
      display_name: "",
      model_name: "",
      default_timeout: 45,
      default_max_tokens: 512,
      supports_multi_turn: true,
      enabled: true,
    }));
  }

  function resetConnectionForm() {
    setEditingConnectionId(null);
    setShowConnectionForm(false);
    setConnectionForm({
      connection_id: "",
      vendor_name: "",
      note: "",
      homepage_url: "",
      display_name: "",
      protocol: "anthropic_compatible",
      base_url: "",
      auth_scheme: "x_api_key",
      auth_env: "MINIMAX_API_KEY",
      api_key: "",
      model_name: "",
      default_timeout: 45,
      default_max_tokens: 512,
      supports_multi_turn: true,
      enabled: true,
      headers_template_text: "{}",
      model_lookup_mode: "skip",
    });
  }

  function toggleHistoryRunSelection(runId) {
    setSelectedHistoryRunIds((prev) => (
      prev.includes(runId) ? prev.filter((item) => item !== runId) : [...prev, runId]
    ));
  }

  function toggleAllHistoryRuns() {
    if (runs.length && selectedHistoryRunIds.length === runs.length) {
      setSelectedHistoryRunIds([]);
      return;
    }
    setSelectedHistoryRunIds(runs.map((run) => run.run_id));
  }

  async function deleteProvider(providerId) {
    if (!window.confirm(`确认删除 Provider "${providerId}"？`)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/providers/${providerId}`, { method: "DELETE" });
      if (editingProviderId === providerId) {
        resetProviderForm();
      }
      await refreshProviders();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteModel(modelAlias) {
    if (!window.confirm(`确认删除 Model Alias "${modelAlias}"？`)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/models/${modelAlias}`, { method: "DELETE" });
      if (editingModelAlias === modelAlias) {
        resetModelForm();
      }
      await refreshProviders();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteConnection(connection) {
    const warning = `确认删除模型接入 "${connection.display_name}"？这会同时移除其底层 Provider / Model 映射，但不会删除已经跑过的历史 run。`;
    if (!window.confirm(warning)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/model-connections/${connection.connection_id}`, { method: "DELETE" });
      if (runForm.model_connection_id === connection.connection_id) {
        setRunForm((prev) => ({ ...prev, model_connection_id: "" }));
      }
      resetConnectionForm();
      await refreshProviders();
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
    }
  }

  function openNewProviderForm() {
    setEditingProviderId(null);
    setShowProviderForm(true);
    setProviderForm({
      provider_id: "",
      display_name: "",
      protocol: "anthropic_compatible",
      base_url: "",
      auth_scheme: "x_api_key",
      auth_env: "",
      headers_template_text: "{}",
      model_lookup_mode: "skip",
      enabled: true,
    });
  }

  function openNewModelForm() {
    setEditingModelAlias(null);
    setShowModelForm(true);
    setModelForm((prev) => ({
      ...prev,
      model_alias: "",
      display_name: "",
      model_name: "",
      default_timeout: 45,
      default_max_tokens: 512,
      supports_multi_turn: true,
      enabled: true,
    }));
  }

  function openNewConnectionForm() {
    resetConnectionForm();
    setShowConnectionForm(true);
  }

  const failureCounts = useMemo(() => {
    const counter = {};
    runItems.forEach((item) => {
      if (item.failure_type) {
        counter[item.failure_type] = (counter[item.failure_type] || 0) + 1;
      }
    });
    return Object.entries(counter).sort((a, b) => b[1] - a[1]);
  }, [runItems]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">∿</div>
          <div className="brand-kicker">LLM Evaluation</div>
          <div className="brand-title">Multi-Model Console</div>
          <div className="brand-note">Research-grade evaluation cockpit for multi-provider model testing.</div>
        </div>
        <nav className="nav">
          {RUN_VIEWS.map((entry) => (
            <button
              key={entry.key}
              className={view === entry.key ? "nav-item active" : "nav-item"}
              onClick={() => setView(entry.key)}
            >
              {entry.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content content-stage">
        <header className="hero hero-editorial">
          <div className="hero-copy">
            <div className="hero-kicker-row">
              <span className="hero-tag">Active View</span>
              <span className="hero-tag hero-tag-ghost">{RUN_VIEWS.find((item) => item.key === view)?.label || "-"}</span>
            </div>
            <div className="hero-title">多模型测评系统</div>
            <div className="hero-subtitle">围绕模型接入、评测执行、逐题诊断与报告可视化构建的一体化评测工作台。</div>
            <div className="hero-endpoint">Endpoint · {API_BASE}</div>
          </div>
          <div className="hero-side">
            <div className="hero-status-card">
              <div className="hero-status-head">
                <span className="hero-status-label">Current Run</span>
                <span className={`status-pill ${runIsActive ? "status-pill-neutral" : "status-pill-ok"}`}>
                  {selectedRun?.execution_status || selectedRun?.status || "idle"}
                </span>
              </div>
              <div className="hero-status-value mono">{selectedRunId || "未选择运行"}</div>
              <div className="hero-status-meta">
                Processed {selectedRunCounts.processed} / {selectedRunCounts.total} ·
                Succeeded {selectedRunCounts.succeeded} · Failed {selectedRunCounts.failed}
              </div>
            </div>
            <div className="hero-actions">
              <button className="action-button" onClick={handleRetryFailures} disabled={!selectedRunId || busy}>
                重试失败题
              </button>
              <button className="action-button secondary" onClick={handleGenerateReport} disabled={!selectedRunId || busy}>
                生成报告
              </button>
            </div>
          </div>
        </header>

        <section className="score-grid">
          <ScoreCard title="Capability" value={selectedRunSummary.capability_score} tone="warm" />
          <ScoreCard title="Safety" value={selectedRunSummary.safety_composite_score} tone="cool" />
          <ScoreCard title="Probe" value={selectedRunSummary.probe_score} tone="earth" />
          <ScoreCard title="Overall" value={selectedRunSummary.overall_macro_score} tone="neutral" />
        </section>

        {visibleError ? <div className="error-banner">{visibleError}</div> : null}
        {notice ? <div className="notice-banner">{notice}</div> : null}

        {view === "create" ? (
          <section className="panel">
            <SectionTitle title="创建评测任务" meta="直接基于模型接入实例发起评测" />
            {selectedConnection ? (
              <div className="hero-subgrid">
                <InfoBanner
                  tone={selectedConnection.configured ? "ok" : "warn"}
                  title={`当前模型接入: ${selectedConnection.display_name}`}
                  body={
                    <>
                      <div>供应商：{selectedConnection.vendor_name}</div>
                      <div>协议：{selectedConnection.protocol}</div>
                      <div>Base URL：{selectedConnection.base_url || "-"}</div>
                      <div>模型名：{selectedConnection.model_name || "-"}</div>
                      <div>所需 Key：{selectedConnection.auth_env || "已内置或无需密钥"}</div>
                    </>
                  }
                />
                <InfoBanner
                  tone={selectedConnection.configured ? "neutral" : "warn"}
                  title={selectedConnection.configured ? "凭据已就绪" : "凭据尚未配置"}
                  body={
                    selectedConnection.configured
                      ? "当前后端环境变量已经可用，可以直接发起评测。"
                      : `请先在模型接入中配置 API Key，或在后端环境中设置 ${selectedConnection.auth_env || "对应环境变量"}。`
                  }
                />
              </div>
            ) : null}
            <form className="form-grid wide" onSubmit={handleCreateRun}>
              <label>
                模型接入实例
                <select
                  value={runForm.model_connection_id}
                  onChange={(event) => {
                    const nextConnectionId = event.target.value;
                    const nextConnection = connections.find((item) => item.connection_id === nextConnectionId);
                    setRunForm((prev) => ({
                      ...prev,
                      model_connection_id: nextConnectionId,
                      provider_id: nextConnection?.provider_id || "",
                      model_alias: nextConnection?.model_alias || "",
                      timeout: nextConnection?.default_timeout || prev.timeout,
                    }));
                  }}
                >
                  {!connections.length ? <option value="">当前没有可用模型接入</option> : null}
                  {connections.map((connection) => (
                    <option key={connection.connection_id} value={connection.connection_id}>
                      {connection.display_name} / {connection.vendor_name} {connection.configured ? "" : "(未配置密钥)"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                模型显示名
                <input value={selectedConnection?.display_name || "-"} readOnly />
              </label>
              <label>
                Timeout
                <input type="number" value={runForm.timeout} onChange={(event) => setRunForm((prev) => ({ ...prev, timeout: event.target.value }))} />
              </label>
              <label>
                并发上限
                <input type="number" min="1" max="4" value={runForm.concurrency_limit} onChange={(event) => setRunForm((prev) => ({ ...prev, concurrency_limit: event.target.value }))} />
              </label>
              <label>
                Max Items
                <input type="number" value={runForm.max_items} onChange={(event) => setRunForm((prev) => ({ ...prev, max_items: event.target.value }))} />
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={runForm.smoke} onChange={(event) => setRunForm((prev) => ({ ...prev, smoke: event.target.checked }))} />
                Smoke Run
              </label>
            </form>
            <div className="module-select-block">
              <div className="detail-subtitle">模块选择</div>
              <ToggleModule selected={runForm.modules} onToggle={toggleRunModule} />
            </div>
            <div className="form-actions">
              <button className="action-button" type="button" onClick={handleCreateRun} disabled={busy}>
                {busy ? "启动中..." : "启动评测"}
              </button>
                <button className="action-button secondary" type="button" onClick={() => setView("models")}>
                  前往模型接入
                </button>
            </div>
          </section>
        ) : null}

        {view === "monitor" ? (
          <>
            <section className="panel">
              <SectionTitle title="实时状态" />
              <div className="meta-row">
                <span>Run: {selectedRun?.run_id || "-"}</span>
                <span>Status: {selectedRun?.execution_status || selectedRun?.status || "-"}</span>
                <span>Provider: {selectedRun?.provider_id || "-"}</span>
                <span>Model: {selectedRun?.model_alias || selectedRun?.model_name || "-"}</span>
                <span>Processed: {selectedRunCounts.processed} / {selectedRunCounts.total}</span>
                <span>Succeeded: {selectedRunCounts.succeeded}</span>
                <span>Failed: {selectedRunCounts.failed}</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${selectedRunCounts.total ? (selectedRunCounts.processed / Math.max(1, selectedRunCounts.total)) * 100 : 0}%`,
                  }}
                />
              </div>
              <div className="progress-caption">
                <span>
                  {selectedRunCounts.processed} / {selectedRunCounts.total}
                  {" "}已处理，成功 {selectedRunCounts.succeeded}，失败 {selectedRunCounts.failed}
                </span>
                <span>
                  {selectedRun?.execution_status === "completed"
                    ? "运行已完成，当前分数与报告入口已可用。"
                    : runIsActive
                      ? "运行中，分数会随完成题目实时更新。"
                      : "请选择或启动一个 run。"}
                </span>
              </div>
              {loadingRuns ? <div className="muted-text">正在刷新运行状态…</div> : null}
              <PathList
                title="当前运行产物"
                paths={selectedRun ? {
                  run_dir: selectedRun.run_dir,
                  item_scores_path: selectedRun.item_scores_path,
                  summary_path: selectedRun.summary_path,
                  canonical_summary_path: selectedRun.canonical_summary_path,
                  report_path: selectedRun.report_path,
                } : null}
              />
            </section>
            <section className="panel">
              <SectionTitle title="模块概览" />
              <div className="table-shell">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>模块</th>
                      <th>得分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(selectedRunSummary.module_scores || {}).map(([module, score]) => (
                      <tr key={module}>
                        <td>{module}</td>
                        <td>{formatValue(score)}</td>
                      </tr>
                    ))}
                    {!Object.keys(selectedRunSummary.module_scores || {}).length ? (
                      <tr>
                        <td colSpan="2">当前还没有模块分。</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel">
              <SectionTitle title="失败类型统计" />
              {failureCounts.length ? (
                <div className="chip-row">
                  {failureCounts.map(([failureType, count]) => (
                    <span className="chip chip-failed" key={failureType}>{failureType}: {count}</span>
                  ))}
                </div>
              ) : (
                <div className="muted-text">当前没有失败类型统计。</div>
              )}
            </section>
          </>
        ) : null}

        {view === "items" ? (
          <section className="panel">
            <SectionTitle title="逐题结果" meta={`当前页 ${runItems.length} / 总计 ${runItemsTotal}`} />
            <div className="filters-row">
              <label>
                模块
                <select value={itemFilters.module} onChange={(event) => setItemFilters((prev) => ({ ...prev, module: event.target.value }))}>
                  <option value="">全部</option>
                  {MODULE_OPTIONS.map((module) => <option key={module} value={module}>{module}</option>)}
                </select>
              </label>
              <label>
                状态
                <select value={itemFilters.status} onChange={(event) => setItemFilters((prev) => ({ ...prev, status: event.target.value }))}>
                  <option value="">全部</option>
                  <option value="ok">ok</option>
                  <option value="failed">failed</option>
                </select>
              </label>
              <label>
                失败类型
                <input value={itemFilters.failure_type} onChange={(event) => setItemFilters((prev) => ({ ...prev, failure_type: event.target.value }))} placeholder="read_timeout / http_529..." />
              </label>
              <label>
                题号
                <input value={itemFilters.question_id} onChange={(event) => setItemFilters((prev) => ({ ...prev, question_id: event.target.value }))} placeholder="A1-001" />
              </label>
              <label className="filter-search">
                关键词
                <input value={itemFilters.search} onChange={(event) => setItemFilters((prev) => ({ ...prev, search: event.target.value }))} placeholder="题面 / subtype / failure" />
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={itemFilters.canonical_only} onChange={(event) => setItemFilters((prev) => ({ ...prev, canonical_only: event.target.checked }))} />
                Canonical
              </label>
              <div className="inline-actions">
                <button className="action-button secondary" type="button" onClick={() => selectedRunId && refreshRun(selectedRunId)}>刷新结果</button>
                <button className="action-button secondary" type="button" onClick={() => setView("timeline")} disabled={!selectedRunItem}>查看时间线</button>
              </div>
            </div>
            <PaginationBar
              page={itemPage}
              pageSize={itemPageSize}
              total={runItemsTotal}
              onPageChange={setItemPage}
              onPageSizeChange={(size) => {
                setItemPageSize(size);
                setItemPage(1);
              }}
            />
            <div className="items-layout">
              <div className="items-list">
                {loadingRunItems ? <div className="muted-text">正在加载逐题结果…</div> : null}
                {!loadingRunItems && !runItems.length ? (
                  <EmptyState
                    title="当前筛选下没有逐题结果"
                    description="可以清空筛选条件，或先在历史 Runs 中选择一个已有 run。"
                  />
                ) : (
                  <div className="table-shell">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Question</th>
                          <th>Module</th>
                          <th>Subtype</th>
                          <th>题面预览</th>
                          <th>Status</th>
                          <th>Score</th>
                          <th>Failure</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runItems.map((item) => (
                          <tr
                            key={`${item.question_id}-${item.attempt_run_id}-${item.source_run_id}`}
                            className={selectedRunItem?.question_id === item.question_id ? "row-active" : ""}
                            onClick={() => setSelectedQuestionId(item.question_id)}
                          >
                            <td className="mono">{item.question_id}</td>
                            <td>{item.module}</td>
                            <td>{item.bank_item?.subtype || "-"}</td>
                            <td>{briefText(item.bank_item?.prompt_template || item.bank_item?.turn_script?.[0]?.content_template)}</td>
                            <td>{item.status}</td>
                            <td>{formatValue(item.primary_score)}</td>
                            <td>{item.failure_type || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <DetailCard title="题目详情" item={selectedRunItem} timelineData={timelineData} />
            </div>
          </section>
        ) : null}

        {view === "timeline" ? (
          <section className="panel">
            <SectionTitle title="多轮时间线" meta={selectedRunItem ? selectedRunItem.question_id : "先在逐题结果中选择一道题"} />
            <DetailCard title="时间线详情" item={selectedRunItem} timelineData={timelineData} />
          </section>
        ) : null}

        {view === "bank" ? (
          <section className="panel">
            <SectionTitle title="题库浏览" meta={`当前命中 ${bankTotal} / 正式题总数 ${bankFacets.total || bankTotal}`} />
            <PathList title="题库文件位置" paths={{ bank_items_path: systemPaths?.bank_items_path }} />
            <div className="filters-row">
              <label>
                模块
                <select value={bankFilters.module} onChange={(event) => setBankFilters((prev) => ({ ...prev, module: event.target.value }))}>
                  <option value="">全部</option>
                  {(bankFacets.modules || []).map((module) => <option key={module.value} value={module.value}>{module.value} ({module.count})</option>)}
                </select>
              </label>
              <label>
                子类
                <select value={bankFilters.subtype} onChange={(event) => setBankFilters((prev) => ({ ...prev, subtype: event.target.value }))}>
                  <option value="">全部</option>
                  {availableBankSubtypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.value} ({item.count})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                题型
                <select value={bankFilters.item_format} onChange={(event) => setBankFilters((prev) => ({ ...prev, item_format: event.target.value }))}>
                  <option value="">全部</option>
                  {(bankFacets.item_formats || []).map((item) => (
                    <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                  ))}
                </select>
              </label>
              <label className="filter-search">
                关键词
                <input value={bankFilters.keyword} onChange={(event) => setBankFilters((prev) => ({ ...prev, keyword: event.target.value }))} placeholder="题面关键词 / question id" />
              </label>
              <div className="inline-actions">
                <button className="action-button secondary" type="button" onClick={resetBankFilters}>清空筛选</button>
              </div>
            </div>
            <PaginationBar
              page={bankPage}
              pageSize={bankPageSize}
              total={bankTotal}
              onPageChange={setBankPage}
              onPageSizeChange={(size) => {
                setBankPageSize(size);
                setBankPage(1);
              }}
            />
            <div className="items-layout">
              <div className="items-list">
                {loadingBank ? <div className="muted-text">正在按筛选条件刷新题库…</div> : null}
                {!loadingBank && !bankRows.length ? (
                  <EmptyState
                    title="当前筛选没有命中正式题"
                    description={`模块=${bankFilters.module || "全部"} / 子类=${bankFilters.subtype || "全部"} / 题型=${bankFilters.item_format || "全部"}`}
                    actionLabel="清空筛选"
                    onAction={resetBankFilters}
                  />
                ) : (
                  <div className="table-shell">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Question</th>
                          <th>Module</th>
                          <th>Subtype</th>
                          <th>题面预览</th>
                          <th>Format</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bankRows.map((item) => (
                          <tr
                            key={item.question_id}
                            className={selectedBankItem?.question_id === item.question_id ? "row-active" : ""}
                            onClick={() => setSelectedBankQuestionId(item.question_id)}
                          >
                            <td className="mono">{item.question_id}</td>
                            <td>{item.module}</td>
                            <td>{item.subtype || "-"}</td>
                            <td>{briefText(item.prompt_template || item.turn_script?.[0]?.content_template)}</td>
                            <td>{item.item_format}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <DetailCard title="正式题详情" item={selectedBankItem} timelineData={null} />
            </div>
          </section>
        ) : null}

{view === "models" ? (
          <section className="panel">
            <SectionTitle title="模型接入" meta="主路径按接入实例配置；底层 Provider / Model 抽象收纳到高级模式" />
            <PathList title="配置文件位置" paths={{ providers_config_path: systemPaths?.providers_config_path }} />
            {loadingProviders ? <div className="muted-text">正在加载模型配置…</div> : null}
            <div className="detail-card connection-hero-card">
              <div className="mini-stat-grid compact-stats">
                <SummaryMiniCard label="接入实例总数" value={connectionSummary.total} />
                <SummaryMiniCard label="已启用" value={connectionSummary.enabled} />
                <SummaryMiniCard label="已配置密钥" value={connectionSummary.configured} />
              </div>
              <div className="toolbar-row compact-toolbar">
                <button className="action-button compact-action" type="button" onClick={openNewConnectionForm}>
                  新增模型接入
                </button>
                <button className="action-button secondary compact-action" type="button" onClick={refreshProviders}>
                  刷新
                </button>
                <button className="action-button secondary compact-action" type="button" onClick={() => setShowAdvancedConfig((prev) => !prev)}>
                  {showAdvancedConfig ? "收起高级模式" : "展开高级模式"}
                </button>
              </div>
              <InfoBanner
                tone={String(systemPaths?.secret_master_configured || "") === "true" ? "ok" : "warn"}
                title={String(systemPaths?.secret_master_configured || "") === "true" ? "API Key 可安全持久化" : "后端尚未配置主密钥"}
                body={
                  String(systemPaths?.secret_master_configured || "") === "true"
                    ? `前端填写的 API Key 会加密后存入 SQLite，主密钥环境变量为 ${systemPaths?.secret_master_env || "QUESTION_BANK_SECRET_KEY"}。`
                    : `若要从前端保存真实 API Key，请先在后端环境中设置 ${systemPaths?.secret_master_env || "QUESTION_BANK_SECRET_KEY"}。`
                }
              />
            </div>

            <div className="connection-grid">
              {connections.length ? connections.map((connection) => (
                <div className="connection-card" key={connection.connection_id}>
                  <div className="connection-card-head">
                    <div>
                      <div className="config-row-title">{connection.display_name}</div>
                      <div className="config-row-subtitle">{connection.vendor_name} / {connection.model_name}</div>
                    </div>
                    <StatusPill configured={connection.configured} envName={connection.auth_env || "内置密钥"} />
                  </div>
                  <div className="connection-meta-grid">
                    <div><span>URL</span><strong title={connection.base_url}>{briefText(connection.base_url, 48)}</strong></div>
                    <div><span>协议</span><strong>{connection.protocol}</strong></div>
                    <div><span>模型</span><strong>{connection.model_name}</strong></div>
                    <div><span>超时</span><strong>{connection.default_timeout}s</strong></div>
                  </div>
                  <div className="config-chip-row">
                    <span className="chip">{connection.enabled !== false ? "enabled" : "disabled"}</span>
                    <span className={`chip ${connection.supports_multi_turn ? "chip-ok" : "chip-soft"}`}>{connection.supports_multi_turn ? "multi-turn" : "single-turn"}</span>
                    {connection.note ? <span className="chip chip-soft">{briefText(connection.note, 24)}</span> : null}
                  </div>
                  <div className="connection-card-actions">
                    <button className="mini-button" type="button" onClick={() => {
                      setRunForm((prev) => ({
                        ...prev,
                        model_connection_id: connection.connection_id,
                        provider_id: connection.provider_id,
                        model_alias: connection.model_alias,
                        timeout: connection.default_timeout || prev.timeout,
                      }));
                      setView("create");
                    }}>
                      用此评测
                    </button>
                    <button className="mini-button" type="button" onClick={() => handleTestConnection(connection.connection_id)}>测试连通性</button>
                    <button className="mini-button" type="button" onClick={() => beginEditConnection(connection)}>编辑</button>
                    <button className="mini-button danger" type="button" onClick={() => deleteConnection(connection)}>删除</button>
                  </div>
                </div>
              )) : (
                <EmptyState
                  title="还没有模型接入实例"
                  description="推荐先创建一个 MiniMax 或 OpenAI-compatible 接入实例，再回到运行创建页发起评测。"
                  actionLabel="立即新增"
                  onAction={openNewConnectionForm}
                />
              )}
            </div>

            {showAdvancedConfig ? (
              <div className="management-grid management-grid-compact advanced-stack">
                <div className="management-column">
                  <div className="detail-card management-surface">
                    <SectionTitle title="高级模式 / Provider" meta="协议、URL 与认证环境变量" />
                    <div className="mini-stat-grid compact-stats">
                      <SummaryMiniCard label="Provider 总数" value={providerSummary.total} />
                      <SummaryMiniCard label="已启用" value={providerSummary.enabled} />
                      <SummaryMiniCard label="已配置密钥" value={providerSummary.configured} />
                    </div>
                    <div className="toolbar-row compact-toolbar">
                      <button className="action-button compact-action" type="button" onClick={openNewProviderForm}>新增 Provider</button>
                    </div>
                    <div className="config-list advanced-config-list">
                      {providers.map((provider) => {
                        const hasLinkedModel = models.some((model) => model.provider_id === provider.provider_id);
                        return (
                          <div className="config-row" key={provider.provider_id} onClick={() => beginEditProvider(provider)}>
                            <div className="config-row-main">
                              <div className="config-row-title">{provider.display_name}</div>
                              <div className="config-row-subtitle mono">{provider.provider_id}</div>
                              <div className="config-chip-row">
                                <span className="chip">{provider.protocol}</span>
                                <span className="chip chip-soft" title={provider.base_url}>{briefText(provider.base_url, 52)}</span>
                              </div>
                            </div>
                            <div className="config-row-actions">
                              <button className="mini-button" type="button" onClick={(event) => { event.stopPropagation(); beginEditProvider(provider); }}>编辑</button>
                              <button className="mini-button danger" type="button" disabled={hasLinkedModel} onClick={(event) => { event.stopPropagation(); deleteProvider(provider.provider_id); }}>删除</button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="management-column">
                  <div className="detail-card management-surface">
                    <SectionTitle title="高级模式 / Model Alias" meta="底层运行映射" />
                    <div className="mini-stat-grid compact-stats">
                      <SummaryMiniCard label="Model 总数" value={modelSummary.total} />
                      <SummaryMiniCard label="已启用" value={modelSummary.enabled} />
                      <SummaryMiniCard label="支持多轮" value={modelSummary.multiTurn} />
                    </div>
                    <div className="toolbar-row compact-toolbar">
                      <button className="action-button compact-action" type="button" onClick={openNewModelForm}>新增 Model Alias</button>
                    </div>
                    <div className="config-list advanced-config-list">
                      {models.map((model) => (
                        <div className="config-row" key={model.model_alias} onClick={() => beginEditModel(model)}>
                          <div className="config-row-main">
                            <div className="config-row-title">{model.display_name || model.model_alias}</div>
                            <div className="config-row-subtitle mono">{model.model_alias}</div>
                            <div className="config-chip-row">
                              <span className="chip chip-soft mono">{model.provider_id}</span>
                              <span className="chip chip-soft">{briefText(model.model_name, 42)}</span>
                            </div>
                          </div>
                          <div className="config-row-actions">
                            <button className="mini-button" type="button" onClick={(event) => { event.stopPropagation(); beginEditModel(model); }}>编辑</button>
                            <button className="mini-button danger" type="button" onClick={(event) => { event.stopPropagation(); deleteModel(model.model_alias); }}>删除</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            <ModalDialog
              open={showConnectionForm}
              title={editingConnectionId ? "编辑模型接入" : "新增模型接入"}
              subtitle={editingConnectionId || "像 Trae / cc-switch 一样，按单个模型接入实例配置"}
              onClose={busy ? undefined : resetConnectionForm}
            >
              <form className="form-stack modal-form" onSubmit={handleConnectionSubmit}>
                <div className="form-grid compact-form-grid">
                  <label>
                    供应商名称
                    <input value={connectionForm.vendor_name} onChange={(event) => setConnectionForm((prev) => ({ ...prev, vendor_name: event.target.value }))} placeholder="MiniMax" />
                  </label>
                  <label>
                    备注
                    <input value={connectionForm.note} onChange={(event) => setConnectionForm((prev) => ({ ...prev, note: event.target.value }))} placeholder="例如：公司专用账号" />
                  </label>
                  <label>
                    官网链接
                    <input value={connectionForm.homepage_url} onChange={(event) => setConnectionForm((prev) => ({ ...prev, homepage_url: event.target.value }))} placeholder="https://platform.minimaxi.com" />
                  </label>
                  <label>
                    显示名称
                    <input value={connectionForm.display_name} onChange={(event) => setConnectionForm((prev) => ({ ...prev, display_name: event.target.value }))} placeholder="MiniMax-M2.7" />
                  </label>
                </div>
                <div className="modal-section-head">请求配置</div>
                <div className="form-grid compact-form-grid">
                  <label>
                    请求地址
                    <input value={connectionForm.base_url} onChange={(event) => setConnectionForm((prev) => ({ ...prev, base_url: event.target.value }))} placeholder="https://api.minimax.chat/anthropic/v1" />
                  </label>
                  <label>
                    API 格式
                    <select value={connectionForm.protocol} onChange={(event) => setConnectionForm((prev) => ({ ...prev, protocol: event.target.value }))}>
                      {PROTOCOL_OPTIONS.filter((item) => item.value !== "mock").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label>
                    认证方式
                    <select value={connectionForm.auth_scheme} onChange={(event) => setConnectionForm((prev) => ({ ...prev, auth_scheme: event.target.value }))}>
                      {AUTH_SCHEME_OPTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                  <label>
                    认证字段环境名
                    <input value={connectionForm.auth_env} onChange={(event) => setConnectionForm((prev) => ({ ...prev, auth_env: event.target.value }))} placeholder="MINIMAX_API_KEY" />
                  </label>
                </div>
                <InfoBanner
                  tone="neutral"
                  title="API Key 录入"
                  body={String(systemPaths?.secret_master_configured || "") === "true"
                    ? "这里可以直接填写真实 API Key，后端会加密后存入 SQLite。留空则沿用已有密钥。"
                    : `当前后端未设置 ${systemPaths?.secret_master_env || "QUESTION_BANK_SECRET_KEY"}，因此只能保存环境变量名，不能安全保存真实密钥。`}
                />
                <label className="stacked-label">
                  API Key
                  <input type="password" value={connectionForm.api_key} onChange={(event) => setConnectionForm((prev) => ({ ...prev, api_key: event.target.value }))} placeholder={editingConnectionId ? "留空表示保持原密钥" : "输入真实 API Key"} />
                </label>
                <div className="modal-section-head">模型映射</div>
                <div className="form-grid compact-form-grid">
                  <label>
                    真实请求模型名
                    <input value={connectionForm.model_name} onChange={(event) => setConnectionForm((prev) => ({ ...prev, model_name: event.target.value }))} placeholder="MiniMax-M2.7" />
                  </label>
                  <label>
                    model_lookup_mode
                    <select value={connectionForm.model_lookup_mode} onChange={(event) => setConnectionForm((prev) => ({ ...prev, model_lookup_mode: event.target.value }))}>
                      {MODEL_LOOKUP_OPTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                  <label>
                    default_timeout
                    <input type="number" value={connectionForm.default_timeout} onChange={(event) => setConnectionForm((prev) => ({ ...prev, default_timeout: event.target.value }))} />
                  </label>
                  <label>
                    default_max_tokens
                    <input type="number" value={connectionForm.default_max_tokens} onChange={(event) => setConnectionForm((prev) => ({ ...prev, default_max_tokens: event.target.value }))} />
                  </label>
                </div>
                <div className="form-grid compact-form-grid checkbox-grid">
                  <label className="checkbox-label compact-checkbox">
                    <input type="checkbox" checked={connectionForm.supports_multi_turn} onChange={(event) => setConnectionForm((prev) => ({ ...prev, supports_multi_turn: event.target.checked }))} />
                    supports_multi_turn
                  </label>
                  <label className="checkbox-label compact-checkbox">
                    <input type="checkbox" checked={connectionForm.enabled} onChange={(event) => setConnectionForm((prev) => ({ ...prev, enabled: event.target.checked }))} />
                    enabled
                  </label>
                </div>
                <details className="advanced-details">
                  <summary>高级选项</summary>
                  <div className="modal-section-head">高级请求头</div>
                  <label className="stacked-label">
                    headers_template JSON
                    <textarea value={connectionForm.headers_template_text} onChange={(event) => setConnectionForm((prev) => ({ ...prev, headers_template_text: event.target.value }))} rows={6} />
                  </label>
                </details>
                <div className="form-actions compact-form-actions">
                  <button className="action-button compact-action" type="submit" disabled={busy}>{editingConnectionId ? "更新模型接入" : "保存模型接入"}</button>
                  {editingConnectionId ? <button className="action-button secondary compact-action" type="button" onClick={() => handleTestConnection(editingConnectionId)} disabled={busy}>测试连通性</button> : null}
                  <button className="action-button secondary compact-action" type="button" onClick={resetConnectionForm}>取消</button>
                </div>
              </form>
            </ModalDialog>

            <ModalDialog
              open={showProviderForm}
              title={editingProviderId ? `编辑 Provider` : "新增 Provider"}
              subtitle={editingProviderId || "高级模式：配置底层协议、URL 与认证环境变量"}
              onClose={busy ? undefined : resetProviderForm}
            >
              <form className="form-stack modal-form" onSubmit={handleProviderSubmit}>
                <div className="form-grid compact-form-grid">
                  <label>
                    provider_id
                    <input value={providerForm.provider_id} onChange={(event) => setProviderForm((prev) => ({ ...prev, provider_id: event.target.value }))} />
                  </label>
                  <label>
                    display_name
                    <input value={providerForm.display_name} onChange={(event) => setProviderForm((prev) => ({ ...prev, display_name: event.target.value }))} />
                  </label>
                  <label>
                    protocol
                    <select value={providerForm.protocol} onChange={(event) => setProviderForm((prev) => ({ ...prev, protocol: event.target.value }))}>
                      {PROTOCOL_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label>
                    base_url
                    <input value={providerForm.base_url} onChange={(event) => setProviderForm((prev) => ({ ...prev, base_url: event.target.value }))} />
                  </label>
                </div>
                <div className="modal-section-head">认证信息</div>
                <div className="form-grid compact-form-grid">
                  <label>
                    auth_scheme
                    <select value={providerForm.auth_scheme} onChange={(event) => setProviderForm((prev) => ({ ...prev, auth_scheme: event.target.value }))}>
                      {AUTH_SCHEME_OPTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                  <label>
                    auth_env
                    <input value={providerForm.auth_env} onChange={(event) => setProviderForm((prev) => ({ ...prev, auth_env: event.target.value }))} placeholder="OPENAI_API_KEY" />
                  </label>
                  <label>
                    model_lookup_mode
                    <select value={providerForm.model_lookup_mode} onChange={(event) => setProviderForm((prev) => ({ ...prev, model_lookup_mode: event.target.value }))}>
                      {MODEL_LOOKUP_OPTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                  <label className="checkbox-label compact-checkbox">
                    <input type="checkbox" checked={providerForm.enabled} onChange={(event) => setProviderForm((prev) => ({ ...prev, enabled: event.target.checked }))} />
                    enabled
                  </label>
                </div>
                <label className="stacked-label">
                  headers_template JSON
                  <textarea value={providerForm.headers_template_text} onChange={(event) => setProviderForm((prev) => ({ ...prev, headers_template_text: event.target.value }))} rows={6} />
                </label>
                <div className="form-actions compact-form-actions">
                  <button className="action-button compact-action" type="submit" disabled={busy}>{editingProviderId ? "更新 Provider" : "保存 Provider"}</button>
                  <button className="action-button secondary compact-action" type="button" onClick={resetProviderForm}>取消</button>
                </div>
              </form>
            </ModalDialog>

            <ModalDialog
              open={showModelForm}
              title={editingModelAlias ? "编辑 Model Alias" : "新增 Model Alias"}
              subtitle={editingModelAlias || "高级模式：底层别名与真实模型映射"}
              onClose={busy ? undefined : resetModelForm}
            >
              <form className="form-stack modal-form" onSubmit={handleModelSubmit}>
                <div className="form-grid compact-form-grid">
                  <label>
                    model_alias
                    <input value={modelForm.model_alias} onChange={(event) => setModelForm((prev) => ({ ...prev, model_alias: event.target.value }))} />
                  </label>
                  <label>
                    provider_id
                    <select value={modelForm.provider_id} onChange={(event) => setModelForm((prev) => ({ ...prev, provider_id: event.target.value }))}>
                      {providers.map((provider) => <option key={provider.provider_id} value={provider.provider_id}>{provider.provider_id}</option>)}
                    </select>
                  </label>
                  <label>
                    display_name
                    <input value={modelForm.display_name} onChange={(event) => setModelForm((prev) => ({ ...prev, display_name: event.target.value }))} />
                  </label>
                  <label>
                    model_name
                    <input value={modelForm.model_name} onChange={(event) => setModelForm((prev) => ({ ...prev, model_name: event.target.value }))} />
                  </label>
                  <label>
                    default_timeout
                    <input type="number" value={modelForm.default_timeout} onChange={(event) => setModelForm((prev) => ({ ...prev, default_timeout: event.target.value }))} />
                  </label>
                  <label>
                    default_max_tokens
                    <input type="number" value={modelForm.default_max_tokens} onChange={(event) => setModelForm((prev) => ({ ...prev, default_max_tokens: event.target.value }))} />
                  </label>
                </div>
                <div className="form-grid compact-form-grid checkbox-grid">
                  <label className="checkbox-label compact-checkbox">
                    <input type="checkbox" checked={modelForm.supports_multi_turn} onChange={(event) => setModelForm((prev) => ({ ...prev, supports_multi_turn: event.target.checked }))} />
                    supports_multi_turn
                  </label>
                  <label className="checkbox-label compact-checkbox">
                    <input type="checkbox" checked={modelForm.enabled} onChange={(event) => setModelForm((prev) => ({ ...prev, enabled: event.target.checked }))} />
                    enabled
                  </label>
                </div>
                <div className="form-actions compact-form-actions">
                  <button className="action-button compact-action" type="submit" disabled={busy}>{editingModelAlias ? "更新 Model" : "保存 Model"}</button>
                  <button className="action-button secondary compact-action" type="button" onClick={resetModelForm}>取消</button>
                </div>
              </form>
            </ModalDialog>
          </section>
        ) : null}

        {view === "history" ? (
          <section className="panel history-panel">
            <SectionTitle title="历史 Runs" meta={`共 ${runs.length} 条`} />
            <div className="history-hero">
              <div className="detail-card history-hero-card">
                <PathList title="历史运行目录" paths={{ evaluation_runs_root: systemPaths?.evaluation_runs_root }} />
                <div className="muted-text">评测结果默认保存在 <code>manifests/evaluation_runs/&lt;run_id&gt;/</code>，正式题库来自 <code>final_bank_specs/generated/final_bank_items.jsonl</code>。</div>
              </div>
              <div className="mini-stat-grid history-stat-grid">
                <SummaryMiniCard label="总 Runs" value={historySummary.total} />
                <SummaryMiniCard label="报告就绪" value={historySummary.reportReady} />
                <SummaryMiniCard label="Retry Runs" value={historySummary.retry} />
                <SummaryMiniCard label="已选择" value={selectedHistoryRunIds.length} />
              </div>
            </div>

            <div className="history-toolbar">
              <div className="history-toolbar-group">
                <button className="mini-button" type="button" onClick={toggleAllHistoryRuns} disabled={!runs.length}>
                  {runs.length && selectedHistoryRunIds.length === runs.length ? "取消全选" : "全选当前列表"}
                </button>
                <button className="mini-button" type="button" onClick={() => setSelectedHistoryRunIds([])} disabled={!selectedHistoryRunIds.length}>
                  清空选择
                </button>
              </div>
              <div className="history-toolbar-group">
                <button
                  className="mini-button"
                  type="button"
                  disabled={!selectedRunId}
                  onClick={() => handlePreviewReport(selectedRunId, { generateIfMissing: !selectedRun?.report_ready })}
                >
                  预览当前报告
                </button>
                <button className="mini-button danger" type="button" disabled={!selectedHistoryRunIds.length} onClick={deleteSelectedRuns}>
                  删除所选 {selectedHistoryRunIds.length ? `(${selectedHistoryRunIds.length})` : ""}
                </button>
              </div>
            </div>

            <div className="history-layout">
              <div className="detail-card history-table-card">
                <SectionTitle title="运行中心" meta="支持多选删除、报告预览和路径复制" />
                <div className="table-shell history-table-shell">
                  <table className="data-table history-table">
                    <thead>
                      <tr>
                        <th className="check-col">
                          <input
                            type="checkbox"
                            checked={runs.length > 0 && selectedHistoryRunIds.length === runs.length}
                            onChange={toggleAllHistoryRuns}
                            aria-label="全选 runs"
                          />
                        </th>
                        <th>Run ID</th>
                        <th>Kind</th>
                        <th>Provider</th>
                        <th>Model</th>
                        <th>Status</th>
                        <th>Processed / Total</th>
                        <th>Succeeded / Failed</th>
                        <th>Report</th>
                        <th>Canonical</th>
                        <th>路径</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((run) => (
                        <tr
                          key={run.run_id}
                          className={selectedRunId === run.run_id ? "row-active" : ""}
                          onClick={() => {
                            setSelectedRunId(run.run_id);
                            setSelectedQuestionId(null);
                            refreshRun(run.run_id);
                          }}
                        >
                          <td className="check-col" onClick={(event) => event.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={historySelection.has(run.run_id)}
                              onChange={() => toggleHistoryRunSelection(run.run_id)}
                              aria-label={`选择 ${run.run_id}`}
                            />
                          </td>
                          <td className="mono data-cell-wrap">{run.run_id}</td>
                          <td className="data-cell-wrap">{run.run_kind || "base"}</td>
                          <td className="data-cell-wrap">{run.provider_id || "-"}</td>
                          <td className="data-cell-wrap">{run.model_alias || run.model_name || "-"}</td>
                          <td className="data-cell-wrap">{run.execution_status || run.status || "-"}</td>
                          <td>{getRunCounts(run).processed} / {getRunCounts(run).total}</td>
                          <td>{getRunCounts(run).succeeded} / {getRunCounts(run).failed}</td>
                          <td><RunArtifactStatus ready={run.report_ready} label="报告" /></td>
                          <td><RunArtifactStatus ready={run.canonical_ready} label="Canonical" /></td>
                          <td><CopyButton value={run.run_dir} label="复制目录" /></td>
                          <td>
                            <div className="history-row-actions" onClick={(event) => event.stopPropagation()}>
                              <button
                                className="mini-button"
                                type="button"
                                onClick={() => handlePreviewReport(run.run_id, { generateIfMissing: !run.report_ready })}
                              >
                                预览
                              </button>
                              <button className="mini-button danger" type="button" onClick={() => deleteRun(run)}>
                                删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {selectedRun ? (
                <div className="detail-card history-detail-card">
                  <SectionTitle title={`Run 详情: ${selectedRun.run_id}`} meta={`${selectedRun.run_kind || "base"} / ${selectedRun.execution_status || selectedRun.status || "-"}`} />
                  <div className="compact-meta-panel">
                    <div className="compact-meta-line"><span>Provider</span><strong>{selectedRun.provider_id || "-"}</strong></div>
                    <div className="compact-meta-line"><span>Model</span><strong>{selectedRun.model_alias || selectedRun.model_name || "-"}</strong></div>
                    <div className="compact-meta-line"><span>Processed</span><strong>{selectedRunCounts.processed} / {selectedRunCounts.total}</strong></div>
                    <div className="compact-meta-line"><span>Succeeded</span><strong>{selectedRunCounts.succeeded}</strong></div>
                    <div className="compact-meta-line"><span>Failed</span><strong>{selectedRunCounts.failed}</strong></div>
                    <div className="compact-meta-line"><span>Inflight</span><strong>{selectedRunCounts.inflight}</strong></div>
                  </div>
                  <div className="history-toolbar history-toolbar-compact">
                    <div className="history-toolbar-group">
                      <button
                        className="mini-button"
                        type="button"
                        onClick={() => handlePreviewReport(selectedRun.run_id, { generateIfMissing: !selectedRun.report_ready })}
                      >
                        打开报告预览
                      </button>
                      <CopyButton value={selectedRun.run_dir} label="复制目录" />
                    </div>
                  </div>
                  <PathList
                    title="文件路径"
                    paths={{
                      run_dir: selectedRun.run_dir,
                      evaluation_run_path: selectedRun.evaluation_run_path,
                      item_scores_path: selectedRun.item_scores_path,
                      summary_path: selectedRun.summary_path,
                      canonical_summary_path: selectedRun.canonical_summary_path,
                      report_path: selectedRun.report_path,
                    }}
                  />
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {view === "reports" ? (
          <section className="panel report-page">
            <SectionTitle title="报告预览" meta={report?.run_id || "选择一个已完成 run"} />
            <PathList title="报告目录" paths={{ reports_root: systemPaths?.reports_root }} />
            <div className="report-page-layout">
              <div className="detail-card report-browser-card">
                <SectionTitle title="可预览报告" meta={`${reportCandidates.length} 个已完成 run`} />
                <div className="config-list report-run-list">
                  {reportCandidates.slice(0, 24).map((run) => (
                    <button
                      key={run.run_id}
                      type="button"
                      className={report?.run_id === run.run_id ? "config-row report-run-row active" : "config-row report-run-row"}
                      onClick={() => handlePreviewReport(run.run_id, { generateIfMissing: !run.report_ready })}
                    >
                      <div className="config-row-main">
                        <div className="config-row-title mono">{run.run_id}</div>
                        <div className="config-row-subtitle">{run.model_alias || run.model_name || "-"} / {run.execution_status || run.status || "-"}</div>
                        <div className="config-chip-row">
                          <RunArtifactStatus ready={run.report_ready} label="报告" />
                          <RunArtifactStatus ready={run.canonical_ready} label="Canonical" />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="stack-sections">
                {report ? (
                  <>
                    <div className="report-hero-surface">
                      <div className="report-score-grid">
                        <ScoreCard title="Capability" value={formatValue(reportSummaryMetrics.capability_score ?? 0)} tone="warm" />
                        <ScoreCard title="Safety" value={formatValue(reportSummaryMetrics.safety_composite_score ?? 0)} tone="neutral" />
                        <ScoreCard title="Probe" value={formatValue(reportSummaryMetrics.probe_score ?? 0)} tone="cool" />
                        <ScoreCard title="Overall" value={formatValue(reportSummaryMetrics.overall_macro_score ?? 0)} tone="neutral" />
                      </div>
                      <div className="meta-row report-meta-row">
                        <span>Run: {report.run_id}</span>
                        <span>Path: {report.report_path}</span>
                      </div>
                    </div>

                    <div className="report-preview-grid">
                      <div className="detail-card report-chart-stage">
                        <SectionTitle title="结构化图表" meta="默认展示 canonical 汇总口径" />
                        <ReportCharts reportData={report} />
                      </div>
                      <div className="detail-card report-preview-card">
                        <SectionTitle title="文档预览" meta="Markdown 实时预览" />
                        <MarkdownPreview content={report.content} />
                      </div>
                    </div>

                    {loadingReport ? <div className="muted-text">正在生成或读取报告…</div> : null}
                    <details className="report-raw-block">
                      <summary>查看原始 Markdown 报告</summary>
                      <pre className="report-view">{report.content}</pre>
                    </details>
                  </>
                ) : (
                  <EmptyState
                    title="还没有加载报告"
                    description="你可以从左侧选择一个已完成 run 直接预览；如果该 run 还没有生成报告，系统会自动补生成并加载。"
                    actionLabel={selectedRunId ? "为当前 Run 生成并预览" : undefined}
                    onAction={selectedRunId ? () => handlePreviewReport(selectedRunId, { generateIfMissing: true }) : undefined}
                  />
                )}
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

export default App;
