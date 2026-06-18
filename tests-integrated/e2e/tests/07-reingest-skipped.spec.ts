/**
 * E2E Spec 07 — Correct & Re-ingest a skipped row.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Skipped Row Re-ingest", () => {
  test("ExceptionTracker skipped rows table is visible", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner/1/exceptions");
    await adminPage.waitForSelector("[data-testid='exception-tracker']", { timeout: 15_000 });
    // The skipped section should exist
    const section = adminPage.locator("[data-testid='exception-tracker__skipped-section']");
    await expect(section).toBeVisible({ timeout: 10_000 });
  });
});
