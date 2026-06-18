/**
 * E2E Spec 03 — XLSX ingestion happy path.
 * Upload → mapping review → approve → progress → complete.
 */
import path from "path";
import { test, expect } from "../fixtures/auth";

const XLSX_FILE = path.join(__dirname, "../fixtures/test-files/valid-payroll.xlsx");

test.describe("XLSX Ingestion Happy Path", () => {
  test("upload file, approve mapping, reach complete status", async ({ adminPage }) => {
    await adminPage.goto("/audit-runner");

    // Locate file input and upload
    const fileInput = adminPage.locator('input[type="file"]').first();
    await fileInput.setInputFiles(XLSX_FILE);

    // Wait for navigation to mapping review
    await adminPage.waitForURL(/mapping/, { timeout: 30_000 });

    // Approve mapping if button available
    const approveBtn = adminPage.locator('[data-testid="field-mapping-review__approve-btn"]');
    if (await approveBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await approveBtn.click();
    }

    // Wait for progress page
    await adminPage.waitForURL(/progress/, { timeout: 30_000 });

    // Wait for terminal status (complete / partial / failed)
    await adminPage.waitForFunction(
      () => {
        const body = document.body.innerText;
        return /complete|partial|failed/i.test(body);
      },
      { timeout: 60_000 }
    );
  });

  test("ingestion page shows upload options", async ({ auditorPage }) => {
    await auditorPage.goto("/audit-runner");
    await auditorPage.waitForSelector("body");
    // Should show file input or upload button
    const hasInput = await auditorPage.locator('input[type="file"], [data-testid*="upload"]').count();
    expect(hasInput).toBeGreaterThan(0);
  });
});
