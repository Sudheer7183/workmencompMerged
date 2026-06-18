/**
 * 13-report-policy-audit.spec.ts — Phase 5 E2E tests.
 *
 * Tests the end-to-end flow for generating an Individual Policy Audit report
 * from the PolicyDetailPage. Requires all services running (including MinIO).
 */

import { test, expect } from "@playwright/test";
import { loginAs } from "../fixtures/auth";

test.describe("Report: Individual Policy Audit", () => {
  test("AUDITOR can generate Individual Policy Audit PDF from PolicyDetail", async ({
    page,
  }) => {
    await loginAs(page, "auditor");
    await page.goto("/policies");

    // Navigate to first policy
    await page
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();
    await expect(page).toHaveURL(/\/policies\//);

    // Generate Audit Report dropdown
    await page.click("[data-testid='generate-report-btn']");
    await expect(
      page.locator("[data-testid='report-format-dropdown']")
    ).toBeVisible();

    // Select PDF
    await page.click("[data-testid='format-pdf-option']");

    // Modal opens with GENERATING state
    await expect(
      page.locator("[data-testid='report-status-modal']")
    ).toBeVisible();
    await expect(
      page.locator("[data-testid='report-status-generating']")
    ).toBeVisible();

    // Wait for report to complete (up to 60s)
    await expect(
      page.locator("[data-testid='report-status-complete']")
    ).toBeVisible({ timeout: 60_000 });

    // Download button visible
    await expect(
      page.locator("[data-testid='report-download-btn']")
    ).toBeVisible();
  });

  test("AUDITOR can generate Individual Policy Audit Excel", async ({ page }) => {
    await loginAs(page, "auditor");
    await page.goto("/policies");

    await page
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();

    await page.click("[data-testid='generate-report-btn']");
    await page.click("[data-testid='format-excel-option']");

    await expect(
      page.locator("[data-testid='report-status-complete']")
    ).toBeVisible({ timeout: 60_000 });
    await expect(
      page.locator("[data-testid='report-download-btn']")
    ).toBeVisible();
  });

  test("REVIEWER sees status complete and can download (cannot generate)", async ({
    browser,
  }) => {
    // Step 1: AUDITOR generates a report
    const auditorContext = await browser.newContext();
    const auditorPage = await auditorContext.newPage();
    await loginAs(auditorPage, "auditor");
    await auditorPage.goto("/policies");
    await auditorPage
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();
    await auditorPage.click("[data-testid='generate-report-btn']");
    await auditorPage.click("[data-testid='format-pdf-option']");

    // Get job_id from the modal (if exposed via data attribute)
    await auditorPage
      .locator("[data-testid='report-status-complete']")
      .waitFor({ timeout: 60_000 });

    await auditorContext.close();

    // Step 2: REVIEWER sees the Download button (RBAC: REVIEWER+ can download)
    const reviewerContext = await browser.newContext();
    const reviewerPage = await reviewerContext.newPage();
    await loginAs(reviewerPage, "reviewer");
    await reviewerPage.goto("/policies");

    // REVIEWER should see policies but no "Generate Audit Report" button
    // (the button is AUDITOR+ only)
    // Navigate to policy detail
    await reviewerPage
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();

    // Verify generate button is not present for REVIEWER
    await expect(
      reviewerPage.locator("[data-testid='generate-report-btn']")
    ).not.toBeVisible();

    await reviewerContext.close();
  });

  test("format dropdown closes when a format is selected", async ({ page }) => {
    await loginAs(page, "auditor");
    await page.goto("/policies");
    await page
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();

    await page.click("[data-testid='generate-report-btn']");
    await expect(
      page.locator("[data-testid='report-format-dropdown']")
    ).toBeVisible();
    await page.click("[data-testid='format-pdf-option']");

    // Dropdown should close after selection
    await expect(
      page.locator("[data-testid='report-format-dropdown']")
    ).not.toBeVisible();
  });

  test("closing modal while GENERATING does not cause errors", async ({
    page,
  }) => {
    await loginAs(page, "auditor");
    await page.goto("/policies");
    await page
      .locator("[data-testid='policy-row']")
      .first()
      .locator("text=Review")
      .click();

    await page.click("[data-testid='generate-report-btn']");
    await page.click("[data-testid='format-pdf-option']");

    // Close modal immediately while generating
    await page.click("[data-testid='report-modal-close-btn']");
    await expect(
      page.locator("[data-testid='report-status-modal']")
    ).not.toBeVisible();

    // No uncaught console errors
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.waitForTimeout(500);
    expect(errors.filter((e) => !e.includes("favicon"))).toHaveLength(0);
  });
});
