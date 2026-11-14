import { test, expect } from '@playwright/test';

test('release Demo A opens flagship cached evidence without synthetic substitution', async ({ page }) => {
  await page.goto('/?demo=A');
  await expect(page.getByLabel('Data mode')).toHaveValue('cache');
  await expect(page.getByLabel('Agent execution')).toHaveValue('real');
  await expect(page.getByTestId('preset-aoi-AOI-OKI-04')).toHaveClass(/active|selected/);
  await expect(page.getByText(/PROVENANCE NOT VERIFIED/).first()).toBeVisible();
});

test('release Demo B opens an explicitly synthetic investigation', async ({ page }) => {
  await page.goto('/?demo=B');
  await expect(page.getByLabel('Data mode')).toHaveValue('fixture');
  await expect(page.getByLabel('Agent execution')).toHaveValue('deterministic');
  await expect(page.getByText('SIMULATED DATA — NOT NASA OBSERVATIONS').first()).toBeVisible();
});

test('synthetic AOI ranking drives map, evidence, fingerprint and five-scene story', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('region', { name: 'AI Earth Investigator' })).toBeVisible();
  await expect(page.getByText(/LIVE NISAR DATA · BLOCKED: B-team change raster\/manifest missing/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeEnabled();
  await page.getByLabel('Data mode').selectOption('fixture');
  await page.getByLabel('Ask about this area').fill('找出目前區域變化最大的三個地方');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.locator('.rank-card')).toHaveCount(3);
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-ranked-region-count', '3');
  await expect(page.locator('.agent-region-rect')).toHaveCount(3);
  await expect(page.locator('.agent-focus-rect')).toHaveCount(1);
  await expect(page.getByText('SIMULATED DATA — NOT NASA OBSERVATIONS').first()).toBeVisible();
  await page.locator('.rank-card').nth(1).getByRole('button', { name: 'Focus on Map' }).click();
  await expect(page.locator('.rank-card.active')).toHaveCount(1);
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-agent-focus-bbox', /.+/);
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-maplibre-focus-applied', /.+/);
  await page.locator('.rank-card.active').getByRole('button', { name: 'Inspect Evidence' }).click();
  await expect(page.locator('.agent-evidence-card')).toContainText('synthetic');
  await page.locator('.rank-card.active').getByRole('button', { name: 'View Radar Fingerprint' }).click();
  await expect(page.locator('#agent-region-fingerprint')).toContainText('Pairwise HV');
  await page.getByRole('button', { name: 'Compare Regions' }).click();
  await expect(page.getByText(/Rank 1 minus rank 2/)).toBeVisible();
  await page.getByRole('button', { name: 'Generate story' }).click();
  await expect(page.locator('.agent-story nav button')).toHaveCount(5);
  await page.locator('.agent-story nav button').nth(2).click();
  await expect(page.locator('.agent-story nav button').nth(2)).toHaveAttribute('aria-current', 'step');
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-agent-focus-bbox', /.+/);
  await page.screenshot({ path: testInfo.outputPath('agent-spatial-story.png'), fullPage: true });
  await page.getByTestId('preset-aoi-AOI-OKI-02').click();
  await expect(page.locator('.agent-story')).toContainText('(Stale)');
  await expect(page.locator('.rank-card')).toHaveCount(0);
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-ranked-region-count', '0');
});

test('natural-language comparison and story execute their tools', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeEnabled();
  await page.getByLabel('Data mode').selectOption('fixture');
  await page.getByLabel('Ask about this area').fill('比較第一個與第二個區域。');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.getByText(/Rank 1 minus rank 2 median absolute change/)).toBeVisible();
  await page.getByLabel('Ask about this area').fill('產生一份可以分享的地表變化故事。');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.locator('.agent-story nav button')).toHaveCount(5);
  await expect(page.locator('.agent-story')).toContainText('研究區域');
});

