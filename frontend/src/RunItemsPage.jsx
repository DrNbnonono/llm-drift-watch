import React, { useEffect, useMemo, useState } from "react";
import { reasoningState } from "./responsePresentation.js";
import { formatEstimatedCost, formatTokens } from "./evaluationMonitor.js";

function segments(response) {
  if (!response) return [];
  if (Array.isArray(response.turn_results)) return response.turn_results.map((value, index) => ({ label: `Turn ${index + 1}`, value }));
  if (response.scenario_results) return Object.entries(response.scenario_results).flatMap(([branch, values]) =>
    (Array.isArray(values) ? values : [values]).map((value, index) => ({ label: `${branch} · Turn ${index + 1}`, value })),
  );
  return [{ label: "回答", value: response }];
}

function finalText(response) {
  return segments(response).map(({ value }) => value?.text || "").filter(Boolean).join("\n\n");
}

function Reasoning({ response }) {
  const state = reasoningState(response);
  if (state === "legacy") return <div className="reasoning-empty legacy">该 Run 创建时未采集思考过程。</div>;
  if (state === "unavailable") return <div className="reasoning-empty">Provider 未返回思考内容。</div>;
  return <div className="reasoning-segments">{segments(response).map(({ label, value }, index) => (
    <div className="reasoning-segment" key={`${label}-${index}`}>
      <strong>{label}</strong>
      {value?.reasoning_available ? <pre className="detail-pre reasoning-body">{value.reasoning}</pre> : <div className="reasoning-empty">本轮未返回思考内容。</div>}
      {value?.reasoning_truncated ? <div className="reasoning-warning">已按 256K 字符上限截断；原始长度 {value.reasoning_original_chars} 字符。</div> : null}
    </div>
  ))}</div>;
}

function Metadata({ response }) {
  return <div className="response-meta-grid">{segments(response).map(({ label, value }, index) => (
    <div key={`${label}-${index}`}><strong>{label}</strong><span>模型：{value?.model_name || value?.model || "-"}</span><span>Stop：{value?.stop_reason || value?.finish_reason || "-"}</span><span>请求 ID：{value?.id || value?.request_id || "-"}</span><span>Usage：{value?.usage ? JSON.stringify(value.usage) : "-"}</span></div>
  ))}</div>;
}

function Question({ item }) {
  const bank = item?.bank_item || {};
  const prompt = bank.prompt_template || bank.prompt || (bank.turn_script ? JSON.stringify(bank.turn_script, null, 2) : "-");
  return <div className="detail-section"><h4>完整题目与多轮脚本</h4><pre className="detail-pre">{prompt}</pre></div>;
}

function Score({ item, formatValue }) {
  const bank = item?.bank_item || {};
  return <>
    <div className="detail-section"><h4>标准答案与评分约束</h4><pre className="detail-pre">{JSON.stringify({ ground_truth: bank.ground_truth, scoring_method: bank.scoring_method || item.score_method, scoring_params: bank.scoring_params }, null, 2)}</pre></div>
    <div className="detail-section"><h4>评分明细</h4><p>规则分 {formatValue(item.rule_score)} · 裁判分 {formatValue(item.judge_score)} · 人工分 {formatValue(item.manual_score)} · 有效分 {formatValue(item.effective_score)}（{item.score_source || "-"}）</p><p>Judge Token：{formatTokens(item.judge_assessment?.raw_response?.billing_usage)} · Judge 费用：{formatEstimatedCost(item.judge_assessment?.raw_response?.estimated_cost)}</p><h5>裁判 criteria / rationale</h5><pre className="detail-pre">{JSON.stringify(item.judge_assessment || item.score_details || {}, null, 2)}</pre></div>
  </>;
}

