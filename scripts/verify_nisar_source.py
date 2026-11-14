"""Read-only source-machine check of a cached AOI against two GCOV HDF5 granules.

Run on the B-team machine. This script does not modify the HDF5 or cache files.
Its JSON report contains hashes and measurements, never environment variables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sar.change.reader import read_gcov_grid_and_metadata, read_gcov_window
from sar.change.windows import verify_grids_compatible


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def audit(t0: Path, t1: Path, cache_dir: Path, evidence_id: str, samples: int = 32,
          derived_files: list[Path] | None = None) -> dict:
    report = {'status': 'FAIL', 'evidence_id': evidence_id, 'checks': {}, 'source_sha256': {},
              'derived_sha256': {}, 'sample_checks': [], 'errors': []}
    evidence = next((r for r in json.loads((cache_dir / 'evidence_store.json').read_text(encoding='utf-8'))['records']
                     if r['evidence_id'] == evidence_id), None)
    analysis = json.loads((cache_dir / 'analysis_store.json').read_text(encoding='utf-8'))['analyses'].get(evidence_id)
    if evidence is None or analysis is None:
        raise ValueError('Evidence or analysis ID missing from cache')
    bbox = analysis['aoi_bbox_wgs84']
    report['aoi'] = {'id': evidence['roi_id'], 'bbox_wgs84': bbox}
    report['cache_file_sha256'] = {name: sha256_file(cache_dir / name) for name in
                                   ('evidence_store.json', 'fingerprint_store.json', 'analysis_store.json')}
    for label, path in (('t0', t0), ('t1', t1)):
        report['source_sha256'][label] = sha256_file(path)
    report['archived_derived_product_sha256'] = {
        path.name: sha256_file(path) for path in (derived_files or [])}
    grid0, meta0 = read_gcov_grid_and_metadata(t0)
    grid1, meta1 = read_gcov_grid_and_metadata(t1)
    verify_grids_compatible(grid0, grid1)
    report['checks']['scene_ids'] = [meta0['scene_id'], meta1['scene_id']] == evidence['scene_ids']
    report['checks']['observation_dates'] = (
        [meta0['acquisition_start_utc'], meta1['acquisition_start_utc']] ==
        [evidence['processing_metadata']['t0_acquisition_utc'], evidence['processing_metadata']['t1_acquisition_utc']])
    report['grid'] = {'crs_epsg': grid0.epsg, 'pixel_spacing_m': [abs(grid0.x_spacing_m), abs(grid0.y_spacing_m)],
                      'width': grid0.width, 'height': grid0.height}
    report['checks']['grid'] = (grid0.epsg == evidence['processing_metadata']['crs_epsg'] and
                                np.allclose(report['grid']['pixel_spacing_m'],
                                            evidence['processing_metadata']['pixel_spacing_m']))
    win0 = read_gcov_window(t0, bbox, precomputed_grid=grid0, precomputed_meta=meta0)
    win1 = read_gcov_window(t1, bbox, precomputed_grid=grid1, precomputed_meta=meta1,
                            precomputed_window=win0.window)
    polygon = win0.window.polygon_mask
    if polygon is None:
        polygon = np.ones(win0.mask.shape, dtype=bool)
    valid = np.asarray(polygon, dtype=bool).copy()
    for win in (win0, win1):
        valid &= (win.mask > 0) & (win.mask < 255)
        for pol in ('HH', 'HV'):
            power = win.power.get(pol)
            if power is None:
                raise ValueError(f'Source polarization {pol} missing')
            valid &= np.isfinite(power) & (power > 0)
    count = int(np.count_nonzero(valid))
    report['valid_pixel_count'] = count
    report['mask_rule'] = '(mask > 0) & (mask < 255) & finite positive HH/HV power in both scenes and AOI'
    report['checks']['valid_pixel_count'] = count == evidence['valid_pixel_count']
    report['checks']['mask_window_shape'] = list(valid.shape) == evidence['summary_statistics']['mask_diagnostics']['window_shape']
    report['derived_sha256']['common_valid_mask'] = hashlib.sha256(np.ascontiguousarray(valid).tobytes()).hexdigest()
    coords = np.argwhere(valid)
    if count == 0:
        raise ValueError('No valid source pixels in AOI')
    rng = np.random.default_rng(2026)
    picks = coords[rng.choice(len(coords), size=min(samples, len(coords)), replace=False)]
    for pol in ('HH', 'HV'):
        p0 = win0.power[pol]
        p1 = win1.power[pol]
        delta = np.full(valid.shape, np.nan, dtype=np.float32)
        delta[valid] = (10 * np.log10(p1[valid].astype(np.float64)) -
                        10 * np.log10(p0[valid].astype(np.float64))).astype(np.float32)
        median = float(np.median(delta[valid]))
        cached = evidence['summary_statistics']['per_polarization'][pol]['median_delta_db']
        report['checks'][f'{pol}_median_pixelwise_delta'] = abs(median - cached) <= 0.0002
        report[f'{pol.lower()}_median_delta_db'] = median
        report['derived_sha256'][f'delta_{pol.lower()}_db'] = hashlib.sha256(np.ascontiguousarray(delta).tobytes()).hexdigest()
        for row, col in picks:
            independent = float(10 * np.log10(float(p1[row, col]) / float(p0[row, col])))
            item = next((x for x in report['sample_checks'] if x['row'] == int(row) and x['col'] == int(col)), None)
            if item is None:
                item = {'row': int(row), 'col': int(col), 'passed': True}
                report['sample_checks'].append(item)
            item[f'{pol}_delta_db'] = independent
            item['passed'] &= abs(independent - float(delta[row, col])) < 1e-5
    report['checks']['random_pixel_recalculation'] = all(x['passed'] for x in report['sample_checks'])
    report['status'] = 'PASS' if all(report['checks'].values()) else 'FAIL'
    report['processing_code_version'] = evidence['algorithm_version']
    report['note'] = 'Source HDF5 checked against cache; hashes of derived arrays identify this run, not an archived product.'
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--t0', type=Path, required=True)
    parser.add_argument('--t1', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--evidence-id', default='E-FLAGSHIP-OKI-004')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--derived', type=Path, action='append', default=[],
                        help='Optional archived change raster or mask; repeat for each product')
    args = parser.parse_args()
    try:
        result = audit(args.t0, args.t1, args.cache_dir, args.evidence_id, args.samples, args.derived)
    except Exception as exc:
        result = {'status': 'FAIL', 'evidence_id': args.evidence_id,
                  'errors': [f'{type(exc).__name__}: {exc}']}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Source verification: {result['status']}; report: {args.output}")
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
