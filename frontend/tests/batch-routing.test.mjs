import assert from "node:assert/strict";
import test from "node:test";
import { batchDetailHash, parseBatchHash } from "../src/batchRouting.js";

test("batch detail hash preserves encoded batch ids", () => {
  const hash = batchDetailHash("batch/a");
  assert.equal(hash, "#/batches/batch%2Fa");
  assert.deepEqual(parseBatchHash(hash), { kind: "detail", batchId: "batch/a" });
  assert.equal(parseBatchHash("#/history").kind, "other");
});
