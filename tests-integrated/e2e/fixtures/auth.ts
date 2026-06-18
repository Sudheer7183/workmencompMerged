/**
 * Playwright auth fixture — handles Keycloak OIDC login for each dev user.
 * All spec files import from this fixture to get authenticated pages.
 */
import { test as base, expect, Page } from "@playwright/test";

const KEYCLOAK_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8080";
const REALM = "audit-platform";

export type UserRole = "TENANT_ADMIN" | "AUDITOR" | "REVIEWER";

interface UserCredentials {
  username: string;
  password: string;
  role: UserRole;
}

const DEV_USERS: Record<UserRole, UserCredentials> = {
  TENANT_ADMIN: { username: "demo-admin",    password: "admin123",    role: "TENANT_ADMIN" },
  AUDITOR:      { username: "demo-auditor",  password: "auditor123",  role: "AUDITOR"      },
  REVIEWER:     { username: "demo-reviewer", password: "reviewer123", role: "REVIEWER"     },
};

/**
 * Logs in via the application's login page (which redirects to Keycloak).
 * Returns the authenticated Page.
 */
async function loginAs(page: Page, role: UserRole): Promise<void> {
  const { username, password } = DEV_USERS[role];
  await page.goto("/");

  // Wait for Keycloak redirect
  await page.waitForURL(/keycloak|localhost:8080|\/login/, { timeout: 30_000 });

  // Fill Keycloak login form
  await page.fill("#username", username);
  await page.fill("#password", password);
  await page.click('[type="submit"]');

  // Wait for app to load after OAuth callback
  await page.waitForURL(/localhost:5173/, { timeout: 30_000 });
  await page.waitForSelector('[data-testid="dashboard__kpi-cards"], [data-testid="onboarding-wizard"]', {
    timeout: 30_000,
  });
}

// Extended test fixture with role-based page helpers
export const test = base.extend<{
  adminPage: Page;
  auditorPage: Page;
  reviewerPage: Page;
}>({
  adminPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, "TENANT_ADMIN");
    await use(page);
    await context.close();
  },
  auditorPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, "AUDITOR");
    await use(page);
    await context.close();
  },
  reviewerPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, "REVIEWER");
    await use(page);
    await context.close();
  },
});

export { expect };
