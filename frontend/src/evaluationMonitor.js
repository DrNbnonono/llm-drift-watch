const STATES = {
  correct: { className: "traffic-correct", label: "答对", symbol: "✓" },
  incorrect: { className: "traffic-incorrect", label: "未满分", symbol: "!" },
  pending_score: { className: "traffic-pending", label: "等待评分", symbol: "…" },
  failed: { className: "traffic-failed", label: "调用失败", symbol: "×" },
  unprocessed: { className: "traffic-unprocessed", label: "未处理", symbol: "○" },
};

export function trafficLightMeta(state) {
  return STATES[state] || STATES.unprocessed;
}

export function formatEstimatedCost(cost) {
  if (!cost) return "未知";
  if (cost.amount === null || cost.amount === undefined) return "未知/不完整";
  const prefix = cost.currency === "USD" || !cost.currency ? "$" : `${cost.currency} `;
  return `${prefix}${Number(cost.amount).toFixed(6)}`;
}

export function formatTokens(usage) {
  if (!usage) return "未知";
  return Number(usage.total_tokens || 0).toLocaleString();
}

export function placeTrafficTooltip(anchor, viewport, tooltip = { width: 336, height: 180 }) {
  const gap = 10;
  const margin = 16;
  const width = Math.min(tooltip.width, Math.max(viewport.width - margin * 2, 0));
  const centeredLeft = anchor.left + anchor.width / 2 - width / 2;
  const left = Math.round(Math.min(Math.max(centeredLeft, margin), viewport.width - width - margin));
  const opensAbove = anchor.top - gap - tooltip.height >= margin;
  const preferredTop = opensAbove ? anchor.top - gap - tooltip.height : anchor.bottom + gap;
  const top = Math.round(Math.min(Math.max(preferredTop, margin), viewport.height - tooltip.height - margin));
  return { left, top, placement: opensAbove ? "above" : "below" };
}
