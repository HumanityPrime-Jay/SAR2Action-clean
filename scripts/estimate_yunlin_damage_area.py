"""Radar-suspected damaged farmland area for Yunlin County after Typhoon Champi.

No model is trained. Each official farmland parcel (國土利用現況調查, 農作使用) gets the median
change of Sentinel-1 RTC backscatter between two passes of the same orbit. A parcel is flagged when
|median change| >= T dB in VV or VH (the TW-01 rule). The same rule is applied to a 12-day interval
without a typhoon as a control, so ordinary change (irrigation, harvest, growth) can be subtracted.

Data: Microsoft Planetary Computer `sentinel-1-rtc` (Catalyst RTC of ESA Sentinel-1 GRD, CC-BY-4.0),
one relative orbit per run, all passes processed the same way.

Usage: python scripts/estimate_yunlin_damage_area.py <farmland.shp> <out_dir> [orbit: 69 | 105]
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from affine import Affine
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT

STAC = 'https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc/items/'
SAS = 'https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-1-rtc'
# Two orbits: 69 ascending (pre/post the warning) and 105 descending (a pass during the warning).
ORBITS = {
    69: ('ascending', {
        'control_pre': 'S1D_IW_GRDH_1SDV_20261002T100029_20261002T100058_004835_009159_rtc',
        'pre': 'S1D_IW_GRDH_1SDV_20261014T100029_20261014T100058_005010_009776_rtc',
        'post': 'S1D_IW_GRDH_1SDV_20261026T100029_20261026T100058_005185_009D7F_rtc',
    }),
    105: ('descending', {
        'control_pre': 'S1C_IW_GRDH_1SDV_20260928T215153_20260928T215218_009653_01336F_rtc',
        'pre': 'S1C_IW_GRDH_1SDV_20261010T215153_20261010T215218_009828_013950_rtc',
        'post': 'S1C_IW_GRDH_1SDV_20261022T215153_20261022T215218_010003_013F4D_rtc',
    }),
}
INTERVALS = {'typhoon': ('pre', 'post'), 'control': ('control_pre', 'pre')}
THRESHOLDS_DB = (2.0, 3.0, 4.0)
PRIMARY_DB = 3.0
MIN_PIXELS, MIN_COVERAGE = 5, 0.8
CLASSES = {'水田': 'paddy', '旱田': 'dry', '果園': 'orchard'}
CRS, RES = 32651, 10.0


def _load_parcels(path: str) -> gpd.GeoDataFrame:
    parcels = gpd.read_file(path)
    if set(parcels['LCODEC_C2']) != {'農作使用'}:
        raise ValueError('Expected only 農作使用 parcels')
    parcels = parcels.to_crs(CRS).reset_index(drop=True)
    parcels['parcel'] = np.arange(1, len(parcels) + 1, dtype=np.int32)
    parcels['cls'] = parcels['LCODEC_C3'].map(CLASSES)
    if parcels['cls'].isna().any():
        raise ValueError('Unexpected land-use class')
    parcels['area_ha'] = parcels.geometry.area / 1e4
    return parcels


def _grid(parcels: gpd.GeoDataFrame) -> tuple[Affine, int, int]:
    x0, y0, x1, y1 = parcels.total_bounds
    x0, y1 = np.floor(x0 / RES) * RES - RES, np.ceil(y1 / RES) * RES + RES
    width, height = int(np.ceil((x1 - x0) / RES)) + 2, int(np.ceil((y1 - y0) / RES)) + 2
    return Affine(RES, 0, x0, 0, -RES, y1), width, height


def _read(item: dict, band: str, token: str, transform: Affine, width: int, height: int) -> np.ndarray:
    href = f"{item['assets'][band]['href']}?{token}"
    with rasterio.open(href) as src, WarpedVRT(src, crs=CRS, transform=transform, width=width, height=height,
                                               resampling=Resampling.nearest, nodata=np.nan) as vrt:
        data = vrt.read(1, out_dtype='float32')
    data[~(data > 0)] = np.nan  # power; 0 and negatives are no-data
    return data


def run(shapefile: str, out_dir: Path, orbit: int = 69) -> dict:
    state, scenes = ORBITS[orbit]
    parcels = _load_parcels(shapefile)
    transform, width, height = _grid(parcels)
    labels = rasterize(zip(parcels.geometry, parcels['parcel']), out_shape=(height, width), transform=transform,
                       fill=0, dtype='int32')
    token = requests.get(SAS, timeout=30).json()['token']
    items = {k: requests.get(STAC + v, timeout=30).json() for k, v in scenes.items()}
    for item in items.values():
        p = item['properties']
        if (p['sat:relative_orbit'], p['sat:orbit_state']) != (orbit, state):
            raise ValueError('Scenes must share one orbit')

    inside = labels > 0
    lab = labels[inside]
    db = {}
    for key, item in items.items():
        for band in ('vv', 'vh'):
            db[(key, band)] = 10 * np.log10(_read(item, band, token, transform, width, height)[inside])
            print(f'read {key} {band}', file=sys.stderr)

    total_px = np.bincount(lab, minlength=len(parcels) + 1)
    table = parcels[['parcel', 'cls', 'area_ha']].copy()
    table['pixels'] = total_px[table['parcel']]
    for name, (a, b) in INTERVALS.items():
        valid = np.isfinite(db[(a, 'vv')]) & np.isfinite(db[(b, 'vv')]) & np.isfinite(db[(a, 'vh')]) & np.isfinite(db[(b, 'vh')])
        frame = pd.DataFrame({'parcel': lab[valid],
                              'dvv': db[(b, 'vv')][valid] - db[(a, 'vv')][valid],
                              'dvh': db[(b, 'vh')][valid] - db[(a, 'vh')][valid]})
        med = frame.groupby('parcel').agg(n=('dvv', 'size'), dvv=('dvv', 'median'), dvh=('dvh', 'median'))
        joined = table[['parcel']].join(med, on='parcel')
        table[f'{name}_n'] = joined['n'].fillna(0).astype(int).to_numpy()
        table[f'{name}_dvv'] = joined['dvv'].round(3).to_numpy()
        table[f'{name}_dvh'] = joined['dvh'].round(3).to_numpy()
        table[f'{name}_screened'] = (table[f'{name}_n'] >= MIN_PIXELS) & (table[f'{name}_n'] >= MIN_COVERAGE * table['pixels'])

    def summarize(rows: pd.DataFrame) -> dict:
        out = {'parcels': int(len(rows)), 'area_ha': round(float(rows['area_ha'].sum()), 1)}
        for name in INTERVALS:
            s = rows[rows[f'{name}_screened']]
            biggest = np.maximum(s[f'{name}_dvv'].abs(), s[f'{name}_dvh'].abs())
            out[name] = {'screened_parcels': int(len(s)), 'screened_area_ha': round(float(s['area_ha'].sum()), 1),
                         'flagged_area_ha': {f'{t:g}': round(float(s.loc[biggest >= t, 'area_ha'].sum()), 1) for t in THRESHOLDS_DB},
                         'flagged_parcels': {f'{t:g}': int((biggest >= t).sum()) for t in THRESHOLDS_DB},
                         # Standing water darkens radar, so floods show as drops.
                         'dropped_area_ha': {f'{t:g}': round(float(s.loc[np.minimum(s[f'{name}_dvv'], s[f'{name}_dvh']) <= -t, 'area_ha'].sum()), 1) for t in THRESHOLDS_DB}}
        both = rows[rows['typhoon_screened'] & rows['control_screened']]
        out['both_screened_area_ha'] = round(float(both['area_ha'].sum()), 1)
        excess = {}
        for t in THRESHOLDS_DB:
            share = {name: float(both.loc[np.maximum(both[f'{name}_dvv'].abs(), both[f'{name}_dvh'].abs()) >= t, 'area_ha'].sum()) / max(float(both['area_ha'].sum()), 1e-9)
                     for name in INTERVALS}
            # Typhoon-interval share above what an ordinary 12 days produces, applied to all farmland of the class.
            excess[f'{t:g}'] = {'typhoon_share': round(share['typhoon'], 4), 'control_share': round(share['control'], 4),
                                'excess_share': round(max(share['typhoon'] - share['control'], 0.0), 4),
                                'suspected_area_ha': round(max(share['typhoon'] - share['control'], 0.0) * out['area_ha'], 1)}
        out['estimate'] = excess
        return out

    summary = {
        'schema_version': 'yunlin-damage-area/1.0',
        'status': 'RADAR_SUSPECTED_NOT_VERIFIED',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'method': ('Per-parcel median Sentinel-1 RTC change (dB). Flag when |median| >= T in VV or VH. '
                   'Suspected area = (typhoon-interval flagged share - control-interval flagged share) x class farmland area. '
                   'No trained model.'),
        'screening_rule': f'>= {MIN_PIXELS} valid 10 m pixels and >= {int(MIN_COVERAGE * 100)}% of the parcel covered',
        'primary_threshold_db': PRIMARY_DB,
        'thresholds_db': list(THRESHOLDS_DB),
        'orbit': {'relative_orbit': orbit, 'state': state},
        'scenes': {k: {'id': v, 'datetime': items[k]['properties']['datetime'], 'platform': items[k]['properties']['platform']} for k, v in scenes.items()},
        'intervals': {k: list(v) for k, v in INTERVALS.items()},
        'source': 'Microsoft Planetary Computer sentinel-1-rtc (Catalyst RTC of ESA Sentinel-1 GRD)',
        'license': 'CC-BY-4.0',
        'farmland_source': '國土利用現況調查 雲林縣 農作使用 (水田/旱田/果園), mostly surveyed 2024-11',
        'limitations': [
            'Radar change is not confirmed damage; irrigation, harvest, planting and soil moisture also change backscatter.',
            'Crop types inside each class are unknown; the survey predates the typhoon.',
            'The control interval is one 12-day window; ordinary change varies through the season.',
        ],
        'total': summarize(table),
        'by_class': {c: summarize(table[table['cls'] == c]) for c in CLASSES.values()},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'yunlin_damage_area_orbit{orbit}.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with gzip.open(out_dir / f'yunlin_parcel_changes_orbit{orbit}.csv.gz', 'wt', encoding='utf-8') as f:
        table.to_csv(f, index=False)
    return summary


if __name__ == '__main__':
    result = run(sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 69)
    print(json.dumps({'total': result['total'], 'by_class': result['by_class']}, ensure_ascii=False, indent=1))
