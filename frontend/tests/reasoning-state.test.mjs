import assert from "node:assert/strict";
import test from "node:test";
import { reasoningState } from "../src/responsePresentation.js";

test("reasoning states distinguish legacy, unavailable and available", () => {
  assert.equal(reasoningState({ text: "old" }), "legacy");
  assert.equal(reasoningState({ text: "new", reasoning_available: false }), "unavailable");
  assert.equal(reasoningState({ text: "new", reasoning_available: true, reasoning: "why" }), "available");
});
