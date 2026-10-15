import { expect, test } from "@playwright/test";

test("streams pipeline progress over SSE into completed rows", async ({ page }) => {
  await page.goto("/ideas/22222222-2222-4222-8222-222222222222");

  await expect(page.getByRole("heading", { level: 1 })).toContainText("AI invoice reconciliation");

  const classifyRow = page.getByRole("listitem").filter({ hasText: "Classify" });
  await expect(classifyRow).toContainText("Done", { timeout: 10_000 });
  await expect(classifyRow).toContainText("$0.010");

  const refineRow = page.getByRole("listitem").filter({ hasText: "Refine" });
  await expect(refineRow).toContainText("Running");

  await expect(page.getByText("Live updates")).toBeVisible();
});
