import { expect, test } from "@playwright/test";

test("Ctrl/Cmd+K opens the palette and jumps to an idea by meaning", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();

  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette).toBeVisible();

  await palette.getByRole("combobox").fill("pets");
  await expect(
    palette.getByRole("option", { name: /Dog walking marketplace for pet owners/ }),
  ).toBeVisible();

  await page.keyboard.press("Enter");
  await page.waitForURL(/\/ideas\/00000000-0000-4000-8000-000000000001$/);
  await expect(page.getByTestId("scorecard")).toBeVisible();
});

test("the palette button and 'n' shortcut reach the intake form", async ({ page }) => {
  await page.goto("/ideas");
  await page.getByTestId("palette-trigger").click();
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();

  await page.locator("body").click({ position: { x: 5, y: 400 } });
  await page.keyboard.press("n");
  await page.waitForURL((url) => url.pathname === "/");
  await expect(page.getByTestId("idea-input")).toBeVisible();
});
