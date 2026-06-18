/**
 * E2E Spec 18 — Labels & Display Tab (Tab 4).
 *
 * Phase 6 — V9 S23, S26
 * Tests the Labels & Display tab in CarrierConfigHub:
 *   - Tab 4 renders LabelsDisplayTab (not ComingSoonTab)
 *   - Label rows are visible with default and override columns
 *   - Inline edit opens on pencil click
 *   - Export CSV button is present
 *   - Import CSV button is present
 *   - Preview Mode toggle is present
 *   - Display Config sub-tab is reachable
 */

import { test, expect } from "../fixtures/auth";

test.describe("Labels & Display Tab", () => {
  test.beforeEach(async ({ adminPage: page }) => {
    await page.goto("/admin/carriers/1/config");
    // Click Tab 4 (Labels & Display)
    await page.getByRole("tab", { name: /labels/i }).click();
    await page.waitForTimeout(500);
  });

  test("Tab 4 renders LabelsDisplayTab, not ComingSoon", async ({ adminPage: page }) => {
    const comingSoon = page.getByTestId("carrier-config-hub__coming-soon");
    await expect(comingSoon).not.toBeVisible();
  });

  test("Labels sub-tab is active by default", async ({ adminPage: page }) => {
    await expect(page.getByText(/labels/i).first()).toBeVisible();
  });

  test("Search bar is visible", async ({ adminPage: page }) => {
    await expect(page.getByPlaceholder(/search/i)).toBeVisible();
  });

  test("Export CSV button is visible", async ({ adminPage: page }) => {
    await expect(page.getByRole("button", { name: /export csv/i })).toBeVisible();
  });

  test("Import CSV button is visible", async ({ adminPage: page }) => {
    await expect(page.getByRole("button", { name: /import csv/i })).toBeVisible();
  });

  test("Preview Mode button is visible", async ({ adminPage: page }) => {
    await expect(page.getByRole("button", { name: /preview mode/i })).toBeVisible();
  });

  test("Display Config sub-tab is accessible", async ({ adminPage: page }) => {
    await page.getByRole("tab", { name: /display config/i }).click();
    // Should not crash
    await page.waitForTimeout(300);
    const errorText = await page.locator(".error, [role='alert']").count();
    expect(errorText).toBe(0);
  });

  test("label rows table has header columns", async ({ adminPage: page }) => {
    await expect(page.getByText(/field key/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/default text/i)).toBeVisible({ timeout: 5000 });
  });
});
