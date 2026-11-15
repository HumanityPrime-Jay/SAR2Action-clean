"""Render the Taixi NISAR map layers as dual-pol false colour (R = HH, G = HV, B = HH - HV).

Display only: each scene is drawn and stretched on its own, and dates are never subtracted (their
processing versions and orbits differ). The window and the township clip are taken from the existing
single-band map images, so the new layers sit exactly where the old ones did.

Usage: python scripts/render_nisar_map.py <pre.h5> <post.h5>
       python scripts/render_nisar_map.py --ascending-pair <pre granule URL> <post granule URL>
         Reads only the Taixi window of two remote GCOV files (Earthdata login from ~/.netrc), puts
         them on the same 20 m grid as the existing scenes and writes nisar_ascending_manifest.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h5py
import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import uniform_filter

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'frontend/public/studio'
GRID = 'science/LSAR/GCOV/grids/frequencyA'
# Each scene is stretched to its own 2nd-98th percentiles inside Taixi. Passes from different processing
# versions and orbit directions are offset in brightness, so shared fixed ranges would paint that offset
# as if the land had changed.
PERCENTILES = (2, 98)
SMOOTH_PX = 3  # 3 x 3 mean on linear power to calm speckle (60 m)


def _window(h5: h5py.File, corners: list[list[float]], shape: tuple[int, int]) -> tuple[slice, slice]:
    x = h5[f'{GRID}/xCoordinates'][:]
    y = h5[f'{GRID}/yCoordinates'][:]
    to_utm = Transformer.from_crs(4326, int(h5[f'{GRID}/projection'][()]), always_xy=True)
    west, north = to_utm.transform(*corners[0])
    col = int(np.argmin(np.abs(x - west)))
    row = int(np.argmin(np.abs(y - north)))
    return slice(row, row + shape[0]), slice(col, col + shape[1])


def _block_mean(power: np.ndarray, valid: np.ndarray, factor: int) -> np.ndarray:
    h, w = power.shape[0] // factor, power.shape[1] // factor
    p = np.where(valid, power, 0.0)[: h * factor, : w * factor].reshape(h, factor, w, factor).sum(axis=(1, 3))
    n = valid[: h * factor, : w * factor].reshape(h, factor, w, factor).sum(axis=(1, 3))
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(n == factor * factor, p / n, np.nan)


def _db(power: np.ndarray) -> np.ndarray:
    valid = np.isfinite(power) & (power > 0)
    filled = np.where(valid, power, 0.0)
    # Mean of valid neighbours only, so edges and holes don't darken.
    mean = uniform_filter(filled, SMOOTH_PX) / np.maximum(uniform_filter(valid.astype(float), SMOOTH_PX), 1e-6)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(valid, 10 * np.log10(mean), np.nan)


def _scale(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return (np.nan_to_num(np.clip((values - lo) / (hi - lo), 0, 1)) * 255).astype(np.uint8)


def _rgba(hh: np.ndarray, hv: np.ndarray, keep: np.ndarray) -> tuple[np.ndarray, dict]:
    shown = keep & np.isfinite(hh) & np.isfinite(hv)
    channels = {'HH': hh, 'HV': hv, 'HH-HV': hh - hv}
    stretch = {k: [round(float(v), 2) for v in np.percentile(c[shown], PERCENTILES)] for k, c in channels.items()}
    rgb = np.dstack([_scale(channels[k], *stretch[k]) for k in ('HH', 'HV', 'HH-HV')])
    return np.dstack([rgb, np.where(shown, 255, 0).astype(np.uint8)]), stretch


def render(h5_path: str, scene: dict) -> tuple[str, float]:
    old = np.array(Image.open(STUDIO / scene['layers']['HV']['image']).convert('RGBA'))
    keep = old[..., 3] > 0  # township clip and valid pixels, as drawn today
    with h5py.File(h5_path) as h5:
        rows, cols = _window(h5, scene['coordinates'], tuple(scene['grid_shape']))
        hh = _db(h5[f'{GRID}/HHHH'][rows, cols])
        hv = _db(h5[f'{GRID}/HVHV'][rows, cols])
    # Alignment check against the old HV layer's brightness.
    lum = old[..., :3].astype(float).mean(axis=2)
    both = keep & np.isfinite(hv)
    corr = float(np.corrcoef(lum[both], hv[both])[0, 1])
    name = f"nisar_{scene['period'].lower()}_rgb_map.png"
    image, stretch = _rgba(hh, hv, keep)
    Image.fromarray(image, 'RGBA').save(STUDIO / name, optimize=True)
    return name, corr, stretch


def main(pre_h5: str, post_h5: str) -> None:
    path = STUDIO / 'nisar_map_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for scene, h5_path in zip(manifest['scenes'], (pre_h5, post_h5)):
        if scene['scene_id'] not in h5_path:
            raise ValueError(f"{h5_path} is not {scene['scene_id']}")
        name, corr, stretch = render(h5_path, scene)
        if corr < 0.8:
            raise ValueError(f'{name} does not line up with the existing layer (r={corr:.2f})')
        scene['layers']['RGB'] = {'image': name, 'composite': 'R=HH G=HV B=HH-HV', 'display_stretch_db': stretch,
                                  'smoothing': f'{SMOOTH_PX}x{SMOOTH_PX} mean on linear power', 'alignment_r': round(corr, 3)}
        print(name, 'r =', round(corr, 3))
    manifest['display_method'] = ('Dual-pol false colour (R=HH, G=HV, B=HH-HV), each scene stretched to its own p02-p98 inside '
                                  'Taixi, 3x3 speckle mean; transparent outside the township and where a scene has no valid '
                                  'pixels; colours are not comparable across dates')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _paint(band: np.ndarray, low: float, high: float) -> np.ndarray:
    """Single-band layer in the same palette and alpha as frontend/scripts/render_nisar_map_assets.py."""
    valid = np.isfinite(band)
    t = np.clip((np.where(valid, band, low) - low) / (high - low), 0, 1)
    stops = np.array([[16, 28, 61], [44, 150, 174], [245, 212, 128]], dtype=float)
    halfway = t <= 0.5
    fraction = np.where(halfway, t * 2, (t - 0.5) * 2)[..., None]
    first = np.where(halfway[..., None], stops[0], stops[1])
    second = np.where(halfway[..., None], stops[1], stops[2])
    rgb = np.rint(first + (second - first) * fraction).astype(np.uint8)
    return np.dstack([rgb, np.where(valid, 220, 0).astype(np.uint8)])


def _read_on_pre_grid(fs, url: str, pre: dict) -> tuple[np.ndarray, np.ndarray, dict, int]:
    """HH and HV linear power of a remote GCOV on the PRE scene's 20 m grid, plus identification."""
    rows_n, cols_n = pre['grid_shape']
    to_utm = Transformer.from_crs(4326, 32651, always_xy=True)
    with fs.open(url, 'rb') as stream, h5py.File(stream) as h5:
        g = h5[GRID]
        x, y = g['xCoordinates'][:], g['yCoordinates'][:]
        if int(g['projection'][()]) != 32651:
            raise ValueError('Unexpected CRS')
        factor = int(round(20 / abs(x[1] - x[0])))
        # The PRE grid's first pixel centre, from its north-west corner.
        west, north = to_utm.transform(*pre['coordinates'][0])
        x0, y0 = round((west - 10) / 20) * 20 + 10, round((north - 10) / 20) * 20 + 10  # PRE centres sit on ...10 m
        half = 10 - 10 / factor
        col = int(np.argmin(np.abs(x - (x0 - half))))
        row = int(np.argmin(np.abs(y - (y0 + half))))
        if abs(x[col] - (x0 - half)) > 0.01 or abs(y[row] - (y0 + half)) > 0.01:
            raise ValueError('This grid does not nest inside the PRE grid')
        sl = (slice(row, row + rows_n * factor), slice(col, col + cols_n * factor))
        mask = g['mask'][sl]
        valid = (mask > 0) & (mask < 255)
        hh = g['HHHH'][sl]; hv = g['HVHV'][sl]
        valid &= np.isfinite(hh) & (hh > 0) & np.isfinite(hv) & (hv > 0)
        hh, hv = _block_mean(hh, valid, factor), _block_mean(hv, valid, factor)
        ident = h5['science/LSAR/identification']
        meta = {'acquisition_start_utc': ident['zeroDopplerStartTime'][()].decode(),
                'orbit_direction': ident['orbitPassDirection'][()].decode().upper(), 'track': int(ident['trackNumber'][()])}
    return hh, hv, meta, factor


