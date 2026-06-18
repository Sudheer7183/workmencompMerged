/**
 * 15-report-exception-report.spec.ts — Phase 5 E2E
 *
 * Tests the "Export Error Report" button in ExceptionTracker.
 * Key assertion: Phase 4 stub toast is GONE; ReportStatusModal appears instead.
 */

import { test, expect } from "@playwright/test";
import { loginAs } from "../fixtures/auth";

test.describe("Report: Exception Report", () => {
  test("Export Error Report from ExceptionTracker generates Excel (not stub toast)", async ({
    page,
  }) => {
    await loginAs(page, "tenantAdmin");
    // Navigate to audit runner
    await page.goto("/audit-runner");

    // Find a partial or complete run's exceptions view
    const viewErrorsBtn = page
      .locator("[data-testid='run-status-partial'], [data-testid='run-status-complete']")
      .first()
      .locator("..")
      .locator("[data-testid='view-errors-btn']");

    if (!(await viewErrorsBtn.isVisible())) {
      test.skip(true, "No partial/complete run available — skipping exception report test");
      return;
    }

    await viewErrorsBtn.click();
    await expect(page).toHaveURL(/exceptions/);

    // Click Export Error Report
    await page.click("[data-testid='exception-tracker__export-btn']");

    // Phase 5: ReportStatusModal should appear (not the Phase 4 stub toast)
    await expect(
      page.locator("[data-testid='report-status-modal']")
    ).toBeVisible({ timeout: 5000 });

    // Phase 4 stub toast must NOT be visible
    await expect(
      page.locator("text=Report generation available in Phase 5")
    ).not.toBeVisible();

    // Wait for completion
    await expect(
      page.locator("[data-testid='report-status-complete']")
    ).toBeVisible({ timeout: 60_000 });

    // Download button
    await expect(
      page.locator("[data-testid='report-download-btn']")
    ).toBeVisible();
  });

  test("Exception report opens with correct run_id scope", async ({ page }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/audit-runner");

    const viewErrorsBtn = page
      .locator("[data-testid='view-errors-btn']")
      .first();

    if (!(await viewErrorsBtn.isVisible())) {
      test.skip(true, "No runs available");
      return;
    }

    await viewErrorsBtn.click();

    // Intercept the generate call to verify run_id is sent
    let capturedPayload: Record<string, unknown> | null = null;
    await page.route("**/api/v1/reports/generate", async (route) => {
      const body = route.request().postDataJSON();
      capturedPayload = body as Record<string, unknown>;
      await route.continue();
    });

    await page.click("[data-testid='exception-tracker__export-btn']");

    await expect(
      page.locator("[data-testid='report-status-modal']")
    ).toBeVisible({ timeout: 5000 });

    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload?.report_type).toBe("exception_report");
    expect(capturedPayload?.output_format).toBe("excel");
    expect(capturedPayload?.run_id).toBeTruthy();
  });
});