test('B-team cached AOI fingerprint, evidence and story stay scoped to the selected AOI', async ({ page }, testInfo) => {
  await page.goto('/');
  await page.getByLabel('Data mode').selectOption('cache');
  await page.getByTestId('preset-aoi-AOI-OKI-04').click();
  await expect(page.getByText(/B-team cached fingerprint loaded/)).toBeVisible();
  await page.getByLabel('Ask about this area').fill('分析這個 AOI 的 HH 與 HV 變化，顯示證據。');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('-0.2128');
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('-0.2056');
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('E-FLAGSHIP-OKI-004');
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('median of valid pixelwise');
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('NOT_ASSESSED');
  await page.getByTestId('cached-radar-fingerprint').getByRole('button', { name: 'Inspect Evidence' }).click();
  await expect(page.getByTestId('cached-evidence-card')).toContainText('E-FLAGSHIP-OKI-004');
  await expect(page.getByTestId('cached-evidence-card')).toContainText('Provenance Pending');
  await expect(page.getByTestId('cached-evidence-card')).toContainText('Verified Source: No');
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-agent-focus-bbox', /.+/);
  await page.getByRole('button', { name: 'Generate story' }).click();
  await expect(page.locator('.agent-story nav button')).toHaveCount(5);
  await expect(page.locator('.agent-story')).toContainText('E-FLAGSHIP-OKI-004');
  await page.locator('.agent-story nav button').nth(3).click();
  await expect(page.locator('.agent-story nav button').nth(3)).toHaveAttribute('aria-current', 'step');
  await page.screenshot({ path: testInfo.outputPath('cached-evidence-story.png'), fullPage: true });
  await page.getByTestId('preset-aoi-AOI-OKI-02').click();
  await expect(page.locator('.agent-story')).toContainText('(Stale)');
  await expect(page.getByTestId('cached-radar-fingerprint')).toHaveCount(0);
});

test('real Gemini investigates B-team cached evidence in the browser', async ({ page }) => {
  test.setTimeout(90_000);
  const status = await (await page.request.get('/api/agent/status')).json();
  test.skip(status.agent?.provider !== 'gemini', 'Requires the Gemini backend profile');
  await page.goto('/');
  await page.getByLabel('Data mode').selectOption('cache');
  await page.getByTestId('preset-aoi-AOI-OKI-04').click();
  await page.getByLabel('Agent execution').selectOption('real');
  await page.getByLabel('Ask about this area').fill('分析 AOI-OKI-04 的 HH/HV 雷達變化，給我證據，這能確認泥炭火災嗎？');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.getByText(/Real AI Analysis · gemini/)).toBeVisible({ timeout: 65_000 });
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('-0.2128');
  await expect(page.getByTestId('cached-radar-fingerprint')).toContainText('-0.2056');
  await expect(page.getByText(/cannot confirm wildfire/).first()).toBeVisible();
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-maplibre-focus-applied', /.+/);
  await page.getByTestId('cached-radar-fingerprint').getByRole('button', { name: 'Inspect Evidence' }).click();
  await expect(page.getByTestId('cached-evidence-card')).toContainText('E-FLAGSHIP-OKI-004');
  await page.getByRole('button', { name: 'Generate story' }).click();
  await expect(page.locator('.agent-story nav button')).toHaveCount(5);
  await expect(page.locator('.agent-story')).toContainText('E-FLAGSHIP-OKI-004');
});

test('real local model calls safe GIS tools through FastAPI', async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeEnabled();
  await expect(page.getByText('Agent Online')).toBeVisible({ timeout: 20_000 });
  await page.getByLabel('Data mode').selectOption('fixture');
  await page.getByLabel('Agent execution').selectOption('real');
  await page.getByLabel('Ask about this area').fill('找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.locator('.rank-card')).toHaveCount(3, { timeout: 50_000 });
  await expect(page.getByText(/Real AI Analysis · (openai_compatible|gemini)/)).toBeVisible();
  await expect(page.getByText(/SIMULATED DATA — NOT NASA OBSERVATIONS/).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Investigation Plan' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Inferred' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Scientific Limitations' })).toBeVisible();
  await expect(page.getByText(/physical cause of radar backscatter change is not established/)).toBeVisible();
  await expect(page.getByTestId('map-viewport')).toHaveAttribute('data-maplibre-focus-applied', /.+/);
  await expect(page.locator('.agent-evidence-card')).toContainText('synthetic');
  await expect(page.getByText(/Rank 1 minus rank 2 median absolute change/)).toBeVisible();
  await page.getByRole('button', { name: 'Generate story' }).click();
  await expect(page.locator('.agent-story nav button')).toHaveCount(5);
  await page.screenshot({ path: testInfo.outputPath('real-agent-flow.png'), fullPage: true });
});
