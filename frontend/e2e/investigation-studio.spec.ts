import { test, expect } from '@playwright/test';

test('satellite map, individual NISAR layers, and six functional story steps', async ({ page }) => {
  await page.goto('/studio');
  await expect(page.getByRole('navigation', { name: 'NASA story mode' }).getByRole('button')).toHaveCount(6);
  await page.getByRole('button', { name: '03 AGRICULTURAL RADAR CHANGE' }).click();
  await expect(page.getByRole('heading', { name: 'YL-CAND-01 · observed VH comparison' })).toBeVisible();
  await expect(page.locator('.maplibregl-canvas')).toBeVisible();
  await expect(page.locator('.studio-map')).toHaveAttribute('data-map-ready', 'true', { timeout: 20_000 });
  await page.getByRole('button', { name: 'Show radar layer' }).click();
  await page.getByLabel('NISAR observation').selectOption('POST');
  await page.getByLabel('NISAR polarization').selectOption('HV');
  await page.getByRole('slider', { name: 'Radar opacity' }).fill('45');
  await expect(page.getByText('110,287 QA-valid pixels', { exact: false })).toBeVisible();
  await expect(page.getByText('Cross-CRID radiometric equivalence', { exact: false }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Hide radar layer' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Fly from Earth → selected field' }).click();
  await expect(page.getByText('Camera: YL-CAND-01')).toBeVisible({ timeout: 15_000 });
  await page.getByLabel('Field candidate').selectOption('YL-CAND-03');
  await expect(page.getByRole('heading', { name: 'YL-CAND-03 · observed VH comparison' })).toBeVisible();
  for (const [label, target] of [
    ['01 DISASTER', 'studio-disaster'], ['02 SATELLITE OBSERVATION', 'studio-observations'],
    ['03 AGRICULTURAL RADAR CHANGE', 'studio-field-change'], ['04 AI INVESTIGATION', 'studio-question'],
    ['05 EVIDENCE VERIFICATION', 'studio-evidence'], ['06 HUMAN ACTION', 'studio-action'],
  ]) {
    const step = page.getByRole('button', { name: label });
    await step.click();
    await expect(step).toHaveAttribute('aria-current', 'step');
    await expect(page.locator(`#${target}`)).toBeVisible();
  }
});

test('five observed fields retain local warning timing, source QA, and scientific limits', async ({ page }) => {
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Investigation Studio' })).toBeVisible();
  await expect(page.getByLabel('Execution mode')).toHaveValue('RECORDED_DETERMINISTIC');
  await expect(page.getByLabel('Field candidate')).toHaveValue('YL-CAND-01');
  await expect(page.getByRole('img', { name: /Observed 2025 and 2026 VH/ })).toBeVisible();
  await expect(page.getByText('2026-10-23 05:51 Taiwan', { exact: false })).toBeVisible();
  await expect(page.getByText('inside the CWA land-warning interval', { exact: false })).toBeVisible();
  await expect(page.getByText('Scientific compatibility warning:', { exact: false })).toBeVisible();
  await expect(page.getByText('Scientific compatibility warning:', { exact: false })).toContainText('P05023');
  await expect(page.getByRole('button', { name: 'Export dossier JSON' })).toBeVisible();
  const selector = page.getByLabel('Field candidate');
  await expect(selector.locator('option')).toHaveCount(5);
  await selector.selectOption('YL-CAND-03');
  await expect(page.getByRole('heading', { name: 'YL-CAND-03 · observed VH comparison' })).toBeVisible();
  await expect(page.getByText('+7.553 dB').first()).toBeVisible();
  await expect(page.getByLabel('Ask the Scientific Agent')).toContainText('7.553 dB');
  await expect(page.getByText('Strict pre-warning change').first()).toBeVisible();
  await expect(page.getByText('Recorded deterministic report is scoped', { exact: false })).toBeVisible();
  await selector.selectOption('YL-CAND-04');
  await expect(page.getByText('+6.518 dB').first()).toBeVisible();
  await selector.selectOption('YL-CAND-05');
  await expect(page.getByRole('heading', { name: 'YL-CAND-05 · observed VH comparison' })).toBeVisible();
});

test('recorded Gemini and deterministic modes remain distinct', async ({ page }) => {
  await page.goto('/studio');
  await expect(page.getByText('historical deterministic run', { exact: false })).toBeVisible();
  await page.getByLabel('Execution mode').selectOption('RECORDED_GEMINI');
  await expect(page.getByText('historical Gemini run', { exact: false })).toBeVisible();
  await expect(page.getByText('Additional recorded Gemini five-field run', { exact: false })).toBeVisible();
  await page.getByText('Additional recorded Gemini five-field run', { exact: false }).click();
  await expect(page.getByText('This tool trace has no paired full report', { exact: false })).toBeVisible();
  await expect(page.getByRole('img', { name: /Evidence provenance graph/ })).toBeVisible();
});

test('live deterministic API runs for selected YL-CAND-03 and resolves its evidence', async ({ page }) => {
  test.skip(!process.env.SAR2ACTION_E2E_REAL_API, 'Requires running local backend with real V3 assets');
  await page.goto('/studio');
  await page.getByLabel('Field candidate').selectOption('YL-CAND-03');
  await page.getByLabel('Execution mode').selectOption('LIVE_DETERMINISTIC');
  const request = page.waitForRequest(req => req.url().includes('/api/agent/investigate-v3'));
  await page.getByRole('button', { name: 'Investigate with live deterministic API' }).click();
  const posted = await request;
  expect(posted.postDataJSON().field_id).toBe('YL-CAND-03');
  expect(posted.postDataJSON().agent_mode).toBe('deterministic');
  await expect(page.getByText('fresh API response after completion', { exact: false })).toBeVisible();
  await expect(page.getByText('vh_five_field_common_change', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('UNRESOLVED_REFERENCE:', { exact: false })).toHaveCount(0);
  await page.getByRole('button', { name: /E-YL-VH-/ }).first().click();
  await expect(page.getByText('Resolved Evidence · E-YL-VH-', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Observation timing' }).click();
  await expect(page.getByText('LIVE_DETERMINISTIC_TOOL', { exact: false }).first()).toBeVisible();
});

test('live Gemini mode makes a fresh bounded V3 request without promoting damage', async ({ page }) => {
  test.setTimeout(90_000);
  test.skip(!process.env.SAR2ACTION_E2E_REAL_GEMINI, 'Requires a running local backend with the user Gemini credential');
  await page.goto('/studio');
  await page.getByLabel('Field candidate').selectOption('YL-CAND-03');
  await page.getByLabel('Execution mode').selectOption('LIVE_GEMINI');
  const request = page.waitForRequest(req => req.url().includes('/api/agent/investigate-v3'));
  await page.getByRole('button', { name: 'Investigate with live Gemini API' }).click();
  const posted = await request;
  expect(posted.postDataJSON().field_id).toBe('YL-CAND-03');
  expect(posted.postDataJSON().agent_mode).toBe('gemini');
  await expect(page.getByText('fresh API response after completion', { exact: false })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('GeminiModelProvider.choose_gis_tools', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('UNRESOLVED', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('CONFIRMED DAMAGE', { exact: false })).toHaveCount(0);
});
