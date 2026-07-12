import { expect, test } from "playwright/test";
test.setTimeout(90000);

const BASE = "http://127.0.0.1:5173";
const ROOT = "20260711T063214Z-5ef648f0";
const RETRY = "20260711T114103Z-1973ec30";

test("history refreshes and exposes explicit item/report actions", async ({ page }) => {
  await page.goto(`${BASE}/#/history`, { waitUntil: "networkidle" });
  await expect(page.locator(".history-panel")).toBeVisible();
  await expect(page.locator(".history-toolbar button").first()).toBeVisible();
  await expect(page.locator(".history-table tbody tr").first()).toBeVisible();
  await expect(page.locator(".history-row-actions button").first()).toBeVisible();
});

test("canonical and attempt deep links retain run, scope and question", async ({ page }) => {
  await page.goto(`${BASE}/#/runs/${ROOT}/items?scope=canonical`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Canonical · 1110 条", { exact: false })).toBeVisible({ timeout: 60000 });
  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/items\/[^?]+\?scope=canonical$/);
  const url = page.url();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(url);
  await expect(page.locator(".reasoning-panel")).toBeVisible({ timeout: 60000 });
  await page.locator(".reasoning-panel").click();
  await expect(page.getByText("该 Run 创建时未采集思考过程。")).toBeVisible();

  await page.goto(`${BASE}/#/runs/${RETRY}/items?scope=attempt`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Attempt · 73 条", { exact: false })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "查看 Root Canonical" })).toBeVisible();
});

for (const width of [768, 1024, 1440]) {
  test(`item detail has no horizontal page overflow at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${BASE}/#/runs/20260712T014956Z-4dc1e30f/items/C2-001?scope=attempt`, { waitUntil: "networkidle" });
    await page.locator(".reasoning-panel").click();
    await expect(page.getByText("Provider 未返回思考内容。")).toBeVisible({ timeout: 15000 });
    const size = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: innerWidth }));
    expect(size.body).toBeLessThanOrEqual(size.viewport + 1);
  });
}
