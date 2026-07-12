export function parseReportHash(hash = "") {
  const match = String(hash).match(/^#\/reports(?:\/([^/?#]+))?\/?$/);
  if (!match) return { kind: "other", runId: null };
  if (!match[1]) return { kind: "list", runId: null };
  try {
    return { kind: "detail", runId: decodeURIComponent(match[1]) };
  } catch {
    return { kind: "other", runId: null };
  }
}

export function reportListHash() {
  return "#/reports";
}

export function reportDetailHash(runId) {
  return `#/reports/${encodeURIComponent(runId)}`;
}

export function sortAndFilterReports(runs, filters = {}) {
  const keyword = String(filters.keyword || "").trim().toLowerCase();
  const model = String(filters.model || "");
  const status = String(filters.status || "");
  const reportStatus = String(filters.reportStatus || "");
  return [...(runs || [])]
    .filter((run) => {
      const modelName = run.model_name || run.model_alias || "";
      const haystack = [run.run_id, modelName, run.bank_version, run.connection_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (keyword && !haystack.includes(keyword)) return false;
      if (model && modelName !== model) return false;
      if (status && (run.execution_status || run.status) !== status) return false;
      if (reportStatus === "ready" && !run.report_ready) return false;
      if (reportStatus === "missing" && run.report_ready) return false;
      return true;
    })
    .sort((a, b) => String(b.finished_at || b.started_at || "").localeCompare(String(a.finished_at || a.started_at || "")));
}
