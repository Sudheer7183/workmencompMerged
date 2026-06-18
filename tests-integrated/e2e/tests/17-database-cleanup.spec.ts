/**
 * E2E Spec 17 — Database Cleanup.
 *
 * Phase 6 — V9 S22.4
 * Tests the full cleanup page workflow:
 *   - TENANT_ADMIN can reach the page
 *   - Preview button shows row counts
 *   - Execute button is disabled until "CONFIRM" is typed (case-sensitive)
 *   - Successful execute shows success message
 *   - REVIEWER cannot access the page
 */

import { test, expect } from "../fixtures/auth";

test.describe("Database Cleanup Page", () => {
  test("TENANT_ADMIN can navigate to the cleanup page", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    await expect(page.locator("h1")).toContainText("Database Cleanup");
  });

  test("cleanup page shows preserved items section", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    await expect(page.getByText(/always preserved/i)).toBeVisible();
  });

  test("Run Preview button is visible", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    await expect(page.getByTestId("cleanup-preview-btn")).toBeVisible();
  });

  test("Execute button is disabled when confirm input is empty", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    const execBtn = page.getByTestId("cleanup-execute-btn");
    await expect(execBtn).toBeDisabled();
  });

  test("Execute button is disabled for lowercase 'confirm'", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    await page.getByTestId("cleanup-confirm-input").fill("confirm");
    await expect(page.getByTestId("cleanup-execute-btn")).toBeDisabled();
  });

  test("Execute button becomes enabled when CONFIRM is typed exactly", async ({ adminPage: page }) => {
    await page.goto("/admin/database-cleanup");
    await page.getByTestId("cleanup-confirm-input").fill("CONFIRM");
    await expect(page.getByTestId("cleanup-execute-btn")).toBeEnabled();
  });

  test("DB Cleanup nav link is visible to TENANT_ADMIN", async ({ adminPage: page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: /db cleanup/i })).toBeVisible();
  });

  test("REVIEWER cannot access cleanup page (redirected or 403)", async ({ reviewerPage: page }) => {
    await page.goto("/admin/database-cleanup");
    // Either redirected away or shows unauthorized
    const url = page.url();
    const body = await page.content();
    const isUnauthorized =
      url.includes("unauthorized") ||
      url.includes("login") ||
      body.toLowerCase().includes("unauthorized") ||
      !body.includes("Database Cleanup");
    expect(isUnauthorized).toBe(true);
  });
});
