import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";
import ResizableTable, { ResizableTh, ResizableTd } from "./components/ResizableTable.jsx";

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "ready", label: "Ready" },
  { value: "draft", label: "Draft" },
  { value: "pilot", label: "Pilot" },
  { value: "frozen", label: "Frozen" },
  { value: "retired", label: "Retired" },
];

const ITEM_FORMAT_OPTIONS = [
  { value: "single_turn", label: "单轮 single_turn" },
  { value: "multi_turn_group", label: "多轮组 multi_turn_group" },
];

const DIFFICULTY_OPTIONS = [
  { value: "", label: "未指定" },
  { value: "easy", label: "简单 easy" },
  { value: "medium", label: "中等 medium" },
  { value: "hard", label: "困难 hard" },
];

const DRIFT_ROLE_OPTIONS = [
  { value: "capability", label: "能力 capability" },
  { value: "safety", label: "安全 safety" },
  { value: "probe", label: "探针 probe" },
];

const STATUS_LABELS = {
  ready: "Ready",
  draft: "Draft",
  pilot: "Pilot",
  frozen: "Frozen",
  retired: "Retired",
};

const STATUS_CLASS = {
  ready: "status-ready",
  draft: "status-draft",
  pilot: "status-pilot",
  frozen: "status-frozen",
  retired: "status-retired",
};

const MODULE_TONE = {}; // populated from /api/dict/modules; legacy keys still resolved by `module-${code}`

function createEmptyDraft() {
  return {
    question_id: "",
    version: "QB-v1.2",
    module: "A1",
    subtype: "",
    item_format: "single_turn",
    difficulty: "",
    drift_role: "capability",
    prompt_template: "",
    turn_script: null,
    ground_truth: "",
    scoring_method: "exact_match",
    scoring_params_text: "{}",
    module_quota_tag: "",
    qa_status: "draft",
    rotation_replaceable: true,
    rotation_priority: 1,
    rotation_lifespan: 90,
    provenance_rewrite_ids: "",
    provenance_source_ids: "",
    provenance_summary: "",
    notes: "",
  };
}

function fromBankItem(item) {
  if (!item) return createEmptyDraft();
  const rp = item.rotation_policy || {};
  const prov = item.provenance || {};
  return {
    question_id: item.question_id || "",
    version: item.version || "QB-v1.2",
    module: item.module || "A1",
    subtype: item.subtype || "",
    item_format: item.item_format || "single_turn",
    difficulty: item.difficulty || "",
    drift_role: item.drift_role || "capability",
    prompt_template: item.prompt_template || "",
    turn_script: item.turn_script || null,
    ground_truth:
      item.ground_truth === null || item.ground_truth === undefined
        ? ""
        : typeof item.ground_truth === "string"
          ? item.ground_truth
          : JSON.stringify(item.ground_truth),
    scoring_method: item.scoring_method || "exact_match",
    scoring_params_text: JSON.stringify(item.scoring_params || {}, null, 2),
    module_quota_tag: item.module_quota_tag || "",
    qa_status: item.qa_status || "ready",
    rotation_replaceable: rp.replaceable !== false,
    rotation_priority: rp.rotation_priority || 1,
    rotation_lifespan: rp.expected_lifespan_days || 90,
    provenance_rewrite_ids: (prov.rewrite_ids || []).join(", "),
    provenance_source_ids: (prov.source_candidate_ids || []).join(", "),
    provenance_summary: prov.transformation_summary || "",
    notes: item.notes || "",
  };
}

function buildPayload(draft) {
  let scoringParams = {};
  if (draft.scoring_params_text && draft.scoring_params_text.trim()) {
    try {
      scoringParams = JSON.parse(draft.scoring_params_text);
    } catch (error) {
      throw new Error(`评分参数不是合法 JSON：${error.message}`);
    }
  }
  const groundTruthRaw = draft.ground_truth;
  let groundTruth = null;
  if (groundTruthRaw !== "" && groundTruthRaw !== null && groundTruthRaw !== undefined) {
    const trimmed = String(groundTruthRaw).trim();
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      groundTruth = Number(trimmed);
    } else {
      groundTruth = trimmed;
    }
  }
  const turnScript = Array.isArray(draft.turn_script) && draft.turn_script.length > 0
    ? draft.turn_script.map((turn, idx) => ({
        turn_index: Number(turn.turn_index) || idx,
        speaker: turn.speaker || "user",
        content_template: turn.content_template || "",
        branch_key: turn.branch_key || null,
      }))
    : null;
  return {
    question_id: draft.question_id.trim(),
    version: draft.version || "QB-v1.2",
    module: draft.module,
    subtype: draft.subtype || null,
    item_format: draft.item_format,
    difficulty: draft.difficulty || null,
    drift_role: draft.drift_role,
    prompt_template: draft.prompt_template || null,
    turn_script: turnScript,
    ground_truth: groundTruth,
    scoring_method: draft.scoring_method,
    scoring_params: scoringParams,
    module_quota_tag: draft.module_quota_tag || null,
    qa_status: draft.qa_status,
    rotation_policy: {
      replaceable: Boolean(draft.rotation_replaceable),
      rotation_priority: Number(draft.rotation_priority) || 1,
      expected_lifespan_days: Number(draft.rotation_lifespan) || null,
    },
    provenance: {
      rewrite_ids: draft.provenance_rewrite_ids
        ? draft.provenance_rewrite_ids.split(",").map((s) => s.trim()).filter(Boolean)
        : [],
      source_candidate_ids: draft.provenance_source_ids
        ? draft.provenance_source_ids.split(",").map((s) => s.trim()).filter(Boolean)
        : [],
      transformation_summary: draft.provenance_summary || "Created/edited from the question bank management UI.",
    },
    notes: draft.notes || "",
  };
}

function StatusPill({ status }) {
  const label = STATUS_LABELS[status] || status || "—";
  const cls = STATUS_CLASS[status] || "status-ready";
  return <span className={`status-pill-bank ${cls}`}>{label}</span>;
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  );
}

