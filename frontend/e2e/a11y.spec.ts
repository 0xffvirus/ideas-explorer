import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home has no axe violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("library has no axe violations", async ({ page }) => {
  await page.goto("/ideas");
  await expect(
    page.getByRole("link", { name: "Pet health tracker for busy owners" }),
  ).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("idea detail has no axe violations", async ({ page }) => {
  await page.goto("/ideas/11111111-1111-4111-8111-111111111111");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
