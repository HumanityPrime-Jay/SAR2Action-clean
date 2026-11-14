import hashlib
import json

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from scripts.validate_nisar_handoff import validate


def test_missing_handoff_reports_concrete_error():
    report = validate(None)
    assert report['status'] == 'INVALID'
    assert 'SAR2ACTION_SPATIAL_MANIFEST' in report['errors'][0]


def test_handoff_raster_alignment_and_checksums(tmp_path):
    transform = from_bounds(100, 0, 100.1, 0.1, 10, 10)
    change = np.ones((10, 10), dtype='float32')
    mask = np.ones((10, 10), dtype='uint8')
    for name, array, nodata in [('change.tif', change, -9999), ('valid.tif', mask, 0)]:
        with rasterio.open(tmp_path/name, 'w', driver='GTiff', height=10, width=10,
                           count=1, dtype=array.dtype, crs='EPSG:4326',
                           transform=transform, nodata=nodata) as dst:
            dst.write(array, 1)
    manifest = {'schema_version': '1', 'data_kind': 'nisar', 'case_id': 'TEST_ONLY',
                'polarization': 'HV', 'scene_ids': ['TEST_T0', 'TEST_T1'],
                'observation_times': ['2026-09-01T00:00:00Z', '2026-09-13T00:00:00Z'],
                'parent_evidence_id': 'TEST_PARENT', 'change_geotiff': 'change.tif',
                'valid_mask_geotiff': 'valid.tif',
                'method': 'TEST dB difference v1', 'scene_versions': ['001', '001'],
                'pixel_resolution_deg': [0.01, 0.01], 'source_backscatter_unit': 'linear_power',
                'change_unit': 'dB', 'conversion_formula': '10*log10(P)',
                'change_sha256': hashlib.sha256((tmp_path/'change.tif').read_bytes()).hexdigest(),
                'valid_mask_sha256': hashlib.sha256((tmp_path/'valid.tif').read_bytes()).hexdigest()}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert validate(path, require_parent=False)['status'] == 'VALID_CONTRACT_ONLY'
    manifest['valid_mask_sha256'] = '0' * 64
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert any('valid_mask_sha256' in error for error in validate(path, require_parent=False)['errors'])
    manifest['valid_mask_sha256'] = hashlib.sha256((tmp_path/'valid.tif').read_bytes()).hexdigest()
    manifest['change_unit'] = 'linear_power'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert any('must be in dB' in error for error in validate(path, require_parent=False)['errors'])
    manifest['change_unit'] = 'dB'
    manifest['pixel_resolution_deg'] = [0.02, 0.01]
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert any('pixel_resolution_deg' in error for error in validate(path, require_parent=False)['errors'])
    manifest['pixel_resolution_deg'] = [0.01, 0.01]
    mask[0, 0] = 255
    with rasterio.open(tmp_path/'valid.tif', 'w', driver='GTiff', height=10, width=10,
                       count=1, dtype='uint8', crs='EPSG:4326', transform=transform,
                       nodata=255) as dst:
        dst.write(mask, 1)
    manifest['valid_mask_sha256'] = hashlib.sha256((tmp_path/'valid.tif').read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest), encoding='utf-8')
    report = validate(path, require_parent=False)
    assert report['status'] == 'VALID_CONTRACT_ONLY'
    assert report['checks'][0]['valid_pixels'] == 99
