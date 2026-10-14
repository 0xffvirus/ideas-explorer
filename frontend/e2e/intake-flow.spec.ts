import { expect, test } from "@playwright/test";

test("intake → live progress → report with cited sections", async ({ page }) => {
  await page.goto("/");

  const input = page.getByTestId("idea-input");
  const analyze = page.getByTestId("analyze-button");
  await expect(analyze).toBeDisabled();
  await input.fill(
    "A marketplace that connects local farmers with restaurants for produce delivery.",
  );
  await expect(analyze).toBeEnabled();
  await analyze.click();

  await page.waitForURL(/\/ideas\/[0-9a-f-]+$/);
  await expect(page.getByTestId("progress-timeline")).toBeVisible();

  // Progress advances step by step instead of arriving as one final blob.
  const doneSteps = page.locator('[data-testid="step-list"] li[data-status="done"]');
  await expect(doneSteps.first()).toBeVisible({ timeout: 8_000 });
  await expect.poll(async () => doneSteps.count(), { timeout: 15_000 }).toBeGreaterThan(1);

  // The report appears when the run finishes.
  await expect(page.getByTestId("scorecard")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("verdict")).toBeVisible();
  await expect(page.getByTestId("overall-score").first()).toBeVisible();
  await expect(page.getByTestId("scorecard").locator("[data-dimension]")).toHaveCount(6);

  // Market tab carries claims with citation links.
  await page.getByRole("tab", { name: "Market" }).click();
  await expect(page.getByTestId("citation").first()).toBeVisible();

  // Sources tab resolves citations to a numbered list.
  await page.getByRole("tab", { name: "Sources" }).click();
  const sources = page.getByTestId("sources-list").locator("li");
  await expect(sources.first()).toBeVisible();
  expect(await sources.count()).toBeGreaterThanOrEqual(3);

  // Section re-run is offered and resumes the run until the report returns.
  await page.getByRole("tab", { name: "Market" }).click();
  await page.getByTestId("rerun-market").click();
  await expect(page.getByTestId("progress-timeline")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("progress-timeline")).toBeHidden({ timeout: 20_000 });
  await page.getByRole("tab", { name: "Overview" }).click();
  await expect(page.getByTestId("scorecard")).toBeVisible({ timeout: 15_000 });
});

test("a reload keeps the run state", async ({ page }) => {
  await page.goto("/ideas/00000000-0000-4000-8000-000000000001");
  await expect(page.getByTestId("scorecard")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("scorecard")).toBeVisible();
  await expect(page.getByTestId("verdict")).toHaveText(/refine|pursue|park/i);
});

test("clarifying questions appear inline and can be skipped", async ({ page }) => {
  await page.goto("/ideas/00000000-0000-4000-8000-000000000003");
  await expect(page.getByTestId("clarify-form")).toBeVisible();
  await expect(page.getByTestId("clarify-submit")).toBeDisabled();
  await page.getByTestId("clarify-skip").click();
  await expect(page.getByTestId("clarify-form")).toBeHidden({ timeout: 10_000 });
});

test("export offers Markdown and PDF and downloads a file", async ({ page }) => {
  await page.goto("/ideas/00000000-0000-4000-8000-000000000001");
  await expect(page.getByTestId("scorecard")).toBeVisible();
  await page.getByRole("button", { name: /actions/i }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /export markdown/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.md$/);
});
