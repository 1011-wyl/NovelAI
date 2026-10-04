import { defineConfig, devices } from "@playwright/test";

const port = process.env.NOVEL_AGENT_E2E_PORT || "18000";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/scripts/global-setup.mjs",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "zh-CN",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
});
