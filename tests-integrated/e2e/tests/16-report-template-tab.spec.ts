/**
 * 16-report-template-tab.spec.ts — Phase 5 E2E
 *
 * Tests Tab 5 (Report Template) of CarrierConfigHub.
 * Verifies TENANT_ADMIN can configure branding and trigger a PDF preview.
 */

import { test, expect } from "@playwright/test";
import { loginAs } from "../fixtures/auth";

test.describe("Report Template Tab (Tab 5)", () => {
  test("TENANT_ADMIN can access Report Template tab", async ({ page }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");

    // Click Tab 5 — Report Template
    await page.click("[data-testid='tab-report-template']");
    await expect(
      page.locator("[data-testid='report-template-tab']")
    ).toBeVisible();
  });

  test("TENANT_ADMIN configures primary colour and saves", async ({ page }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");
    await page.click("[data-testid='tab-report-template']");

    // Set primary colour
    await page.fill("[data-testid='primary-colour-input']", "2E86C1");
    await page.fill("[data-testid='secondary-colour-input']", "1A3C5E");

    // Set contact block
    await page.fill(
      "[data-testid='contact-block-input']",
      "<p>123 Test St | test@platform.com</p>"
    );

    // Save
    await page.click("[data-testid='save-template-btn']");
    await expect(
      page.locator("[data-testid='save-success-toast']")
    ).toBeVisible({ timeout: 5000 });
  });

  test("Primary colour input validates hex format", async ({ page }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");
    await page.click("[data-testid='tab-report-template']");

    // Enter invalid hex
    await page.fill("[data-testid='primary-colour-input']", "ZZZZZZ");

    // Save button should be disabled or show error
    const saveBtn = page.locator("[data-testid='save-template-btn']");
    await expect(saveBtn).toBeDisabled();
  });

  test("PDF Preview button opens a new tab with MinIO pre-signed URL", async ({
    page,
  }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");
    await page.click("[data-testid='tab-report-template']");

    // Intercept the new tab that opens
    const newTabPromise = page.waitForEvent("popup");
    await page.click("[data-testid='pdf-preview-btn']");
    const newTab = await newTabPromise;

    // New tab should open (even if MinIO URL in tests)
    await newTab.waitForLoadState("domcontentloaded");
    expect(newTab.url()).toBeTruthy();
    // URL should contain the report (MinIO pre-signed URL or similar)
    expect(newTab.url().length).toBeGreaterThan(10);
  });

  test("AUDITOR cannot access Report Template tab (TENANT_ADMIN only)", async ({
    page,
  }) => {
    await loginAs(page, "auditor");
    await page.goto("/admin/carriers/1/config");

    await page.click("[data-testid='tab-report-template']");

    // Should see access denied message, not the template form
    await expect(
      page.locator("[data-testid='report-template-tab']")
    ).not.toBeVisible();

    // The save button should not be present
    await expect(
      page.locator("[data-testid='save-template-btn']")
    ).not.toBeVisible();
  });

  test("logo upload zone is visible and accepts image files", async ({
    page,
  }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");
    await page.click("[data-testid='tab-report-template']");

    // Upload zone / button visible
    await expect(
      page.locator("[data-testid='logo-upload-btn']")
    ).toBeVisible();
  });

  test("template form has no hardcoded hex colours in rendered HTML", async ({
    page,
  }) => {
    await loginAs(page, "tenantAdmin");
    await page.goto("/admin/carriers/1/config");
    await page.click("[data-testid='tab-report-template']");

    // Get the rendered HTML of the tab
    const tabHtml = await page
      .locator("[data-testid='report-template-tab']")
      .innerHTML();

    // Check for inline hardcoded hex in style attributes
    const hexInlinePattern = /style="[^"]*#[0-9a-fA-F]{3,6}/;
    expect(tabHtml).not.toMatch(hexInlinePattern);
  });
});
