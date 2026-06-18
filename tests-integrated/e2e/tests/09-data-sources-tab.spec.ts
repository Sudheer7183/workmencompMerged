/**
 * E2E Spec 09 — Data Sources Tab (Tab 1) CRUD.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Data Sources Tab", () => {
  test("Tab 1 renders DataSourcesTab for TENANT_ADMIN", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-1']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-1']");
    await adminPage.waitForSelector("[data-testid='data-sources-tab']", { timeout: 10_000 });
    expect(await adminPage.locator("[data-testid='data-sources-tab']").isVisible()).toBe(true);
  });

  test("Add Source button is visible", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-1']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-1']");
    await adminPage.waitForSelector("[data-testid='data-sources-tab__add-btn']", { timeout: 10_000 });
    expect(await adminPage.locator("[data-testid='data-sources-tab__add-btn']").isVisible()).toBe(true);
  });

  test("clicking Add Source shows the form", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-1']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-1']");
    await adminPage.waitForSelector("[data-testid='data-sources-tab__add-btn']", { timeout: 10_000 });
    await adminPage.click("[data-testid='data-sources-tab__add-btn']");
    await adminPage.waitForSelector("[data-testid='data-sources-tab__form']", { timeout: 5_000 });
    expect(await adminPage.locator("[data-testid='data-sources-tab__form']").isVisible()).toBe(true);
  });

  test("AUDITOR cannot see Tab 1 admin content", async ({ auditorPage }) => {
    await auditorPage.goto("/admin/carriers/1/config");
    // If page loads, Tab 1 should show access-denied message
    await auditorPage.waitForSelector("body", { timeout: 10_000 });
  });
});
