import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

const SCREENSHOT_DIR = resolve('..', 'docs', 'earth-intelligence-screenshots');

test.describe('Earth Change Intelligence Platform — E2E Journeys A–H', () => {
  test.beforeAll(() => {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
  });

  test('navigates all 8 Earth Change Intelligence features against real FastAPI backend', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('sar2action.lang', 'en');
    });

    await page.goto('/');
    await expect(page.locator('nav[aria-label="Main menu"], nav[aria-label="主選單"]')).toBeVisible();

    // Open Earth Intelligence workspace from topbar
    await page.getByRole('button', { name: /Earth Intelligence|地球變化智慧/i }).click();
    await expect(page.getByText(/GLOBAL EVENT CATALOG/i)).toBeVisible({ timeout: 15_000 });

    // Journey A: Global Event Catalog + Search/Filter
    await expect(page.getByText(/Typhoon Champi/i).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '01-earth-explorer-lens.png'), fullPage: false });

    // Journey B: Reality Lens switching (OBSERVED -> HYPOTHESES -> UNKNOWN -> NEXT_EVIDENCE)
    await page.getByRole('tab', { name: /B · HYPOTHESES/i }).click();
    await expect(page.getByText(/YL-CAND-03/i).first()).toBeVisible({ timeout: 10_000 });
    await page.getByRole('tab', { name: /C · UNKNOWN/i }).click();
    await page.getByRole('tab', { name: /D · NEXT EVIDENCE/i }).click();
    await page.getByRole('tab', { name: /A · OBSERVED/i }).click();

    // Journey C: Earth Memory Timeline
    await page.getByRole('tab', { name: 'Earth Memory' }).click();
    await expect(page.getByText(/NO OBSERVATION Gaps/i)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '02-earth-memory-timeline.png'), fullPage: false });

    // Journey D: Change Fingerprint
    await page.getByRole('tab', { name: 'Fingerprint' }).click();
    await expect(page.getByText(/CHANGE FINGERPRINT/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/NOT_AVAILABLE/i).first()).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '03-fingerprint-viewer.png'), fullPage: false });

    // Journey E: Scientific Hypothesis Arena + Run Experiment
    await page.getByRole('tab', { name: 'Hypothesis Arena' }).click();
    await expect(page.getByText(/Competing Hypothesis Arena/i)).toBeVisible({ timeout: 10_000 });
    const runExpBtn = page.getByRole('button', { name: /Run Experiment/i }).first();
    await expect(runExpBtn).toBeVisible({ timeout: 10_000 });
    await runExpBtn.click();
    await expect(page.getByText(/EXECUTED|NON_DISCRIMINATING|COMPLETED|EVALUATED|SUPPORTING|INCONCLUSIVE/i).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '04-hypothesis-arena.png'), fullPage: false });

    // Journey F: Evidence Gap Navigator (Stage-1 policy, no auto-download)
    await page.getByRole('tab', { name: 'Evidence Gaps' }).click();
    await expect(page.getByText(/EVIDENCE GAP NAVIGATOR/i).first()).toBeVisible({ timeout: 10_000 });
    const searchCatalogBtn = page.getByRole('button', { name: /Search Catalog/i }).first();
    if (await searchCatalogBtn.isVisible()) {
      await searchCatalogBtn.click();
      await expect(page.getByText(/compatible=|LIVE_CMR|OFFLINE|SKIPPED|CMR_UNAVAILABLE|zero scenes fabricated/i).first()).toBeVisible({ timeout: 15_000 });
    }

    // Journey G: AI Guided Discovery
    const queryInput = page.getByLabel('Guided discovery query');
    await queryInput.fill('Why did YL-CAND-03 change and is crop damage confirmed?');
    await page.getByRole('button', { name: /^Explore$/i }).click();
    await expect(page.getByText(/UNRESOLVED|NOT CONFIRMED|7\.55336/i).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '05-ai-guided-discovery.png'), fullPage: false });

    // Journey H: Planetary Story Player (7 chapters)
    await page.getByRole('tab', { name: 'Story' }).click();
    await page.getByRole('button', { name: 'Generate Story' }).click();
    await expect(page.getByText(/1 \/ 7/i).first()).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: resolve(SCREENSHOT_DIR, '06-planetary-story-player.png'), fullPage: false });
  });
});
