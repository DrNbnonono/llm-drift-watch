export function parseRunHash(hash = "") {
  const value = String(hash);
  if (/^#\/history\/?$/.test(value)) return { kind: "history", runId: null, questionId: null, scope: null };
  const match = value.match(/^#\/runs\/([^/?#]+)\/items(?:\/([^?#]+))?(?:\?([^#]*))?$/);
  if (!match) return { kind: "other", runId: null, questionId: null, scope: null };
  try {
    const params = new URLSearchParams(match[3] || "");
    const scope = params.get("scope");
    return {
      kind: match[2] ? "item" : "items",
      runId: decodeURIComponent(match[1]),
      questionId: match[2] ? decodeURIComponent(match[2]) : null,
      scope: scope === "canonical" || scope === "attempt" ? scope : null,
    };
  } catch {
    return { kind: "other", runId: null, questionId: null, scope: null };
  }
}

export function defaultRunScope(run) {
  return (run?.run_kind || "base") === "retry" ? "attempt" : "canonical";
}

export function historyHash() {
  return "#/history";
}

export function runItemsHash(runId, scope = "canonical", questionId = null) {
  const suffix = questionId ? `/${encodeURIComponent(questionId)}` : "";
  return `#/runs/${encodeURIComponent(runId)}/items${suffix}?scope=${scope === "attempt" ? "attempt" : "canonical"}`;
}
