import { expect, test } from '@playwright/test';

test('Final RC Integration: Full flow from PR1 Globe to the relief assistant and statutory relief', async ({ page }) => {
  // A. Open root entrance
  await page.goto('/');
  await expect(page.locator('.home-globe .maplibregl-canvas')).toBeVisible({ timeout: 20_000 });

  // B. EventPicker and Farmer Form
  await page.getByRole('navigation', { name: '主選單' }).getByRole('button', { name: '受災地圖' }).click();
  const mapRegion = page.getByRole('region', { name: '受災地圖' });
  await mapRegion.getByRole('combobox', { name: /地區/ }).selectOption('central');
  await mapRegion.getByRole('combobox', { name: /災害事件/ }).selectOption('champi-2026-yunlin');
  await mapRegion.getByRole('checkbox', { name: /我是農民/ }).check();
  await mapRegion.getByRole('combobox', { name: /這塊田種的作物/ }).selectOption('peanut');
  await mapRegion.getByRole('button', { name: /進入受災地圖/ }).click();
  await expect(mapRegion.getByRole('listbox', { name: '候選田區' })).toBeVisible();

  // C. Relief estimate from the official schedule: peanut → 雜糧（三）, NT$ 36,000/ha, real API
  await page.getByRole('navigation', { name: '主選單' }).getByRole('button', { name: '補助助手' }).click();
  const assist = page.getByRole('region', { name: '補助助手' });
  await expect(assist.getByRole('combobox', { name: '救助品項（附表二）' })).toHaveValue('grains_3_peanut_sweetpotato', { timeout: 10_000 });
  await expect(assist).toContainText('36,000 /ha');
  await expect(assist.getByText('試算上限').locator('xpath=following-sibling::*[1]')).toHaveText(/^NT\$ [\d,]+$/, { timeout: 10_000 });
  await expect(assist).toContainText('申請期限已過');

  // D. A farmer starts in the farmer view; the agent answers with verbatim articles
  const viewSwitch = assist.getByRole('switch', { name: '農政專業模式' });
  await expect(viewSwitch).toHaveAttribute('aria-checked', 'false');
  await assist.getByRole('button', { name: '申請期限是什麼時候？' }).click();
  const answer = assist.locator('.msg.bot').last();
  await expect(answer).toContainText('你登記的作物是落花生', { timeout: 30_000 });
  await expect(answer.getByRole('link', { name: '《農業天然災害救助辦法》第12條' })).toBeVisible();

  // E. The authority view shows the same answer with the legal check
  await viewSwitch.click();
  await expect(answer).toContainText('【法規檢核】');

  // F. The Investigation Studio stays available at /studio
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: 'Investigation Studio' })).toBeVisible();
  await expect(page.locator('#studio-mode')).toHaveValue('RECORDED_DETERMINISTIC');
});
