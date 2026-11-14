"""QA real Taixi pre/post GCOV pixels without assuming cross-CRID comparability."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from shapely.geometry import mapping, shape
from shapely.ops import transform as project
from analyze_tw03_harmony import _png

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/exports/typhoon_champi'
RELEASE_NOTES = 'https://hyp3-docs.asf.alaska.edu/nisar-docs/release-notes/'


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _stats(array: np.ndarray) -> dict:
    return {key: float(value) for key, value in {
        'min': np.min(array), 'p05': np.percentile(array, 5), 'median': np.median(array),
        'mean': np.mean(array), 'p95': np.percentile(array, 95), 'max': np.max(array),
        'std': np.std(array)}.items()}


def run() -> dict:
    manifest = json.loads((OUT / 'harmony_fetch_manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'DOWNLOADED_UNVALIDATED':
        raise ValueError('Both Harmony jobs must finish before science QA')
    features = json.loads((OUT / 'candidate_aois.geojson').read_text(encoding='utf-8'))['features']
    feature = next(f for f in features if f['properties']['township_name'] == 'Taixi Township')
    inventory = json.loads((OUT / 'scene_inventory.json').read_text(encoding='utf-8'))['scenes']
    files = {(p['path'].split('/')[-1].split('_')[0], p['variable']): p for p in manifest['files']}
    expected = {(t, v) for t in ('PRE', 'POST') for v in ('HHHH', 'HVHV', 'mask', 'numberOfLooks')}
    if set(files) != expected:
        raise ValueError('Incomplete variable set')
    results = {}
    output_paths = []
    for label in ('PRE', 'POST'):
        job = next(j for j in manifest['jobs'] if j['label'] == label)
        scene = next(s for s in inventory if s['scene_id'] == job['scene_id'])
        if (scene['track'], scene['frame'], scene['orbit_direction'], set(scene['polarizations'])) != (
                '61', '76', 'DESCENDING', {'HH', 'HV'}):
            raise ValueError('Unexpected scene geometry or polarization')
        arrays, profiles, tags = {}, {}, {}
        for variable in ('HHHH', 'HVHV', 'mask', 'numberOfLooks'):
            record = files[(label, variable)]
            path = ROOT / record['path']
            if _sha(path) != record['sha256']:
                raise ValueError('Downloaded subset hash mismatch')
            with rasterio.open(path) as source:
                arrays[variable] = source.read(1)
                profiles[variable] = source.profile.copy()
                tags[variable] = source.tags(1)
        reference = profiles['HHHH']
        if any((p['crs'], p['transform'], p['width'], p['height']) !=
               (reference['crs'], reference['transform'], reference['width'], reference['height'])
               for p in profiles.values()):
            raise ValueError('Variables in one observation are misaligned')
        if reference['crs'].to_epsg() != 32651:
            raise ValueError('Unexpected NISAR CRS')
        mask_description = tags['mask'].get('description', '')
        if not all(x in mask_description for x in ('fully-focused', 'value 0', 'value 255')):
            raise ValueError('Mask semantics not supported by subset metadata')
        if reference['nodata'] is not None and not np.isnan(reference['nodata']):
            raise ValueError('Unexpected radar NoData value')
        if profiles['mask']['nodata'] != 255:
            raise ValueError('Unexpected mask NoData value')
        for var in ('HHHH', 'HVHV'):
            if 'Covariance between' not in tags[var].get('description', ''):
                raise ValueError('Gamma0 covariance metadata absent')
        transformer = Transformer.from_crs(4326, reference['crs'], always_xy=True)
        polygon = project(transformer.transform, shape(feature['geometry']))
        inside = geometry_mask([mapping(polygon)], arrays['HHHH'].shape,
                               reference['transform'], invert=True)
        quality = inside & (arrays['mask'] > 0) & (arrays['mask'] < 255)
        quality &= np.isfinite(arrays['numberOfLooks']) & (arrays['numberOfLooks'] > 0)
        valid = quality.copy()
        for var in ('HHHH', 'HVHV'):
            valid &= np.isfinite(arrays[var]) & (arrays[var] > 0)
        count = int(valid.sum())
        if count == 0:
            raise ValueError('No valid pixels within Taixi township boundary')
        layers = {}
        for variable, pol in (('HHHH', 'HH'), ('HVHV', 'HV')):
            db = np.full(valid.shape, np.nan, dtype='float32')
            db[valid] = (10 * np.log10(arrays[variable][valid].astype('float64'))).astype('float32')
            layers[pol] = db
        out_tif = OUT / f'Taixi_{label}_HH_HV_db.tif'
        profile = reference.copy()
        profile.update(driver='GTiff', count=2, dtype='float32', nodata=np.nan,
                       compress='deflate', predictor=3)
        with rasterio.open(out_tif, 'w', **profile) as dst:
            for band, pol in enumerate(('HH', 'HV'), 1):
                dst.write(layers[pol], band)
                dst.set_band_description(band, f'{pol} gamma0 dB {label}')
            dst.update_tags(scene_id=scene['scene_id'], aoi='Taixi Township',
                            crid=scene['crid'], product_maturity=scene['product_maturity'],
                            event_relation=scene['event_relation'])
        # Display only per-scene values. No pre/post subtraction.
        hh = layers['HH']
        out_png = OUT / f'Taixi_{label}_HH_preview.png'
        # Blue/white/red display around -10 dB; each PNG is a single date.
        _png(out_png, (hh + 10.0) * 0.3, valid)
        output_paths.extend([out_tif, out_png])
        results[label] = {
            'scene_id': scene['scene_id'], 'concept_id': scene['concept_id'],
            'acquisition_start_utc': scene['acquisition_start_utc'],
            'event_relation': scene['event_relation'], 'crid': scene['crid'],
            'product_maturity': scene['product_maturity'],
            'crs': reference['crs'].to_string(), 'shape': list(valid.shape),
            'grid_transform': [float(x) for x in reference['transform'][:6]],
            'pixel_spacing_m': [abs(reference['transform'].a), abs(reference['transform'].e)],
            'township_pixels': int(inside.sum()), 'quality_pixels': int(quality.sum()),
            'valid_pixels': count, 'valid_fraction_of_township_pixels': count / int(inside.sum()),
            'mask_counts_in_township': {str(k): int(v) for k, v in zip(*np.unique(
                arrays['mask'][inside], return_counts=True))},
            'number_of_looks': _stats(arrays['numberOfLooks'][valid]),
            'nonfinite_counts_in_township': {v: int((~np.isfinite(arrays[v]) & inside).sum())
                                            for v in ('HHHH', 'HVHV', 'numberOfLooks')},
            'gamma0_power_positive_finite': True,
            'radiometric_convention': 'GCOV gamma0 power converted to dB using 10*log10(positive power)',
            'mask_semantics': '1..254 fully-focused; 0 partially-focused or invalid; 255 outside acquisition',
            'gamma0_db': {pol: _stats(layers[pol][valid].astype('float64')) for pol in ('HH', 'HV')},
            'outputs': [str(p.relative_to(ROOT)).replace('\\', '/') for p in (out_tif, out_png)]}
    pre, post = results['PRE'], results['POST']
    compatibility = {
        'same_sensor_band_polarization_track_frame_orbit': True,
        'crid_match': pre['crid'] == post['crid'],
        'product_maturity_match': pre['product_maturity'] == post['product_maturity'],
        'grid_match': (pre['crs'], pre['shape'], pre['grid_transform']) ==
                      (post['crs'], post['shape'], post['grid_transform']),
        'radiometric_cross_version_validated': False,
        'qa_decision': 'SEPARATE_OBSERVATIONS_ONLY',
        'reason': 'ASF P05036 release notes warn that maturity/processing differences can affect results; cross-CRID radiometric equivalence has not been established for this pair.',
        'release_notes_url': RELEASE_NOTES,
        'verified_typhoon_delta_allowed': False}
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'case_id': 'CHAMPI-YUNLIN-TAIXI', 'aoi_id': feature['properties']['aoi_id'],
              'aoi_kind': 'ADMINISTRATIVE_TOWNSHIP_NOT_FIELD', 'observations': results,
              'comparability': compatibility, 'damage_attribution': 'NOT_ESTABLISHED',
              'parcel_level_loss': None}
    report_path = OUT / 'science_qa.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    output_paths.append(report_path)
    summary = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
               'status': 'REAL_PRE_POST_SCENES_QA_PASSED_CROSS_CRID_DELTA_BLOCKED',
               'inputs': manifest['files'],
               'outputs': [{'path': str(p.relative_to(ROOT)).replace('\\', '/'),
                            'size_bytes': p.stat().st_size, 'sha256': _sha(p)} for p in output_paths]}
    (OUT / 'science_manifest.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = run()
    print('science_qa', result['comparability']['qa_decision'],
          [(k, v['valid_pixels']) for k, v in result['observations'].items()])
