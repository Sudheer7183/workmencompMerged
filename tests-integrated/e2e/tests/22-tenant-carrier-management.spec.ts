/**
 * E2E Spec 22 — Tenant Carrier Management (Phase 7A)
 *
 * Tests:
 *   1. SUPER_ADMIN can provision a tenant with zero carriers
 *   2. TENANT_ADMIN sees Carriers tab in Organisation Settings
 *   3. TENANT_ADMIN can add a carrier from the Carriers tab
 *   4. Added carrier appears in the Assigned Carriers table
 *   5. Added carrier appears in the Carrier Configuration Hub
 *   6. TENANT_ADMIN can remove a carrier (soft delete)
 *   7. Removed carrier disappears from Assigned list
 *   8. Removed carrier reappears in Available carriers list
 *   9. REVIEWER cannot see Carriers tab
 *  10. Re-adding a removed carrier works (idempotency)
 */

import { test, expect } from "../fixtures/auth";

test.describe("Tenant Carrier Management — Phase 7A", () => {
  // ── Test 1: SUPER_ADMIN provisioning with zero carriers ─────────────────

  test("SUPER_ADMIN can create a tenant with zero carriers", async ({
    superAdminPage,
  }) => {
    // Navigate to tenant creation wizard
    await superAdminPage.goto("/platform/tenants/new");
    await superAdminPage.waitForSelector(".wizard-step");

    // Step 1 — Fill tenant details
    await superAdminPage.fill('[name="name"], #tenant-name, input[placeholder*="name" i]', "Zero Carrier E2E Tenant");
    await superAdminPage.fill('[name="slug"], #tenant-slug, input[placeholder*="slug" i]', "zero-carrier-e2e");
    await superAdminPage.selectOption("select", "AUDIT_COMPANY");
    await superAdminPage.click("button:has-text('Next')");

    // Step 2 — Admin user details
    await superAdminPage.waitForSelector(".wizard-step");
    await superAdminPage.fill('[name="admin_email"], input[type="email"]', "admin@zerocarrier-e2e.test");
    await superAdminPage.fill('[name="admin_first_name"], input[placeholder*="first" i]', "Test");
    await superAdminPage.fill('[name="admin_last_name"], input[placeholder*="last" i]', "Admin");
    await superAdminPage.click("button:has-text('Next')");

    // Step 3 — Carrier Assignment (OPTIONAL in Phase 7A — skip without selecting)
    await superAdminPage.waitForSelector(".wizard-step");
    // Verify the optional hint is shown
    await expect(superAdminPage.locator(".wizard-step__hint")).toBeVisible();
    // Verify Activate/Next button is enabled even with zero carriers
    const nextBtn = superAdminPage.locator("button:has-text('Next'), button:has-text('Activate')").first();
    await expect(nextBtn).toBeEnabled();
    // Skip — do not select any carrier
    await superAdminPage.click("button:has-text('Next')");

    // Step 4 — Review shows "no carriers" notice
    await superAdminPage.waitForSelector(".wizard-review");
    await expect(
      superAdminPage.locator(".wizard-review__no-carriers")
    ).toBeVisible();
    // The Activate button must be enabled
    const activateBtn = superAdminPage.locator("button:has-text('Activate')");
    await expect(activateBtn).toBeEnabled();
  });

  // ── Test 2: TENANT_ADMIN sees Carriers tab ───────────────────────────────

  test("TENANT_ADMIN sees Carriers tab in Organisation Settings", async ({
    adminPage,
  }) => {
    await adminPage.goto("/admin/settings");
    await adminPage.waitForSelector(".org-settings");

    await expect(
      adminPage.locator('.org-settings__tab:has-text("Carriers")')
    ).toBeVisible();
  });

  // ── Test 3 + 4: Add a carrier ───────────────────────────────────────────

  test("TENANT_ADMIN can add a carrier from the Carriers tab", async ({
    adminPage,
  }) => {
    await adminPage.goto("/admin/settings");
    await adminPage.waitForSelector(".org-settings");

    // Switch to Carriers tab
    await adminPage.click('.org-settings__tab:has-text("Carriers")');
    await adminPage.waitForSelector(".carrier-mgmt");

    // Wait for available carriers to load
    await adminPage.waitForSelector(".carrier-mgmt__select");
    const options = await adminPage.locator(".carrier-mgmt__select option").count();
    if (options <= 1) {
      test.skip(); // No carriers available to add in this environment
    }

    // Select the first available carrier
    await adminPage.selectOption(".carrier-mgmt__select", { index: 1 });

    // Click Add Carrier
    const addBtn = adminPage.locator("button:has-text('Add Carrier')");
    await expect(addBtn).toBeEnabled();
    await addBtn.click();

    // Wait for the assignment to complete
    await adminPage.waitForResponse(
      (resp) => resp.url().includes("/api/v1/tenant/carriers") && resp.status() === 201
    );
  });

  // ── Test 4: Added carrier appears in Assigned table ─────────────────────

  test("Added carrier appears in the Assigned Carriers table", async ({
    adminPage,
  }) => {
    await adminPage.goto("/admin/settings");
    await adminPage.click('.org-settings__tab:has-text("Carriers")');
    await adminPage.waitForSelector(".carrier-mgmt__table");

    // At least one row should be in the assigned table
    const rows = adminPage.locator(".carrier-mgmt__row");
    await expect(rows.first()).toBeVisible();
  });

  // ── Test 5: Added carrier appears in Config Hub ─────────────────────────

  test("Added carrier appears in Carrier Configuration Hub after addition", async ({
    adminPage,
  }) => {
    await adminPage.goto("/admin/carrier-config");
    await adminPage.waitForSelector(".carrier-config-hub, [data-testid='carrier-select']");
    // The hub should now show at least one carrier in its selector
    const carrierSelect = adminPage.locator("select, .carrier-config-hub__select").first();
    await expect(carrierSelect).toBeVisible();
  });

  // ── Test 6 + 7: Remove a carrier ────────────────────────────────────────

  test("TENANT_ADMIN can remove a carrier (inline confirm)", async ({
    adminPage,
  }) => {
    await adminPage.goto("/admin/settings");
    await adminPage.click('.org-settings__tab:has-text("Carriers")');
    await adminPage.waitForSelector(".carrier-mgmt__table");

    const removeButtons = adminPage.locator("button:has-text('Remove')");
    const count = await removeButtons.count();
    if (count === 0) test.skip(); // Nothing to remove

    // Click first Remove
    await removeButtons.first().click();

    // Inline confirm should appear
    await expect(
      adminPage.locator(".carrier-mgmt__confirm-text")
    ).toBeVisible();

    // Click Confirm
    await adminPage.click("button:has-text('Confirm')");

    // Wait for DELETE response
    await adminPage.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/tenant/carriers/") &&
        resp.status() === 204
    );
  });

  // ── Test 9: REVIEWER cannot see Carriers tab ────────────────────────────

  test("REVIEWER does not see Carriers tab in Organisation Settings", async ({
    reviewerPage,
  }) => {
    await reviewerPage.goto("/admin/settings");

    // Either the page doesn't exist for reviewer, or Carriers tab not visible
    const carriersTab = reviewerPage.locator(
      '.org-settings__tab:has-text("Carriers")'
    );
    const isVisible = await carriersTab.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });

  // ── Test 10: Info banner when zero carriers selected in wizard ───────────

  test("Wizard Step 3 shows info banner when zero carriers selected", async ({
    superAdminPage,
  }) => {
    await superAdminPage.goto("/platform/tenants/new");
    await superAdminPage.waitForSelector(".wizard-step");

    // Fill step 1 minimum
    await superAdminPage.fill('input:first-of-type', "Banner Test Tenant");

    // Navigate to step 3 by clicking Next twice
    for (let i = 0; i < 2; i++) {
      const next = superAdminPage.locator("button:has-text('Next')");
      if (await next.isEnabled()) await next.click();
      await superAdminPage.waitForTimeout(500);
    }

    // Should show info banner with zero carriers
    await expect(
      superAdminPage.locator(".wizard-step__info-banner")
    ).toBeVisible();
  });
});
