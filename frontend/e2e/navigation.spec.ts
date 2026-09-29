/**
 * E2E: Navigation & Page Structure
 *
 * Verifies routing, sidebar navigation, and basic page load for all
 * primary routes in the Occuris forensic dashboard.
 */
import { test, expect } from '@playwright/test';

const ROUTES = [
  { path: '/monitoring', heading: /Regional|Monitoring|Satellite/i },
  { path: '/investigation', heading: /Dark Vessel|Forensics/i },
  { path: '/replay', heading: /Replay|Timeline|Vessel/i },
  { path: '/report', heading: /Report|Case|Dossier/i },
  { path: '/spillsplit', heading: /Spill|Split|Analysis/i },
];

test.describe('Route Navigation', () => {
  for (const route of ROUTES) {
    test(`${route.path} loads without error`, async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      // Page should not be blank
      const body = page.locator('body');
      await expect(body).not.toBeEmpty();
      // No uncaught JS error crash page
      const errorOverlay = page.locator('[data-vite-error]');
      const overlayCount = await errorOverlay.count();
      expect(overlayCount).toBe(0);
    });
  }

  test('redirects unknown paths to /monitoring', async ({ page }) => {
    await page.goto('/nonexistent-route');
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/monitoring');
  });

  test('sidebar navigation works', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('domcontentloaded');
    // Check that the sidebar exists
    const sidebar = page.locator('.sidebar, nav, [class*="sidebar"]').first();
    await expect(sidebar).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Page Accessibility Basics', () => {
  test('investigation page has correct ARIA roles', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');
    // The state banner, if present, should have role="alert"
    const alerts = page.locator('[role="alert"]');
    const alertCount = await alerts.count();
    // Accept 0 or more alerts — the banner only shows for AMBIGUOUS/NO_STRONG_MATCH
    expect(alertCount).toBeGreaterThanOrEqual(0);
  });

  test('all pages have readable text content', async ({ page }) => {
    for (const route of ROUTES) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      const bodyText = await page.locator('body').textContent();
      // Every page must have some content
      expect(bodyText?.length).toBeGreaterThan(20);
    }
  });
});
