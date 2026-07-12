import assert from "node:assert/strict";
import test from "node:test";
import { formatEstimatedCost, placeTrafficTooltip, trafficLightMeta } from "../src/evaluationMonitor.js";

test("traffic light states have accessible labels and stable classes", () => {
  assert.deepEqual(trafficLightMeta("correct"), { className: "traffic-correct", label: "答对", symbol: "✓" });
  assert.equal(trafficLightMeta("incorrect").className, "traffic-incorrect");
  assert.equal(trafficLightMeta("pending_score").label, "等待评分");
  assert.equal(trafficLightMeta("failed").symbol, "×");
  assert.equal(trafficLightMeta("unprocessed").label, "未处理");
});

test("unknown estimated cost is never formatted as zero", () => {
  assert.equal(formatEstimatedCost(null), "未知");
  assert.equal(formatEstimatedCost({ amount: null, complete: false }), "未知/不完整");
  assert.equal(formatEstimatedCost({ amount: 0.0012, currency: "USD", complete: true }), "$0.001200");
});

test("tooltip opens below a cell when there is not enough room above", () => {
  assert.deepEqual(
    placeTrafficTooltip({ top: 12, bottom: 32, left: 500, width: 20 }, { width: 1200, height: 800 }, { width: 336, height: 180 }),
    { left: 342, top: 42, placement: "below" },
  );
});

test("tooltip stays inside the right edge of the viewport", () => {
  const position = placeTrafficTooltip(
    { top: 500, bottom: 520, left: 1180, width: 20 },
    { width: 1200, height: 800 },
    { width: 336, height: 180 },
  );
  assert.deepEqual(position, { left: 848, top: 310, placement: "above" });
});
