import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

test('draws after zoom and pan, measures and round-trips a real farmland feature', async ({ page }) => {
  await page.goto('/studio');
  const map = page.locator('.studio-map');
  await expect(map).toHaveAttribute('data-map-ready', 'true', { timeout: 20_000 });
  await page.getByRole('button', { name: 'Polygon 編輯' }).click();
  await map.getByRole('button', { name: 'Zoom in' }).click();
  await map.scrollIntoViewIfNeeded();
  const box = (await map.boundingBox())!;
  await page.mouse.move(box.x + 170, box.y + 120);
  await page.mouse.down();
  await page.mouse.move(box.x + 200, box.y + 140, { steps: 6 });
  await page.mouse.up();
  for (const [x, y] of [
    [100, 70],
    [155, 70],
    [155, 125],
    [100, 125],
  ]) {
    await map.click({ position: { x, y } });
  }
  await expect(page.getByTestId('gis-cursor-crs')).toContainText('WGS84');
  await expect(page.getByTestId('gis-cursor-crs')).toContainText('TWD97');
  await page.getByRole('button', { name: '封閉 Polygon' }).click();
  await page.getByRole('button', { name: '量測面積' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'MEASURED_NOT_OFFICIAL' })).toBeVisible();
  const marker = map.getByRole('button', { name: 'Vertex 1.1.1', exact: true });
  await marker.scrollIntoViewIfNeeded();
  const vertex = (await marker.boundingBox())!;
  await page.mouse.move(vertex.x + vertex.width / 2, vertex.y + vertex.height / 2);
  await page.mouse.down();
  await page.mouse.move(vertex.x + 16, vertex.y - 8, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('button', { name: '下載 GeoJSON' })).toBeDisabled();
  await page.getByRole('button', { name: '復原' }).click();

  const real = JSON.parse(await readFile(resolve('public/studio/fields.geojson'), 'utf8'));
  const feature = real.features.find((field: { properties: { field_id: string } }) => field.properties.field_id === 'YL-CAND-01');
  const input = page.getByLabel('匯入 WGS84 GeoJSON');
  await input.setInputFiles({
    name: 'field.geojson',
    mimeType: 'application/geo+json',
    buffer: Buffer.from(JSON.stringify(feature)),
  });
  const result = page.getByRole('status').filter({ hasText: 'MEASURED_NOT_OFFICIAL' });
  await expect(result).toContainText('125089.43 m²');
  await expect(result).toContainText('EPSG:3826');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下載 GeoJSON' }).click();
  const filename = (await (await download).path())!;
  const exported = JSON.parse(await readFile(filename, 'utf8'));
  expect(exported.geometry).toEqual(feature.geometry);
  expect(exported.properties.geometry_source).toBe('USER_DRAWN');
  await input.setInputFiles(filename);
  await expect(result).toContainText('125089.43 m²');
  await expect(page.getByLabel('Field candidate')).toHaveValue('YL-CAND-01');
  await expect(page.getByText(/NO_REGISTERED_SATELLITE_STATISTICS/)).toBeVisible();
});

test('PR1 flow retains globe, farmer card, relief precision, and Investigation Studio navigation', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.home-globe .maplibregl-canvas')).toBeVisible({ timeout: 20_000 });
  await page.getByRole('navigation', { name: '主選單' }).getByRole('button', { name: '受災地圖' }).click();
  const mapRegion = page.getByRole('region', { name: '受災地圖' });
  await mapRegion.getByRole('combobox', { name: /地區/ }).selectOption('central');
  await mapRegion.getByRole('combobox', { name: /災害事件/ }).selectOption('champi-2026-yunlin');
  await mapRegion.getByRole('combobox', { name: /這塊田種的作物/ }).selectOption('garlic');
  await mapRegion.getByRole('button', { name: /進入受災地圖/ }).click();
  await expect(mapRegion.getByRole('listbox', { name: '候選田區' })).toBeVisible();
  await page.getByRole('button', { name: '補助助手', exact: true }).click();
  const assist = page.getByRole('region', { name: '補助助手' });
  await expect(assist).toContainText('12.5247 ha');
  await expect(assist).toContainText('NT$ 325,642');
  await page.getByRole('link', { name: 'Investigation Studio' }).click();
  await expect(page.getByRole('heading', { name: 'Investigation Studio' })).toBeVisible();
  await expect(page.getByLabel('Field candidate').locator('option')).toHaveCount(5);
  await page.getByRole('button', { name: 'Show radar layer' }).click();
  await page.getByLabel('NISAR observation').selectOption('POST');
  await expect(page.getByText('Cross-CRID radiometric equivalence', { exact: false }).first()).toBeVisible();
});
