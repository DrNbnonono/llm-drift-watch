import React from "react";

/**
 * Independent Run Report detail view. Used as the destination of
 * "list row click → 详情页" navigation in Phase 5. State continues
 * to live in App.jsx for now; this component is a presentational
 * extraction that removes the deeply nested JSX from App.jsx.
 */
export default function RunReportPage({
  report,
  reportCandidates,
  activeReportRunId,
  reportSummaryMetrics,
  loadingReport,
  systemPaths,
  apiFetch,
  onBack,
  onPreviewReport,
  helpers: { SectionTitle, PathList, ScoreCard, ReportCharts, MarkdownPreview, formatValue, RunArtifactStatus, EmptyState },
}) {
  return (
    <section className="panel report-page">
      <div className="report-page-header">
        <button type="button" className="action-button secondary compact-action" onClick={onBack}>
          ← 返回历史 Runs
        </button>
        <SectionTitle title="报告预览" meta={report?.run_id || "选择一个已完成 run"} />
      </div>
      <PathList title="报告目录" paths={{ reports_root: systemPaths?.reports_root }} />
      <div className="report-page-layout">
        <div className="detail-card report-browser-card">
          <SectionTitle title="可预览报告" meta={`${reportCandidates.length} 个已完成 run`} />
          <div className="config-list report-run-list">
            {reportCandidates.slice(0, 24).map((run) => (
              <button
                key={run.run_id}
                type="button"
                className={(report?.run_id === run.run_id || activeReportRunId === run.run_id) ? "config-row report-run-row active" : "config-row report-run-row"}
                onClick={() => onPreviewReport(run.run_id, { generateIfMissing: !run.report_ready })}
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
            />
          )}
        </div>
      </div>
    </section>
  );
}
