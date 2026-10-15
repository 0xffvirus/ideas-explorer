import { expect, test } from "@playwright/test";

test("renders mocked ideas, debounces search, and keeps history clean", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  const historyBefore = await page.evaluate(() => history.length);

  await page.getByRole("searchbox", { name: "Search ideas" }).fill("quantum");
  await expect(page).toHaveURL(/q=quantum/);
  await expect(
    page.getByRole("link", { name: "Quantum-safe backup for small teams" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Pet health tracker for busy owners" })).toHaveCount(
    0,
  );

  // Debounced typing must replace, not push history entries.
  expect(await page.evaluate(() => history.length)).toBe(historyBefore);
});

test("shows the empty state with a create-from-query link", async ({ page }) => {
  await page.goto("/ideas?q=zzzzzz");

  await expect(page.getByText("No ideas match — create one from this query")).toBeVisible();
  await page.locator("#main").getByRole("link", { name: "New idea" }).click();
  await expect(page).toHaveURL(/\/\?q=zzzzzz/);
  await expect(page.getByRole("textbox", { name: "Your idea" })).toHaveValue("zzzzzz");
});

test("syncs filters to the URL and back/forward restores them", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  const doneChip = page.getByRole("button", { name: "Status: Done" });
  const pursueChip = page.getByRole("button", { name: "Verdict: Pursue" });

  await doneChip.click();
  await expect(page).toHaveURL(/status=done/);
  await expect(doneChip).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("link", { name: /AI invoice reconciliation/ })).toHaveCount(0);

  await pursueChip.click();
  await expect(page).toHaveURL(/verdict=pursue/);
  await expect(pursueChip).toHaveAttribute("aria-pressed", "true");

  await page.goBack();
  await expect(page).not.toHaveURL(/verdict=pursue/);
  await expect(doneChip).toHaveAttribute("aria-pressed", "true");

  await page.goBack();
  await expect(page).not.toHaveURL(/status=done/);
  await expect(doneChip).toHaveAttribute("aria-pressed", "false");

  await page.goForward();
  await expect(page).toHaveURL(/status=done/);
  await expect(doneChip).toHaveAttribute("aria-pressed", "true");
});

test("switches between list and board views via the URL", async ({ page }) => {
  await page.goto("/ideas");
  await page.getByRole("button", { name: "Board view" }).click();

  await expect(page).toHaveURL(/view=board/);
  await expect(page.getByRole("region", { name: "Done ideas" })).toBeVisible();

  await page.getByRole("button", { name: "List view" }).click();
  await expect(page).not.toHaveURL(/view=board/);
});