def _earthdata_fs():
    import netrc

    import fsspec
    import requests

    login, _, password = netrc.netrc().authenticators('urs.earthdata.nasa.gov')
    token = requests.post('https://urs.earthdata.nasa.gov/api/users/find_or_create_token', auth=(login, password), timeout=30).json()['access_token']
    return fsspec.filesystem('https', headers={'Authorization': f'Bearer {token}'}, block_size=4 * 2**20)


def add_ascending_pair(pre_url: str, post_url: str) -> None:
    """The ascending 039 pair (10/14 -> 10/26) on the existing PRE grid. Both passes cover all of Taixi,
    so the field comparison can show complete images; the 10/28 descending pass misses the south."""
    manifest = json.loads((STUDIO / 'nisar_map_manifest.json').read_text(encoding='utf-8'))
    pre = next(s for s in manifest['scenes'] if s['period'] == 'PRE')
    town = np.array(Image.open(STUDIO / pre['layers']['RGB']['image']).convert('RGBA'))[..., 3] > 0  # Taixi clip
    fs = _earthdata_fs()
    out = {}
    for period, url in (('PRE_ASC', pre_url), ('POST_ASC', post_url)):
        hh, hv, meta, factor = _read_on_pre_grid(fs, url, pre)
        scene_id = url.rsplit('/', 1)[-1].removesuffix('.h5')
        layers = {}
        for pol, power in (('HH', hh), ('HV', hv)):
            with np.errstate(divide='ignore', invalid='ignore'):
                band = np.where(power > 0, 10 * np.log10(power), np.nan)
            low, high = (float(v) for v in np.nanpercentile(band, (5, 95)))
            name = f'nisar_{period.lower()}_{pol.lower()}_map.png'
            Image.fromarray(_paint(band, low, high), 'RGBA').save(STUDIO / name, optimize=True)
            layers[pol] = {'image': name, 'valid_pixels': int(np.isfinite(band).sum()), 'display_stretch_db': [round(low, 2), round(high, 2)]}
        image, stretch = _rgba(_db(hh), _db(hv), town)
        rgb_name = f'nisar_{period.lower()}_rgb_map.png'
        Image.fromarray(image, 'RGBA').save(STUDIO / rgb_name, optimize=True)
        layers['RGB'] = {'image': rgb_name, 'composite': 'R=HH G=HV B=HH-HV', 'display_stretch_db': stretch,
                         'smoothing': f'{factor}x{factor} block mean to 20 m, then {SMOOTH_PX}x{SMOOTH_PX} mean on linear power'}
        coverage = float((town & np.isfinite(hh)).sum() / town.sum())
        out[period] = {'period': period, 'scene_id': scene_id, **meta, 'crid': scene_id.split('_')[-5],
                       'product_maturity': 'VALIDATED' if 'GCOV_V1' in url else 'PROVISIONAL', 'crs': 'EPSG:32651',
                       'grid_shape': pre['grid_shape'], 'coordinates': pre['coordinates'], 'township_coverage': round(coverage, 3),
                       'layers': layers}
        print(period, scene_id[:60], 'Taixi coverage', round(coverage, 3))
    (STUDIO / 'nisar_ascending_manifest.json').write_text(json.dumps({
        'case_id': manifest['case_id'],
        'note': ('Ascending track 039 pair around the typhoon. Both passes cover all of Taixi, unlike the 10/28 '
                 'descending pass. Display only; each image keeps its own stretch.'),
        'display_method': 'HH/HV: own p05/p95 stretch per image, transparent where no valid pixel. RGB: ' + manifest['display_method'],
        'pre_scene': out['PRE_ASC'], 'scene': out['POST_ASC']}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == '--ascending-pair':
        add_ascending_pair(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
