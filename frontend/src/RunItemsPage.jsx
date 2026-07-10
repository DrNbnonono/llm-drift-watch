import React, { useEffect, useMemo, useState } from "react";

function responseText(response) {
  if (!response) return "";
  if (response.text !== undefined) return String(response.text || "");
  if (response.turn_results) return response.turn_results.map((row) => row.text || "").join("\n\n");
  if (response.scenario_results) return Object.values(response.scenario_results).flat().map((row) => row.text || "").join("\n\n");
  return "";
}

function AnswerBasis({ item }) {
  const bank = item?.bank_item || {};
  const params = bank.scoring_params || {};
  const method = bank.scoring_method || item?.score_method;
  let title = "无唯一标准答案";
  let body = "该题按期望行为、风险边界和评分规则评估。";
  if (bank.ground_truth !== null && bank.ground_truth !== undefined && bank.ground_truth !== "") {
    title = "标准答案";
    body = typeof bank.ground_truth === "string" ? bank.ground_truth : JSON.stringify(bank.ground_truth, null, 2);
  } else if (method === "exec") {
    title = "代码测试 Oracle";
    body = JSON.stringify(params.tests || params.test_cases || params, null, 2);
  } else if (["constraint_set", "rule", "injection_resilience", "escalation_resilience", "pseudo_compliance_resilience"].includes(method)) {
    title = "约束与评分规则";
    body = JSON.stringify(params, null, 2);
  }
  return (
    <div className="detail-section">
      <h4>参考答案与评分依据</h4>
      <strong>{title}</strong>
      <pre className="detail-pre">{body}</pre>
      <details><summary>查看原始题目快照 JSON</summary><pre className="detail-pre">{JSON.stringify(bank, null, 2)}</pre></details>
    </div>
  );
}

