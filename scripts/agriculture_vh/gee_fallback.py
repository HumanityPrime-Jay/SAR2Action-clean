"""Bounded Colab fallback for Earth Engine Sentinel-1 GRD, already in dB.

This provider writes a separate subdirectory and never overwrites OPERA evidence.
The caller must run ee.Authenticate() and ee.Initialize(project=...) first.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shapely.geometry import shape

from .common import OUTPUT, PERIODS, TAIXI_AOI, now_utc, write_csv, write_json
from .discover_fields import discover, locate_source, try_portal_download
from .download_opera import select_minimum
from .extract_vh import MIN_COVERAGE, MIN_VALID_PIXELS, TIME_COLUMNS
from .compare_years import compare
from .plot_timeseries import plot

OUT = OUTPUT / 'gee_fallback'
MAX_CATALOG_SCENES_PER_YEAR = 150


def _inventory(ee) -> list[dict]:
    records = []
    for year, (start, end) in PERIODS.items():
        collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                      .filterDate(start, end).filterBounds(ee.Geometry(TAIXI_AOI.__geo_interface__))
                      .filter(ee.Filter.eq('instrumentMode', 'IW'))
                      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')))
        count = int(collection.size().getInfo())
        if count > MAX_CATALOG_SCENES_PER_YEAR:
            raise RuntimeError(f'GEE {year} catalog exceeds {MAX_CATALOG_SCENES_PER_YEAR} scene bound')
        items = collection.toList(count).getInfo()
        for item in items:
            props = item.get('properties', {})
            scene_id = item.get('id') or item.get('name')
            if not scene_id:
                raise RuntimeError('Earth Engine scene lacks a source asset ID')
            # Earth Engine may omit system:footprint from a collection listing.
            # Query that source image's geometry rather than assume AOI coverage.
            footprint = props.get('system:footprint')
            if not footprint:
                footprint = ee.Image(scene_id).geometry().getInfo()
            if not footprint:
                raise RuntimeError('Earth Engine scene lacks a verifiable footprint')
            acquisition = __import__('datetime').datetime.fromtimestamp(
                props['system:time_start'] / 1000, __import__('datetime').timezone.utc).isoformat()
            orbit = props.get('relativeOrbitNumber_start')
            direction = props.get('orbitProperties_pass')
            platform = props.get('platform_number')
            if orbit is None or direction not in ('ASCENDING', 'DESCENDING') or not platform:
                continue
            geometry = shape(footprint)
            overlap = geometry.intersection(TAIXI_AOI).area / TAIXI_AOI.area
            if overlap <= 0:
                continue
            records.append({'granule_id': scene_id, 'asset_id': scene_id,
                            'source_collection': 'COPERNICUS/S1_GRD',
                            'acquisition_datetime': acquisition, 'year': year,
                            'platform': 'Sentinel-1' + str(platform),
                            'relative_orbit': orbit, 'orbit_direction': direction,
                            'polarization': 'VH', 'product_version': 'EE_GRD_DB',
                            'beam_mode': 'IW', 'burst_id': 'IW_GRD_FULL_SCENE',
                            'product_type': 'GRD_DB', 'vh_url': None, 'mask_url': None,
                            'data_url': None, 'aoi_overlap_ratio': round(overlap, 6),
                            'footprint_geojson': footprint})
    records.sort(key=lambda r: (r['acquisition_datetime'], r['granule_id']))
    write_json(OUT / 'scene_inventory.json', records)
    write_csv(OUT / 'scene_inventory.csv',
              [{**r, 'footprint_geojson': json.dumps(r['footprint_geojson'])} for r in records],
              ['granule_id', 'acquisition_datetime', 'year', 'platform', 'relative_orbit',
               'orbit_direction', 'polarization', 'product_version', 'beam_mode', 'burst_id',
               'source_collection', 'aoi_overlap_ratio', 'footprint_geojson'])
    return records


def _stat(stats: dict, suffix: str) -> float | None:
    value = stats.get('VH_' + suffix)
    return round(float(value), 5) if value is not None else None


def run(project: str, field_source: Path | None = None) -> dict:
    if not project or project.lower().startswith('your-'):
        raise ValueError('A registered Earth Engine Cloud project is required')
    import ee
    ee.Initialize(project=project)
    # One live request verifies project authorization in the Colab runtime.
    if ee.String('EARTH_ENGINE_READY').getInfo() != 'EARTH_ENGINE_READY':
        raise RuntimeError('Earth Engine project authorization failed')
    source = locate_source(field_source)
    if source is None:
        source = try_portal_download(Path(__file__).resolve().parents[2] / 'data/raw/P雲林縣_農田坵塊圖.zip')
    fields = discover(source, limit=5)
    write_json(OUT / 'field_candidates.geojson', fields)
    inventory = _inventory(ee)
    selected, primary = select_minimum(inventory, fields, per_year=3)
    rows = []
    reducer = (ee.Reducer.mean().combine(ee.Reducer.median(), sharedInputs=True)
               .combine(ee.Reducer.percentile([25, 75]), sharedInputs=True)
               .combine(ee.Reducer.count(), sharedInputs=True))
    for scene in selected:
        image = ee.Image(scene['asset_id']).select('VH')  # COPERNICUS/S1_GRD is already dB.
        for feature in fields['features']:
            interior = shape(feature['properties']['interior_geometry'])
            if not shape(scene['footprint_geojson']).covers(interior):
                continue
            geometry = ee.Geometry(feature['properties']['interior_geometry'])
            stats = image.reduceRegion(reducer, geometry=geometry, scale=10,
                                       maxPixels=1_000_000, tileScale=2).getInfo()
            total = ee.Image.constant(1).reduceRegion(ee.Reducer.count(), geometry=geometry,
                         scale=10, crs=image.projection(), maxPixels=1_000_000, tileScale=2).getInfo()
            count = int(stats.get('VH_count') or 0)
            interior_count = int(total.get('constant') or 0)
            ratio = count / interior_count if interior_count else 0.0
            flags = [] if count >= MIN_VALID_PIXELS and ratio >= MIN_COVERAGE else ['INSUFFICIENT_SPATIAL_SUPPORT']
            evidence_id = 'E-YL-GEE-VH-' + hashlib.sha256((feature['properties']['field_id'] + '|' +
                          scene['asset_id']).encode()).hexdigest()[:16].upper()
            rows.append({'field_id': feature['properties']['field_id'], 'year': scene['year'],
                         'acquisition_datetime': scene['acquisition_datetime'],
                         'vh_median_db': _stat(stats, 'median'), 'vh_mean_db': _stat(stats, 'mean'),
                         'vh_p25_db': _stat(stats, 'p25'), 'vh_p75_db': _stat(stats, 'p75'),
                         'valid_pixel_count': count, 'interior_pixel_count': interior_count,
                         'valid_coverage_ratio': round(ratio, 5), 'platform': scene['platform'],
                         'relative_orbit': scene['relative_orbit'], 'orbit_direction': scene['orbit_direction'],
                         'burst_id': scene['burst_id'], 'product_version': scene['product_version'],
                         'source_scene_id': scene['asset_id'], 'source_asset_id': scene['asset_id'],
                         'source_collection': 'COPERNICUS/S1_GRD', 'source_vh_sha256': None,
                         'evidence_id': evidence_id, 'qa_flags': flags})
    rows.sort(key=lambda r: (r['field_id'], r['acquisition_datetime']))
    if not rows:
        raise RuntimeError('GEE had no valid field observations for the selected scenes')
    write_csv(OUT / 'vh_timeseries.csv',
              [{**r, 'qa_flags': '|'.join(r['qa_flags'])} for r in rows],
              TIME_COLUMNS + ['source_asset_id', 'source_collection'])
    write_json(OUT / 'vh_timeseries.json', {'status': 'OBSERVED_EE_S1_GRD',
               'mean_definition': 'Arithmetic mean of valid pixel dB values; no second log conversion',
               'observations': rows})
    comparison = compare(rows, persist=False)
    write_json(OUT / 'vh_statistics.json', comparison)
    primary_rows = [r for r in rows if r['field_id'] == primary and not r['qa_flags']]
    plot(primary_rows, OUT / 'vh_comparison.png')
    evidence = {'status': 'OBSERVED_EE_S1_GRD', 'schema_version': 'yunlin-vh-evidence-v2',
                'records': [{'evidence_id': r['evidence_id'], 'field_id': r['field_id'],
                             'source_asset_id': r['source_asset_id'], 'source_collection': r['source_collection'],
                             'acquisition_datetime': r['acquisition_datetime'], 'vh_median_db': r['vh_median_db'],
                             'valid_pixel_count': r['valid_pixel_count'], 'crop_damage_status': 'UNKNOWN'}
                            for r in rows]}
    write_json(OUT / 'agent_evidence.json', evidence)
    result = {'status': 'OBSERVED_EE_S1_GRD', 'generated_at_utc': now_utc(),
              'earth_engine_project': project, 'source_collection': 'COPERNICUS/S1_GRD',
              'source_units': 'dB', 'log10_applied': False,
              'catalog_counts': {str(y): sum(r['year'] == y for r in inventory) for y in (2025, 2026)},
              'selected_counts': {str(y): sum(r['year'] == y for r in selected) for y in (2025, 2026)},
              'field_count': len(fields['features']), 'qa_passing_rows': sum(not r['qa_flags'] for r in rows),
              'crop_damage_status': 'UNKNOWN', 'primary_field_id': primary,
              'source_scene_ids': [r['asset_id'] for r in selected]}
    write_json(OUT / 'source_manifest.json', result)
    write_json(OUT / 'scientific_qa.json', result)
    return result
