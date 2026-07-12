import assert from "node:assert/strict";
import test from "node:test";
import { defaultRunScope, historyHash, parseRunHash, runItemsHash } from "../src/runRouting.js";

test("history and run item hashes round trip", () => {
  assert.equal(historyHash(), "#/history");
  assert.deepEqual(parseRunHash("#/history"), { kind: "history", runId: null, questionId: null, scope: null });
  assert.deepEqual(parseRunHash(runItemsHash("root/a", "canonical", "C2/001")), {
    kind: "item", runId: "root/a", questionId: "C2/001", scope: "canonical",
  });
});

test("scope defaults differ for base and retry", () => {
  assert.equal(defaultRunScope({ run_kind: "base" }), "canonical");
  assert.equal(defaultRunScope({ run_kind: "retry" }), "attempt");
  assert.equal(parseRunHash("#/runs/r/items").scope, null);
});
