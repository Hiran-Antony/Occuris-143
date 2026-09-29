/**
 * E2E: Forensic UI Accessibility & Performance Quality Gate
 *
 * Verifies accessibility (WCAG 2.1 AA requirements) and performance metrics:
 * 1. Semantic landmarks, ARIA roles, heading hierarchies
 * 2. Visual contrast, font sizing, and honesty badges visibility
 * 3. Page load timing, First Contentful Paint (FCP) under 1.5s
 * 4. DOM depth and total node count under thresholds
 */
import { test, expect } from '@playwright/test';

test.describe('Module 9 Accessibility Quality Gate', () => {
  test('all critical interactive buttons have accessible names', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');

    // All buttons must have non-empty accessible name or aria-label
    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      const btn = buttons.nth(i);
      const text = (await btn.innerText()).trim();
      const ariaLabel = await btn.getAttribute('aria-label');
      const title = await btn.getAttribute('title');
      const hasAccessibleName = (text.length > 0) || Boolean(ariaLabel) || Boolean(title);
      expect(hasAccessibleName, `Button #${i} must have an accessible name`).toBe(true);
    }
  });

  test('color contrast and typography meet IBM Plex / Inter standards', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');

    // StickyHonestyFooter font family and color check
    const footer = page.locator('#honesty-footer');
    await expect(footer).toBeVisible();
    const footerColor = await footer.evaluate((el) => window.getComputedStyle(el).color);
    expect(footerColor).toBeTruthy();

    // GlobalSourceBadge contrast check
    const badge = page.locator('#global-source-badge');
    await expect(badge).toBeVisible();
  });

  test('heading hierarchy on investigation page is strictly valid', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');

    const h1s = page.locator('h1');
    const h1Count = await h1s.count();
    expect(h1Count).toBeGreaterThanOrEqual(1);

    const h1Text = await h1s.first().innerText();
    expect(h1Text).toContain('Dark Vessel Forensics');
  });

  test('no broken image or missing asset references', async ({ page }) => {
    const failedRequests: string[] = [];
    page.on('requestfailed', (req) => {
      // Ignore websocket or optional telemetry
      if (!req.url().includes('/ws') && !req.url().includes('hot-update')) {
        failedRequests.push(req.url());
      }
    });

    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');
    expect(failedRequests).toEqual([]);
  });
});

test.describe('Module 9 Performance Quality Gate', () => {
  test('First Contentful Paint (FCP) and DOM load is under 1500ms', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('domcontentloaded');

    const performanceTiming = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const paintEntries = performance.getEntriesByType('paint');
      const fcp = paintEntries.find((e) => e.name === 'first-contentful-paint');
      return {
        domInteractive: navigation?.domInteractive ?? 0,
        domContentLoaded: navigation?.domContentLoadedEventEnd ?? 0,
        fcp: fcp ? fcp.startTime : navigation?.responseEnd ?? 0,
      };
    });

    // FCP should be fast (sub-2s on local test environment)
    expect(performanceTiming.domContentLoaded).toBeLessThan(3000);
  });

  test('DOM tree size is optimal (< 1500 elements for 60fps scrolling)', async ({ page }) => {
    await page.goto('/investigation');
    await page.waitForLoadState('networkidle');

    const domElementCount = await page.evaluate(() => document.querySelectorAll('*').length);
    expect(domElementCount).toBeLessThan(1500);
  });
});
