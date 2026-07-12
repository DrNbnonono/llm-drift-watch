import React, { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { formatEstimatedCost, formatTokens, placeTrafficTooltip, trafficLightMeta } from "./evaluationMonitor.js";

function Stat({ label, value, detail }) {
  return <div className="monitor-stat"><span>{label}</span><strong>{value}</strong>{detail ? <small>{detail}</small> : null}</div>;
}

export default function EvaluationMonitor({ grid, loading, onRefresh, onOpenItem, onGenerateReport }) {
  const [moduleFilter, setModuleFilter] = useState("");
  const [onlyIncorrect, setOnlyIncorrect] = useState(false);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [sortKey, setSortKey] = useState("configured");
  const [activeTooltip, setActiveTooltip] = useState(null);
  const models = grid?.models || (grid?.run_id ? [grid] : []);
  const displayedModels = useMemo(() => [...models].sort((a, b) => {
    if (sortKey === "accuracy") return Number(b.summary?.accuracy ?? -1) - Number(a.summary?.accuracy ?? -1);
    if (sortKey === "tokens") return Number(b.summary?.token_usage?.total_tokens || 0) - Number(a.summary?.token_usage?.total_tokens || 0);
    if (sortKey === "cost") return Number(b.summary?.estimated_cost?.amount ?? -1) - Number(a.summary?.estimated_cost?.amount ?? -1);
    return 0;
  }), [models, sortKey]);
  const modules = useMemo(() => [...new Set(models.flatMap((model) => model.cells?.map((cell) => cell.module) || []))], [models]);
  const totals = useMemo(() => models.reduce((acc, model) => {
    const summary = model.summary || {};
    for (const key of ["total", "processed", "correct", "incorrect", "failed", "pending_score"]) acc[key] += Number(summary[key] || 0);
    return acc;
  }, { total: 0, processed: 0, correct: 0, incorrect: 0, failed: 0, pending_score: 0 }), [models]);
  const billing = grid?.billing_summary || (models.length === 1 ? models[0].summary : null) || {};
  const scored = totals.correct + totals.incorrect;

  useEffect(() => {
    const closeTooltip = () => setActiveTooltip(null);
    window.addEventListener("resize", closeTooltip);
    return () => {
      window.removeEventListener("resize", closeTooltip);
    };
  }, []);

  const showTooltip = (event, cell, meta) => {
    const anchor = event.currentTarget.getBoundingClientRect();
    const position = placeTrafficTooltip(anchor, { width: window.innerWidth, height: window.innerHeight });
    setActiveTooltip({ cell, meta, position });
  };

  return <><section className="panel evaluation-monitor">
    <div className="monitor-heading"><div><h2>测评进度红绿灯</h2><p>绿色满分、红色未满分、琥珀描边等待评分、黑色调用失败、灰色未处理。</p></div><div className="inline-actions">{grid?.batch_id ? <button className="action-button" onClick={() => onGenerateReport?.(grid.batch_id)}>生成批次报告</button> : null}<button className="action-button secondary" onClick={onRefresh} disabled={loading}>{loading ? "刷新中…" : "立即刷新"}</button></div></div>
    {grid?.report_path ? <div className="info-banner">批次报告：<code>{grid.report_path}</code></div> : null}
    <div className="monitor-stat-grid"><Stat label="总进度" value={`${totals.processed}/${totals.total}`} /><Stat label="已评分正确率" value={scored ? `${(totals.correct / scored * 100).toFixed(1)}%` : "-"} detail={`${totals.correct}/${scored}`} /><Stat label="失败 / 待评分" value={`${totals.failed} / ${totals.pending_score}`} /><Stat label="Token" value={formatTokens(billing.token_usage)} /><Stat label="估算费用" value={formatEstimatedCost(billing.estimated_cost)} /></div>
    <div className="monitor-filters"><label>模型排序<select value={sortKey} onChange={(event) => setSortKey(event.target.value)}><option value="configured">配置顺序</option><option value="accuracy">正确率</option><option value="tokens">Token</option><option value="cost">费用</option></select></label><label>模块<select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}><option value="">全部</option>{modules.map((module) => <option key={module}>{module}</option>)}</select></label><label>题号<input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="A1-001" /></label><label className="checkbox-label"><input type="checkbox" checked={onlyIncorrect} onChange={(event) => setOnlyIncorrect(event.target.checked)} />仅看未满分</label><label className="checkbox-label"><input type="checkbox" checked={onlyFailed} onChange={(event) => setOnlyFailed(event.target.checked)} />仅看失败</label></div>
    {!models.length ? <div className="muted-text">选择或启动 Run 后显示逐题状态。</div> : <div className="traffic-matrix-shell"><table className="traffic-matrix"><thead><tr><th>模型</th><th>Token</th><th>费用</th>{modules.filter((module) => !moduleFilter || module === moduleFilter).map((module) => <th key={module}>{module}</th>)}</tr></thead><tbody>{displayedModels.map((model) => <tr key={model.run_id}><th><strong>{model.model_name}</strong><small>{model.execution_status}</small></th><td>{formatTokens(model.summary?.token_usage)}</td><td>{formatEstimatedCost(model.summary?.estimated_cost)}</td>{modules.filter((module) => !moduleFilter || module === moduleFilter).map((module) => {
      const cells = (model.cells || []).filter((cell) => cell.module === module && (!keyword || cell.question_id.toLowerCase().includes(keyword.toLowerCase())) && (!onlyIncorrect || cell.state === "incorrect") && (!onlyFailed || cell.state === "failed"));
      return <td key={module}><div className="traffic-cell-group">{cells.map((cell) => { const meta = trafficLightMeta(cell.state); return <button key={cell.question_id} type="button" className={`traffic-cell ${meta.className}`} aria-label={`${cell.question_id} ${meta.label}`} aria-describedby={activeTooltip?.cell === cell ? "traffic-tooltip-overlay" : undefined} onMouseEnter={(event) => showTooltip(event, cell, meta)} onMouseLeave={() => setActiveTooltip(null)} onFocus={(event) => showTooltip(event, cell, meta)} onBlur={() => setActiveTooltip(null)} onClick={() => onOpenItem(model.run_id, cell.question_id)}><span aria-hidden="true">{meta.symbol}</span></button>; })}</div></td>;
    })}</tr>)}</tbody></table></div>}
  </section>{activeTooltip && typeof document !== "undefined" ? createPortal(<div id="traffic-tooltip-overlay" role="tooltip" className={`traffic-tooltip-overlay traffic-tooltip-${activeTooltip.position.placement}`} style={{ left: activeTooltip.position.left, top: activeTooltip.position.top }}><strong>{activeTooltip.cell.question_id} · {activeTooltip.meta.label}</strong><span>{activeTooltip.cell.summary || "无题目摘要"}</span><span>得分：{activeTooltip.cell.effective_score ?? "待定"}（{activeTooltip.cell.score_source || "-"}）</span><span>回答：{formatTokens(activeTooltip.cell.token_usage)} Token · {formatEstimatedCost(activeTooltip.cell.estimated_cost)}</span><span>Judge：{formatTokens(activeTooltip.cell.judge_token_usage)} Token · {formatEstimatedCost(activeTooltip.cell.judge_estimated_cost)}</span><span>耗时：{activeTooltip.cell.latency_ms ?? "-"} ms</span>{activeTooltip.cell.failure_type || activeTooltip.cell.error ? <span>失败：{activeTooltip.cell.failure_type || activeTooltip.cell.error}</span> : null}</div>, document.body) : null}</>;
}
