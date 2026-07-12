import React from "react";
import { formatEstimatedCost, formatTokens } from "./evaluationMonitor.js";

export default function RunReportPage({
  report,
  reportSummaryMetrics,
  loadingReport,
  onBack,
  onViewItems,
  helpers: { SectionTitle, ScoreCard, ReportCharts, MarkdownPreview, formatValue, EmptyState },
}) {
  return (
    <section className="panel report-page report-detail-page">
      <div className="report-page-header">
        <button type="button" className="action-button secondary compact-action" onClick={onBack}>
          ← 返回报告列表
        </button>
        {report?.run_id ? <button type="button" className="action-button compact-action" onClick={() => onViewItems(report.run_id)}>查看 Canonical 逐题结果</button> : null}
        <SectionTitle title="报告详情" meta={report?.run_id || "正在加载报告"} />
      </div>
      {loadingReport ? <div className="muted-text">正在生成或读取报告…</div> : null}
      {report ? (
        <div className="stack-sections report-detail-content">
          <div className="report-hero-surface">
            <div className="report-score-grid">
              <ScoreCard title="Capability" value={formatValue(reportSummaryMetrics.capability_score ?? 0)} tone="warm" />
              <ScoreCard title="Safety" value={formatValue(reportSummaryMetrics.safety_composite_score ?? 0)} tone="neutral" />
              <ScoreCard title="Probe" value={formatValue(reportSummaryMetrics.probe_score ?? 0)} tone="cool" />
              <ScoreCard title="Overall" value={formatValue(reportSummaryMetrics.overall_macro_score ?? 0)} tone="neutral" />
            </div>
            <div className="meta-row report-meta-row"><span>Run: {report.run_id}</span><span>Path: {report.report_path}</span></div>
            <div className="monitor-stat-grid report-billing-grid"><div className="monitor-stat"><span>回答 Token</span><strong>{formatTokens(report.billing?.answer?.token_usage)}</strong></div><div className="monitor-stat"><span>回答费用</span><strong>{formatEstimatedCost(report.billing?.answer?.estimated_cost)}</strong></div><div className="monitor-stat"><span>Judge Token</span><strong>{formatTokens(report.billing?.judge?.token_usage)}</strong></div><div className="monitor-stat"><span>Judge 费用</span><strong>{formatEstimatedCost(report.billing?.judge?.estimated_cost)}</strong></div></div>
          </div>
          <div className="report-preview-grid report-detail-grid">
            <div className="detail-card report-chart-stage"><SectionTitle title="结构化图表" meta="默认展示 canonical 汇总口径" /><ReportCharts reportData={report} /></div>
            <div className="detail-card report-preview-card"><SectionTitle title="文档预览" meta="Markdown 实时预览" /><MarkdownPreview content={report.content} /></div>
          </div>
          <details className="report-raw-block"><summary>查看原始 Markdown 报告</summary><pre className="report-view">{report.content}</pre></details>
        </div>
      ) : !loadingReport ? <EmptyState title="报告不可用" description="该 Run 的报告不存在或加载失败，请返回列表重试。" /> : null}
    </section>
  );
}
