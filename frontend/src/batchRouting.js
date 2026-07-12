export function parseBatchHash(hash = "") {
  const match = String(hash).match(/^#\/batches\/([^/?#]+)\/?$/);
  if (!match) return { kind: "other", batchId: null };
  try { return { kind: "detail", batchId: decodeURIComponent(match[1]) }; }
  catch { return { kind: "other", batchId: null }; }
}

export function batchDetailHash(batchId) {
  return `#/batches/${encodeURIComponent(batchId)}`;
}
