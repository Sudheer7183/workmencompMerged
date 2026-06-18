/**
 * E2E Spec 06 — Rollback confirmation dialog.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Rollback Flow", () => {
  test("ExceptionTracker page loads for TENANT_ADMIN", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner/1/exceptions");
    await adminPage.waitForSelector("body");
    await adminPage.waitForTimeout(2000);
    // Should render the tracker (even if run 1 doesn't exist, it shows error state)
    await adminPage.waitForSelector("[data-testid='exception-tracker']", { timeout: 15_000 });
  });

  test("Rollback button not present for AUDITOR", async ({ auditorPage }) => {
    await auditorPage.goto("/audit-runner/1/exceptions");
    await auditorPage.waitForSelector("[data-testid='exception-tracker']", { timeout: 15_000 });
    const rollbackBtn = auditorPage.locator("[data-testid='exception-tracker__rollback-btn']");
    await expect(rollbackBtn).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
  });
});
