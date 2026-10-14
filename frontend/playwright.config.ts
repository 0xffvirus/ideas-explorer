import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `pnpm build && pnpm start -p ${PORT}`,
    url: `http://localhost:${PORT}/ideas`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: {
      ALLOW_MOCK_BUILD: "1",
      NEXT_PUBLIC_API_MOCKING: "enabled",
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
      // Section re-runs run slower so progress states are observable in e2e.
      NEXT_PUBLIC_MOCK_RERUN_MS: "2500",
      // Build e2e artifacts separately from the normal dev/prod output.
      NEXT_DIST_DIR: ".next-e2e",
    },
  },
});
