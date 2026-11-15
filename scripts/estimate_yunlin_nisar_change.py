"""NISAR L-band change on Yunlin farmland around Typhoon Champi, against an ordinary 12 days.

Same idea as estimate_yunlin_damage_area.py, with NISAR GCOV instead of Sentinel-1. Three frames:
descending orbit 061 frames 076 (north and east) and 077 (south), and ascending orbit 039 frame 013,
which fills the south of the county that the 10/28 descending pass missed. Each parcel is measured
inside one frame only, so all dates share one geometry. Per frame the control interval is two
P05023 passes 12 days apart before the typhoon, and the typhoon interval runs from the last of
those to the first P05036 pass after it. Across those two versions HH shows no offset on land, while
HV in P05036 reads higher on dark targets (a noise-floor difference). A blanket correction would also
remove any county-wide real change, so HH is the primary channel and HH+HV results are reported
beside it; the two intervals' median shift is recorded as a diagnostic.

Usage: python scripts/estimate_yunlin_nisar_change.py <farmland.shp> <towns.gpkg> <h5 dir> <out_dir>
  Granules missing from <h5 dir> are read remotely (window only) with the Earthdata login in ~/.netrc.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
from affine import Affine
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject, transform_bounds

GRID = 'science/LSAR/GCOV/grids/frequencyA'
BASE = 'https://nisar.asf.earthdatacloud.nasa.gov/NISAR'
GRANULES = {
    '061D-076': {
        'control_pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_061_D_076_2005_DHDH_A_20261004T103752_20261004T103826_P05023_N_F_J_001',
        'pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_061_D_076_2005_DHDH_A_20261016T103752_20261016T103826_P05023_N_F_J_001',
        'post': 'NISAR_L2_GCOV_V1/NISAR_L2_PR_GCOV_034_061_D_076_2005_DHDH_A_20261028T103752_20261028T103825_P05036_N_F_J_001',
    },
    '061D-077': {
        'control_pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_061_D_077_2005_DHDH_M_20261004T103822_20261004T103901_P05023_N_F_J_001',
        'pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_061_D_077_2005_DHDH_M_20261016T103822_20261016T103901_P05023_N_F_J_001',
        'post': 'NISAR_L2_GCOV_V1/NISAR_L2_PR_GCOV_034_061_D_077_2005_DHDH_M_20261028T103828_20261028T103901_P05036_N_F_J_001',
    },
    # The 10/28 descending pass leaves a gap over the south of the county, so ascending orbit 039 fills it.
    '039A-013': {
        'control_pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_039_A_013_4005_DHDH_A_20261002T212424_20261002T212501_P05023_N_F_J_001',
        'pre': 'NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_039_A_013_4005_DHDH_A_20261014T212424_20261014T212501_P05023_N_F_J_001',
        'post': 'NISAR_L2_GCOV_V1/NISAR_L2_PR_GCOV_034_039_A_013_4005_DHDH_A_20261026T212424_20261026T212501_P05036_N_F_J_001',
    },
}
INTERVALS = {'typhoon': ('pre', 'post'), 'control': ('control_pre', 'pre')}
THRESHOLDS_DB = (2.0, 3.0, 4.0)
MIN_PIXELS, MIN_COVERAGE = 3, 0.8  # 20 m pixels
CLASSES = {'水田': 'paddy', '旱田': 'dry', '果園': 'orchard'}
CRS, RES = 32651, 20.0


def _open(name: str, h5_dir: Path, fs):
    local = h5_dir / f"{name.split('/')[-1]}.h5"
    if local.exists():
        return h5py.File(local)
    return h5py.File(fs.open(f"{BASE}/{name}/{name.split('/')[-1]}.h5", 'rb'))


def _remote_fs():
    import netrc

    import aiohttp
    import fsspec
    import requests

    login, _, password = netrc.netrc().authenticators('urs.earthdata.nasa.gov')
    token = requests.post('https://urs.earthdata.nasa.gov/api/users/find_or_create_token', auth=(login, password), timeout=30).json()['access_token']
    # A stalled range read otherwise hangs forever; the timeout turns it into a retry.
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=90)
    return fsspec.filesystem('https', headers={'Authorization': f'Bearer {token}'}, block_size=4 * 2**20,
                             client_kwargs={'timeout': timeout})


def _read(h5: h5py.File, transform: Affine, shape: tuple[int, int]) -> dict[str, np.ndarray]:
    """HH and HV linear power on the county grid; NaN where the frame has no valid pixel.
    Frames come in their own UTM zone (077 is zone 50), so each block is warped by nearest neighbour."""
    g = h5[GRID]
    epsg = int(g['projection'][()])
    x, y = g['xCoordinates'][:], g['yCoordinates'][:]
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    factor = int(round(RES / abs(dx)))  # 4005-mode frames post at 10 m: average 2 x 2 to 20 m
    if factor < 1 or abs(abs(dx) * factor - RES) > 1e-6:
        raise ValueError('Posting does not divide 20 m')
    west, south = transform.c, transform.f - RES * shape[0]
    east, north = transform.c + RES * shape[1], transform.f
    bx0, by0, bx1, by1 = transform_bounds(CRS, epsg, west, south, east, north)
    c0, c1 = np.searchsorted(x, bx0 - 5 * RES), np.searchsorted(x, bx1 + 5 * RES)
    r0, r1 = np.searchsorted(-y, -(by1 + 5 * RES)), np.searchsorted(-y, -(by0 - 5 * RES))
    out = {k: np.full(shape, np.nan, dtype='float32') for k in ('HH', 'HV')}
    if c1 <= c0 or r1 <= r0:
        return out
    r1, c1 = r0 + (r1 - r0) // factor * factor, c0 + (c1 - c0) // factor * factor
    mask = g['mask'][r0:r1, c0:c1]
    valid = (mask > 0) & (mask < 255)
    src_transform = Affine(dx * factor, 0, x[c0] - dx / 2, 0, dy * factor, y[r0] - dy / 2)
    for key, ds in (('HH', 'HHHH'), ('HV', 'HVHV')):
        block = g[ds][r0:r1, c0:c1].astype('float32')
        block[~(valid & (block > 0))] = np.nan
        if factor > 1:  # mean power, only where every fine pixel is valid
            h, w = block.shape[0] // factor, block.shape[1] // factor
            block = block.reshape(h, factor, w, factor).mean(axis=(1, 3))
        reproject(block, out[key], src_transform=src_transform, src_crs=f'EPSG:{epsg}', src_nodata=np.nan,
                  dst_transform=transform, dst_crs=f'EPSG:{CRS}', dst_nodata=np.nan, resampling=Resampling.nearest)
    return out


def _cached_read(name: str, h5_dir: Path, fs, transform: Affine, shape: tuple[int, int], tries: int = 4):
    """Window read, cached next to the h5 files so a rerun does not fetch it again. Remote reads retry
    on transient errors (Earthdata Cloud returns the odd 502)."""
    cache = h5_dir / f"{name.split('/')[-1]}.yunlin{int(RES)}m.npz"
    if cache.exists():
        z = np.load(cache)
        if z['shape'].tolist() == list(shape) and np.allclose(z['transform'], tuple(transform)[:6]):
            return str(z['start']), {'HH': z['HH'], 'HV': z['HV']}
    for attempt in range(tries):
        try:
            with _open(name, h5_dir, fs) as h5:
                start = h5['science/LSAR/identification/zeroDopplerStartTime'][()].decode()
                arrays = _read(h5, transform, shape)
            break
        except Exception as err:  # network errors come through h5py as aiohttp or OS errors
            if isinstance(err, ValueError) or attempt == tries - 1:
                raise
            print(f'retry {name.split("/")[-1][:40]}: {type(err).__name__}', file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    np.savez_compressed(cache, start=start, shape=np.array(shape), transform=np.array(tuple(transform)[:6]), **arrays)
    return start, arrays


def _version_offset(db: dict, inside: np.ndarray) -> dict[str, float]:
    """Median typhoon-interval change minus median control-interval change over the county's land pixels.
    A version offset and any county-wide real change both show up here; it is reported, not removed."""
    out = {}
    for pol in ('HH', 'HV'):
        t = db[('post', pol)] - db[('pre', pol)]
        c = db[('pre', pol)] - db[('control_pre', pol)]
        ok = np.isfinite(t) & np.isfinite(c) & inside
        out[pol] = round(float(np.median(t[ok]) - np.median(c[ok])), 3) if ok.any() else 0.0
    return out


def run(shapefile: str, towns_path: str, h5_dir: Path, out_dir: Path) -> dict:
    parcels = gpd.read_file(shapefile).to_crs(CRS).reset_index(drop=True)
    parcels['parcel'] = np.arange(1, len(parcels) + 1, dtype=np.int32)
    parcels['cls'] = parcels['LCODEC_C3'].map(CLASSES)
    parcels['area_ha'] = parcels.geometry.area / 1e4
    towns = gpd.read_file(towns_path).to_crs(CRS)
    reps = gpd.GeoDataFrame(parcels[['parcel']], geometry=parcels.geometry.representative_point(), crs=CRS)
    parcels['town'] = gpd.sjoin(reps, towns[['TOWNNAME', 'geometry']], how='left', predicate='within').groupby(level=0)['TOWNNAME'].first()

    x0, y0, x1, y1 = parcels.total_bounds
    x0, y1 = np.floor(x0 / RES) * RES - RES, np.ceil(y1 / RES) * RES + RES
    shape = (int(np.ceil((y1 - y0) / RES)) + 2, int(np.ceil((x1 - x0) / RES)) + 2)
    transform = Affine(RES, 0, x0, 0, -RES, y1)
    labels = rasterize(zip(parcels.geometry, parcels['parcel']), out_shape=shape, transform=transform, fill=0, dtype='int32')
    inside = labels > 0
    lab = labels[inside]
    total_px = np.bincount(lab, minlength=len(parcels) + 1)
    county = rasterize([(towns.geometry.union_all(), 1)], out_shape=shape, transform=transform, fill=0, dtype='uint8') > 0

    fs = None if all((h5_dir / f"{n.split('/')[-1]}.h5").exists() for f in GRANULES.values() for n in f.values()) else _remote_fs()
    per_frame, offsets, scenes = {}, {}, {}
    for frame, dates in GRANULES.items():
        db = {}
        for key, name in dates.items():
            start, arrays = _cached_read(name, h5_dir, fs, transform, shape)
            scenes[f'{frame}_{key}'] = {'id': name.split('/')[-1], 'start_utc': start, 'crid': name.split('_')[-5], 'collection': name.split('/')[0]}
            for pol, arr in arrays.items():
                db[(key, pol)] = 10 * np.log10(arr)
            print(f'read {frame} {key}', file=sys.stderr)
        offsets[frame] = _version_offset(db, county)
        cols = {}
        for name, (a, b) in INTERVALS.items():
            dhh = (db[(b, 'HH')] - db[(a, 'HH')])[inside]
            dhv = (db[(b, 'HV')] - db[(a, 'HV')])[inside]
            ok = np.isfinite(dhh) & np.isfinite(dhv)
            med = pd.DataFrame({'parcel': lab[ok], 'dhh': dhh[ok], 'dhv': dhv[ok]}).groupby('parcel').agg(
                n=('dhh', 'size'), dhh=('dhh', 'median'), dhv=('dhv', 'median'))
            cols[name] = med.reindex(parcels['parcel'])
        per_frame[frame] = cols

    # Each parcel uses the frame where both intervals see the most of it.
    score = np.stack([np.minimum(c['typhoon']['n'].fillna(0).to_numpy(), c['control']['n'].fillna(0).to_numpy()) for c in per_frame.values()])
    pick = np.array(list(per_frame))[score.argmax(axis=0)]
    table = parcels[['parcel', 'cls', 'town', 'area_ha']].copy()
    table['pixels'] = total_px[table['parcel']]
    table['frame'] = pick
    for name in INTERVALS:
        for col in ('n', 'dhh', 'dhv'):
            values = np.select([pick == f for f in per_frame], [per_frame[f][name][col].to_numpy() for f in per_frame])
            table[f'{name}_{col}'] = np.round(values, 3) if col != 'n' else np.nan_to_num(values).astype(int)
        table[f'{name}_screened'] = (table[f'{name}_n'] >= MIN_PIXELS) & (table[f'{name}_n'] >= MIN_COVERAGE * table['pixels'])

    def flags(rows: pd.DataFrame, name: str, t: float) -> dict[str, pd.Series]:
        hh, hv = rows[f'{name}_dhh'], rows[f'{name}_dhv']
        return {'HH_any': hh.abs() >= t, 'HH_drop': hh <= -t, 'HH_rise': hh >= t,
                'any': np.maximum(hh.abs(), hv.abs()) >= t, 'drop': np.minimum(hh, hv) <= -t, 'rise': np.maximum(hh, hv) >= t}

    def summarize(rows: pd.DataFrame) -> dict:
        out = {'parcels': int(len(rows)), 'area_ha': round(float(rows['area_ha'].sum()), 1)}
        both = rows[rows['typhoon_screened'] & rows['control_screened']]
        area = float(both['area_ha'].sum())
        out['measured_area_ha'] = round(area, 1)
        out['measured_share'] = round(area / max(out['area_ha'], 1e-9), 3)
        out['median_change_db'] = {name: {'HH': round(float(both[f'{name}_dhh'].median()), 2), 'HV': round(float(both[f'{name}_dhv'].median()), 2)}
                                   for name in INTERVALS} if len(both) else {}
        est = {}
        for t in THRESHOLDS_DB:
            ft, fc = flags(both, 'typhoon', t), flags(both, 'control', t)
            est[f'{t:g}'] = {}
            for kind in ft:
                st = float(both.loc[ft[kind], 'area_ha'].sum()) / max(area, 1e-9)
                sc = float(both.loc[fc[kind], 'area_ha'].sum()) / max(area, 1e-9)
                excess = max(st - sc, 0.0)
                # The measured share stands in for the parcels no frame covered well.
                est[f'{t:g}'][kind] = {'typhoon_share': round(st, 4), 'control_share': round(sc, 4), 'excess_share': round(excess, 4),
                                       'measured_excess_ha': round(excess * area, 1), 'suspected_area_ha': round(excess * out['area_ha'], 1)}
        out['estimate'] = est
        return out

    summary = {
        'schema_version': 'yunlin-nisar-change/1.0',
        'status': 'RADAR_SUSPECTED_NOT_VERIFIED',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'method': ('Per-parcel median NISAR GCOV change (dB). Flag when the HH median (HH_*) or the HH or HV median moves >= T dB, any direction, down or up. '
                   'Suspected area = (typhoon-interval flagged share - control-interval flagged share) x farmland area. No trained model.'),
        'screening_rule': f'>= {MIN_PIXELS} valid 20 m pixels and >= {int(MIN_COVERAGE * 100)}% of the parcel covered, both intervals, one frame',
        'thresholds_db': list(THRESHOLDS_DB),
        'frames': list(GRANULES),
        'intervals': {'061D': {'control': '2026-10-04 -> 2026-10-16', 'typhoon': '2026-10-16 -> 2026-10-28'},
                      '039A': {'control': '2026-10-02 -> 2026-10-14', 'typhoon': '2026-10-14 -> 2026-10-26'}},
        'frame_area_ha': {f: round(float(table.loc[(table['frame'] == f) & table['typhoon_screened'] & table['control_screened'], 'area_ha'].sum()), 1) for f in GRANULES},
        'interval_median_shift_db': {'note': 'typhoon minus control median change on county land; version offset plus any county-wide change, not removed', **offsets},
        'scenes': scenes,
        'source': 'NASA/ASF NISAR L2 GCOV (Earthdata Cloud)',
        'farmland_source': '國土利用現況調查 雲林縣 農作使用 (水田/旱田/果園)',
        'towns_source': 'NLSC TOWN_MOI_1120317',
        'total': summarize(table),
        'by_class': {c: summarize(table[table['cls'] == c]) for c in CLASSES.values()},
        'by_town': {t: summarize(g) for t, g in table.groupby('town')},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'yunlin_nisar_change.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with gzip.open(out_dir / 'yunlin_nisar_parcel_changes.csv.gz', 'wt', encoding='utf-8') as f:
        table.to_csv(f, index=False)
    return summary


if __name__ == '__main__':
    result = run(sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))
    print(json.dumps({'total': result['total'], 'interval_median_shift_db': result['interval_median_shift_db']}, ensure_ascii=False, indent=1))
