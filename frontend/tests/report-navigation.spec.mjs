import { expect, test } from "playwright/test";

const BASE_URL = "http://127.0.0.1:5173";

for (const viewport of [
  { name: "desktop", width: 1440, height: 960 },
  { name: "compact", width: 1024, height: 900 },
  { name: "tablet", width: 768, height: 900 },
]) {
  test(`report list and deep-linked detail fit ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`${BASE_URL}/#/reports`, { waitUntil: "networkidle" });
    await expect(page.locator(".report-list-table")).toBeVisible();
    await expect(page.locator(".report-browser-card")).toHaveCount(0);

    const firstRow = page.locator(".report-list-row").first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();
    await expect(page).toHaveURL(/#\/reports\/[^/]+$/);
    await expect(page.getByRole("button", { name: /返回报告列表/ })).toBeVisible();
    await expect(page.locator(".report-browser-card")).toHaveCount(0);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator(".report-detail-page")).toBeVisible();

    const dimensions = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }));
    expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport + 1);
    await page.screenshot({ path: `output/report-detail-${viewport.name}.png`, fullPage: true });
  });
}
