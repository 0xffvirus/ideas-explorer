import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PET_IDEA = "11111111-1111-4111-8111-111111111111";
const QUANTUM_IDEA = "44444444-4444-4444-8444-444444444444";

test("compare flow: multi-select in the library lands on aligned scorecards", async ({ page }) => {
  await page.goto("/ideas");

  await page
    .getByRole("checkbox", {
      name: "Select Pet health tracker for busy owners for comparison",
    })
    .check();
  await page
    .getByRole("checkbox", {
      name: "Select Quantum-safe backup for small teams for comparison",
    })
    .check();
  await page.getByRole("link", { name: "Compare selected" }).click();

  await expect(page).toHaveURL(/\/compare\?ids=/);
  await expect(page.getByRole("heading", { name: "Compare" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Pet health tracker for busy owners" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Quantum-safe backup for small teams" }),
  ).toBeVisible();

  // Aligned dimension matrix for the idea with a report.
  await expect(page.getByRole("rowheader", { name: "Problem severity" })).toBeVisible();
  await expect(page.getByLabel(/Score 4 out of 5/).first()).toBeVisible();
  await expect(page.getByText("No completed report yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open report" })).toBeVisible();
});

test("compare validates the selection client-side", async ({ page }) => {
  await page.goto(`/compare?ids=${PET_IDEA}`);

  await expect(page.getByText("Pick at least 2 ideas to compare.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to library" })).toBeVisible();
});

test("compare has no axe violations", async ({ page }) => {
  await page.goto(`/compare?ids=${PET_IDEA},${QUANTUM_IDEA}`);
  await expect(page.getByRole("heading", { name: "Compare" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "Problem severity" })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
