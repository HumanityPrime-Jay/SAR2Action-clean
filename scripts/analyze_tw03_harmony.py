"""QA and analyze real provisional NISAR GCOV Harmony subsets for TW-01.

This computes within-sensor, pre-event change only. It makes no damage claim.
"""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from shapely.geometry import box, mapping
from shapely.ops import transform as project_geometry


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'processed' / 'tw03'
CATALOG = ROOT / 'docs' / 'TW03_EVIDENCE_CATALOG.json'
LAYERS = ('HHHH', 'HVHV', 'mask', 'numberOfLooks')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _stats(values: np.ndarray) -> dict:
    if values.size == 0:
        raise ValueError('No valid samples for statistics')
    return {key: float(value) for key, value in {
        'min': np.min(values), 'p05': np.percentile(values, 5),
        'mean': np.mean(values), 'median': np.median(values),
        'p95': np.percentile(values, 95), 'max': np.max(values),
        'std': np.std(values),
    }.items()}


def _png(path: Path, hh: np.ndarray, valid: np.ndarray) -> None:
    # Fixed ±3 dB display stretch, blue/white/red; gray means excluded pixel.
    scaled = np.clip(hh / 3.0, -1.0, 1.0)
    image = np.full((*hh.shape, 3), 205, dtype=np.uint8)
    neg = valid & (scaled < 0)
    pos = valid & (scaled >= 0)
    image[neg, 0] = np.asarray(255 * (1 + scaled[neg]), dtype=np.uint8)
    image[neg, 1] = np.asarray(255 * (1 + scaled[neg]), dtype=np.uint8)
    image[neg, 2] = 255
    image[pos, 0] = 255
    image[pos, 1] = np.asarray(255 * (1 - scaled[pos]), dtype=np.uint8)
    image[pos, 2] = np.asarray(255 * (1 - scaled[pos]), dtype=np.uint8)
    raw = b''.join(b'\x00' + image[row].tobytes() for row in range(image.shape[0]))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack(
            '!I', zlib.crc32(kind + payload) & 0xffffffff)

    data = (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', image.shape[1], image.shape[0], 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, level=9)) + chunk(b'IEND', b''))
    path.write_bytes(data)


def analyze() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    fetch = json.loads((OUTPUT / 'harmony_fetch_manifest.json').read_text(encoding='utf-8'))
    bbox = catalog.get('aoi_bbox_wgs84')
    if bbox != [120.295487, 23.677427, 120.344513, 23.722573]:
        raise ValueError('TW-01 bbox differs from the user-attested original')
    if fetch.get('status') != 'DOWNLOADED_UNVALIDATED' or fetch.get('aoi_bbox_wgs84') != bbox:
        raise ValueError('Harmony fetch manifest is absent or inconsistent')
    if any(item.get('tw01_aoi_coverage') is not True for item in catalog['nisar']):
        raise ValueError('Exact NISAR footprint does not cover TW-01')
    if [item.get('scene_id') for item in catalog['nisar']] != [
        'NISAR_L2_PR_GCOV_032_061_D_076_2005_DHDH_A_20261004T103752_20261004T103826_P05023_N_F_J_001',
        'NISAR_L2_PR_GCOV_033_061_D_076_2005_DHDH_A_20261016T103752_20261016T103826_P05023_N_F_J_001']:
        raise ValueError('NISAR source scene IDs are not the locked pair')
    if len({(item['orbit_direction'], item['track'], item['frame']) for item in catalog['nisar']}) != 1:
        raise ValueError('Orbit, track, or frame mismatch')
    if any(set(item['polarizations']) != {'HH', 'HV'} for item in catalog['nisar']):
        raise ValueError('NISAR polarization mismatch')
    files = {(item['path'].split('/')[-1].split('_')[0], item['variable']): item
             for item in fetch['files']}
    if set(files) != {(t, v) for t in ('T0', 'T1') for v in LAYERS}:
        raise ValueError('Expected eight exact Harmony subsets')
    arrays = {}
    profiles = {}
    tags = {}
    for (time_label, variable), record in files.items():
        path = ROOT / record['path']
        if not path.is_file() or _sha256(path) != record['sha256']:
            raise ValueError('Harmony subset file integrity mismatch')
        with rasterio.open(path) as source:
            arrays[(time_label, variable)] = source.read(1)
            profiles[(time_label, variable)] = source.profile.copy()
            tags[(time_label, variable)] = source.tags(1)
    reference = profiles[('T0', 'HHHH')]
    for profile in profiles.values():
        if (profile['crs'], profile['transform'], profile['width'], profile['height']) != (
                reference['crs'], reference['transform'], reference['width'], reference['height']):
            raise ValueError('Harmony layers are not on one aligned grid')
    if reference['crs'].to_epsg() != 32651:
        raise ValueError('Unexpected TW-01 projected CRS')
    if any(profiles[(t, v)]['nodata'] is not None and
           not np.isnan(profiles[(t, v)]['nodata']) for t in ('T0', 'T1') for v in ('HHHH', 'HVHV', 'numberOfLooks')):
        raise ValueError('Unexpected numeric NoData sentinel')
    for t in ('T0', 'T1'):
        description = tags[(t, 'mask')].get('description', '')
        if not all(term in description for term in ('fully-focused', 'value 0', 'value 255')):
            raise ValueError('Mask semantics could not be verified from source metadata')
        if profiles[(t, 'mask')]['nodata'] != 255:
            raise ValueError('Mask NoData semantics mismatch')
        for variable in ('HHHH', 'HVHV'):
            if 'Covariance between' not in tags[(t, variable)].get('description', ''):
                raise ValueError('Covariance variable metadata mismatch')

    transformer = Transformer.from_crs(4326, reference['crs'], always_xy=True)
    polygon = project_geometry(transformer.transform, box(*bbox))
    aoi_pixels = geometry_mask([mapping(polygon)], out_shape=arrays[('T0', 'HHHH')].shape,
                               transform=reference['transform'], invert=True)
    if not aoi_pixels.any():
        raise ValueError('AOI has no grid cells')
    masks = [arrays[(t, 'mask')] for t in ('T0', 'T1')]
    looks = [arrays[(t, 'numberOfLooks')] for t in ('T0', 'T1')]
    quality = aoi_pixels.copy()
    for mask, look in zip(masks, looks):
        quality &= (mask > 0) & (mask < 255) & np.isfinite(look) & (look > 0)
    valid = quality.copy()
    for t in ('T0', 'T1'):
        for variable in ('HHHH', 'HVHV'):
            power = arrays[(t, variable)]
            valid &= np.isfinite(power) & (power > 0)
    count = int(valid.sum())
    if count == 0:
        raise ValueError('No common valid gamma0 power pixels inside TW-01')
    delta = {}
    statistics = {}
    for variable, pol in (('HHHH', 'HH'), ('HVHV', 'HV')):
        t0 = arrays[('T0', variable)][valid].astype(np.float64)
        t1 = arrays[('T1', variable)][valid].astype(np.float64)
        difference = 10.0 * np.log10(t1) - 10.0 * np.log10(t0)
        image = np.full(valid.shape, np.nan, dtype=np.float32)
        image[valid] = difference.astype(np.float32)
        delta[pol] = image
        statistics[pol] = {
            'valid_pixels': count,
            't0_gamma0_power': _stats(t0), 't1_gamma0_power': _stats(t1),
            'delta_db': _stats(difference),
        }
    output_tif = OUTPUT / 'TW03_delta_HH_HV_db.tif'
    profile = reference.copy()
    profile.update(driver='GTiff', count=2, dtype='float32', nodata=np.nan,
                   compress='deflate', predictor=3)
    with rasterio.open(output_tif, 'w', **profile) as destination:
        for band, pol in enumerate(('HH', 'HV'), start=1):
            destination.write(delta[pol], band)
            destination.set_band_description(band, 'Delta ' + pol + ' dB (T1 minus T0)')
        destination.update_tags(aoi_id='TW-01', source='NISAR L2 GCOV Harmony subset',
                                product_maturity='PROVISIONAL', crid_validation='NOT_VALIDATED',
                                event_relation='BOTH_PRE_EVENT')
    output_png = OUTPUT / 'TW03_delta_HH_preview.png'
    _png(output_png, delta['HH'], valid)
    qa = {
        'aoi_source': 'USER_ATTESTED_ORIGINAL_2026-11-14', 'aoi_bbox_wgs84': bbox,
        'aoi_center_rule': 'Projected WGS84 bbox polygon; pixel centers included',
        'aoi_pixels': int(aoi_pixels.sum()),
        'common_quality_pixels': int(quality.sum()),
        'common_valid_pixels': count,
        'valid_fraction_of_aoi': count / int(aoi_pixels.sum()),
        'crs': reference['crs'].to_string(), 'width': reference['width'],
        'height': reference['height'], 'pixel_spacing_m': [abs(reference['transform'].a),
                                                        abs(reference['transform'].e)],
        'grid_alignment': 'EXACT_MATCH_ALL_EIGHT_LAYERS',
        'mask_semantics': '1..254 fully-focused subswath; 0 partially-focused/invalid; 255 outside acquisition',
        'mask_counts_within_aoi': {t: {str(k): int(v) for k, v in zip(*np.unique(
            arrays[(t, 'mask')][aoi_pixels], return_counts=True))} for t in ('T0', 'T1')},
        'number_of_looks': {t: _stats(arrays[(t, 'numberOfLooks')][valid]) for t in ('T0', 'T1')},
        'nan_nodata_counts_within_aoi': {t: {v: int((~np.isfinite(arrays[(t, v)]) & aoi_pixels).sum())
                                           for v in ('HHHH', 'HVHV', 'numberOfLooks')} for t in ('T0', 'T1')},
        'gamma0_power_qa': 'POSITIVE_FINITE_ON_COMMON_VALID_PIXELS',
        'product_maturity': 'PROVISIONAL', 'crid': 'P05023', 'crid_validated': False,
        'event_relation': 'BOTH_NISAR_OBSERVATIONS_PRECEDE_CHAMPI_LAND_WARNING',
        'damage_attribution': 'NOT_SUPPORTED_BY_THIS_PRE_EVENT_PAIR',
    }
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
               'case_id': 'TW-01', 'data_mode': 'TW03_PROVISIONAL_OBSERVED',
               'source_scene_ids': [item['scene_id'] for item in catalog['nisar']],
               'acquisition_start_utc': [item['acquisition_start_utc'] for item in catalog['nisar']],
               'orbit_direction': catalog['nisar'][0]['orbit_direction'],
               'track': catalog['nisar'][0]['track'], 'frame': catalog['nisar'][0]['frame'],
               'polarizations': ['HH', 'HV'], 'qa': qa, 'statistics': statistics,
               'scientific_conclusion': 'Real pre-event NISAR radar change only; no storm damage claim.'}
    stats_path = OUTPUT / 'TW03_statistics.json'
    stats_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    evidence = {'case_id': 'TW-01', 'aoi_id': 'TW-01',
                'provenance_status': 'REAL_HARMONY_SUBSET_QA_PASSED; PROVISIONAL_CRID_NOT_VALIDATED; AOI_USER_ATTESTED',
                'records': [
                    {'evidence_id': f'E-TW01-NISAR-TW03-{pol}', 'type': 'REAL_NISAR_PRE_EVENT_CHANGE',
                     'polarization': pol, 'valid_pixels': count,
                     'delta_db': statistics[pol]['delta_db'],
                     'source_evidence_ids': [item['evidence_id'] for item in catalog['nisar']],
                     'data_mode': 'TW03_PROVISIONAL_OBSERVED',
                     'damage_claim_supported': False,
                     'artifact': 'data/processed/tw03/TW03_delta_HH_HV_db.tif'}
                    for pol in ('HH', 'HV')]}
    evidence_path = OUTPUT / 'TW03_evidence.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    outputs = [output_tif, output_png, stats_path, evidence_path]
    manifest = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                'status': 'REAL_PROVISIONAL_SUBSET_QA_PASSED',
                'aoi_bbox_wgs84': bbox, 'harmony_jobs': fetch['jobs'],
                'input_files': fetch['files'],
                'output_files': [{'path': str(path.relative_to(ROOT)).replace('\\', '/'),
                                  'size_bytes': path.stat().st_size, 'sha256': _sha256(path)}
                                 for path in outputs],
                'source_granule_concept_ids': [item['concept_id'] for item in catalog['nisar']],
                'crid_validation': 'NOT_VALIDATED', 'product_maturity': 'PROVISIONAL',
                'damage_claim_supported': False}
    (OUTPUT / 'TW03_manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    catalog['aoi_status'] = 'USER_ATTESTED_ORIGINAL'
    catalog['aoi_provenance'] = 'User supplied original TW-01 bbox in chat on 2026-11-14; independent source document unavailable'
    catalog['source_subset_status'] = 'HARMONY_SUBSET_QA_PASSED'
    catalog['tw03_change_status'] = 'REAL_PROVISIONAL_SUBSET_QA_PASSED'
    for index, item in enumerate(catalog['nisar']):
        label = ('T0', 'T1')[index]
        item['raster_status'] = 'HARMONY_SUBSET_QA_PASSED'
        item['crs'] = qa['crs']
        item['grid_alignment'] = qa['grid_alignment']
        item['mask_semantics'] = qa['mask_semantics']
        item['number_of_looks'] = qa['number_of_looks'][label]
        item['valid_pixel_count'] = count
        item['gamma0_positive_finite_qa'] = True
        item['nan_nodata_qa'] = qa['nan_nodata_counts_within_aoi'][label]
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    result = analyze()
    print('TW03 analysis:', result['data_mode'], result['qa']['common_valid_pixels'],
          'valid pixels; no storm damage claim')
