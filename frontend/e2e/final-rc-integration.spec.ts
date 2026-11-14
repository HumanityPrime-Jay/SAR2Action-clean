import { expect, test } from '@playwright/test';

test('Final RC Integration: Full flow from PR1 Globe to TW-05 Agent & Statutory Relief', async ({ page }) => {
  // A. Open root entrance
  await page.goto('/');
  await expect(page.locator('.home-globe .maplibregl-canvas')).toBeVisible({ timeout: 20_000 });

  // B. EventPicker and Farmer Form
  await page.getByRole('navigation', { name: '主選單' }).getByRole('button', { name: '受災地圖' }).click();
  const mapRegion = page.getByRole('region', { name: '受災地圖' });
  await mapRegion.getByRole('combobox', { name: /地區/ }).selectOption('central');
  await mapRegion.getByRole('combobox', { name: /災害事件/ }).selectOption('champi-2026-yunlin');
  await mapRegion.getByRole('combobox', { name: /這塊田種的作物/ }).selectOption('peanut');
  await mapRegion.getByRole('button', { name: /進入受災地圖/ }).click();
  await expect(mapRegion.getByRole('listbox', { name: '候選田區' })).toBeVisible();

  // C. Assist Screen - Taixi Demo baseline
  await page.getByRole('button', { name: '補助助手', exact: true }).click();
  const assist = page.getByRole('region', { name: '補助助手' });
  await expect(assist).toContainText('NT$ 325,642');
  await expect(assist).toContainText('DEMO · TAIXI');

  // D. Switch to TW-05 Verified Field #74 and query Tool Calling Agent
  await page.getByRole('button', { name: 'TW-05 雲林實測' }).click();
  const parcelSelect = page.getByRole('combobox', { name: '選擇 TW-05 農田' });
  await parcelSelect.selectOption('74');

  const input = page.getByRole('textbox', { name: '輸入問題' });
  await input.fill('請檢查此坵塊之雷達回波變化與光學品質');
  await page.getByRole('button', { name: '送出' }).click();

  // E. Verify real API response in UI
  await expect(page.locator('.msg.bot').last()).toContainText('針對農田 #74 調查完成', { timeout: 20_000 });
  await expect(page.getByText(/DETERMINISTIC_TOOL_PIPELINE|GEMINI_FUNCTION_CALLING_LIVE/)).toBeVisible();
  await expect(page.locator('.msg.bot').last()).toContainText('E-TW01-PARCEL-74');

  // F. Switch to parcel #4183 and verify precision statutory relief of NT$ 16,343
  await parcelSelect.selectOption('4183');
  await expect(page.getByText('NT$ 16,343')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('0.453978 公頃')).toBeVisible();
  await expect(page.getByText('CONDITIONAL ESTIMATE / NOT OFFICIAL')).toBeVisible();

  // G. Navigate to Investigation Studio and verify recorded mode
  await page.getByRole('link', { name: 'Investigation Studio' }).click();
  await expect(page.getByRole('heading', { name: 'Investigation Studio' })).toBeVisible();
  await expect(page.locator('#studio-mode')).toHaveValue('RECORDED_DETERMINISTIC');
  await expect(page.getByText('Recorded mode displays a completed historical run')).toBeVisible();
});
