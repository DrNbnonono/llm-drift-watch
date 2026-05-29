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
  { key: "models", label: "模型管理" },
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
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
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
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [showModelForm, setShowModelForm] = useState(false);
  const [itemPage, setItemPage] = useState(1);
  const [itemPageSize, setItemPageSize] = useState(20);
  const [bankPage, setBankPage] = useState(1);
  const [bankPageSize, setBankPageSize] = useState(20);

  const [runForm, setRunForm] = useState({
    provider_id: "minimax_anthropic",
    model_alias: "minimax_m2_7",
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
    if (selectedRunId && selectedRunItem?.question_id) {
      loadTimeline(selectedRunId, selectedRunItem.question_id, itemFilters.canonical_only);
    } else {
      setTimelineData(null);
    }
  }, [selectedRunId, selectedRunItem?.question_id, itemFilters.canonical_only]);

  useEffect(() => {
    const shouldLock = showProviderForm || showModelForm;
    const previousOverflow = document.body.style.overflow;
    if (shouldLock) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [showProviderForm, showModelForm]);

  async function refreshProviders() {
    setLoadingProviders(true);
    try {
      const data = await apiFetch("/api/providers");
      const nextProviders = data.providers || [];
      const nextModels = data.models || [];
      setProviders(nextProviders);
      setModels(nextModels);
      if ((!runForm.model_alias || !nextModels.some((item) => item.model_alias === runForm.model_alias)) && nextModels.length) {
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
      setError(humanizeError(err?.message || err));
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
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        provider_id: runForm.provider_id,
        model_alias: runForm.model_alias,
        modules: runForm.modules.length ? runForm.modules : null,
        smoke: runForm.smoke,
        timeout: Number(runForm.timeout) || null,
        concurrency_limit: Number(runForm.concurrency_limit) || 1,
        max_items: runForm.max_items ? Number(runForm.max_items) : null,
      };
      const run = await apiFetch("/api/runs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
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
    try {
      await apiFetch(`/api/runs/${selectedRunId}/report`, { method: "POST" });
      const reportData = await apiFetch(`/api/reports/${selectedRunId}`);
      setReport(reportData);
      setView("reports");
    } catch (err) {
      setError(humanizeError(err?.message || err));
    } finally {
      setBusy(false);
      setLoadingReport(false);
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
          <div className="brand-kicker">LLM Evaluation</div>
          <div className="brand-title">Multi-Model Console</div>
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

      <main className="content">
        <header className="hero">
          <div>
            <div className="hero-title">多模型测评系统</div>
            <div className="hero-subtitle">支持模型注册、历史兼容、题库浏览、逐题详情和多轮时间线。</div>
            <div className="hero-endpoint">API: {API_BASE}</div>
          </div>
          <div className="hero-actions">
            <button className="action-button" onClick={handleRetryFailures} disabled={!selectedRunId || busy}>
              重试失败题
            </button>
            <button className="action-button secondary" onClick={handleGenerateReport} disabled={!selectedRunId || busy}>
              生成报告
            </button>
          </div>
        </header>

        <section className="score-grid">
          <ScoreCard title="Capability" value={selectedRunSummary.capability_score} tone="warm" />
          <ScoreCard title="Safety" value={selectedRunSummary.safety_composite_score} tone="cool" />
          <ScoreCard title="Probe" value={selectedRunSummary.probe_score} tone="earth" />
          <ScoreCard title="Overall" value={selectedRunSummary.overall_macro_score} tone="neutral" />
        </section>

        {error ? <div className="error-banner">{error}</div> : null}
        {notice ? <div className="notice-banner">{notice}</div> : null}

        {view === "create" ? (
          <section className="panel">
            <SectionTitle title="创建评测任务" meta="支持旧 run 和新模型同屏管理" />
            {selectedProvider ? (
              <div className="hero-subgrid">
                <InfoBanner
                  tone={selectedProvider.configured ? "ok" : "warn"}
                  title={`当前 Provider: ${selectedProvider.display_name}`}
                  body={
                    <>
                      <div>协议：{selectedProvider.protocol}</div>
                      <div>Base URL：{selectedProvider.base_url || "-"}</div>
                      <div>所需 Key：{selectedProvider.auth_env || "无需密钥"}</div>
                    </>
                  }
                />
                <InfoBanner
                  tone={selectedProvider.configured ? "neutral" : "warn"}
                  title={selectedProvider.configured ? "凭据已就绪" : "凭据尚未配置"}
                  body={
                    selectedProvider.configured
                      ? "当前后端环境变量已经可用，可以直接发起评测。"
                      : `请先在后端环境中设置 ${selectedProvider.auth_env || "对应环境变量"}，否则模型请求会失败。`
                  }
                />
              </div>
            ) : null}
            <form className="form-grid wide" onSubmit={handleCreateRun}>
              <label>
                Provider
                <select
                  value={runForm.provider_id}
                  onChange={(event) => {
                    const nextProviderId = event.target.value;
                    const firstModel = models.find((model) => model.provider_id === nextProviderId && model.enabled !== false);
                    setRunForm((prev) => ({
                      ...prev,
                      provider_id: nextProviderId,
                      model_alias: firstModel?.model_alias || "",
                    }));
                  }}
                >
                  {providers.map((provider) => (
                    <option key={provider.provider_id} value={provider.provider_id}>
                      {provider.display_name} {provider.configured ? "" : "(未配置密钥)"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Model Alias
                <select
                  value={runForm.model_alias}
                  onChange={(event) => setRunForm((prev) => ({ ...prev, model_alias: event.target.value }))}
                >
                  {!modelsForProvider.length ? <option value="">当前 Provider 下没有可用模型</option> : null}
                  {modelsForProvider.map((model) => (
                    <option key={model.model_alias} value={model.model_alias}>
                      {model.display_name}
                    </option>
                  ))}
                </select>
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
                <span>Completed: {selectedRun?.progress?.items_completed ?? selectedRun?.totals?.items_completed ?? 0} / {selectedRun?.progress?.items_total ?? selectedRun?.totals?.items_total ?? 0}</span>
                <span>Failed: {selectedRun?.progress?.items_failed ?? selectedRun?.totals?.items_failed ?? 0}</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${selectedRun?.progress?.items_total ? (selectedRun.progress.items_completed / Math.max(1, selectedRun.progress.items_total)) * 100 : 0}%`,
                  }}
                />
              </div>
              <div className="progress-caption">
                <span>
                  {selectedRun?.progress?.items_completed ?? 0} / {selectedRun?.progress?.items_total ?? 0}
                  {" "}已处理
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
            <SectionTitle title="模型管理" meta="非密钥配置保存到项目文件，密钥仍只走环境变量" />
            <PathList title="配置文件位置" paths={{ providers_config_path: systemPaths?.providers_config_path }} />
            {loadingProviders ? <div className="muted-text">正在加载模型配置…</div> : null}
            <div className="management-grid management-grid-compact">
              <div className="management-column">
                <div className="detail-card management-surface">
                  <SectionTitle title="Provider 管理" meta="协议、URL、认证环境变量" />
                  <div className="mini-stat-grid compact-stats">
                    <SummaryMiniCard label="Provider 总数" value={providerSummary.total} />
                    <SummaryMiniCard label="已启用" value={providerSummary.enabled} />
                    <SummaryMiniCard label="已配置密钥" value={providerSummary.configured} />
                  </div>
                  <div className="toolbar-row compact-toolbar">
                    <button className="action-button compact-action" type="button" onClick={openNewProviderForm}>
                      新增 Provider
                    </button>
                    <button className="action-button secondary compact-action" type="button" onClick={refreshProviders}>
                      刷新
                    </button>
                  </div>
                  <div className="compact-hint-row">
                    <span>密钥不会写入配置文件，只会读取后端环境变量。</span>
                  </div>
                  <div className="config-list">
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
                              <span className="chip chip-soft mono" title={provider.auth_env || "无需密钥"}>{provider.auth_env || "无需密钥"}</span>
                              <StatusPill configured={provider.configured} envName={provider.auth_env} />
                              <span className={`chip ${provider.enabled !== false ? "chip-ok" : "chip-failed"}`}>{provider.enabled !== false ? "enabled" : "disabled"}</span>
                            </div>
                          </div>
                          <div className="config-row-actions">
                            <button className="mini-button" type="button" onClick={(event) => { event.stopPropagation(); beginEditProvider(provider); }}>编辑</button>
                            <button
                              className="mini-button danger"
                              type="button"
                              disabled={hasLinkedModel}
                              title={hasLinkedModel ? "请先删除或迁移该 Provider 下的 Model Alias" : "删除 Provider"}
                              onClick={(event) => { event.stopPropagation(); deleteProvider(provider.provider_id); }}
                            >
                              删除
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="management-column">
                <div className="detail-card management-surface">
                  <SectionTitle title="Model Alias 管理" meta="内部别名、真实 model_name 与默认参数" />
                  <div className="mini-stat-grid compact-stats">
                    <SummaryMiniCard label="Model 总数" value={modelSummary.total} />
                    <SummaryMiniCard label="已启用" value={modelSummary.enabled} />
                    <SummaryMiniCard label="支持多轮" value={modelSummary.multiTurn} />
                  </div>
                  <div className="toolbar-row compact-toolbar">
                    <button className="action-button compact-action" type="button" onClick={openNewModelForm}>
                      新增 Model Alias
                    </button>
                    <button className="action-button secondary compact-action" type="button" onClick={refreshProviders}>
                      刷新
                    </button>
                  </div>
                  <div className="compact-hint-row">
                    <span>建议先选 Provider，再填写稳定英文 alias；真实模型名填在 model_name。</span>
                  </div>
                  <div className="config-list">
                    {models.length ? models.map((model) => (
                      <div className="config-row" key={model.model_alias} onClick={() => beginEditModel(model)}>
                        <div className="config-row-main">
                          <div className="config-row-title">{model.display_name || model.model_alias}</div>
                          <div className="config-row-subtitle mono">{model.model_alias}</div>
                          <div className="config-chip-row">
                            <span className="chip chip-soft mono" title={model.provider_id}>{model.provider_id}</span>
                            <span className="chip chip-soft" title={model.model_name}>{briefText(model.model_name, 44)}</span>
                            <span className="chip">timeout {model.default_timeout}s</span>
                            <span className="chip">{model.default_max_tokens} tokens</span>
                            <span className={`chip ${model.supports_multi_turn ? "chip-ok" : "chip-soft"}`}>{model.supports_multi_turn ? "multi-turn" : "single-turn"}</span>
                            <span className={`chip ${model.enabled !== false ? "chip-ok" : "chip-failed"}`}>{model.enabled !== false ? "enabled" : "disabled"}</span>
                          </div>
                        </div>
                        <div className="config-row-actions">
                          <button className="mini-button" type="button" onClick={(event) => { event.stopPropagation(); beginEditModel(model); }}>编辑</button>
                          <button className="mini-button danger" type="button" onClick={(event) => { event.stopPropagation(); deleteModel(model.model_alias); }}>删除</button>
                        </div>
                      </div>
                    )) : (
                      <EmptyState
                        title="还没有 Model Alias"
                        description="点击“新增 Model Alias”创建第一个模型映射。"
                        actionLabel="立即新增"
                        onAction={openNewModelForm}
                      />
                    )}
                  </div>
                </div>
              </div>
            </div>

            <ModalDialog
              open={showProviderForm}
              title={editingProviderId ? `编辑 Provider` : "新增 Provider"}
              subtitle={editingProviderId || "配置协议、URL 与认证环境变量"}
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
                <InfoBanner
                  tone={providerForm.auth_scheme === "none" ? "neutral" : "warn"}
                  title={providerForm.auth_scheme === "none" ? "当前 Provider 不需要密钥" : `请在后端环境中配置 ${providerForm.auth_env || "对应环境变量"}`}
                  body={providerForm.auth_scheme === "none" ? "例如 mock provider 可以不依赖认证。" : "这里填写的是环境变量名，不是明文 API Key。"}
                />
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
                <div className="modal-section-head">高级请求头</div>
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
              subtitle={editingModelAlias || "为 Provider 绑定可复用的模型别名"}
              onClose={busy ? undefined : resetModelForm}
            >
              <form className="form-stack modal-form" onSubmit={handleModelSubmit}>
                <div className="form-grid compact-form-grid">
                  <label>
                    model_alias
                    <input
                      value={modelForm.model_alias}
                      onChange={(event) => setModelForm((prev) => ({ ...prev, model_alias: event.target.value }))}
                      onBlur={() => {
                        if (!modelForm.model_alias.trim()) {
                          const nextAlias = slugifyAlias(modelForm.model_name || modelForm.display_name);
                          if (nextAlias) {
                            setModelForm((prev) => ({ ...prev, model_alias: nextAlias }));
                          }
                        }
                      }}
                      placeholder="例如 minimax_m2_7"
                    />
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
                    <input
                      value={modelForm.model_name}
                      onChange={(event) => setModelForm((prev) => ({ ...prev, model_name: event.target.value }))}
                      placeholder="例如 MiniMax-M2.7"
                    />
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
                <div className="compact-meta-panel">
                  <div className="compact-meta-line"><span>绑定 Provider</span><strong>{selectedModelProvider?.display_name || modelForm.provider_id || "-"}</strong></div>
                  <div className="compact-meta-line"><span>所需 Key</span><code>{selectedModelProvider?.auth_env || "无需密钥"}</code></div>
                  <div className="compact-meta-line"><span>当前状态</span><strong>{selectedModelProvider?.configured ? "环境已配置" : "环境未配置"}</strong></div>
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
          <section className="panel">
            <SectionTitle title="历史 Runs" meta={`共 ${runs.length} 条`} />
            <PathList title="历史运行目录" paths={{ evaluation_runs_root: systemPaths?.evaluation_runs_root }} />
            <div className="muted-text">评测结果默认保存在 <code>manifests/evaluation_runs/&lt;run_id&gt;/</code>，正式题库来自 <code>final_bank_specs/generated/final_bank_items.jsonl</code>。</div>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Kind</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Status</th>
                    <th>Completed / Total</th>
                    <th>Report</th>
                    <th>Canonical</th>
                    <th>路径</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.run_id}
                      onClick={() => {
                        setSelectedRunId(run.run_id);
                        setSelectedQuestionId(null);
                        refreshRun(run.run_id);
                      }}
                    >
                      <td className="mono">{run.run_id}</td>
                      <td>{run.run_kind || "base"}</td>
                      <td>{run.provider_id || "-"}</td>
                      <td>{run.model_alias || run.model_name || "-"}</td>
                      <td>{run.execution_status || run.status || "-"}</td>
                      <td>{run.totals?.items_completed ?? 0} / {run.totals?.items_total ?? 0}</td>
                      <td><RunArtifactStatus ready={run.report_ready} label="报告" /></td>
                      <td><RunArtifactStatus ready={run.canonical_ready} label="Canonical" /></td>
                      <td><CopyButton value={run.run_dir} label="复制目录" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {selectedRun ? (
              <div className="detail-card inline-detail-card">
                <SectionTitle title={`Run 产物: ${selectedRun.run_id}`} />
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
          </section>
        ) : null}

        {view === "reports" ? (
          <section className="panel">
            <SectionTitle title="报告" />
            <PathList title="报告目录" paths={{ reports_root: systemPaths?.reports_root }} />
            {report ? (
              <>
                <div className="meta-row">
                  <span>Run: {report.run_id}</span>
                  <span>Path: {report.report_path}</span>
                </div>
                {loadingReport ? <div className="muted-text">正在生成或读取报告…</div> : null}
                <pre className="report-view">{report.content}</pre>
              </>
            ) : (
              <div className="muted-text">先选择一个 run 并生成报告。生成后的 Markdown 会保存在对应 run 目录下。</div>
            )}
          </section>
        ) : null}
      </main>
    </div>
  );
}

export default App;
