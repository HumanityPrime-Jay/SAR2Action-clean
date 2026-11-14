"""Inventory B-team handoff files without treating catalog metadata as pixels."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.validate_nisar_handoff import REQUIRED, validate


ROOT = Path(__file__).resolve().parents[1]
data = ROOT / 'data'
catalog_path = data / 'scenes' / 'scene_manifest.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.is_file() else {}
scenes = catalog.get('scenes') or []
pairs = catalog.get('screened_pairs') or []
sidecars = sorted(data.rglob('*_QA_STATS.h5'))
all_h5 = sorted(data.rglob('*.h5'))
rasters = sorted(data.rglob('*.tif')) + sorted(data.rglob('*.tiff'))
change = [path for path in rasters if any(token in path.stem.lower() for token in ('change', 'delta'))]
masks = [path for path in rasters if 'mask' in path.stem.lower()]
manifest_env = os.environ.get('SAR2ACTION_SPATIAL_MANIFEST', '').strip()
manifest_path = Path(manifest_env) if manifest_env else None
contract = validate(manifest_path)
inventory = {
    'status': 'BLOCKED' if contract['status'] != 'VALID_CONTRACT_ONLY' else 'CONTRACT_VALID_PENDING_SCIENCE',
    'catalog': {'status': 'PRESENT_METADATA_ONLY' if scenes else 'MISSING',
                'path': str(catalog_path) if catalog_path.is_file() else None,
                'scene_count': len(scenes), 'screened_pair_count': len(pairs),
                'pair_qa_status': 'CATALOG_SCREENED_NOT_PIXEL_VALIDATED' if pairs else 'MISSING',
                'has_polarization_dates_versions': bool(scenes and all(
                    item.get('scene_id') and item.get('polarizations') and
                    item.get('acquisition_start_utc') and item.get('processing_version') for item in scenes))},
    'raster_handoff': {'change_geotiff_count': len(change),
                       'change_geotiff_files': [str(path) for path in change[:10]],
                       'mask_geotiff_count': len(masks),
                       'mask_geotiff_files': [str(path) for path in masks],
                       'matching_change_mask_pair_status': 'CONTRACT_VALID' if contract['status'] == 'VALID_CONTRACT_ONLY'
                           else 'UNVERIFIED' if change else 'MISSING_CHANGE_RASTER'},
    'hdf5': {'qa_sidecar_count': len(sidecars),
             'qa_sidecar_size_range_bytes': [min((path.stat().st_size for path in sidecars), default=0),
                                             max((path.stat().st_size for path in sidecars), default=0)],
             'full_gcov_scene_file_count': len([path for path in all_h5 if path not in sidecars]),
             'note': 'Small QA_STATS sidecars contain metadata/statistics, not source GCOV pixel arrays.'},
    'manifest': {'configured_path': str(manifest_path) if manifest_path else None,
                 'required_fields': sorted(REQUIRED),
                 'missing_fields': sorted(REQUIRED) if manifest_path is None else [],
                 'validation': contract},
    'missing_required_files': ([
        'B-team live spatial manifest JSON (SAR2ACTION_SPATIAL_MANIFEST)',
        'signed polarization-specific dB change GeoTIFF referenced by the manifest',
        'pixel-aligned valid-mask GeoTIFF referenced by that same manifest',
        'source GCOV scene pixel files or auditable per-pixel extraction for independent verification',
    ] if contract['status'] != 'VALID_CONTRACT_ONLY' else []),
    'radar_fingerprint': {'status': 'BLOCKED_NO_VALID_SCENE_PIXELS'},
    'parent_evidence': {'status': 'BLOCKED_NO_LIVE_MANIFEST_OR_DERIVED_EVIDENCE'},
    'live_agent': {'status': 'BLOCKED_NO_VALIDATED_NISAR_HANDOFF',
                   'synthetic_fallback': False},
    'minimum_b_team_handoff': [
        'Signed georeferenced dB change GeoTIFF for one compatible scene pair and polarization.',
        'Pixel-aligned jointly valid mask GeoTIFF with explicit NoData.',
        'Live JSON manifest with all required fields, scene versions, unit/conversion declarations and SHA-256 hashes.',
        'Registered parent Evidence ID with matching scene pair, AOI, polarization, dates, QA decision and processing provenance.',
        'Source GCOV pixel files or auditable source-pixel samples and processing record for independent dB/NoData spot checks.',
    ],
}
output = ROOT / 'docs' / 'phase6_nisar_data_validation.json'
output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': inventory['status'], 'scene_count': len(scenes),
                  'screened_pair_count': len(pairs), 'change_geotiff_count': len(change),
                  'qa_sidecar_count': len(sidecars), 'full_gcov_scene_file_count': inventory['hdf5']['full_gcov_scene_file_count']}))
