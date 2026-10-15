import { expect, test } from "@playwright/test";

test("j/k moves through ideas and Enter opens the selected one", async ({ page }) => {
  await page.goto("/ideas");
  const first = page.getByRole("link", { name: "Pet health tracker for busy owners" });
  const second = page.getByRole("link", { name: "AI invoice reconciliation for freelancers" });
  await expect(first).toBeVisible();

  await page.keyboard.press("j");
  await expect(first).toBeFocused();

  await page.keyboard.press("j");
  await expect(second).toBeFocused();

  await page.keyboard.press("k");
  await expect(first).toBeFocused();

  await page.keyboard.press("j");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ideas\/22222222-2222-4222-8222-222222222222$/);
});

test("/ focuses the search input", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  await page.keyboard.press("/");
  await expect(page.getByRole("searchbox", { name: "Search ideas" })).toBeFocused();
});

test("n starts a new idea from the library", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  await page.keyboard.press("n");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Describe your idea");
});
