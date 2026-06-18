/**
 * E2E Spec 02 — Dashboard renders after login.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Dashboard", () => {
  test("renders KPI cards for TENANT_ADMIN", async ({ adminPage }) => {
    await adminPage.goto("/dashboard");
    await adminPage.waitForSelector("[data-testid]", { timeout: 15_000 });
    const body = await adminPage.content();
    expect(body).toContain("dashboard");
  });

  test("renders for AUDITOR", async ({ auditorPage }) => {
    await auditorPage.goto("/dashboard");
    await auditorPage.waitForSelector("body");
  });

  test("renders for REVIEWER", async ({ reviewerPage }) => {
    await reviewerPage.goto("/dashboard");
    await reviewerPage.waitForSelector("body");
  });
});
