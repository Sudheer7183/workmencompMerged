/**
 * E2E Spec 08 — Calc rules editor two-step approval.
 */
import { test, expect } from "../fixtures/auth";

test.describe("Calc Rules Editor", () => {
  test("carrier config hub renders for TENANT_ADMIN", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub']", { timeout: 15_000 });
    expect(await adminPage.locator("[data-testid='carrier-config-hub__tabs']").isVisible()).toBe(true);
  });

  test("Tab 3 (Calc Engine) is active by default", async ({ adminPage }) => {
    await adminPage.goto("/admin/carriers/1/config");
    await adminPage.waitForSelector("[data-testid='carrier-config-hub__tab-3']", { timeout: 15_000 });
    const tab3 = adminPage.locator("[data-testid='carrier-config-hub__tab-3']");
    const classes = await tab3.getAttribute("class") ?? "";
    expect(classes).toContain("active");
  });
});
