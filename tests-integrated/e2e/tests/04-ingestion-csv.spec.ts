/**
 * E2E Spec 04 — CSV ingestion end-to-end.
 */
import path from "path";
import { test, expect } from "../fixtures/auth";

const CSV_FILE = path.join(__dirname, "../fixtures/test-files/valid-payroll.csv");

test.describe("CSV Ingestion", () => {
  test("CSV file is accepted and reaches mapping review", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner");

    // Find the CSV upload slot (Phase 4 adds type3 option)
    const csvRadio = adminPage.locator('input[value="type3"]');
    if (await csvRadio.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await csvRadio.click();
    }

    const fileInput = adminPage.locator('input[type="file"]').first();
    await fileInput.setInputFiles(CSV_FILE);

    // Should navigate to mapping review (same as XLSX flow)
    await adminPage.waitForURL(/mapping|progress/, { timeout: 30_000 });
    await adminPage.waitForSelector("body");
  });
});
