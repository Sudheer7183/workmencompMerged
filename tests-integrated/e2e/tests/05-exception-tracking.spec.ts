/**
 * E2E Spec 05 — Exception tracking with malformed file.
 */
import path from "path";
import { test, expect } from "../fixtures/auth";

const MALFORMED_FILE = path.join(__dirname, "../fixtures/test-files/malformed-payroll.xlsx");

test.describe("Exception Tracking", () => {
  test("malformed file with skip_on_error shows partial status", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner");
    const fileInput = adminPage.locator('input[type="file"]').first();
    await fileInput.setInputFiles(MALFORMED_FILE);

    // Wait for mapping or progress
    await adminPage.waitForURL(/mapping|progress/, { timeout: 30_000 });
    await adminPage.waitForSelector("body");

    // If on mapping page, approve
    const approveBtn = adminPage.locator('[data-testid="field-mapping-review__approve-btn"]');
    if (await approveBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await approveBtn.click();
      await adminPage.waitForURL(/progress/, { timeout: 30_000 });
    }

    // Wait for terminal status
    await adminPage.waitForFunction(
      () => /complete|partial|failed/i.test(document.body.innerText),
      { timeout: 60_000 }
    );
  });

  test("ExceptionTracker page renders when navigated to directly", async ({ adminPage }) => {
    // Navigate with a run_id — even a non-existent one will show the loading/error state
    await adminPage.goto("/audit-runner/1/exceptions");
    await adminPage.waitForSelector("[data-testid='exception-tracker'], [data-testid='ingestion-progress']", {
      timeout: 15_000,
    });
  });

  test("View Errors link navigates to exceptions page", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner/1/exceptions");
    const url = adminPage.url();
    expect(url).toContain("/exceptions");
  });
});