function IconArchive() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="4" rx="1" />
      <path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8" />
      <path d="M10 12h4" />
    </svg>
  );
}

function IconRestore() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg className="bank-search-glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function BankFormModal({ open, mode, initial, busy, error, moduleOptions = [], onClose, onSubmit }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => fromBankItem(initial));

  useEffect(() => {
    if (open) {
      setDraft(fromBankItem(initial));
    }
  }, [open, initial]);

  if (!open) return null;

  const isEdit = mode === "edit";
  const title = isEdit ? `编辑题目 · ${initial?.question_id || ""}` : "新建题目";

  function updateField(name, value) {
    setDraft((prev) => ({ ...prev, [name]: value }));
  }

  function updateTurn(index, field, value) {
    setDraft((prev) => {
      const list = Array.isArray(prev.turn_script) ? [...prev.turn_script] : [];
      list[index] = { ...list[index], [field]: value };
      return { ...prev, turn_script: list };
    });
  }

  function addTurn() {
    setDraft((prev) => {
      const list = Array.isArray(prev.turn_script) ? [...prev.turn_script] : [];
      list.push({ turn_index: list.length, speaker: "user", content_template: "", branch_key: null });
      return { ...prev, turn_script: list };
    });
  }

  function removeTurn(index) {
    setDraft((prev) => {
      const list = Array.isArray(prev.turn_script) ? [...prev.turn_script] : [];
      list.splice(index, 1);
      return { ...prev, turn_script: list };
    });
  }

  function handleSubmit(event) {
    event.preventDefault();
    try {
      const payload = buildPayload(draft);
      onSubmit(payload);
    } catch (err) {
      onSubmit(null, err);
    }
  }

  return createPortal(
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal-card"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        style={{ width: "min(960px, calc(100vw - 2rem))" }}
      >
        <form onSubmit={handleSubmit}>
          <div className="modal-header">
            <div>
              <div className="modal-title">{title}</div>
              <div className="modal-subtitle">
                完整字段会写入 <code>final_bank_specs/generated/final_bank_items.jsonl</code> 并同步进 SQLite。
              </div>
            </div>
            <button type="button" className="modal-close" onClick={onClose} aria-label="关闭">×</button>
          </div>
          <div className="modal-body">
            <div className="bank-form-grid">
              <div className="bank-form-field">
                <label>{t("forms.questionId")}</label>
                <input
                  value={draft.question_id}
                  disabled={isEdit}
                  onChange={(event) => updateField("question_id", event.target.value)}
                  placeholder="例如 A1-001"
                  required
                />
                {isEdit ? <div className="bank-form-hint">Question ID 在编辑时不可修改。</div> : null}
              </div>
              <div className="bank-form-field">
                <label>{t("forms.version")}</label>
                <input
                  value={draft.version}
                  onChange={(event) => updateField("version", event.target.value)}
                  placeholder="QB-v1.2"
                />
              </div>
              <div className="bank-form-field">
                <label>{t("forms.module")}</label>
                <select value={draft.module} onChange={(event) => updateField("module", event.target.value)}>
                  {(moduleOptions.length ? moduleOptions : [{code:"A1"},{code:"A2"}]).map((m) => (
                    <option key={m.code} value={m.code}>
                      {m.code}{m.display_name ? ` · ${m.display_name}` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="bank-form-field">
                <label>{t("forms.subtype")}</label>
                <input
                  value={draft.subtype}
                  onChange={(event) => updateField("subtype", event.target.value)}
                  placeholder="例如 math_reasoning"
                />
              </div>
              <div className="bank-form-field">
                <label>题型 Item Format</label>
                <select value={draft.item_format} onChange={(event) => updateField("item_format", event.target.value)}>
                  {ITEM_FORMAT_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="bank-form-field">
                <label>难度 Difficulty</label>
                <select value={draft.difficulty} onChange={(event) => updateField("difficulty", event.target.value)}>
                  {DIFFICULTY_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="bank-form-field">
                <label>能力定位 Drift Role</label>
                <select value={draft.drift_role} onChange={(event) => updateField("drift_role", event.target.value)}>
                  {DRIFT_ROLE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="bank-form-field">
                <label>状态 QA Status</label>
                <select value={draft.qa_status} onChange={(event) => updateField("qa_status", event.target.value)}>
                  {STATUS_OPTIONS.filter((opt) => opt.value).map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>

              <div className="bank-form-field is-full">
                <label>题面 Prompt Template</label>
                <textarea
                  rows={5}
                  value={draft.prompt_template}
                  onChange={(event) => updateField("prompt_template", event.target.value)}
                  placeholder="单轮题直接填写题面；多轮题可留空，配合下方 turn script 使用。"
                />
              </div>

              <div className="bank-form-field is-full">
                <label>多轮脚本 Turn Script</label>
                <div className="bank-form-hint">适用于 <code>multi_turn_group</code>；单轮题可忽略。</div>
                <div className="bank-form-turn-list">
                  {(Array.isArray(draft.turn_script) ? draft.turn_script : []).map((turn, idx) => (
                    <div className="bank-form-turn-item" key={`turn-${idx}`}>
                      <input
                        type="number"
                        value={turn.turn_index ?? idx}
                        onChange={(event) => updateTurn(idx, "turn_index", event.target.value)}
                        placeholder="turn_index"
                      />
                      <select value={turn.speaker || "user"} onChange={(event) => updateTurn(idx, "speaker", event.target.value)}>
                        <option value="system">system</option>
                        <option value="user">user</option>
                        <option value="assistant">assistant</option>
                      </select>
                      <textarea
                        rows={3}
                        value={turn.content_template || ""}
                        onChange={(event) => updateTurn(idx, "content_template", event.target.value)}
                        placeholder="该轮的内容模板"
                      />
                      <button type="button" className="bank-form-turn-remove" onClick={() => removeTurn(idx)} aria-label="删除该轮">×</button>
                    </div>
                  ))}
                  <button type="button" className="bank-form-turn-add" onClick={addTurn}>+ 添加一轮</button>
                </div>
              </div>

              <div className="bank-form-field">
                <label>标准答案 Ground Truth</label>
                <input
                  value={draft.ground_truth}
                  onChange={(event) => updateField("ground_truth", event.target.value)}
                  placeholder="支持纯数字或文本"
                />
              </div>
              <div className="bank-form-field">
                <label>评分方法 Scoring Method</label>
                <input
                  value={draft.scoring_method}
                  onChange={(event) => updateField("scoring_method", event.target.value)}
                  placeholder="exact_match / numeric_em / f1 / rouge_l / refusal ..."
                />
              </div>

              <div className="bank-form-field is-full">
                <label>评分参数 Scoring Params (JSON)</label>
                <textarea
                  rows={4}
                  value={draft.scoring_params_text}
                  onChange={(event) => updateField("scoring_params_text", event.target.value)}
                  placeholder='例如 {"answer_format": "答案：[数字]"}'
                />
                <div className="bank-form-hint">必须是合法 JSON 文本。空对象表示无参数。</div>
              </div>

              <div className="bank-form-field">
                <label>{t("forms.moduleQuotaTag")}</label>
                <input
                  value={draft.module_quota_tag}
                  onChange={(event) => updateField("module_quota_tag", event.target.value)}
                  placeholder="可选"
                />
              </div>
              <div className="bank-form-field">
                <label>可被替换 Replaceable</label>
                <select
                  value={String(Boolean(draft.rotation_replaceable))}
                  onChange={(event) => updateField("rotation_replaceable", event.target.value === "true")}
                >
                  <option value="true">是</option>
                  <option value="false">否</option>
                </select>
              </div>
              <div className="bank-form-field">
                <label>轮换优先级 Priority</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={draft.rotation_priority}
                  onChange={(event) => updateField("rotation_priority", Number(event.target.value))}
                />
              </div>
              <div className="bank-form-field">
                <label>预期寿命（天）</label>
                <input
                  type="number"
                  min={0}
                  value={draft.rotation_lifespan}
                  onChange={(event) => updateField("rotation_lifespan", event.target.value)}
                />
              </div>

              <div className="bank-form-field is-full"><label>溯源 Provenance</label></div>
              <div className="bank-form-field is-full">
                <label>Rewrite IDs（逗号分隔）</label>
                <input
                  value={draft.provenance_rewrite_ids}
                  onChange={(event) => updateField("provenance_rewrite_ids", event.target.value)}
                  placeholder="例如 rw-a1-001, rw-a1-002"
                />
              </div>
              <div className="bank-form-field is-full">
                <label>Source Candidate IDs（逗号分隔）</label>
                <input
                  value={draft.provenance_source_ids}
                  onChange={(event) => updateField("provenance_source_ids", event.target.value)}
                  placeholder="例如 gsm8k-train-00000"
                />
              </div>
              <div className="bank-form-field is-full">
                <label>Transformation Summary</label>
                <textarea
                  rows={2}
                  value={draft.provenance_summary}
                  onChange={(event) => updateField("provenance_summary", event.target.value)}
                />
              </div>

              <div className="bank-form-field is-full">
                <label>备注 Notes</label>
                <textarea
                  rows={2}
                  value={draft.notes}
                  onChange={(event) => updateField("notes", event.target.value)}
                />
              </div>
            </div>
            {error ? <div className="bank-form-error">{error}</div> : null}
          </div>
          <div className="bank-form-footer">
            <div className="bank-form-footer-meta">
              修改会自动写入 SQLite 与 JSONL；题库浏览 / 评测会立即看到新版本。
            </div>
            <div className="bank-form-footer-actions">
              <button type="button" className="action-button secondary compact-action" onClick={onClose} disabled={busy}>
                取消
              </button>
              <button type="submit" className="action-button compact-action" disabled={busy}>
                {busy ? "保存中…" : isEdit ? "保存修改" : "创建题目"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}

function BankConfirmDialog({ open, tone = "danger", title, body, callout, confirmLabel, cancelLabel = "取消", busy, onConfirm, onCancel }) {
  if (!open) return null;
  return createPortal(
    <div className="modal-backdrop" onClick={onCancel} role="presentation">
      <div
        className="modal-card"
        style={{ width: "min(520px, calc(100vw - 2rem))" }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <div>
            <div className="modal-title">{title}</div>
            {body ? <div className="modal-subtitle">{body}</div> : null}
          </div>
          <button type="button" className="modal-close" onClick={onCancel} aria-label="关闭">×</button>
        </div>
        <div className="modal-body">
          <div className={`bank-confirm is-${tone}`}>
            <div className="bank-confirm-title">{title}</div>
            <div className="bank-confirm-body">{body}</div>
            {callout ? (
              <div className="bank-confirm-callout">
                {callout.map((row, idx) => (
                  <div key={idx}>
                    <span className="callout-key">{row.label}：</span>
                    <span>{row.value}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        <div className="bank-form-footer">
          <div className="bank-form-footer-meta">该操作会直接修改题库主存储与 JSONL。</div>
          <div className="bank-form-footer-actions">
            <button type="button" className="action-button secondary compact-action" onClick={onCancel} disabled={busy}>
              {cancelLabel}
            </button>
            <button
              type="button"
              className={`action-button compact-action ${tone === "danger" ? "is-danger" : ""}`}
              onClick={onConfirm}
              disabled={busy}
            >
              {busy ? "处理中…" : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function briefText(text, maxLen = 90) {
  if (!text) return "";
  const compact = String(text).replace(/\s+/g, " ").trim();
  return compact.length > maxLen ? `${compact.slice(0, maxLen)}…` : compact;
}

function BankDetail({ item, onAction, busy, canMutate }) {
  const { t } = useTranslation();
  if (!item) {
    return (
      <div className="bank-detail">
        <div className="bank-detail-empty">
          <span className="bank-detail-empty-mark">λ</span>
          <div>从左侧选择一道题，或点击“新建题目”开始你的私有题库。</div>
        </div>
      </div>
    );
  }
  const status = item.qa_status || "ready";
  const isArchived = status === "retired";
  const isMulti = item.item_format === "multi_turn_group";
  return (
    <div className="bank-detail">
      <div className="bank-detail-head">
        <div className="bank-detail-id">{item.question_id}</div>
        <div className="bank-detail-title">
          {briefText(item.prompt_template || item.turn_script?.[0]?.content_template || "未提供题面预览", 90)}
        </div>
        <div className="bank-detail-subtitle">
          <span className={`bank-cell-module module-${item.module || "default"}`}>
            <span className="module-mark">{item.module}</span>
            {item.subtype || "—"} · {item.item_format}
          </span>
        </div>
        <div className="bank-detail-actions">
          <StatusPill status={status} />
          {canMutate ? (
            <>
              <button type="button" className="action-button secondary compact-action" onClick={() => onAction("edit", item)} disabled={busy}>
                <IconEdit /> 编辑
              </button>
              {isArchived ? (
                <button type="button" className="action-button secondary compact-action" onClick={() => onAction("restore", item)} disabled={busy}>
                  <IconRestore /> 恢复
                </button>
              ) : (
                <button type="button" className="action-button secondary compact-action" onClick={() => onAction("archive", item)} disabled={busy}>
                  <IconArchive /> 归档
                </button>
              )}
              <button type="button" className="action-button compact-action is-danger" onClick={() => onAction("delete", item)} disabled={busy}>
                <IconTrash /> 删除
              </button>
            </>
          ) : null}
        </div>
      </div>
      <div className="bank-detail-body">
        <section className="bank-section">
          <div className="bank-section-head">
            <span className="bank-section-title">基础信息</span>
            <span className="bank-section-note">meta</span>
          </div>
          <div className="bank-kv-grid">
            <div className="bank-kv"><span className="bank-kv-key">{t("forms.version")}</span><span className="bank-kv-value mono-id">{item.version || "—"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Drift Role</span><span className="bank-kv-value">{item.drift_role || "—"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Difficulty</span><span className="bank-kv-value">{item.difficulty || "—"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Quota Tag</span><span className="bank-kv-value mono-id">{item.module_quota_tag || "—"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Replaceable</span><span className="bank-kv-value">{item.rotation_policy?.replaceable ? "是" : "否"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Priority · Lifespan</span><span className="bank-kv-value">{item.rotation_policy?.rotation_priority ?? "—"} · {item.rotation_policy?.expected_lifespan_days ?? "—"} 天</span></div>
          </div>
        </section>

        <section className="bank-section">
          <div className="bank-section-head">
            <span className="bank-section-title">题面</span>
            <span className="bank-section-note">{isMulti ? `${(item.turn_script || []).length} turns` : "single-turn"}</span>
          </div>
          {isMulti && Array.isArray(item.turn_script) && item.turn_script.length > 0 ? (
            <div>
              {item.turn_script.map((turn, idx) => (
                <div className="bank-turn-row" key={`${item.question_id}-${idx}`}>
                  <div className="bank-turn-meta">
                    Turn {turn.turn_index ?? idx} · {turn.speaker}
                    {turn.branch_key ? ` · ${turn.branch_key}` : ""}
                  </div>
                  <div className="bank-turn-content">{turn.content_template}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bank-prompt-block">{item.prompt_template || "未提供题面"}</div>
          )}
        </section>

        <section className="bank-section">
          <div className="bank-section-head">
            <span className="bank-section-title">评分</span>
            <span className="bank-section-note">scoring</span>
          </div>
          <div className="bank-kv-grid">
            <div className="bank-kv"><span className="bank-kv-key">Method</span><span className="bank-kv-value mono-id">{item.scoring_method || "—"}</span></div>
            <div className="bank-kv"><span className="bank-kv-key">Ground Truth</span><span className="bank-kv-value mono-id">
              {item.ground_truth === null || item.ground_truth === undefined ? "—" : String(item.ground_truth)}
            </span></div>
          </div>
          <pre className="bank-prompt-block" style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: "0.82rem" }}>
            {JSON.stringify(item.scoring_params || {}, null, 2)}
          </pre>
        </section>

        <section className="bank-section">
          <div className="bank-section-head">
            <span className="bank-section-title">溯源</span>
            <span className="bank-section-note">provenance</span>
          </div>
          <pre className="bank-prompt-block" style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: "0.82rem" }}>
            {JSON.stringify(item.provenance || {}, null, 2)}
          </pre>
          {item.notes ? <div className="bank-form-hint">备注：{item.notes}</div> : null}
        </section>
      </div>
    </div>
  );
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

export default function BankPage({ apiFetch, systemPaths, onToast, canMutate = true }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [facets, setFacets] = useState({
    total: 0,
    versions: [],
    modules: [],
    subtypes: [],
    item_formats: [],
    qa_statuses: [],
  });
  const [filters, setFilters] = useState({
    version: "",
    module: "",
    subtype: "",
    item_format: "",
    qa_status: "",
    keyword: "",
    include_archived: true,
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [moduleDict, setModuleDict] = useState([]);
  const requestSeq = useRef(0);

  const [formState, setFormState] = useState({ open: false, mode: "create", item: null, busy: false, error: null });
  const [confirmState, setConfirmState] = useState({ open: false, kind: null, item: null, items: [], busy: false });

  const availableSubtypes = useMemo(() => {
    // 始终展示全量 subtype,跨 module 通用;后端会按 (module, subtype) 双键过滤
    return facets.subtypes || [];
  }, [facets.subtypes]);

  async function loadFacets() {
    try {
      const data = await apiFetch("/api/bank/facets");
      setFacets(data);
    } catch (error) {
      onToast?.("error", "加载题库维度失败", error.message);
    }
  }

  async function loadRows() {
    const seq = ++requestSeq.current;
    setLoading(true);
    try {
      const params = {
        version: filters.version,
        module: filters.module,
        subtype: filters.subtype,
        item_format: filters.item_format,
        qa_status: filters.qa_status,
        include_archived: filters.include_archived,
        keyword: filters.keyword,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      };
      const data = await apiFetch(`/api/bank/items${buildQuery(params)}`);
      if (seq !== requestSeq.current) return;
      setRows(data.items || []);
      setTotal(data.total || 0);
      if (data.items && data.items.length) {
        if (!data.items.find((it) => it.question_id === selectedId)) {
          setSelectedId(data.items[0].question_id);
        }
      } else {
        setSelectedId(null);
      }
      setSelectedIds((prev) => prev.filter((qid) => (data.items || []).some((it) => it.question_id === qid)));
    } catch (error) {
      onToast?.("error", "加载题库失败", error.message);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    loadFacets();
    loadModuleDict();
  }, []);

  async function loadModuleDict() {
    try {
      const data = await apiFetch("/api/dict/modules?include_inactive=true");
      const items = (data?.items || []).slice().sort((a, b) => {
        const orderA = a.sort_order ?? 0;
        const orderB = b.sort_order ?? 0;
        if (orderA !== orderB) return orderA - orderB;
        return String(a.code).localeCompare(String(b.code));
      });
      setModuleDict(items);
    } catch (err) {
      // 静默失败:继续用 fallback 列表
      setModuleDict([]);
    }
  }

  useEffect(() => {
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.version,
    filters.module,
    filters.subtype,
    filters.item_format,
    filters.qa_status,
    filters.include_archived,
    filters.keyword,
    page,
    pageSize,
  ]);

  useEffect(() => {
    // 仅当所选 subtype 在任何模块里都不存在时才清空
    if (filters.subtype && !(facets.subtypes || []).some((s) => s.value === filters.subtype)) {
      setFilters((prev) => ({ ...prev, subtype: "" }));
    }
  }, [facets.subtypes, filters.subtype]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    if (detailOpen) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [detailOpen]);

  const selectedItem = useMemo(() => {
    if (!rows.length) return null;
    return rows.find((it) => it.question_id === selectedId) || rows[0];
  }, [rows, selectedId]);
  const selectedVersionLabel = filters.version || ((facets.versions || [])[0]?.value ?? "全部版本");
  const selectedRows = useMemo(() => rows.filter((it) => selectedIds.includes(it.question_id)), [rows, selectedIds]);
  const allVisibleSelected = rows.length > 0 && rows.every((it) => selectedIds.includes(it.question_id));

  const totalAll = facets.total || total;
  const archivedCount = useMemo(() => (facets.qa_statuses || []).find((s) => s.value === "retired")?.count || 0, [facets.qa_statuses]);
  const activeCount = useMemo(() => (facets.qa_statuses || []).find((s) => s.value === "ready")?.count || 0, [facets.qa_statuses]);
  const draftCount = useMemo(() => (facets.qa_statuses || []).find((s) => s.value === "draft")?.count || 0, [facets.qa_statuses]);

  function handleAction(kind, item) {
    if (kind === "edit") setFormState({ open: true, mode: "edit", item, busy: false, error: null });
    else if (kind === "create") {
      const base = createEmptyDraft();
      base.version = filters.version || base.version;
      setFormState({ open: true, mode: "create", item: base, busy: false, error: null });
    } else if (kind === "archive") setConfirmState({ open: true, kind: "archive", item, items: [], busy: false });
    else if (kind === "restore") setConfirmState({ open: true, kind: "restore", item, items: [], busy: false });
    else if (kind === "delete") setConfirmState({ open: true, kind: "delete", item, items: [], busy: false });
    else if (kind === "bulk-archive") setConfirmState({ open: true, kind: "bulk-archive", item: null, items: selectedRows, busy: false });
    else if (kind === "bulk-restore") setConfirmState({ open: true, kind: "bulk-restore", item: null, items: selectedRows, busy: false });
    else if (kind === "bulk-delete") setConfirmState({ open: true, kind: "bulk-delete", item: null, items: selectedRows, busy: false });
  }

  async function handleFormSubmit(payload, buildError) {
    if (buildError) {
      setFormState((prev) => ({ ...prev, error: buildError.message }));
      return;
    }
    setFormState((prev) => ({ ...prev, busy: true, error: null }));
    try {
      if (formState.mode === "edit") {
        await apiFetch(`/api/bank/items/${payload.question_id}`, { method: "PUT", body: JSON.stringify(payload) });
        onToast?.("success", "已保存修改", `${payload.question_id} 已更新。`);
      } else {
        await apiFetch("/api/bank/items", { method: "POST", body: JSON.stringify(payload) });
        onToast?.("success", "已创建题目", `${payload.question_id} 已加入题库。`);
      }
      setFormState({ open: false, mode: "create", item: null, busy: false, error: null });
      await Promise.all([loadFacets(), loadRows()]);
    } catch (error) {
      setFormState((prev) => ({ ...prev, busy: false, error: error.message }));
    }
  }

  async function handleConfirm() {
    const { kind, item, items } = confirmState;
    if (!item && !(items && items.length)) return;
    setConfirmState((prev) => ({ ...prev, busy: true }));
    try {
      if (kind === "archive") {
        await apiFetch(`/api/bank/items/${item.question_id}/archive`, { method: "POST" });
        onToast?.("success", "已归档", `${item.question_id} 已转为 retired。`);
      } else if (kind === "restore") {
        await apiFetch(`/api/bank/items/${item.question_id}/restore?qa_status=ready`, { method: "POST" });
        onToast?.("success", "已恢复", `${item.question_id} 已恢复为 ready。`);
      } else if (kind === "delete") {
        await apiFetch(`/api/bank/items/${item.question_id}`, { method: "DELETE" });
        onToast?.("success", "已删除", `${item.question_id} 已从题库中移除。`);
      } else if (kind === "bulk-archive") {
        const result = await apiFetch("/api/bank/items/bulk-action", {
          method: "POST",
          body: JSON.stringify({ action: "archive", question_ids: items.map((entry) => entry.question_id) }),
        });
        onToast?.("success", "已批量归档", `已归档 ${result.count || 0} 道题。`);
      } else if (kind === "bulk-restore") {
        const result = await apiFetch("/api/bank/items/bulk-action", {
          method: "POST",
          body: JSON.stringify({ action: "restore", qa_status: "ready", question_ids: items.map((entry) => entry.question_id) }),
        });
        onToast?.("success", "已批量恢复", `已恢复 ${result.count || 0} 道题。`);
      } else if (kind === "bulk-delete") {
        const result = await apiFetch("/api/bank/items/bulk-action", {
          method: "POST",
          body: JSON.stringify({ action: "delete", question_ids: items.map((entry) => entry.question_id) }),
        });
        onToast?.("success", "已批量删除", `已删除 ${result.count || 0} 道题。`);
      }
      setSelectedIds([]);
      setConfirmState({ open: false, kind: null, item: null, items: [], busy: false });
      await Promise.all([loadFacets(), loadRows()]);
    } catch (error) {
      onToast?.("error", "操作失败", error.message);
      setConfirmState((prev) => ({ ...prev, busy: false }));
    }
  }

  function getConfirmConfig() {
    const { kind, item, items } = confirmState;
    const bulkCount = items?.length || 0;
    if (!item && !bulkCount) return null;
    if (kind === "archive") {
      return {
        tone: "warning",
        title: "归档这道题？",
        body: "归档后这道题会进入 retired 状态；评测与列表默认会隐藏它，可随时恢复。",
        callout: [
          { label: "Question", value: item.question_id },
          { label: "Module", value: `${item.module} · ${item.subtype || "—"}` },
        ],
        confirmLabel: "归档",
      };
    }
    if (kind === "bulk-archive") {
      return {
        tone: "warning",
        title: `归档选中的 ${bulkCount} 道题？`,
        body: "这些题会一起进入 retired 状态；默认不再进入评测集合，但后续仍可批量恢复。",
        callout: [
          { label: "Selected", value: `${bulkCount} items` },
          { label: "Version", value: selectedVersionLabel },
        ],
        confirmLabel: "批量归档",
      };
    }
    if (kind === "restore") {
      return {
        tone: "warning",
        title: "恢复这道题？",
        body: "恢复后状态会回到 ready，重新出现在题库浏览与可评测集合中。",
        callout: [
          { label: "Question", value: item.question_id },
          { label: "Module", value: `${item.module} · ${item.subtype || "—"}` },
        ],
        confirmLabel: "恢复",
      };
    }
    if (kind === "bulk-restore") {
      return {
        tone: "warning",
        title: `恢复选中的 ${bulkCount} 道题？`,
        body: "恢复后这些题的状态会统一回到 ready，重新出现在可评测集合中。",
        callout: [
          { label: "Selected", value: `${bulkCount} items` },
          { label: "Version", value: selectedVersionLabel },
        ],
        confirmLabel: "批量恢复",
      };
    }
    if (kind === "delete") {
      return {
        tone: "danger",
        title: "永久删除这道题？",
        body: "删除会同时从 SQLite 与 final_bank_items.jsonl 移除，相关历史 run 中的成绩会保留但失去题面引用。此操作不可撤销。",
        callout: [
          { label: "Question", value: item.question_id },
          { label: "Module", value: `${item.module} · ${item.subtype || "—"}` },
          { label: "Scoring", value: item.scoring_method || "—" },
        ],
        confirmLabel: "确认删除",
      };
    }
    if (kind === "bulk-delete") {
      return {
        tone: "danger",
        title: `永久删除选中的 ${bulkCount} 道题？`,
        body: "删除会同时从 SQLite 与 final_bank_items.jsonl 移除。相关历史 run 成绩会保留，但可能失去题面引用。此操作不可撤销。",
        callout: [
          { label: "Selected", value: `${bulkCount} items` },
          { label: "Version", value: selectedVersionLabel },
        ],
        confirmLabel: "确认批量删除",
      };
    }
    return null;
  }

  const confirmConfig = getConfirmConfig();

  return (
    <section className="panel bank-page">
      <div className="bank-hero">
        <div className="bank-hero-main">
          <div className="bank-eyebrow">Question Bank Atelier</div>
          <h1 className="bank-display">
            策划、筛选与<em>归档</em>你的私有题库
          </h1>
          <div className="bank-subtitle">
            每一道题都来自公开 benchmark 的私有化改写。在这里查看模块分布、
            维护题面质量、把暂时不用的题目归档（retired），或彻底移除已经失效的旧题。
          </div>
        </div>
        <div className="bank-hero-stats">
          <div className="bank-stat-card is-active">
            <div className="bank-stat-label">Active · ready</div>
            <div className="bank-stat-value">{activeCount}<span className="stat-suffix">/ {totalAll}</span></div>
          </div>
          <div className="bank-stat-card is-draft">
            <div className="bank-stat-label">Drafts</div>
            <div className="bank-stat-value">{draftCount}</div>
          </div>
          <div className="bank-stat-card is-archived">
            <div className="bank-stat-label">Archived</div>
            <div className="bank-stat-value">{archivedCount}</div>
          </div>
          <div className="bank-stat-card">
            <div className="bank-stat-label">Versions</div>
            <div className="bank-stat-value">{(facets.versions || []).length}</div>
          </div>
        </div>
      </div>

      <div className="bank-toolbar">
        <div className="bank-filter-cluster">
          <span className="bank-filter-label">{t("forms.version")}</span>
          <div className="bank-pill-group" role="tablist">
            <button
              type="button"
              className={`bank-pill ${filters.version === "" ? "is-active" : ""}`}
              onClick={() => { setFilters((prev) => ({ ...prev, version: "" })); setPage(1); }}
            >
              全部版本
            </button>
            {(facets.versions || []).map((v) => (
              <button
                key={v.value || "unknown"}
                type="button"
                className={`bank-pill ${filters.version === v.value ? "is-active" : ""}`}
                onClick={() => { setFilters((prev) => ({ ...prev, version: v.value })); setPage(1); }}
              >
                {v.value || "未标注"}
                <span className="pill-count">{v.count}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="bank-filter-cluster">
          <span className="bank-filter-label">{t("forms.status")}</span>
          <div className="bank-pill-group" role="tablist">
            {STATUS_OPTIONS.map((opt) => {
              const count = opt.value ? (facets.qa_statuses || []).find((s) => s.value === opt.value)?.count || 0 : null;
              const active = filters.qa_status === opt.value;
              return (
                <button
                  key={opt.value || "all"}
                  type="button"
                  className={`bank-pill ${active ? "is-active" : ""}`}
                  onClick={() => { setFilters((prev) => ({ ...prev, qa_status: opt.value })); setPage(1); }}
                >
                  {opt.label}
                  {count !== null ? <span className="pill-count">{count}</span> : null}
                </button>
              );
            })}
          </div>
        </div>

        <div className="bank-filter-cluster">
          <span className="bank-filter-label">{t("forms.module")}</span>
          <select
            className="bank-search"
            style={{ padding: "0.4rem 0.7rem" }}
            value={filters.module}
            onChange={(event) => { setFilters((prev) => ({ ...prev, module: event.target.value, subtype: "" })); setPage(1); }}
          >
            <option value="">全部</option>
            {(facets.modules || []).map((m) => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
          </select>
        </div>

        <div className="bank-filter-cluster">
          <span className="bank-filter-label">{t("forms.subtype")}</span>
          <select
            className="bank-search"
            style={{ padding: "0.4rem 0.7rem" }}
            value={filters.subtype}
            onChange={(event) => { setFilters((prev) => ({ ...prev, subtype: event.target.value })); setPage(1); }}
            disabled={!availableSubtypes.length}
          >
            <option value="">全部</option>
            {availableSubtypes.map((s) => <option key={s.value} value={s.value}>{s.value} ({s.count})</option>)}
          </select>
        </div>

        <div className="bank-filter-cluster">
          <span className="bank-filter-label">{t("forms.format")}</span>
          <select
            className="bank-search"
            style={{ padding: "0.4rem 0.7rem" }}
            value={filters.item_format}
            onChange={(event) => { setFilters((prev) => ({ ...prev, item_format: event.target.value })); setPage(1); }}
          >
            <option value="">全部</option>
            {(facets.item_formats || []).map((f) => <option key={f.value} value={f.value}>{f.value} ({f.count})</option>)}
          </select>
        </div>

        <label className="bank-search" style={{ flex: "1 1 14rem" }}>
          <IconSearch />
          <input
            value={filters.keyword}
            onChange={(event) => { setFilters((prev) => ({ ...prev, keyword: event.target.value })); setPage(1); }}
            placeholder="题面关键词 / question id"
          />
        </label>

        <label className="bank-pill" style={{ border: "1px solid rgba(201,184,159,0.7)" }}>
          <input
            type="checkbox"
            checked={filters.include_archived}
            onChange={(event) => { setFilters((prev) => ({ ...prev, include_archived: event.target.checked })); setPage(1); }}
            style={{ accentColor: "var(--accent)" }}
          />
          <span>含已归档</span>
        </label>

        {canMutate ? (
          <button type="button" className="bank-create-button" onClick={() => handleAction("create", null)} disabled={formState.busy}>
            新建题目
          </button>
        ) : null}
      </div>

      {canMutate && selectedIds.length ? (
        <div className="bank-bulk-toolbar">
          <div className="bank-bulk-toolbar-meta">
            已选择 <strong>{selectedIds.length}</strong> 道题 · 当前版本 {selectedVersionLabel}
          </div>
          <div className="bank-bulk-toolbar-actions">
            <button type="button" className="action-button secondary compact-action" onClick={() => handleAction("bulk-archive", null)}>
              批量归档
            </button>
            <button type="button" className="action-button secondary compact-action" onClick={() => handleAction("bulk-restore", null)}>
              批量恢复
            </button>
            <button type="button" className="action-button danger compact-action" onClick={() => handleAction("bulk-delete", null)}>
              批量删除
            </button>
            <button type="button" className="action-button secondary compact-action" onClick={() => setSelectedIds([])}>
              清空选择
            </button>
          </div>
        </div>
      ) : null}

      <div className="bank-table-wrap">
        <div className="bank-table-head">
          <div>
            <div className="bank-table-title">题库</div>
            <div className="bank-table-subtitle">
              当前命中 {rows.length} / {total}（正式题总数 {totalAll}） · 版本 {selectedVersionLabel}
            </div>
          </div>
          <div className="bank-table-meta">
            {(facets.modules || []).length} modules · {(facets.subtypes || []).length} subtypes
          </div>
        </div>
        {loading ? <div className="muted-text" style={{ padding: "1.4rem" }}>正在按筛选条件刷新题库…</div> : null}
        {!loading && !rows.length ? (
          <div className="bank-detail-empty" style={{ minHeight: "12rem" }}>
            <span className="bank-detail-empty-mark">∅</span>
            <div>没有命中任何题目。试试调整筛选条件或新建一道题。</div>
          </div>
        ) : null}
        {rows.length ? (
          <div style={{ overflowX: "auto" }}>
            <ResizableTable
              storageKey="bank-table-v1"
              className="bank-table"
              defaultWidths={[3, 6.5, 5.5, 4.5, 11, 6.5, 8]}
            >
              {({ widths, beginDrag }) => (
                <>
              <thead>
                <tr>
                  {canMutate ? <th style={{ width: `${widths[0]}rem` }}><input type="checkbox" checked={allVisibleSelected} onChange={(event) => {
                    if (event.target.checked) {
                      setSelectedIds((prev) => Array.from(new Set([...prev, ...rows.map((it) => it.question_id)])));
                    } else {
                      setSelectedIds((prev) => prev.filter((qid) => !rows.some((it) => it.question_id === qid)));
                    }
                  }} /></th> : null}
                  <ResizableTh width={widths[1]} onBeginDrag={(e) => beginDrag(e, 1)}>ID</ResizableTh>
                  <ResizableTh width={widths[2]} onBeginDrag={(e) => beginDrag(e, 2)}>{t("forms.version")}</ResizableTh>
                  <ResizableTh width={widths[3]} onBeginDrag={(e) => beginDrag(e, 3)}>{t("forms.module")}</ResizableTh>
                  <ResizableTh width={widths[4]} onBeginDrag={(e) => beginDrag(e, 4)}>{t("forms.subtype")}</ResizableTh>
                  <ResizableTh width={widths[5]} onBeginDrag={(e) => beginDrag(e, 5)}>题面预览</ResizableTh>
                  <ResizableTh width={widths[6]} onBeginDrag={(e) => beginDrag(e, 6)}>状态</ResizableTh>
                  <ResizableTh width={widths[7]} onBeginDrag={(e) => beginDrag(e, 7)}>{t("forms.format")}</ResizableTh>
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => {
                  const isActive = selectedItem?.question_id === item.question_id;
                  const isArchivedRow = (item.qa_status || "ready") === "retired";
                  return (
                    <tr
                      key={item.question_id}
                      className={`${isActive ? "is-active" : ""} ${isArchivedRow ? "is-archived" : ""}`}
                      onClick={() => {
                        setSelectedId(item.question_id);
                        setDetailOpen(true);
                      }}
                    >
                      {canMutate ? (
                        <td onClick={(event) => event.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(item.question_id)}
                            onChange={(event) => {
                              if (event.target.checked) {
                                setSelectedIds((prev) => Array.from(new Set([...prev, item.question_id])));
                              } else {
                                setSelectedIds((prev) => prev.filter((qid) => qid !== item.question_id));
                              }
                            }}
                          />
                        </td>
                      ) : null}
                      <ResizableTd width={widths[1]} className="bank-cell-id">{item.question_id}</ResizableTd>
                      <ResizableTd width={widths[2]}>{item.version || "—"}</ResizableTd>
                      <ResizableTd width={widths[3]}>
                        <span className={`bank-cell-module module-${item.module || "default"}`}>
                          <span className="module-mark">{item.module}</span>
                        </span>
                      </ResizableTd>
                      <ResizableTd width={widths[4]} style={{ wordBreak: "break-word" }}>{item.subtype || "—"}</ResizableTd>
                      <ResizableTd width={widths[5]}>
                        <div className="bank-cell-prompt">
                          {briefText(item.prompt_template || item.turn_script?.[0]?.content_template, 200)}
                        </div>
                      </ResizableTd>
                      <ResizableTd width={widths[6]}><StatusPill status={item.qa_status || "ready"} /></ResizableTd>
                      <ResizableTd width={widths[7]}>{item.item_format}</ResizableTd>
                    </tr>
                  );
                })}
              </tbody>
                </>
              )}
            </ResizableTable>
          </div>
        ) : null}
      </div>

      {rows.length ? (
        <div className="pagination-bar">
          <div className="pagination-info">
            第 {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} 条 / 共 {total} 条
          </div>
          <div className="pagination-controls">
            <button type="button" className="action-button secondary compact-action" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              上一页
            </button>
            <span className="pagination-page">第 {page} 页</span>
            <button type="button" className="action-button secondary compact-action" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>
              下一页
            </button>
            <select
              className="action-button secondary compact-action"
              value={pageSize}
              onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}
            >
              {[10, 20, 50, 100].map((size) => <option key={size} value={size}>{size} / 页</option>)}
            </select>
          </div>
        </div>
      ) : null}

      <BankFormModal
        open={formState.open}
        mode={formState.mode}
        initial={formState.item}
        busy={formState.busy}
        error={formState.error}
        moduleOptions={moduleDict}
        onClose={() => setFormState({ open: false, mode: "create", item: null, busy: false, error: null })}
        onSubmit={handleFormSubmit}
      />

      {confirmConfig ? (
        <BankConfirmDialog
          open={confirmState.open}
          tone={confirmConfig.tone}
          title={confirmConfig.title}
          body={confirmConfig.body}
          callout={confirmConfig.callout}
          confirmLabel={confirmConfig.confirmLabel}
          busy={confirmState.busy}
          onCancel={() => setConfirmState({ open: false, kind: null, item: null, items: [], busy: false })}
          onConfirm={handleConfirm}
        />
      ) : null}

      {detailOpen && selectedItem
        ? createPortal(
            <div
              className="modal-backdrop"
              onClick={() => setDetailOpen(false)}
              role="presentation"
            >
              <div
                className="modal-card modal-card-lg"
                onClick={(event) => event.stopPropagation()}
                role="dialog"
                aria-modal="true"
              >
                <div className="modal-header">
                  <div>
                    <div className="modal-title">题目详情</div>
                    <div className="modal-subtitle">
                      {selectedItem.question_id} · {selectedItem.module}{selectedItem.subtype ? ` · ${selectedItem.subtype}` : ""}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="modal-close"
                    onClick={() => setDetailOpen(false)}
                    aria-label="关闭"
                  >
                    ×
                  </button>
                </div>
                <div className="modal-body">
                  <BankDetail
                    item={selectedItem}
                    onAction={(kind, item) => {
                      setDetailOpen(false);
                      handleAction(kind, item);
                    }}
                    busy={formState.busy || confirmState.busy}
                    canMutate={canMutate}
                  />
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </section>
  );
}
