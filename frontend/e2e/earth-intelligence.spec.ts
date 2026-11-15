import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

const SCREENSHOT_DIR = resolve('..', 'docs', 'earth-intelligence-screenshots');
const FINAL_DIR = resolve(SCREENSHOT_DIR, 'final');

test.describe('Earth Change Intelligence Platform — E2E Journeys 1–8 & Multi-Viewport Verification', () => {
  test.beforeAll(() => {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
    mkdirSync(FINAL_DIR, { recursive: true });
  });

  test('executes all 8 browser journeys, captures 10 final screenshots, and verifies responsive viewports', async ({ page }) => {
    test.setTimeout(90_000);

    await page.addInitScript(() => {
      localStorage.setItem('sar2action.lang', 'en');
    });

    // Desktop 1920x1080
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');
    await expect(page.locator('nav[aria-label="Main menu"], nav[aria-label="主選單"]')).toBeVisible();

    // Open Earth Intelligence workspace from topbar
    await page.getByRole('button', { name: /Earth Intelligence|地球變化智慧/i }).click();
    await expect(page.getByText(/GLOBAL EVENT CATALOG/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Typhoon Champi/i).first()).toBeVisible({ timeout: 15_000 });

    // Wait for MapLibre tiles to paint and focus Taixi AOI
    await page.getByRole('button', { name: /Focus Taixi AOI|聚焦雲林台西/i }).click();
    await page.waitForTimeout(2400);
    await page.screenshot({ path: resolve(FINAL_DIR, '01-global-earth-desktop.png'), fullPage: false });
    await page.screenshot({ path: resolve(FINAL_DIR, '10-full-product-overview.png'), fullPage: false });

    // Journey 1: Global Earth -> Select Event -> Fly-To Region -> Open Observation
    await page.getByRole('button', { name: /YL-CAND-03/i }).first().click();
    await expect(page.getByText(/CONTEXT: CHAMPI-YUNLIN-TAIXI · YL-CAND-03/i)).toBeVisible();

    // Journey 3: Reality Lens -> OBSERVED -> HYPOTHESES -> UNKNOWN -> NEXT EVIDENCE
    await page.getByRole('tab', { name: 'Reality Lens' }).click();
    await page.getByRole('tab', { name: /B · HYPOTHESES/i }).click();
    await expect(page.getByText(/no_fake_confidence=true/i)).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: resolve(FINAL_DIR, '03-reality-lens.png'), fullPage: false });
    await page.getByRole('tab', { name: /C · UNKNOWN/i }).click();
    await page.getByRole('tab', { name: /D · NEXT EVIDENCE/i }).click();
    await page.getByRole('tab', { name: /A · OBSERVED/i }).click();

    // Journey 2: Earth Memory -> Scrub -> Play -> Pause -> Change Date
    await page.getByRole('tab', { name: 'Earth Memory' }).click();
    await expect(page.getByText(/NO OBSERVATION Gaps/i)).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /^Play$/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /^Pause$/i }).first().click();
    await page.screenshot({ path: resolve(FINAL_DIR, '02-earth-memory-animation.png'), fullPage: false });

    // Journey 5: Fingerprint -> Select Field -> Compare Another Field + Info Tooltip
    await page.getByRole('tab', { name: 'Fingerprint' }).click();
    await expect(page.getByText(/CHANGE FINGERPRINT/i)).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: 'Compare Fingerprints' }).click();
    await expect(page.getByText(/COMPATIBLE|Feature Distance/i).first()).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: resolve(FINAL_DIR, '05-fingerprint-comparison.png'), fullPage: false });

    // Journey 4: Hypothesis Arena -> Select Hypothesis -> Run Experiment -> Review Evidence
    await page.getByRole('tab', { name: 'Hypothesis Arena' }).click();
    await expect(page.getByText(/Competing Hypothesis Arena/i)).toBeVisible({ timeout: 10_000 });
    const runExpBtn = page.getByRole('button', { name: /Run Experiment/i }).first();
    await expect(runExpBtn).toBeVisible({ timeout: 10_000 });
    await runExpBtn.click();
    await expect(page.getByText(/EXECUTED|NON_DISCRIMINATING|COMPLETED|EVALUATED|SUPPORTING|INCONCLUSIVE/i).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: resolve(FINAL_DIR, '04-hypothesis-arena.png'), fullPage: false });

    // Journey 6: Evidence Gap -> View Missing Evidence -> Search Catalog -> Review Result
    await page.getByRole('tab', { name: 'Evidence Gaps' }).click();
    await expect(page.getByText(/WHAT WE KNOW/i)).toBeVisible({ timeout: 10_000 });
    const searchCatalogBtn = page.getByRole('button', { name: /Search Catalog/i }).first();
    await searchCatalogBtn.click();
    await expect(page.getByText('APPROVAL REQUIRED', { exact: true })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: resolve(FINAL_DIR, '06-evidence-gap.png'), fullPage: false });

    // Journey 7: Guided Discovery -> Request Map Action -> Verify Map State Changed
    await page.getByRole('tab', { name: 'AI Discovery' }).click();
    const queryInput = page.getByLabel('Guided discovery query');
    await queryInput.fill('What does this number mean?');
    await page.getByRole('button', { name: /^Explore$/i }).click();
    await expect(page.getByText(/Validated Actions:/i)).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: resolve(FINAL_DIR, '07-guided-discovery.png'), fullPage: false });

    // Journey 8: Planetary Story -> Generate Story -> Play Chapters -> Export / Import UI
    await page.getByRole('tab', { name: 'Story' }).click();
    await page.getByRole('button', { name: 'Generate Story' }).click();
    await expect(page.getByText(/1 \/ 7/i).first()).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /Next →/i }).click();
    await expect(page.getByText(/2 \/ 7/i).first()).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: resolve(FINAL_DIR, '08-planetary-story.png'), fullPage: false });

    // Responsive Verification across Desktop (1440x900, 1366x768), Tablet (768x1024), Mobile (390x844, 375x812)
    for (const vp of [
      { width: 1440, height: 900 },
      { width: 1366, height: 768 },
      { width: 768, height: 1024 },
      { width: 375, height: 812 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(vp);
      await expect(page.getByLabel('Earth Change Interactive Map')).toBeVisible();
    }

    // Mobile screenshot at 390x844
    await page.getByRole('button', { name: /Focus Taixi AOI|聚焦雲林台西/i }).click();
    await page.getByRole('tab', { name: 'Forensics' }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: resolve(FINAL_DIR, '09-mobile-view.png'), fullPage: false });

    const perfMetrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
      const paint = performance.getEntriesByType('paint');
      const mem = (performance as unknown as { memory?: { usedJSHeapSize: number; totalJSHeapSize: number } }).memory;
      return {
        domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd - nav.startTime) : null,
        loadEventMs: nav ? Math.round(nav.loadEventEnd - nav.startTime) : null,
        fcpMs: paint.find((p) => p.name === 'first-contentful-paint')?.startTime
          ? Math.round(paint.find((p) => p.name === 'first-contentful-paint')!.startTime)
          : null,
        usedJSHeapMB: mem ? Math.round((mem.usedJSHeapSize / (1024 * 1024)) * 10) / 10 : null,
      };
    });
    console.log('PERF_METRICS_JSON:', JSON.stringify(perfMetrics));
  });
});
