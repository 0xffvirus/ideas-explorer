import { expect, test } from "@playwright/test";

test("Ctrl+K opens the palette and finds an idea by a brief-only word", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  await dialog.getByPlaceholder(/search ideas/i).fill("litter");

  const option = page.getByRole("option", { name: /Pet health tracker/ });
  await expect(option).toBeVisible();
  await option.click();

  await expect(page).toHaveURL(/\/ideas\/11111111-1111-4111-8111-111111111111$/);
});

test("Escape closes the palette", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("palette actions navigate to the library", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open command palette" }).click();
  await page.getByRole("option", { name: "Go to library" }).click();

  await expect(page).toHaveURL(/\/ideas$/);
});
