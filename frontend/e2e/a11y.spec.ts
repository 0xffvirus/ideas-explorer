import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const DOG_ID = "00000000-0000-4000-8000-000000000001";
const INVOICE_ID = "00000000-0000-4000-8000-000000000002";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function scan(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return results.violations;
}

test("intake has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("idea-input")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Turn a rough idea/i })).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("library has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("idea page has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto(`/ideas/${DOG_ID}`);
  await expect(page.getByTestId("scorecard")).toBeVisible();
  expect(await scan(page)).toEqual([]);

  await page.getByRole("tab", { name: "Market" }).click();
  await expect(page.getByTestId("citation").first()).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("compare has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto(`/compare?ids=${DOG_ID},${INVOICE_ID}`);
  await expect(page.getByText("Overall score")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("command palette has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("board view has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/ideas?view=board");
  await expect(page.getByTestId("idea-board")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("the clarifying-questions state has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/ideas/00000000-0000-4000-8000-000000000003");
  await expect(page.getByTestId("clarify-form")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});