export default function RunItemsPage({
  runItems, runItemsTotal, loadingRunItems, itemFilters, setItemFilters, itemPage, itemPageSize,
  setItemPage, setItemPageSize, selectedRunId, selectedRunItem, moduleOptions = [],
  helpers: { SectionTitle, PaginationBar, EmptyState, briefText, formatValue, setView, apiFetch },
  onRefreshRun, onSelectQuestion,
}) {
  const [reviewer, setReviewer] = useState("");
  const [manualScore, setManualScore] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [thread, setThread] = useState(null);
  const [message, setMessage] = useState("");
  const answer = useMemo(() => responseText(selectedRunItem?.response), [selectedRunItem]);

  useEffect(() => {
    apiFetch?.("/api/review-settings").then((data) => setReviewer(data.reviewer_name || "")).catch(() => {});
    setThread(null);
  }, [apiFetch, selectedRunItem?.question_id]);

  async function submitManualReview(event) {
    event.preventDefault();
    if (!selectedRunItem || !reviewer.trim() || manualScore === "") return;
    setReviewBusy(true);
    try {
      await apiFetch(`/api/runs/${selectedRunId}/items/${selectedRunItem.question_id}/manual-review`, {
        method: "POST",
        body: JSON.stringify({ reviewer: reviewer.trim(), score: Number(manualScore), note: reviewNote, confirmed: true }),
      });
      await onRefreshRun(selectedRunId);
      setReviewNote("");
    } finally {
      setReviewBusy(false);
    }
  }

  async function retryJudge() {
    if (!selectedRunItem) return;
    setReviewBusy(true);
    try {
      await apiFetch(`/api/runs/${selectedRunId}/items/${selectedRunItem.question_id}/judge`, { method: "POST", body: "{}" });
      await onRefreshRun(selectedRunId);
    } finally {
      setReviewBusy(false);
    }
  }

  async function startThread() {
    const created = await apiFetch(`/api/runs/${selectedRunId}/items/${selectedRunItem.question_id}/review-threads`, { method: "POST", body: "{}" });
    setThread(created);
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!message.trim() || !thread) return;
    const updated = await apiFetch(`/api/review-threads/${thread.thread_id}/messages`, {
      method: "POST", body: JSON.stringify({ content: message.trim() }),
    });
    setThread(updated);
    setMessage("");
  }

  return (
    <section className="panel">
      <SectionTitle title="逐题回答与评分" meta={`当前页 ${runItems.length} / 总计 ${runItemsTotal}`} />
      <div className="filters-row">
        <label>模块<select value={itemFilters.module} onChange={(event) => setItemFilters((prev) => ({ ...prev, module: event.target.value }))}><option value="">全部</option>{moduleOptions.map((module) => <option key={module.code || module} value={module.code || module}>{module.code || module} · {module.display_name || module}</option>)}</select></label>
        <label>状态<select value={itemFilters.status} onChange={(event) => setItemFilters((prev) => ({ ...prev, status: event.target.value }))}><option value="">全部</option><option value="ok">ok</option><option value="failed">failed</option></select></label>
        <label>题号<input value={itemFilters.question_id} onChange={(event) => setItemFilters((prev) => ({ ...prev, question_id: event.target.value }))} placeholder="A1-001" /></label>
        <label className="filter-search">关键词<input value={itemFilters.search} onChange={(event) => setItemFilters((prev) => ({ ...prev, search: event.target.value }))} placeholder="题面 / 回答 / 失败原因" /></label>
        <label className="checkbox-label"><input type="checkbox" checked={itemFilters.canonical_only} onChange={(event) => setItemFilters((prev) => ({ ...prev, canonical_only: event.target.checked }))} />Canonical</label>
        <div className="inline-actions"><button className="action-button secondary" type="button" onClick={() => onRefreshRun(selectedRunId)}>刷新</button><button className="action-button secondary" type="button" onClick={() => setView("history")}>返回历史 Runs</button></div>
      </div>
      <PaginationBar page={itemPage} pageSize={itemPageSize} total={runItemsTotal} onPageChange={setItemPage} onPageSizeChange={(size) => { setItemPageSize(size); setItemPage(1); }} />
      <div className="items-layout">
        <div className="items-list">
          {loadingRunItems ? <div className="muted-text">正在加载逐题结果…</div> : null}
          {!loadingRunItems && !runItems.length ? <EmptyState title="当前筛选下没有结果" description="清空筛选条件或从历史 Runs 选择一个评测。" /> : (
            <div className="table-shell"><table className="data-table"><thead><tr><th>版本 / 题号</th><th>模块 / 类型</th><th>回答预览</th><th>规则</th><th>裁判</th><th>人工</th><th>有效分</th><th>复核</th></tr></thead><tbody>
              {runItems.map((item) => <tr key={`${item.question_id}-${item.attempt_run_id}`} className={selectedRunItem?.question_id === item.question_id ? "row-active" : ""} onClick={() => onSelectQuestion(item.question_id)}>
                <td><span className="mono">{item.bank_version}</span><br /><span className="mono">{item.question_id}</span></td>
                <td>{item.module}<br />{item.bank_item?.subtype || "-"}</td><td>{briefText(responseText(item.response), 110)}</td>
                <td>{formatValue(item.rule_score)}</td><td>{formatValue(item.judge_score)}</td><td>{formatValue(item.manual_score)}</td><td><strong>{formatValue(item.effective_score)}</strong><br />{item.score_source}</td>
                <td><span className={`status-pill ${item.review_status === "pending" ? "status-pill-warn" : "status-pill-ok"}`}>{item.review_status}</span></td>
              </tr>)}
            </tbody></table></div>
          )}
        </div>
        <aside className="detail-card run-answer-detail">
          {!selectedRunItem ? <EmptyState title="选择一道题查看完整回答" description="这里会展示题目快照、模型原始回答和所有评分来源。" /> : <>
            <h3>{selectedRunItem.bank_version} · {selectedRunItem.question_id}</h3>
            <div className="detail-section"><h4>题目</h4><pre className="detail-pre">{selectedRunItem.bank_item?.prompt_template || JSON.stringify(selectedRunItem.bank_item?.turn_script, null, 2)}</pre></div>
            <div className="detail-section"><h4>模型回答</h4><pre className="detail-pre response-body">{answer || "（空回答）"}</pre><details><summary>原始响应</summary><pre className="detail-pre">{JSON.stringify(selectedRunItem.response?.raw ?? selectedRunItem.response, null, 2)}</pre></details></div>
            <AnswerBasis item={selectedRunItem} />
            <div className="detail-section"><h4>评分明细</h4><p>规则分 {formatValue(selectedRunItem.rule_score)} · 裁判分 {formatValue(selectedRunItem.judge_score)} · 人工分 {formatValue(selectedRunItem.manual_score)} · 有效分 {formatValue(selectedRunItem.effective_score)}（{selectedRunItem.score_source}）</p><pre className="detail-pre">{JSON.stringify(selectedRunItem.judge_assessment || selectedRunItem.score_details, null, 2)}</pre><button type="button" className="action-button secondary" disabled={reviewBusy || selectedRunItem.review_policy?.mode !== "judge"} onClick={retryJudge}>重新裁判</button></div>
            <form className="detail-section form-stack" onSubmit={submitManualReview}><h4>人工复核</h4><label>Reviewer<input required value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label><label>分数（0～1）<input type="number" min="0" max="1" step="0.01" required value={manualScore} onChange={(event) => setManualScore(event.target.value)} /></label><label>备注<textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} /></label><button className="action-button" disabled={reviewBusy}>确认人工分</button></form>
            <div className="detail-section"><h4>独立后续对话</h4>{!thread ? <button className="action-button secondary" type="button" onClick={startThread}>基于本次回答继续对话</button> : <><div className="review-chat">{thread.messages.map((entry) => <div key={entry.id} className={`review-message ${entry.role}`}><strong>{entry.role}</strong><div>{entry.content}</div></div>)}</div><form className="inline-form" onSubmit={sendMessage}><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="继续追问（不会修改正式 Run）" /><button className="action-button">发送</button></form></>}</div>
          </>}
        </aside>
      </div>
    </section>
  );
}
