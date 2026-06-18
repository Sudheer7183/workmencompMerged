import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["list"],
  ],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
});
