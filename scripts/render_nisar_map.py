"""Render the Taixi NISAR map layers as dual-pol false colour (R = HH, G = HV, B = HH - HV).

Display only: each scene is drawn on its own, and the two dates are never subtracted (their
processing versions differ). The window and the township clip are taken from the existing
single-band map images, so the new layers sit exactly where the old ones did.

Usage: python scripts/render_nisar_map.py <pre.h5> <post.h5>
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
# Fixed ranges (dB) so both dates use the same colours.
STRETCH = {'HH': (-16.0, 2.0), 'HV': (-25.0, -10.0), 'HH-HV': (3.0, 15.0)}
SMOOTH_PX = 3  # 3 x 3 mean on linear power to calm speckle (60 m)


def _window(h5: h5py.File, corners: list[list[float]], shape: tuple[int, int]) -> tuple[slice, slice]:
    x = h5[f'{GRID}/xCoordinates'][:]
    y = h5[f'{GRID}/yCoordinates'][:]
    to_utm = Transformer.from_crs(4326, int(h5[f'{GRID}/projection'][()]), always_xy=True)
    west, north = to_utm.transform(*corners[0])
    col = int(np.argmin(np.abs(x - west)))
    row = int(np.argmin(np.abs(y - north)))
    return slice(row, row + shape[0]), slice(col, col + shape[1])


def _db(power: np.ndarray) -> np.ndarray:
    valid = np.isfinite(power) & (power > 0)
    filled = np.where(valid, power, 0.0)
    # Mean of valid neighbours only, so edges and holes don't darken.
    mean = uniform_filter(filled, SMOOTH_PX) / np.maximum(uniform_filter(valid.astype(float), SMOOTH_PX), 1e-6)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(valid, 10 * np.log10(mean), np.nan)


def _scale(values: np.ndarray, key: str) -> np.ndarray:
    lo, hi = STRETCH[key]
    return (np.nan_to_num(np.clip((values - lo) / (hi - lo), 0, 1)) * 255).astype(np.uint8)


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
    rgb = np.dstack([_scale(hh, 'HH'), _scale(hv, 'HV'), _scale(hh - hv, 'HH-HV')])
    alpha = np.where(keep & np.isfinite(hh) & np.isfinite(hv), 255, 0).astype(np.uint8)
    name = f"nisar_{scene['period'].lower()}_rgb_map.png"
    Image.fromarray(np.dstack([rgb, alpha]), 'RGBA').save(STUDIO / name, optimize=True)
    return name, corr


def main(pre_h5: str, post_h5: str) -> None:
    path = STUDIO / 'nisar_map_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for scene, h5_path in zip(manifest['scenes'], (pre_h5, post_h5)):
        if scene['scene_id'] not in h5_path:
            raise ValueError(f"{h5_path} is not {scene['scene_id']}")
        name, corr = render(h5_path, scene)
        if corr < 0.8:
            raise ValueError(f'{name} does not line up with the existing layer (r={corr:.2f})')
        scene['layers']['RGB'] = {'image': name, 'composite': 'R=HH G=HV B=HH-HV', 'display_stretch_db': STRETCH,
                                  'smoothing': f'{SMOOTH_PX}x{SMOOTH_PX} mean on linear power', 'alignment_r': round(corr, 3)}
        print(name, 'r =', round(corr, 3))
    manifest['display_method'] = ('Dual-pol false colour per scene (R=HH, G=HV, B=HH-HV) with fixed dB ranges and a 3x3 speckle '
                                  'mean; transparent outside the township and where a scene has no valid pixels; '
                                  'not a quantitative cross-date comparison')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
