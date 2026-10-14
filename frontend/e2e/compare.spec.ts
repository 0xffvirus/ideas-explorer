import { expect, test } from "@playwright/test";

const DOG_ID = "00000000-0000-4000-8000-000000000001";
const INVOICE_ID = "00000000-0000-4000-8000-000000000002";

test("multi-select in the library opens a side-by-side comparison", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();

  const checkboxes = page.getByTestId("idea-select");
  await checkboxes.nth(0).click();
  await checkboxes.nth(1).click();

  const bar = page.getByTestId("selection-bar");
  await expect(bar).toBeVisible();
  await expect(bar).toContainText("2 selected");

  await bar.getByRole("button", { name: "Compare" }).click();
  await page.waitForURL(/\/compare\?ids=/);
  const compare = page.getByTestId("compare-screen");
  await expect(compare.getByRole("heading", { name: "Compare", level: 1 })).toBeVisible();
  await expect(compare.getByText("2 ideas side by side")).toBeVisible();
  await expect(compare.getByText("Overall score", { exact: true })).toBeVisible();
  await expect(compare.getByText("Verdict", { exact: true })).toBeVisible();
});

test("compare rejects selections that are too small", async ({ page }) => {
  await page.goto(`/compare?ids=${DOG_ID}`);
  await expect(page.getByText(/Pick two or three ideas/i)).toBeVisible();
});

test("compare renders three reports with aligned score rows", async ({ page }) => {
  await page.goto(`/compare?ids=${DOG_ID},${INVOICE_ID}`);
  const compare = page.getByTestId("compare-screen");
  await expect(compare.getByText("Overall score", { exact: true })).toBeVisible();
  await expect(compare.getByText("TAM", { exact: true })).toBeVisible();
  await expect(compare.getByText("MVP cost", { exact: true })).toBeVisible();
});
