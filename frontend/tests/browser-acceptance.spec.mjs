import { expect, test } from "playwright/test";

test("versioned bank and run creation controls are visible", async ({ page }) => {
  await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
  const versionSelect = page.getByLabel("题库版本（必选）");
  await expect(versionSelect).toHaveValue("QB-v1.3");
  await expect(versionSelect.locator("option")).toHaveCount(5);

  await page.getByRole("button", { name: "题库管理" }).click();
  await expect(page.getByText(/当前命中 20 \/ 627/)).toBeVisible();
  await page.getByRole("button", { name: /QB-v1\.0/ }).click();
  await expect(page.getByText(/当前命中 20 \/ 567/)).toBeVisible();
  const activeVersion = page.getByRole("button", { name: /QB-v1\.0/ });
  await expect(activeVersion).toContainText("QB-v1.0");
  const color = await activeVersion.evaluate((node) => getComputedStyle(node).color);
  expect(color).toMatch(/^rgb\((?:[0-9]|1[0-9]), (?:[0-9]|1[0-9]), (?:[0-9]|1[0-9])\)$/);
  await page.screenshot({ path: "output/versioned-bank-final.png", fullPage: true });
});

test("per-question answer and manual review entry are visible", async ({ page }) => {
  await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "逐题结果" }).click();
  await expect(page.getByText("逐题回答与评分")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "规则" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "裁判" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "人工" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "有效分" })).toBeVisible();
  const firstRow = page.locator(".data-table tbody tr").first();
  if (await firstRow.count()) await firstRow.click();
  await expect(page.getByText("参考答案与评分依据")).toBeVisible();
  await expect(page.getByText("人工复核").last()).toBeVisible();
  await page.screenshot({ path: "output/run-answer-final.png", fullPage: true });
});
