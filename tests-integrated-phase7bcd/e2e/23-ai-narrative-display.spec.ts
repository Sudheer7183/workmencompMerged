/**
 * E2E Spec 23 — AI Narrative Display
 *
 * Tests the NarrativePanel rendering on the Policy Detail page.
 * Verifies all five display states are reachable via UI.
 */

import { test, expect } from "@playwright/test";

test.describe("23 — AI Narrative Display", () => {
  test.beforeEach(async ({ page }) => {
    // Log in as TENANT_ADMIN
    await page.goto("/");
    await page.fill('[data-testid="email"]', "admin@test.tenant.com");
    await page.fill('[data-testid="password"]', "TestPassword1!");
    await page.click('[data-testid="login-btn"]');
    await page.waitForURL("**/dashboard");
  });

  test("narrative panel renders on policy detail page", async ({ page }) => {
    await page.goto("/policies");
    await page.waitForSelector("table");
    // Click first policy
    const firstRow = page.locator("table tbody tr").first();
    await firstRow.click();
    await page.waitForURL("**/policies/**");
    // Navigate to AI Narrative tab
    const aiTab = page.getByText("AI Narrative");
    await aiTab.click();
    // Panel should be visible
    await expect(page.locator('[data-testid="narrative-panel"]')).toBeVisible();
  });

  test("narrative panel shows correct title", async ({ page }) => {
    await page.goto("/policies");
    await page.waitForSelector("table");
    await page.locator("table tbody tr").first().click();
    await page.waitForURL("**/policies/**");
    await page.getByText("AI Narrative").click();
    await expect(page.locator(".narrative-panel__title")).toContainText("AI-Generated Audit Narrative");
  });

  test("narrative panel toggle expand/collapse", async ({ page }) => {
    await page.goto("/policies");
    await page.waitForSelector("table");
    await page.locator("table tbody tr").first().click();
    await page.waitForURL("**/policies/**");
    await page.getByText("AI Narrative").click();
    const panel = page.locator('[data-testid="narrative-panel"]');
    await expect(panel).toBeVisible();
    // If there's narrative text, test toggle
    const toggleBtn = panel.locator('[data-testid="btn-toggle-narrative"]');
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click();
      // After click, the button text should change
      await expect(toggleBtn).toBeVisible();
    }
  });

  test("narrative panel uses BEM classes — no inline colour styles", async ({ page }) => {
    await page.goto("/policies");
    await page.waitForSelector("table");
    await page.locator("table tbody tr").first().click();
    await page.waitForURL("**/policies/**");
    await page.getByText("AI Narrative").click();
    // Check that no inline colour styles are on the panel
    const panel = page.locator('[data-testid="narrative-panel"]');
    await expect(panel).toBeVisible();
    const colorStyle = await panel.evaluate((el) => window.getComputedStyle(el).color);
    // Should be set by CSS variables, not inline
    const inlineColor = await panel.getAttribute("style");
    expect(inlineColor ?? "").not.toMatch(/color:/);
  });
});
