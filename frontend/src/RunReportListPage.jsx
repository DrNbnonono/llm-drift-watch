import React, { useMemo, useState } from "react";

import { sortAndFilterReports } from "./reportRouting.js";

const PAGE_SIZES = [10, 20, 50, 100];

function displayScore(run) {
  const metrics = run.summary_metrics || run.summary?.summary_metrics || {};
  const value = metrics.overall_macro_score;
  return value === null || value === undefined ? "-" : Number(value).toFixed(3);
}

export default function RunReportListPage({ runs, loading, onOpenReport, helpers: { SectionTitle, PaginationBar, RunArtifactStatus, EmptyState } }) {
  const [filters, setFilters] = useState({ keyword: "", model: "", status: "", reportStatus: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const modelOptions = useMemo(
    () => [...new Set((runs || []).map((run) => run.model_name || run.model_alias).filter(Boolean))].sort(),
    [runs],
  );
  const filtered = useMemo(() => sortAndFilterReports(runs, filters), [runs, filters]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const rows = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  function updateFilter(name, value) {
    setFilters((previous) => ({ ...previous, [name]: value }));
    setPage(1);
  }

  return (
    <section className="panel report-list-page">
      <SectionTitle title="报告" meta={`${filtered.length} / ${(runs || []).length} 个可用 Run`} />
      <div className="filter-grid report-list-filters">
        <label>搜索<input value={filters.keyword} onChange={(event) => updateFilter("keyword", event.target.value)} placeholder="Run ID、模型或题库版本" /></label>
        <label>模型<select value={filters.model} onChange={(event) => updateFilter("model", event.target.value)}><option value="">全部</option>{modelOptions.map((model) => <option key={model} value={model}>{model}</option>)}</select></label>
        <label>运行状态<select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}><option value="">全部</option><option value="completed">已完成</option><option value="running">运行中</option><option value="failed">失败</option></select></label>
        <label>报告状态<select value={filters.reportStatus} onChange={(event) => updateFilter("reportStatus", event.target.value)}><option value="">全部</option><option value="ready">已就绪</option><option value="missing">未生成</option></select></label>
      </div>
      {loading ? <div className="muted-text">正在加载报告列表…</div> : null}
      {!loading && rows.length === 0 ? <EmptyState title="没有匹配的报告" description="调整筛选条件，或先完成一次评测运行。" /> : null}
      {rows.length ? (
        <div className="table-wrap report-list-table-wrap">
          <table className="data-table report-list-table">
            <thead><tr><th>Run ID</th><th>模型</th><th>题库版本</th><th>完成时间</th><th>执行状态</th><th>报告</th><th>Canonical</th><th>Overall</th></tr></thead>
            <tbody>{rows.map((run) => (
              <tr key={run.run_id} className="report-list-row" tabIndex={0} onClick={() => onOpenReport(run)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onOpenReport(run); }}>
                <td className="mono">{run.run_id}</td><td>{run.model_name || run.model_alias || "-"}</td><td>{run.bank_version || "-"}</td><td>{run.finished_at || run.started_at || "-"}</td><td>{run.execution_status || run.status || "-"}</td>
                <td><RunArtifactStatus ready={run.report_ready} label="报告" /></td><td><RunArtifactStatus ready={run.canonical_ready} label="Canonical" /></td><td>{displayScore(run)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : null}
      <PaginationBar page={currentPage} pageSize={pageSize} total={filtered.length} onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} pageSizeOptions={PAGE_SIZES} />
    </section>
  );
}
