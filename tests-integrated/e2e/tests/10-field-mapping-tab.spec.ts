/**
 * E2E Spec 10 — Field Mapping Tab (Tab 2) save and activate.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Field Mapping Tab", () => {
  test("Tab 2 renders FieldMappingTab for TENANT_ADMIN", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-2']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-2']");
    await adminPage.waitForSelector("[data-testid='field-mapping-tab']", { timeout: 10_000 });
    expect(await adminPage.locator("[data-testid='field-mapping-tab']").isVisible()).toBe(true);
  });

  test("Add Mapping button is visible", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-2']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-2']");
    await adminPage.waitForSelector("[data-testid='field-mapping-tab__add-row-btn']", { timeout: 10_000 });
    expect(await adminPage.locator("[data-testid='field-mapping-tab__add-row-btn']").isVisible()).toBe(true);
  });

  test("Add Mapping row appears after clicking Add Mapping", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-2']", { timeout: 15_000 });
    await adminPage.click("[data-testid='carrier-config-hub__tab-2']");
    await adminPage.waitForSelector("[data-testid='field-mapping-tab__add-row-btn']", { timeout: 10_000 });
    await adminPage.click("[data-testid='field-mapping-tab__add-row-btn']");
    await adminPage.waitForSelector("[data-testid='field-mapping-tab__pending-section']", { timeout: 5_000 });
    expect(await adminPage.locator("[data-testid='field-mapping-tab__pending-section']").isVisible()).toBe(true);
  });
});
