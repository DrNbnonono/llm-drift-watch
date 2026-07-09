import React from "react";

/**
 * Independent per-question results page. Phase 5 destination of
 * "list row click → 详情页". Renders the per-run item-level table
 * with the existing filter / pagination / detail card.
 */
export default function RunItemsPage({
  runItems,
  runItemsTotal,
  loadingRunItems,
  itemFilters,
  setItemFilters,
  itemPage,
  itemPageSize,
  setItemPage,
  setItemPageSize,
  selectedRunId,
  selectedRunItem,
  moduleOptions = [],
  helpers: { SectionTitle, PaginationBar, EmptyState, DetailCard, briefText, formatValue, setView },
  onRefreshRun,
  onSelectQuestion,
}) {
  return (
    <section className="panel">
      <SectionTitle title="逐题结果" meta={`当前页 ${runItems.length} / 总计 ${runItemsTotal}`} />
      <div className="filters-row">
        <label>
          模块
          <select value={itemFilters.module} onChange={(event) => setItemFilters((prev) => ({ ...prev, module: event.target.value }))}>
            <option value="">全部</option>
            {moduleOptions.map((module) => <option key={module.code || module} value={module.code || module}>{module.code || module}</option>)}
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
          <button className="action-button secondary" type="button" onClick={() => selectedRunId && onRefreshRun(selectedRunId)}>刷新结果</button>
          <button className="action-button secondary" type="button" onClick={() => setView("timeline")} disabled={!selectedRunItem}>查看时间线</button>
          <button className="action-button secondary" type="button" onClick={() => setView("history")}>返回历史 Runs</button>
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
                      onClick={() => onSelectQuestion(item.question_id)}
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
        <DetailCard title="题目详情" item={selectedRunItem} timelineData={null} />
      </div>
    </section>
  );
}
