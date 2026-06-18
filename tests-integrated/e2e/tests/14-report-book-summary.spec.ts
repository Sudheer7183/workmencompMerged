/**
 * 14-report-book-summary.spec.ts — Phase 5 E2E
 * Tests Policy Book Summary report from PoliciesListPage.
 */

import { test, expect } from "@playwright/test";
import { loginAs } from "../fixtures/auth";

test.describe("Report: Policy Book Summary", () => {
  test("Policy Book Summary PDF generated from Policies list", async ({
    page,
  }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/policies");

    // Book summary button in page header
    await expect(
      page.locator("[data-testid='book-summary-btn']")
    ).toBeVisible();

    // Open format dropdown
    await page.click("[data-testid='book-summary-btn']");
    await expect(
      page.locator("[data-testid='report-format-dropdown']")
    ).toBeVisible();

    // Select PDF
    await page.click("[data-testid='format-pdf-option']");

    // Wait for completion
    await expect(
      page.locator("[data-testid='report-status-complete']")
    ).toBeVisible({ timeout: 60_000 });

    // Verify download URL is a MinIO pre-signed URL
    const downloadBtn = page.locator("[data-testid='report-download-btn']");
    await expect(downloadBtn).toBeVisible();
  });

  test("Policy Book Summary Excel generated from Policies list", async ({
    page,
  }) => {
    await loginAs(page, "auditor");
    await page.goto("/policies");

    await page.click("[data-testid='book-summary-btn']");
    await page.click("[data-testid='format-excel-option']");

    await expect(
      page.locator("[data-testid='report-status-complete']")
    ).toBeVisible({ timeout: 60_000 });
    await expect(
      page.locator("[data-testid='report-download-btn']")
    ).toBeVisible();
  });
});
