import { expect, test } from "@playwright/test";

const DOG_ID = "00000000-0000-4000-8000-000000000001";

test("search finds ideas by meaning and reflects the query in the URL", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();

  await page.getByTestId("library-search").fill("pets");
  await expect(page.getByTestId("match-hint")).toContainText("match");
  await expect(page).toHaveURL(/q=pets/);
  await expect(
    page.getByRole("link", { name: /Dog walking marketplace for pet owners/ }),
  ).toBeVisible();
});

test("filters land in the URL and back restores the previous state", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();

  await page.getByRole("button", { name: /^verdict/i }).click();
  await page.getByRole("menuitemradio", { name: "Pursue" }).click();
  await expect(page).toHaveURL(/verdict=pursue/);
  await expect(page.getByRole("button", { name: /remove filter: pursue/i })).toBeVisible();

  await page.goBack();
  await expect(page).not.toHaveURL(/verdict=pursue/);
  await expect(page.getByRole("button", { name: /remove filter: pursue/i })).toBeHidden();

  await page.goForward();
  await expect(page).toHaveURL(/verdict=pursue/);
});

test("keyboard: / focuses search, j/k move through results", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();
  await page.locator("body").click({ position: { x: 5, y: 400 } });

  await page.keyboard.press("/");
  await expect(page.getByTestId("library-search")).toBeFocused();

  await page.keyboard.press("Escape");
  await page.getByTestId("library-search").blur();
  await page.keyboard.press("j");
  await expect(page.locator("[data-idea-link]:focus")).toHaveCount(1);
  await page.keyboard.press("j");
  const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-idea-link"));
  expect(focused).not.toBeNull();

  await page.keyboard.press("k");
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/ideas\/[0-9a-f-]+$/);
});

test("empty search offers to create an idea from the query", async ({ page }) => {
  await page.goto("/ideas?q=zzzznothing");
  await expect(page.getByText(/No ideas match this search/i)).toBeVisible({ timeout: 5_000 });
  await page.getByRole("link", { name: /Create an idea from/i }).click();
  await expect(page.getByTestId("idea-input")).toHaveValue("zzzznothing");
});

test("board view groups by status", async ({ page }) => {
  await page.goto("/ideas?view=board");
  await expect(page.getByTestId("idea-board")).toBeVisible();
  await expect(page.getByRole("region", { name: /Analyzed —/ })).toBeVisible();
});

test("mobile: the library is usable at 360px without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/ideas");
  await expect(page.getByTestId("idea-list")).toBeVisible();
  await expect(page.getByTestId("library-search")).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  await page.getByRole("button", { name: /^status/i }).click();
  await page.getByRole("menuitemradio", { name: "Analyzed" }).click();
  await expect(page).toHaveURL(/status=done/);

  await page.goto(`/ideas/${DOG_ID}`);
  await expect(page.getByTestId("scorecard")).toBeVisible();
  const detailOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(detailOverflow).toBeLessThanOrEqual(1);
});
