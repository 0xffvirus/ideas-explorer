import { expect, test } from "@playwright/test";

test("submits an idea and lands on its queued detail page", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Your idea" })
    .fill("A drone that delivers tacos to hikers on long trails");
  await page.getByRole("button", { name: /analyze/i }).click();

  await expect(page).toHaveURL(/\/ideas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/tacos/i);
  // The status badge is the first "Queued" label; the pipeline rows follow.
  await expect(page.getByText("Queued", { exact: true }).first()).toBeVisible();
});

test("submits with Ctrl+Enter", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your idea" }).fill("A micro-library for seed swaps");
  await page.getByRole("textbox", { name: "Your idea" }).press("Control+Enter");

  await expect(page).toHaveURL(/\/ideas\/[0-9a-f-]{36}$/);
});

test("disables Analyze for empty or whitespace-only input", async ({ page }) => {
  await page.goto("/");
  const analyze = page.getByRole("button", { name: /analyze/i });

  await expect(analyze).toBeDisabled();
  await page.getByRole("textbox", { name: "Your idea" }).fill("    \n  ");
  await expect(analyze).toBeDisabled();
  await page.getByRole("textbox", { name: "Your idea" }).fill("A real idea");
  await expect(analyze).toBeEnabled();
});

test("keeps the intake draft across reloads", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your idea" }).fill("An idea I am still writing");

  await page.reload();

  await expect(page.getByRole("textbox", { name: "Your idea" })).toHaveValue(
    "An idea I am still writing",
  );
});

test("prefills the intake from a ?q= link", async ({ page }) => {
  await page.goto("/?q=pets%20for%20renters");

  await expect(page.getByRole("textbox", { name: "Your idea" })).toHaveValue("pets for renters");
});
