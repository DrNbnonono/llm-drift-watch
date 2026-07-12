import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  parseReportHash,
  reportDetailHash,
  reportListHash,
  sortAndFilterReports,
} from "../src/reportRouting.js";

test("report hashes support list, detail, and unrelated views", () => {
  assert.deepEqual(parseReportHash("#/reports"), { kind: "list", runId: null });
  assert.deepEqual(parseReportHash("#/reports/run%2Fwith%20spaces"), {
    kind: "detail",
    runId: "run/with spaces",
  });
  assert.deepEqual(parseReportHash("#/bank"), { kind: "other", runId: null });
  assert.equal(reportListHash(), "#/reports");
  assert.equal(reportDetailHash("run/with spaces"), "#/reports/run%2Fwith%20spaces");
});

test("report list filters and sorts newest runs first", () => {
  const runs = [
    { run_id: "old", model_name: "MiniMax-M3", finished_at: "2026-07-10T01:00:00Z", execution_status: "completed", report_ready: true },
    { run_id: "new", model_name: "mock-echo", finished_at: "2026-07-11T01:00:00Z", execution_status: "completed", report_ready: false },
    { run_id: "failed", model_name: "MiniMax-M3", finished_at: "2026-07-12T01:00:00Z", execution_status: "failed", report_ready: false },
  ];

  assert.deepEqual(sortAndFilterReports(runs, { keyword: "minimax", status: "completed", reportStatus: "ready" }).map((run) => run.run_id), ["old"]);
  assert.deepEqual(sortAndFilterReports(runs, {}).map((run) => run.run_id), ["failed", "new", "old"]);
});

test("report list and detail are separate components", async () => {
  const [listSource, detailSource] = await Promise.all([
    readFile(new URL("../src/RunReportListPage.jsx", import.meta.url), "utf8"),
    readFile(new URL("../src/RunReportPage.jsx", import.meta.url), "utf8"),
  ]);

  assert.match(listSource, /<table className="data-table report-list-table">/);
  assert.match(listSource, /Overall/);
  assert.doesNotMatch(detailSource, /reportCandidates|report-browser-card|report-run-list/);
  assert.match(detailSource, /返回报告列表/);
});

test("App wires report list and detail to hash navigation", async () => {
  const source = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");

  assert.match(source, /import RunReportListPage from "\.\/RunReportListPage\.jsx"/);
  assert.match(source, /window\.addEventListener\("hashchange"/);
  assert.match(source, /window\.location\.hash = reportDetailHash\(run\.run_id\)/);
  assert.match(source, /<RunReportListPage/);
  assert.match(source, /view === "runReport"/);
});
