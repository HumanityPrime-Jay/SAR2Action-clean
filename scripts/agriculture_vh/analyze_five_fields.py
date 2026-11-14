"""Reconcile real OPERA COG pixels with the CSV and summarize five fields.

All differences are descriptive differences of observed median pixel dB values.
The land-warning window is a timing reference, not a field-impact timestamp.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import rasterio
from pyproj import Transformer
from shapely import transform as transform_geometry
from shapely.geometry import shape

from .common import OUTPUT, RASTER_DIR, now_utc, resolve_raster_path, write_json
from .compare_years import EVENT_START, EVENT_END
from .extract_vh import extract_one, MIN_COVERAGE, MIN_VALID_PIXELS

CSV_PATH = OUTPUT / 'vh_timeseries.csv'
FIELDS_PATH = OUTPUT / 'field_candidates.geojson'
LOCAL_TZ = timezone(timedelta(hours=8))


def _csv_rows() -> list[dict]:
    with CSV_PATH.open(encoding='utf-8', newline='') as stream:
        raw = list(csv.DictReader(stream))
    rows = []
    for item in raw:
        row = dict(item)
        row['year'] = int(row['year'])
        for key in ('vh_median_db', 'vh_mean_db', 'vh_p25_db', 'vh_p75_db', 'valid_coverage_ratio'):
            row[key] = float(row[key]) if row[key] else None
        for key in ('valid_pixel_count', 'interior_pixel_count'):
            row[key] = int(row[key])
        row['qa_flags'] = row['qa_flags'].split('|') if row['qa_flags'] else []
        rows.append(row)
    return rows


def _r(value: float) -> float:
    return round(value, 5)


def _observation(row: dict) -> dict:
    timestamp = datetime.fromisoformat(row['acquisition_datetime'])
    start, end = datetime.fromisoformat(EVENT_START), datetime.fromisoformat(EVENT_END)
    relation = ('HISTORICAL_REFERENCE' if row['year'] == 2025 else
                'PRE_WARNING' if timestamp < start else
                'POST_WARNING' if timestamp > end else 'WARNING_WINDOW')
    return {'acquisition_utc': row['acquisition_datetime'],
            'acquisition_taiwan': timestamp.astimezone(LOCAL_TZ).isoformat(),
            'warning_relation': relation, 'vh_median_db': row['vh_median_db'],
            'vh_mean_db': row['vh_mean_db'], 'vh_p25_db': row['vh_p25_db'],
            'vh_p75_db': row['vh_p75_db'], 'valid_pixel_count': row['valid_pixel_count'],
            'interior_pixel_count': row['interior_pixel_count'],
            'valid_coverage_ratio': row['valid_coverage_ratio'],
            'evidence_id': row['evidence_id'], 'source_scene_id': row['source_scene_id'],
            'qa_flags': row['qa_flags']}


def _delta(a: dict, b: dict, label: str) -> dict:
    return {'label': label, 'from_utc': a['acquisition_datetime'], 'to_utc': b['acquisition_datetime'],
            'median_difference_db': _r(b['vh_median_db'] - a['vh_median_db']),
            'direction': 'INCREASE' if b['vh_median_db'] > a['vh_median_db'] else
                         'DECREASE' if b['vh_median_db'] < a['vh_median_db'] else 'NO_CHANGE',
            'evidence_ids': [a['evidence_id'], b['evidence_id']],
            'causal_attribution': 'UNKNOWN'}


def build_comparison(rows: list[dict], features: list[dict], csv_sha256: str) -> dict:
    ids = [f['properties']['field_id'] for f in features]
    if len(ids) != 5 or len(set(ids)) != 5 or len(rows) != 30:
        raise ValueError('Expected five distinct official field candidates and 30 observations')
    if len({r['evidence_id'] for r in rows}) != 30:
        raise ValueError('Duplicate field-scene Evidence ID')
    expected_geometry = {r['source_scene_id'] for r in rows}
    if len(expected_geometry) != 6 or len({(r['platform'], r['relative_orbit'], r['orbit_direction'],
                                           r['burst_id'], r['product_version']) for r in rows}) != 1:
        raise ValueError('Source scene geometry or processing family is not consistent')
    projected = Transformer.from_crs('EPSG:4326', 'EPSG:32651', always_xy=True).transform
    geometries = {f['properties']['field_id']:
                  transform_geometry(shape(f['geometry']), projected, interleaved=False)
                  for f in features}
    interior_geometries = {f['properties']['field_id']:
                           transform_geometry(shape(f['properties']['interior_geometry']), projected,
                                              interleaved=False)
                           for f in features}
    if any(not g.is_valid or g.is_empty or g.area <= 0 for g in
           list(geometries.values()) + list(interior_geometries.values())):
        raise ValueError('Invalid official farmland or buffered interior geometry')
    distances = {a: {b: round(geometries[a].distance(geometries[b]), 1) for b in ids if b != a}
                 for a in ids}
    fields = []
    for field_id in ids:
        each = sorted((r for r in rows if r['field_id'] == field_id),
                      key=lambda r: r['acquisition_datetime'])
        by_year = {y: [r for r in each if r['year'] == y] for y in (2025, 2026)}
        if any(len(by_year[y]) != 3 for y in (2025, 2026)):
            raise ValueError('Expected three genuine dates in each year for every field')
        if any(r['vh_median_db'] is None or r['valid_pixel_count'] < MIN_VALID_PIXELS or
               r['valid_coverage_ratio'] < MIN_COVERAGE or
               'INSUFFICIENT_SPATIAL_SUPPORT' in r['qa_flags'] for r in each):
            raise ValueError('Observed field has insufficient valid pixel support')
        old, current = by_year[2025], by_year[2026]
        pairs = []
        for a, b in zip(old, current):
            a_time = datetime.fromisoformat(a['acquisition_datetime'])
            b_time = datetime.fromisoformat(b['acquisition_datetime'])
            calendar_gap = abs((b_time.replace(year=2025) - a_time).total_seconds()) / 86400
            if calendar_gap > 6:
                raise ValueError('Cross-year acquisition dates are not close enough')
            pairs.append({'2025_utc': a['acquisition_datetime'], '2026_utc': b['acquisition_datetime'],
                          'calendar_gap_days': round(calendar_gap, 3),
                          '2025_vh_median_db': a['vh_median_db'], '2026_vh_median_db': b['vh_median_db'],
                          '2026_minus_2025_db': _r(b['vh_median_db'] - a['vh_median_db']),
                          'evidence_ids': [a['evidence_id'], b['evidence_id']],
                          'interpretation': 'DESCRIPTIVE_ONLY'})
        warning_start = datetime.fromisoformat(EVENT_START)
        warning_end = datetime.fromisoformat(EVENT_END)
        pre = [r for r in current if datetime.fromisoformat(r['acquisition_datetime']) < warning_start]
        after = [r for r in current if datetime.fromisoformat(r['acquisition_datetime']) > warning_end]
        during = [r for r in current if warning_start <= datetime.fromisoformat(r['acquisition_datetime']) <= warning_end]
        fields.append({'field_id': field_id, 'field_area_m2': round(geometries[field_id].area, 1),
                       'interior_area_m2': round(interior_geometries[field_id].area, 1),
                       'nearest_other_field_m': min(distances[field_id].values()),
                       'distance_to_other_fields_m': distances[field_id],
                       'crop_label': 'UNVERIFIED_FARMLAND_CANDIDATE',
                       'spatial_support': {'min_valid_pixels': min(r['valid_pixel_count'] for r in each),
                                           'min_interior_pixels': min(r['interior_pixel_count'] for r in each),
                                           'min_valid_coverage_ratio': min(r['valid_coverage_ratio'] for r in each),
                                           'threshold_pixels': MIN_VALID_PIXELS,
                                           'threshold_coverage_ratio': MIN_COVERAGE,
                                           'assessment': 'PASS_WITH_MIXED_PIXEL_AND_NOISE_FLOOR_LIMITATIONS'},
                       'observations': {'2025': [_observation(r) for r in old],
                                        '2026': [_observation(r) for r in current]},
                       'matched_date_pairs': pairs,
                       '2025_early_to_middle': _delta(old[0], old[1], 'HISTORICAL_EARLY_TO_MIDDLE'),
                       '2025_early_to_late': _delta(old[0], old[2], 'HISTORICAL_EARLY_TO_LATE'),
                       '2026_pre_warning_change': _delta(pre[0], pre[-1], 'PRE_WARNING') if len(pre) >= 2 else None,
                       '2026_pre_warning_status': 'ONE_OBSERVATION_ONLY' if len(pre) == 1 else 'AVAILABLE',
                       '2026_pre_to_warning_window': _delta(pre[-1], during[0], 'PRE_TO_WARNING_WINDOW') if pre and during else None,
                       '2026_pre_to_post_warning': _delta(pre[-1], after[0], 'PRE_TO_POST_WARNING') if pre and after else None,
                       '2026_warning_to_post_warning': _delta(during[-1], after[0], 'WARNING_TO_POST_WARNING') if during and after else None,
                       'cross_year_early_to_middle_change_difference_db':
                           _r((current[1]['vh_median_db'] - current[0]['vh_median_db']) -
                              (old[1]['vh_median_db'] - old[0]['vh_median_db'])),
                       'evidence_ids': [r['evidence_id'] for r in each]})
    middle = [f['2026_pre_to_warning_window']['median_difference_db'] for f in fields]
    full = [f['2026_pre_to_post_warning']['median_difference_db'] for f in fields]
    return {'schema_version': 'taixi-five-field-comparison-v1', 'status': 'OBSERVED_DESCRIPTIVE_ONLY',
            'source': 'NASA OPERA RTC-S1 VH linear gamma0 COGs', 'input_csv_sha256': csv_sha256,
            'event_reference': {'kind': 'CWA_LAND_WARNING_NOT_FIELD_IMPACT_TIME',
                                'start_taiwan': EVENT_START, 'end_taiwan': EVENT_END,
                                'middle_scene_utc': current[1]['acquisition_datetime'],
                                'middle_scene_taiwan': _observation(current[1])['acquisition_taiwan'],
                                'middle_scene_relation': 'WARNING_WINDOW'},
            'shared_acquisition_geometry': {'platform': rows[0]['platform'],
                                            'relative_orbit': rows[0]['relative_orbit'],
                                            'orbit_direction': rows[0]['orbit_direction'],
                                            'burst_id': rows[0]['burst_id'],
                                            'product_version': rows[0]['product_version']},
            'fields': fields,
            'cross_field_pattern': {'pre_to_warning_increase_count': sum(x > 0 for x in middle),
                                    'pre_to_warning_decrease_count': sum(x < 0 for x in middle),
                                    'pre_to_post_increase_count': sum(x > 0 for x in full),
                                    'pre_to_post_decrease_count': sum(x < 0 for x in full),
                                    'spatial_adjacency_threshold_m': 1000,
                                    'shared_response_is_causal_evidence': False},
            'scientific_limits': ['Three dates per year do not establish a calibrated anomaly probability.',
                                  'One 2026 observation precedes the land warning; a strictly pre-warning change is unavailable.',
                                  'The October 22 UTC scene is October 23 local, inside the warning window.',
                                  'Warning time does not establish field-level impact time or damage.',
                                  'Thirty-meter VH field medians may contain mixed-pixel effects.',
                                  'Noise correction is tagged in the source, but a local noise-floor margin is not quantified.',
                                  'Crop type and harvest records are unverified.']}


def verify_rasters(rows: list[dict], features: list[dict]) -> dict:
    downloads = json.loads((RASTER_DIR / 'download_manifest.json').read_text(encoding='utf-8'))
    if len(downloads) != 6:
        raise ValueError('Expected six downloaded source scenes')
    scene_index = {item['scene']['granule_id']: item for item in downloads}
    field_index = {f['properties']['field_id']: f for f in features}
    scene_qa = []
    for item in downloads:
        with rasterio.open(resolve_raster_path(item['files']['vh']['path'])) as vh, rasterio.open(resolve_raster_path(item['files']['mask']['path'])) as mask:
            if vh.crs != mask.crs or vh.transform != mask.transform or vh.shape != mask.shape:
                raise ValueError('VH and mask grids differ')
            tags = vh.tags()
            scene_qa.append({'source_scene_id': item['scene']['granule_id'],
                             'vh_sha256': item['files']['vh']['sha256'],
                             'mask_sha256': item['files']['mask']['sha256'],
                             'crs': str(vh.crs), 'pixel_size_m': list(vh.res),
                             'vh_nodata': str(vh.nodata), 'mask_nodata': str(mask.nodata),
                             'noise_correction_applied_tag':
                                 tags.get('PROCESSING_INFORMATION_NOISE_CORRECTION_APPLIED'),
                             'local_noise_floor_margin_db': None})
    checked = []
    for row in rows:
        source = scene_index[row['source_scene_id']]
        observed = extract_one(source['scene'], source['files'], field_index[row['field_id']])
        for key in ('field_id', 'year', 'acquisition_datetime', 'vh_median_db', 'vh_mean_db',
                    'vh_p25_db', 'vh_p75_db', 'valid_pixel_count', 'interior_pixel_count',
                    'valid_coverage_ratio', 'evidence_id', 'source_scene_id', 'source_vh_sha256'):
            if observed[key] != row[key]:
                raise ValueError(f'Raster/CSV mismatch: {row["field_id"]} {row["acquisition_datetime"]} {key}')
        checked.append(row['evidence_id'])
    return {'status': 'PASS', 'reextracted_field_scene_count': len(checked),
            'raster_scene_count': len(scene_index), 'evidence_ids': checked,
            'source_scene_qa': scene_qa,
            'checks': ['VH and mask SHA-256', 'OPERA linear gamma0 processing tags',
                       'VH/mask CRS grid and 30 m alignment', 'mask 0 valid / 255 fill',
                       '35 m buffered field interior pixel centers', 'positive finite power to 10log10 dB',
                       'CSV medians, means, quartiles, pixel counts and Evidence IDs']}


def plot_assets(comparison: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter
    from .plot_timeseries import plot

    rows = _csv_rows()
    plot(rows, OUTPUT / 'five_fields_comparison.png')
    plot([r for r in rows if r['field_id'] == 'YL-CAND-01'], OUTPUT / 'selected_field_comparison.png')
    fields = comparison['fields']
    fig, ax = plt.subplots(figsize=(10, 5))
    x = list(range(5))
    ax.bar([i - 0.2 for i in x], [f['2026_pre_to_warning_window']['median_difference_db'] for f in fields],
           0.4, label='Pre-warning → warning-window')
    ax.bar([i + 0.2 for i in x], [f['2026_pre_to_post_warning']['median_difference_db'] for f in fields],
           0.4, label='Pre-warning → post-warning')
    ax.set_xticks(x, [f['field_id'].replace('YL-CAND-', '') for f in fields])
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_ylabel('Difference of observed median VH (dB)')
    ax.set_xlabel('Official farmland candidate ID suffix')
    ax.legend()
    ax.set_title('Taixi field changes: descriptive, no causal attribution')
    fig.text(0.02, 0.02, 'Oct 22 UTC acquisition = Oct 23 05:51 Taiwan, inside warning window; crop damage unknown.', fontsize=8)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUTPUT / 'cross_field_change_comparison.png', dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 3.2))
    start = datetime.fromisoformat(EVENT_START).replace(tzinfo=None)
    end = datetime.fromisoformat(EVENT_END).replace(tzinfo=None)
    ax.axvspan(start, end, color='#e9a269', alpha=0.3, label='CWA land-warning window')
    current = fields[0]['observations']['2026']
    for i, item in enumerate(current):
        time = datetime.fromisoformat(item['acquisition_taiwan']).replace(tzinfo=None)
        ax.axvline(time, color='#305c89', linewidth=1)
        ax.scatter(time, 0, s=55, color='#305c89')
        ax.annotate(f"{item['acquisition_taiwan'][5:16]}\n{item['warning_relation']}",
                    (time, 0), xytext=(0, 16 if i != 1 else -48),
                    textcoords='offset points', ha='center', fontsize=8)
    ax.set_xlim(datetime(2026, 10, 9), datetime(2026, 11, 6))
    ax.set_ylim(-1, 1)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(DateFormatter('%b %d'))
    ax.set_title('2026 OPERA VH acquisitions and Taiwan land-warning times')
    ax.legend(loc='upper right')
    fig.tight_layout()
    fig.savefig(OUTPUT / 'event_timeline.png', dpi=180)
    plt.close(fig)


def run() -> dict:
    rows = _csv_rows()
    features = json.loads(FIELDS_PATH.read_text(encoding='utf-8'))['features']
    pixel_qa = verify_rasters(rows, features)
    result = build_comparison(rows, features, hashlib.sha256(CSV_PATH.read_bytes()).hexdigest())
    result['generated_at_utc'] = now_utc()
    result['pixel_reverification'] = pixel_qa
    write_json(OUTPUT / 'field_comparison.json', result)
    plot_assets(result)
    return result


if __name__ == '__main__':
    summary = run()
    print(json.dumps({'status': summary['status'], 'fields': len(summary['fields']),
                      'reextracted': summary['pixel_reverification']['reextracted_field_scene_count'],
                      'cross_field_pattern': summary['cross_field_pattern']}, indent=2))
