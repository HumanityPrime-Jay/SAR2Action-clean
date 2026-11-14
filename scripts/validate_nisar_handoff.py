"""Strict B-team spatial manifest validator. Never substitutes synthetic data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REQUIRED = {'schema_version', 'data_kind', 'case_id', 'polarization', 'scene_ids',
            'observation_times', 'parent_evidence_id', 'change_geotiff',
            'valid_mask_geotiff', 'change_sha256', 'valid_mask_sha256', 'method',
            'scene_versions', 'pixel_resolution_deg', 'source_backscatter_unit',
            'change_unit', 'conversion_formula'}


def validate(path: Path | None, require_parent: bool = True) -> dict:
    report = {'status': 'INVALID', 'manifest': str(path) if path else None,
              'data_kind': None, 'errors': [], 'checks': []}
    errors = report['errors']
    if path is None:
        errors.append('SAR2ACTION_SPATIAL_MANIFEST is not set; B-team live GeoTIFF handoff is missing.')
        return report
    path = path.resolve()
    if not path.is_file():
        errors.append(f'Manifest file does not exist: {path}')
        return report
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        errors.append(f'Manifest is not readable JSON: {type(exc).__name__}')
        return report
    if not isinstance(manifest, dict):
        errors.append('Manifest root must be an object.')
        return report
    report['data_kind'] = manifest.get('data_kind')
    missing = sorted(REQUIRED - manifest.keys())
    if missing:
        errors.append('Missing required fields: ' + ', '.join(missing))
    if manifest.get('schema_version') != '1' or manifest.get('data_kind') != 'nisar':
        errors.append('schema_version must be 1 and data_kind must be nisar.')
    if manifest.get('polarization') not in ('HH', 'HV', 'VV', 'VH'):
        errors.append('Unsupported or missing polarization.')
    scenes = manifest.get('scene_ids')
    times = manifest.get('observation_times')
    if not isinstance(scenes, list) or len(scenes) != 2 or not all(isinstance(x, str) and x for x in scenes):
        errors.append('scene_ids must contain two nonempty scene identifiers.')
    versions = manifest.get('scene_versions')
    if not isinstance(versions, list) or len(versions) != 2 or not all(isinstance(x, str) and x for x in versions):
        errors.append('scene_versions must identify both source product versions.')
    resolution = manifest.get('pixel_resolution_deg')
    if not isinstance(resolution, list) or len(resolution) != 2 or any(
        not isinstance(x, (int, float)) or not np.isfinite(x) or x <= 0 for x in resolution):
        errors.append('pixel_resolution_deg must contain positive finite x/y degree spacing.')
    if not isinstance(manifest.get('method'), str) or not manifest.get('method').strip():
        errors.append('A nonempty processing method/version is required.')
    if manifest.get('change_unit') != 'dB':
        errors.append('Signed change raster must be in dB; never apply log10 to an existing dB raster.')
    source_unit = manifest.get('source_backscatter_unit')
    formula = manifest.get('conversion_formula')
    if (source_unit == 'linear_power' and formula != '10*log10(P)') or (
        source_unit == 'dB' and formula != 'none') or source_unit not in ('linear_power', 'dB'):
        errors.append('source_backscatter_unit/conversion_formula must be linear_power/10*log10(P) or dB/none.')
    if not isinstance(times, list) or len(times) != 2:
        errors.append('observation_times must contain exactly two UTC timestamps.')
    else:
        try:
            parsed = [datetime.fromisoformat(str(value).replace('Z', '+00:00')) for value in times]
            if any(value.utcoffset() is None for value in parsed) or parsed[0] >= parsed[1]:
                raise ValueError('timestamps are not ordered UTC')
        except (ValueError, TypeError):
            errors.append('observation_times must be ordered ISO-8601 timestamps with UTC offset.')
    if missing or errors:
        return report

    raster_paths = {}
    for name, checksum in [('change_geotiff', 'change_sha256'),
                           ('valid_mask_geotiff', 'valid_mask_sha256')]:
        rel = manifest[name]
        candidate = (path.parent / rel).resolve() if isinstance(rel, str) else path.parent
        if not candidate.is_relative_to(path.parent) or not candidate.is_file():
            errors.append(f'{name} must name an existing file inside manifest directory.')
            continue
        raster_paths[name] = candidate
        digest = hashlib.sha256()
        with candidate.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != manifest[checksum]:
            errors.append(f'{checksum} does not match {candidate.name}.')
    if len(raster_paths) != 2:
        return report

    try:
        with rasterio.open(raster_paths['change_geotiff']) as change, rasterio.open(raster_paths['valid_mask_geotiff']) as mask:
            if change.driver != 'GTiff' or mask.driver != 'GTiff':
                errors.append('Both inputs must be GeoTIFF files.')
            if change.count != 1 or mask.count != 1:
                errors.append('Both rasters must be single-band.')
            if change.crs is None or change.crs.to_epsg() != 4326:
                errors.append('Change raster CRS must be EPSG:4326.')
            if mask.crs != change.crs or mask.transform != change.transform or mask.shape != change.shape:
                errors.append('Change and valid-mask rasters are not pixel-aligned.')
            if change.transform.a <= 0 or change.transform.e >= 0 or abs(change.transform.b) > 1e-10 or abs(change.transform.d) > 1e-10:
                errors.append('Rasters must be north-up and unrotated.')
            if resolution and (abs(change.transform.a - resolution[0]) > 1e-9 or
                               abs(abs(change.transform.e) - resolution[1]) > 1e-9):
                errors.append('Declared pixel_resolution_deg differs from GeoTIFF transform.')
            if not np.issubdtype(np.dtype(change.dtypes[0]), np.floating):
                errors.append('Signed dB change raster must use a floating-point dtype.')
            if change.nodata is None:
                errors.append('Change raster must declare a NoData value.')
            if mask.nodata is None:
                errors.append('Valid mask must declare a NoData value.')
            if not errors:
                valid_count = 0
                for _, window in change.block_windows(1):
                    values = change.read(1, window=window)
                    valid = (mask.read(1, window=window) > 0) & (mask.read_masks(1, window=window) > 0)
                    if np.any(valid & ~np.isfinite(values)):
                        errors.append('Valid mask includes non-finite change pixels.')
                        break
                    if change.nodata is not None and np.any(valid & (values == change.nodata)):
                        errors.append('Valid mask includes declared NoData change pixels.')
                        break
                    valid_count += int(valid.sum())
                if valid_count == 0:
                    errors.append('No jointly valid change pixels are present.')
                report['checks'].append({'raster_shape': change.shape,
                                         'crs': str(change.crs), 'valid_pixels': valid_count})
    except (rasterio.errors.RasterioError, OSError, ValueError) as exc:
        errors.append(f'GeoTIFF validation failed: {type(exc).__name__}: {exc}')

    if require_parent and not errors:
        try:
            from backend.app.services.science_service import ScienceService
            parent = ScienceService().get_evidence(manifest['parent_evidence_id'])
            if list(parent.scene_ids) != scenes:
                errors.append('Parent Evidence scene IDs do not match manifest.')
            parent_pols = [str(x.value if hasattr(x, 'value') else x) for x in parent.polarizations]
            if manifest['polarization'] not in parent_pols:
                errors.append('Parent Evidence does not support requested polarization.')
            quality = str(parent.quality_status.value if hasattr(parent.quality_status, 'value') else parent.quality_status)
            if quality not in ('COMPARABLE', 'LIMITED'):
                errors.append('Parent Evidence scene pair is not comparable.')
            parent_meta = parent.processing_metadata.model_dump() if hasattr(parent.processing_metadata, 'model_dump') else parent.processing_metadata
            if isinstance(parent_meta, dict):
                try:
                    recorded = [datetime.fromisoformat(str(parent_meta[key]).replace('Z', '+00:00'))
                                for key in ('t0_acquisition_utc', 't1_acquisition_utc')]
                    if recorded != parsed:
                        errors.append('Parent Evidence observation timestamps do not match manifest.')
                except (KeyError, ValueError, TypeError):
                    errors.append('Parent Evidence acquisition timestamps are missing or invalid.')
                crids = [parent_meta.get('t0_crid'), parent_meta.get('t1_crid')]
                if any(crids) and any(crid and crid != version for crid, version in zip(crids, versions)):
                    errors.append('Scene versions do not match parent Evidence CRIDs.')
            if parent.valid_pixel_count <= 0:
                errors.append('Parent Evidence has no valid pixels.')
        except Exception as exc:
            errors.append(f'Parent Evidence ID is unavailable: {type(exc).__name__}.')
    if not errors:
        report['status'] = 'VALID_CONTRACT_ONLY'
        report['checks'].append({'scene_ids': scenes, 'observation_times': times,
                                 'polarization': manifest['polarization'],
                                 'parent_evidence_id': manifest['parent_evidence_id']})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=Path(os.environ['SAR2ACTION_SPATIAL_MANIFEST'])
                        if os.environ.get('SAR2ACTION_SPATIAL_MANIFEST') else None)
    parser.add_argument('--skip-parent', action='store_true', help='Validate files before A-team Evidence Ledger is available')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(args.manifest, require_parent=not args.skip_parent)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['status'] == 'VALID_CONTRACT_ONLY' else 1)