export default function RunItemsPage({
  runItems, runItemsTotal, loadingRunItems, itemFilters, setItemFilters, itemPage, itemPageSize,
  setItemPage, setItemPageSize, selectedRunId, selectedRun, selectedRunItem, runs = [], moduleOptions = [],
  helpers: { SectionTitle, PaginationBar, EmptyState, briefText, formatValue, apiFetch },
  onRefreshRun, onSelectQuestion, onSelectRun, onScopeChange,
}) {
  const answer = useMemo(() => finalText(selectedRunItem?.response), [selectedRunItem]);
  const [reviewer, setReviewer] = useState("");
  const [manualScore, setManualScore] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewHistory, setReviewHistory] = useState([]);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    apiFetch?.("/api/review-settings").then((data) => setReviewer((old) => old || data.reviewer_name || "")).catch(() => {});
  }, [apiFetch]);

  useEffect(() => {
    if (!selectedRunId || !selectedRunItem?.question_id) { setReviewHistory([]); return; }
    apiFetch?.(`/api/runs/${selectedRunId}/items/${encodeURIComponent(selectedRunItem.question_id)}/reviews`)
      .then((data) => setReviewHistory(data.manual_reviews || [])).catch(() => setReviewHistory([]));
  }, [apiFetch, selectedRunId, selectedRunItem?.question_id]);

  async function submitManualReview(event) {
    event.preventDefault();
    if (!selectedRunItem) return;
    setReviewBusy(true); setReviewError("");
    try {
      const result = await apiFetch(`/api/runs/${selectedRunId}/items/${encodeURIComponent(selectedRunItem.question_id)}/manual-review`, {
        method: "POST",
        body: JSON.stringify({ attempt_run_id: selectedRunItem.attempt_run_id, reviewer: reviewer.trim(), score: Number(manualScore), note: reviewNote.trim(), confirmed: true }),
      });
      setReviewHistory(result.item?.manual_reviews || [...reviewHistory, result.review]);
      setReviewNote("");
      await onRefreshRun(selectedRunId);
    } catch (error) { setReviewError(error?.message || String(error)); }
    finally { setReviewBusy(false); }
  }
  return <section className="panel run-items-page">
    <div className="run-items-header">
      <div><h2>逐题结果</h2><div className="mono">{selectedRunId || "未选择 Run"}</div><div className="muted-text">{selectedRun?.model_name || selectedRun?.model_alias || "-"} · {selectedRun?.run_kind || "base"} · {selectedRun?.bank_version || "-"} · {itemFilters.canonical_only ? "Canonical" : "Attempt"} · {runItemsTotal} 条</div></div>
      <label>Run 选择器<select value={selectedRunId || ""} onChange={(event) => onSelectRun?.(event.target.value)}>{runs.map((run) => <option value={run.run_id} key={run.run_id}>{run.run_id} · {run.run_kind || "base"}</option>)}</select></label>
      <div className="inline-actions"><button className={itemFilters.canonical_only ? "action-button" : "action-button secondary"} onClick={() => onScopeChange?.("canonical")}>Canonical</button><button className={!itemFilters.canonical_only ? "action-button" : "action-button secondary"} onClick={() => onScopeChange?.("attempt")}>Attempt</button><button className="action-button secondary" onClick={() => onRefreshRun(selectedRunId)}>刷新</button></div>
    </div>
    {selectedRun?.run_kind === "retry" && selectedRun.parent_run_id ? <button className="mini-button" onClick={() => onSelectRun?.(selectedRun.parent_run_id)}>查看 Root Canonical</button> : null}
    <div className="filters-row">
      <label>模块<select value={itemFilters.module} onChange={(event) => setItemFilters((old) => ({ ...old, module: event.target.value }))}><option value="">全部</option>{moduleOptions.map((m) => <option key={m.code || m} value={m.code || m}>{m.code || m}</option>)}</select></label>
      <label>状态<select value={itemFilters.status} onChange={(event) => setItemFilters((old) => ({ ...old, status: event.target.value }))}><option value="">全部</option><option value="ok">ok</option><option value="failed">failed</option></select></label>
      <label>题号<input value={itemFilters.question_id} onChange={(event) => setItemFilters((old) => ({ ...old, question_id: event.target.value }))} /></label>
      <label>关键词<input value={itemFilters.search} onChange={(event) => setItemFilters((old) => ({ ...old, search: event.target.value }))} /></label>
    </div>
    <PaginationBar page={itemPage} pageSize={itemPageSize} total={runItemsTotal} onPageChange={setItemPage} onPageSizeChange={(size) => { setItemPageSize(size); setItemPage(1); }} />
    <div className="items-layout"><div className="items-list">
      {loadingRunItems ? <div className="muted-text">正在加载逐题结果…</div> : null}
      {!loadingRunItems && !runItems.length ? <EmptyState title="没有匹配结果" description="请调整筛选条件，或确认 Run 是否仍存在。" /> : <div className="table-shell"><table className="data-table"><thead><tr><th>题号</th><th>模块</th><th>回答预览</th><th>状态</th><th>有效分</th></tr></thead><tbody>{runItems.map((item) => <tr key={`${item.question_id}-${item.attempt_run_id || ""}`} className={selectedRunItem?.question_id === item.question_id ? "row-active" : ""} onClick={() => onSelectQuestion(item.question_id)}><td className="mono">{item.question_id}</td><td>{item.module}</td><td>{briefText(finalText(item.response), 120)}</td><td>{item.status}</td><td>{formatValue(item.effective_score)}<br />{item.score_source}</td></tr>)}</tbody></table></div>}
    </div><aside className="detail-card run-answer-detail">{!selectedRunItem ? <EmptyState title="选择一道题" description="查看题目、思考过程、最终回答与评分。" /> : <><h3>{selectedRunItem.bank_version} · {selectedRunItem.question_id}</h3><Question item={selectedRunItem} /><details className="detail-section reasoning-panel"><summary><strong>模型思考过程</strong></summary><Reasoning response={selectedRunItem.response} /></details><div className="detail-section"><h4>最终回答</h4><pre className="detail-pre response-body">{answer || "（空回答）"}</pre></div><div className="detail-section"><h4>调用元数据</h4><Metadata response={selectedRunItem.response} /><p>Token：{formatTokens(selectedRunItem.token_usage)} · 估算费用：{formatEstimatedCost(selectedRunItem.estimated_cost)}</p></div><Score item={selectedRunItem} formatValue={formatValue} />
      <form className="detail-section manual-review-card form-stack" onSubmit={submitManualReview}><h4>人工复核</h4><p className="muted-text">人工分提交后立即成为有效分，并保留原规则分和裁判分。</p><label>复核人<input required value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label><label>人工分（0–1）<input required type="number" min="0" max="1" step="0.01" value={manualScore} onChange={(event) => setManualScore(event.target.value)} /></label><label>复核备注<textarea required value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="说明评分错误原因或修正依据" /></label>{reviewError ? <div className="error-banner">{reviewError}</div> : null}<button className="action-button" disabled={reviewBusy}>{reviewBusy ? "提交中…" : "提交人工评分"}</button></form>
      <details className="detail-section"><summary><strong>复核历史（{reviewHistory.length}）</strong></summary>{reviewHistory.length ? <div className="review-history-list">{reviewHistory.map((review) => <article key={review.id || review.created_at}><strong>{review.reviewer} · {formatValue(review.score)} · {review.verdict}</strong><p>{review.note}</p><small>{review.created_at}</small></article>)}</div> : <p className="muted-text">暂无人工复核记录。</p>}</details>
      <details className="detail-section"><summary><strong>原始规范化响应</strong></summary><pre className="detail-pre">{JSON.stringify(selectedRunItem.response, null, 2)}</pre></details></>}</aside></div>
  </section>;
}
