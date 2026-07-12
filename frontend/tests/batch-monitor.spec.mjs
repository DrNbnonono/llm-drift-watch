import { expect, test } from "playwright/test";

const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const BATCH = "batch-20260712T070754Z-5eda591a";

test("batch history opens a two-model traffic-light matrix", async ({ page }) => {
  await page.goto(`${BASE}/#/history`, { waitUntil: "domcontentloaded" });
  const batchRow = page.getByRole("button", { name: new RegExp(BATCH) });
  await expect(batchRow).toBeVisible({ timeout: 15000 });
  await batchRow.click();
  await expect(page.locator(".traffic-matrix")).toBeVisible({ timeout: 30000 });
  await expect(page.locator(".traffic-matrix tbody tr")).toHaveCount(2);
  await expect(page.locator(".traffic-cell")).toHaveCount(4);
  await page.locator(".traffic-cell").first().hover();
  const tooltip = page.locator(".traffic-tooltip-overlay");
  await expect(tooltip).toBeVisible();
  const bounds = await tooltip.boundingBox();
  const viewport = page.viewportSize();
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height);
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width);
});

test("manual review is submitted from item detail and changes the grid state", async ({ page, request }) => {
  const before = await (await request.get(`${API}/api/evaluation-batches/${BATCH}/progress-grid`)).json();
  const targetModel = before.models.find((model) => model.cells.some((cell) => cell.state === "incorrect"));
  if (!targetModel) {
    const reviewed = before.models.flatMap((model) => model.cells).find((cell) => cell.score_source === "manual");
    expect(reviewed?.state).toBe("correct");
    return;
  }
  const target = targetModel.cells.find((cell) => cell.state === "incorrect");
  await page.goto(`${BASE}/#/runs/${targetModel.run_id}/items/${target.question_id}?scope=attempt`, { waitUntil: "domcontentloaded" });
  const form = page.locator(".manual-review-card");
  await expect(form).toBeVisible({ timeout: 30000 });
  await form.locator("input").nth(0).fill("Playwright Reviewer");
  await form.locator("input").nth(1).fill("1");
  await form.locator("textarea").fill("人工核对后确认答案完全符合标准答案与评分约束。");
  await form.getByRole("button", { name: "提交人工评分" }).click();
  await expect(page.getByText(/人工分 1/)).toBeVisible({ timeout: 30000 });
  const after = await (await request.get(`${API}/api/evaluation-batches/${BATCH}/progress-grid`)).json();
  const reviewed = after.models.find((model) => model.run_id === targetModel.run_id).cells.find((cell) => cell.question_id === target.question_id);
  expect(reviewed.state).toBe("correct");
  expect(reviewed.score_source).toBe("manual");
});

for (const width of [768, 1024, 1440]) {
  test(`traffic matrix remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${BASE}/#/history`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: new RegExp(BATCH) }).click();
    await expect(page.locator(".traffic-matrix-shell")).toBeVisible({ timeout: 30000 });
    const overflow = await page.locator(".traffic-matrix-shell").evaluate((element) => ({ scroll: element.scrollWidth, client: element.clientWidth }));
    expect(overflow.scroll).toBeGreaterThanOrEqual(overflow.client);
    const body = await page.evaluate(() => ({ scroll: document.body.scrollWidth, client: innerWidth }));
    expect(body.scroll).toBeLessThanOrEqual(body.client + 1);
  });
}
