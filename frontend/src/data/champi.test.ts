import { expect, it } from 'vitest';
import { geometryPath, parcelById, type FieldGeometry } from './champi';

it('keeps real source precision and rejects other case parcel IDs', () => {
  expect(parcelById('YL-CAND-01')?.areaHa).toBe(12.52471);
  expect(parcelById('YL-CAND-01')?.sourceAreaM2).toBe(125247.1);
  expect(parcelById('4183')).toBeUndefined();
});

it('renders all polygon parts and interior rings', () => {
  const ring = [[0, 0], [4, 0], [4, 4], [0, 0]] as [number, number][];
  const hole = [[1, 1], [2, 1], [2, 2], [1, 1]] as [number, number][];
  const geometry: FieldGeometry = { type: 'MultiPolygon', coordinates: [[ring, hole], [ring]] };
  expect(geometryPath(geometry, (point) => point).match(/M/g)).toHaveLength(3);
});
