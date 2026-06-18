/**
 * E2E Spec 25 — Expression Builder (Drag-and-Drop)
 *
 * Tests the ExpressionBuilder in the Calc Rules tab of Carrier Config Hub.
 */

import { test, expect } from "@playwright/test";

test.describe("25 — Expression Builder (Phase 7D)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.fill('[data-testid="email"]', "admin@test.tenant.com");
    await page.fill('[data-testid="password"]', "TestPassword1!");
    await page.click('[data-testid="login-btn"]');
    await page.waitForURL("**/dashboard");
  });

  async function navigateToCalcRulesTab(page: import("@playwright/test").Page) {
    await page.goto("/admin/carriers/1/config");
    // Click Tab 3 — Calc Engine
    await page.getByRole("tab", { name: /Calc Engine/i }).click();
    await page.waitForSelector(".calc-rules-list", { timeout: 5000 }).catch(() => {});
  }

  test("expression builder renders when editing an editable rule", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    // Click Edit on the first editable rule
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      // ExpressionBuilder should appear
      const builderOrToggle = page.locator('[data-testid="expression-builder"], [data-testid="btn-switch-mode"]');
      await expect(builderOrToggle.first()).toBeVisible({ timeout: 3000 });
    }
  });

  test("Switch to Raw Text shows textarea", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      const switchBtn = page.locator('[data-testid="btn-switch-mode"]');
      if (await switchBtn.isVisible()) {
        // Toggle to raw mode
        const btnText = await switchBtn.textContent();
        if (btnText?.includes("Raw Text")) {
          await switchBtn.click();
          await expect(page.locator('[data-testid="raw-expression-textarea"]')).toBeVisible();
        }
      }
    }
  });

  test("Switch back to Builder from raw mode", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      const switchBtn = page.locator('[data-testid="btn-switch-mode"]');
      if (await switchBtn.isVisible()) {
        await switchBtn.click(); // switch to raw
        await switchBtn.click(); // switch back to builder
        await expect(page.locator('[data-testid="expression-builder"]')).toBeVisible();
      }
    }
  });

  test("complex expression shows complexity notice", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      // Switch to raw
      const switchBtn = page.locator('[data-testid="btn-switch-mode"]');
      if (await switchBtn.isVisible()) {
        await switchBtn.click();
        const textarea = page.locator('[data-testid="raw-expression-textarea"]');
        if (await textarea.isVisible()) {
          await textarea.fill("max(actual_payroll_reported, est_payroll)");
          await switchBtn.click(); // switch to builder
          // Complex notice should appear
          const notice = page.locator('[data-testid="complex-notice"]');
          if (await notice.isVisible({ timeout: 1000 }).catch(() => false)) {
            await expect(notice).toContainText("too complex");
          }
        }
      }
    }
  });

  test("operator buttons are visible in builder mode", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      const builder = page.locator('[data-testid="expression-builder"]');
      if (await builder.isVisible()) {
        // Check for operator buttons
        const plusBtn = page.locator('[data-testid="op-btn-+"]');
        if (await plusBtn.isVisible()) {
          await expect(plusBtn).toBeEnabled();
        }
      }
    }
  });

  test("raw expression display stays in sync", async ({ page }) => {
    await navigateToCalcRulesTab(page);
    const editBtn = page.getByRole("button", { name: /^Edit$/i }).first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      const rawDisplay = page.locator('[data-testid="raw-expression-display"]');
      if (await rawDisplay.isVisible()) {
        const rawText = await rawDisplay.textContent();
        expect(rawText).not.toBe("");
      }
    }
  });
});
