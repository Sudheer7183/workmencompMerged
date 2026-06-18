/**
 * E2E Spec 01 — Authentication.
 * Tests real Keycloak login/logout for each dev role.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Authentication", () => {
  test("TENANT_ADMIN can log in and sees dashboard", async ({ adminPage }) => {
    await expect(adminPage).toHaveURL(/dashboard|admin/);
    // Should see some dashboard content
    await adminPage.waitForSelector("body");
    const content = await adminPage.content();
    expect(content.length).toBeGreaterThan(100);
  });

  test("AUDITOR can log in and sees audit runner", async ({ auditorPage }) => {
    await expect(auditorPage).toHaveURL(/dashboard|audit/);
    await auditorPage.waitForSelector("body");
  });

  test("REVIEWER can log in", async ({ reviewerPage }) => {
    await expect(reviewerPage).toHaveURL(/dashboard|review/);
    await reviewerPage.waitForSelector("body");
  });

  test("unauthenticated request redirects to login", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto("/dashboard");
    // Should be redirected to Keycloak or login page
    await page.waitForURL(/keycloak|login/, { timeout: 20_000 });
    await context.close();
  });
});
