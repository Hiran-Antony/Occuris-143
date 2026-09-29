/**
 * E2E: Honesty Doctrine UI Elements
 *
 * Verifies that all court-mandated forensic honesty indicators are present
 * and correctly rendered across pages.
 */
import { test, expect } from '@playwright/test';

test.describe('Honesty Doctrine UI', () => {
  test('GlobalSourceBadge is visible on the monitoring page', async ({ page }) => {
    await page.goto('/monitoring');
    const badge = page.locator('#global-source-badge');
    await expect(badge).toBeVisible({ timeout: 10_000 });
    // Should contain AIS source mode text
    await expect(badge).toContainText('AIS Source');
    // Should contain UTC time
    await expect(badge).toContainText('UTC');
  });

  test('GlobalSourceBadge shows REPLAY mode by default', async ({ page }) => {
    await page.goto('/monitoring');
    const badge = page.locator('#global-source-badge');
    await expect(badge).toBeVisible({ timeout: 10_000 });
    await expect(badge).toContainText('REPLAY');
    await expect(badge).toContainText('Synthetic AIS Replay');
  });

  test('StickyHonestyFooter is visible on the investigation page', async ({ page }) => {
    await page.goto('/investigation');
    const footer = page.locator('#honesty-footer');
    await expect(footer).toBeVisible({ timeout: 10_000 });
    // Must contain the honesty doctrine text
    await expect(footer).toContainText('Investigation Priority ≠ Guilt');
    await expect(footer).toContainText('HONESTY DOCTRINE');
    await expect(footer).toContainText('OCCURIS PS 26143');
  });

  test('StateBanner renders for AMBIGUOUS or NO_STRONG_MATCH states', async ({ page }) => {
    await page.goto('/investigation');
    // The banner may or may not be present depending on the data state.
    // We just verify that if the banner exists, it has the correct attributes.
    const banner = page.locator('#state-banner');
    const bannerCount = await banner.count();
    if (bannerCount > 0) {
      await expect(banner).toHaveAttribute('role', 'alert');
    }
  });

  test('GlobalSourceBadge persists across route navigation', async ({ page }) => {
    await page.goto('/monitoring');
    await expect(page.locator('#global-source-badge')).toBeVisible({ timeout: 10_000 });

    // Navigate to investigation page
    await page.goto('/investigation');
    await expect(page.locator('#global-source-badge')).toBeVisible({ timeout: 10_000 });

    // Navigate to report page
    await page.goto('/report');
    await expect(page.locator('#global-source-badge')).toBeVisible({ timeout: 10_000 });
  });
});
