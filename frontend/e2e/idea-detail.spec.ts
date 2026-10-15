import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PET_IDEA = "11111111-1111-4111-8111-111111111111";
const INVOICE_IDEA = "22222222-2222-4222-8222-222222222222";
const CLARIFY_IDEA = "66666666-6666-4666-8666-666666666666";

test("full journey: intake → streaming progress → report tabs with citations", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Your idea" })
    .fill("A subscription box for rare houseplants");
  await page.getByRole("button", { name: /analyze/i }).click();

  await expect(page).toHaveURL(/\/ideas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("subscription box");

  // Streaming progress: rows move from queued to running before the report appears.
  await expect(page.getByRole("heading", { name: "Analysis progress" })).toBeVisible();
  await expect(page.getByText("Running").first()).toBeVisible({ timeout: 15_000 });

  // The run completes and the page flips to the report.
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Scorecard" })).toBeVisible();
  await expect(page.getByText("Problem severity")).toBeVisible();

  // Market section renders structured payload plus a cited claim.
  await page.getByRole("tab", { name: "Market" }).click();
  await expect(page.getByRole("heading", { name: "Market Size" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Source 1/ })).toBeVisible();
  await expect(page.getByText("unverified").first()).toBeVisible();

  // Sources tab lists the numbered sources.
  await page.getByRole("tab", { name: "Sources" }).click();
  await expect(page.getByRole("link", { name: /Pet tech market report 2025/ })).toBeVisible();
});

test("clarifier: answers the questions and the run continues to done", async ({ page }) => {
  await page.goto(`/ideas/${CLARIFY_IDEA}`);

  await expect(
    page.getByRole("heading", { name: "Help the analysis continue" }),
  ).toBeVisible({ timeout: 15_000 });
  await page
    .getByRole("textbox", { name: "Which city or neighborhood is this for?" })
    .fill("Portland, Oregon");
  await page
    .getByRole("textbox", { name: "Will members pay a monthly fee or per visit?" })
    .fill("$10 a month membership");
  await page.getByRole("button", { name: "Submit answers" }).click();

  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible({ timeout: 30_000 });
});

test("not-completed sections render a placeholder", async ({ page }) => {
  await page.goto(`/ideas/${PET_IDEA}`);
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();

  await page.getByRole("tab", { name: "Business model" }).click();
  await expect(page.getByText("Not completed")).toBeVisible();
  await expect(page.getByRole("button", { name: /Re-run Business model/i })).toBeVisible();
});

test("re-running a section restarts progress", async ({ page }) => {
  await page.goto(`/ideas/${PET_IDEA}`);
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();

  await page.getByRole("tab", { name: "Market" }).click();
  await page.getByRole("button", { name: /Re-run Market/i }).click();

  await expect(page.getByRole("heading", { name: "Analysis progress" })).toBeVisible();
  const marketRow = page.getByRole("listitem").filter({ hasText: "Market" });
  await expect(marketRow).toContainText("Running", { timeout: 10_000 });
});

test("archive from detail removes the idea from the library", async ({ page }) => {
  await page.goto(`/ideas/${PET_IDEA}`);
  await page.getByRole("button", { name: "Archive idea" }).click();
  await expect(page.getByText("Archived")).toBeVisible();

  await page.goto("/ideas");
  await expect(page.getByRole("link", { name: "Pet health tracker for busy owners" })).toHaveCount(
    0,
  );
});

test("running detail has no axe violations", async ({ page }) => {
  await page.goto(`/ideas/${INVOICE_IDEA}`);
  await expect(page.getByRole("heading", { name: "Analysis progress" })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
