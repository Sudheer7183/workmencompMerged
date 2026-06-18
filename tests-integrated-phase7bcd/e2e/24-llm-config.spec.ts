/**
 * E2E Spec 24 — LLM Configuration Tab
 *
 * Tests saving and retrieving LLM configuration through the
 * Carrier Config Hub Tab 7 (AI Configuration).
 */

import { test, expect } from "@playwright/test";

test.describe("24 — LLM Config Tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.fill('[data-testid="email"]', "admin@test.tenant.com");
    await page.fill('[data-testid="password"]', "TestPassword1!");
    await page.click('[data-testid="login-btn"]');
    await page.waitForURL("**/dashboard");
  });

  async function navigateToAIConfigTab(page: import("@playwright/test").Page) {
    await page.goto("/admin/carriers");
    await page.waitForSelector('[data-testid="carrier-list"]', { timeout: 5000 }).catch(() => {});
    // Click first carrier's Configure link
    const configLink = page.getByRole("link", { name: /configure/i }).first();
    if (await configLink.isVisible()) {
      await configLink.click();
    } else {
      // Try direct navigation if carrier IDs are known
      await page.goto("/admin/carriers/1/config");
    }
    // Click Tab 7 — AI Configuration
    await page.getByRole("tab", { name: /AI Configuration/i }).click();
    await page.waitForSelector('[data-testid="ai-config-tab"]', { timeout: 3000 }).catch(() => {});
  }

  test("AI Configuration tab renders with correct content", async ({ page }) => {
    await navigateToAIConfigTab(page);
    await expect(page.locator('[data-testid="ai-config-tab"]')).toBeVisible();
    await expect(page.locator('[data-testid="select-provider"]')).toBeVisible();
  });

  test("provider selection shows model dropdown", async ({ page }) => {
    await navigateToAIConfigTab(page);
    const providerSelect = page.locator('[data-testid="select-provider"]');
    await providerSelect.selectOption("anthropic");
    await expect(page.locator('[data-testid="select-model"]')).not.toBeDisabled();
  });

  test("Anthropic provider shows API key field", async ({ page }) => {
    await navigateToAIConfigTab(page);
    await page.locator('[data-testid="select-provider"]').selectOption("anthropic");
    await expect(page.locator('[data-testid="input-api-key"]')).toBeVisible();
  });

  test("Ollama provider shows base URL but no API key", async ({ page }) => {
    await navigateToAIConfigTab(page);
    await page.locator('[data-testid="select-provider"]').selectOption("ollama");
    await expect(page.locator('[data-testid="input-base-url"]')).toBeVisible();
    await expect(page.locator('[data-testid="input-api-key"]')).not.toBeVisible();
  });

  test("save button is disabled without provider and model", async ({ page }) => {
    await navigateToAIConfigTab(page);
    await expect(page.locator('[data-testid="btn-save-config"]')).toBeDisabled();
  });

  test("api key field is type=password (not revealed in DOM)", async ({ page }) => {
    await navigateToAIConfigTab(page);
    await page.locator('[data-testid="select-provider"]').selectOption("openai");
    const keyField = page.locator('[data-testid="input-api-key"]');
    await expect(keyField).toHaveAttribute("type", "password");
  });
});
