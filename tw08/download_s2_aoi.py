"""Download and clip Sentinel-2 L2A COG windows over the TW-01 Yunlin 5x5 km AOI.

Strict isolation: reads AOI bounds matching TW-01 (`EPSG:32651`, 222150..227250 E,
2622180..2627280 N) and writes only into `tw08/inputs/`. Does not modify `sar/`,
`tw01/`, `tw03/`, `backend/`, or `frontend/`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "inputs"

STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
AOI_BBOX_WGS84 = [120.2745, 23.6865, 120.3256, 23.7335]
DATETIME_WINDOW = "2026-10-01T00:00:00Z/2026-11-10T23:59:59Z"

# Exact EPSG:32651 grid bounds aligned to BOTH MGRS-51QTG 10m/20m native pixels AND covering TW-01 AOI
# Note: MGRS-51QTG origin is (199980 E, 2700000 N). Expanding X by 10m on each side (222150->222140,
# 227250->227260) aligns both 10m (510x512) and 20m (255x256) grids to exact integer pixel offsets
# so every 20m SCL/RedEdge/SWIR pixel matches a 2x2 block of 10m pixels with zero resampling shift.
AOI_MIN_X = 222140.0
AOI_MIN_Y = 2622180.0
AOI_MAX_X = 227260.0
AOI_MAX_Y = 2627280.0

TARGET_SCENES: list[tuple[str, str]] = [
    ("2026-10-11", "S2B_51QTG_20261011_0_L2A"),
    ("2026-10-16", "S2C_51QTG_20261016_0_L2A"),
    ("2026-10-26", "S2C_51QTG_20261026_0_L2A"),
    ("2026-11-05", "S2C_51QTG_20261105_0_L2A"),
]

# (canonical_band_name, earthsearch_asset_key, expected_resolution_m, expected_shape)
REQUIRED_BANDS: list[tuple[str, str, int, tuple[int, int]]] = [
    ("B02", "blue", 10, (510, 512)),
    ("B03", "green", 10, (510, 512)),
    ("B04", "red", 10, (510, 512)),
    ("B08", "nir", 10, (510, 512)),
    ("B05", "rededge1", 20, (255, 256)),
    ("B8A", "nir08", 20, (255, 256)),
    ("B11", "swir16", 20, (255, 256)),
    ("B12", "swir22", 20, (255, 256)),
    ("SCL", "scl", 20, (255, 256)),
]


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def query_stac_scenes() -> dict[str, dict[str, Any]]:
    """Query Earth Search STAC API v1 for the 4 target Yunlin MGRS-51QTG Sentinel-2 L2A scenes."""
    payload = {
        "collections": [COLLECTION],
        "bbox": AOI_BBOX_WGS84,
        "datetime": DATETIME_WINDOW,
        "limit": 50,
    }
    resp = httpx.post(STAC_SEARCH_URL, json=payload, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    features = data.get("features", [])
    by_id = {feat["id"]: feat for feat in features}

    missing_ids = [scene_id for _, scene_id in TARGET_SCENES if scene_id not in by_id]
    if missing_ids:
        raise RuntimeError(f"Missing target STAC scene IDs from search results: {missing_ids}")
    return by_id


def clip_and_save_band(
    stac_id: str,
    band_name: str,
    asset_info: dict[str, Any],
    res_m: int,
    expected_shape: tuple[int, int],
) -> dict[str, Any]:
    """Read exact AOI window from remote COG in EPSG:32651 and write compressed GeoTIFF."""
    href = asset_info["href"]
    out_path = INPUT_DIR / f"{stac_id}_{band_name}.tif"

    with rasterio.open(href) as src:
        if src.crs is None or src.crs.to_epsg() != 32651:
            raise ValueError(f"{stac_id} {band_name}: unexpected CRS {src.crs}; expected EPSG:32651")
        if src.res != (float(res_m), float(res_m)):
            raise ValueError(
                f"{stac_id} {band_name}: unexpected resolution {src.res}; expected ({res_m}, {res_m})"
            )

        raw_win = rasterio.windows.from_bounds(
            AOI_MIN_X, AOI_MIN_Y, AOI_MAX_X, AOI_MAX_Y, transform=src.transform
        )
        col_off = int(round(raw_win.col_off))
        row_off = int(round(raw_win.row_off))
        if abs(raw_win.col_off - col_off) > 1e-6 or abs(raw_win.row_off - row_off) > 1e-6:
            raise ValueError(
                f"{stac_id} {band_name}: sub-pixel window offset detected ({raw_win.col_off}, {raw_win.row_off})"
            )

        window = Window(col_off, row_off, expected_shape[1], expected_shape[0])
        arr = src.read(1, window=window)
        if arr.shape != expected_shape:
            raise ValueError(f"{stac_id} {band_name}: got shape {arr.shape}, expected {expected_shape}")

        win_transform = src.window_transform(window)
        nodata_val = src.nodata if src.nodata is not None else 0

        profile = {
            "driver": "GTiff",
            "height": expected_shape[0],
            "width": expected_shape[1],
            "count": 1,
            "dtype": str(arr.dtype),
            "crs": src.crs,
            "transform": win_transform,
            "nodata": nodata_val,
            "compress": "deflate",
        }
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(arr, 1)
            dst.update_tags(
                stac_id=stac_id,
                band=band_name,
                source_url=href,
                resolution_m=str(res_m),
            )

    if band_name == "SCL":
        nonzero_valid = int(np.count_nonzero(arr > 0))
    else:
        nonzero_valid = int(np.count_nonzero(arr > 0))

    return {
        "band": band_name,
        "asset_key": None,  # filled by caller
        "filename": out_path.name,
        "resolution_m": res_m,
        "shape": list(expected_shape),
        "dtype": str(arr.dtype),
        "transform": list(win_transform)[:6],
        "nonzero_pixels": nonzero_valid,
        "file_bytes": out_path.stat().st_size,
        "sha256": _sha256(out_path),
        "source_href": href,
        "stac_raster_bands": asset_info.get("raster:bands", []),
    }


def main() -> int:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    by_id = query_stac_scenes()

    inventory: dict[str, Any] = {
        "schema_version": "tw08a-stac-inputs/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stac_endpoint": STAC_SEARCH_URL,
        "collection": COLLECTION,
        "aoi_crs": "EPSG:32651",
        "aoi_bounds_epsg32651": [AOI_MIN_X, AOI_MIN_Y, AOI_MAX_X, AOI_MAX_Y],
        "aoi_bbox_wgs84": AOI_BBOX_WGS84,
        "scenes": [],
    }

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
    ):
        for date_str, stac_id in TARGET_SCENES:
            feat = by_id[stac_id]
            props = feat["properties"]
            assets = feat["assets"]
            scene_rec: dict[str, Any] = {
                "date": date_str,
                "stac_id": stac_id,
                "product_uri": props.get("s2:product_uri"),
                "datetime_utc": props.get("datetime"),
                "platform": props.get("platform"),
                "mgrs_tile": props.get("grid:code"),
                "processing_baseline": props.get("s2:processing_baseline"),
                "tile_cloud_cover_percent": props.get("eo:cloud_cover"),
                "earthsearch_boa_offset_applied": props.get("earthsearch:boa_offset_applied"),
                "bands": {},
            }
            print(
                f"Downloading {date_str} | {stac_id} | {props.get('s2:product_uri')} "
                f"(tile cloud={props.get('eo:cloud_cover'):.2f}%)"
            )
            for band_name, asset_key, res_m, expected_shape in REQUIRED_BANDS:
                if asset_key not in assets:
                    raise KeyError(f"{stac_id}: missing STAC asset key '{asset_key}'")
                rec = clip_and_save_band(stac_id, band_name, assets[asset_key], res_m, expected_shape)
                rec["asset_key"] = asset_key
                scene_rec["bands"][band_name] = rec
            inventory["scenes"].append(scene_rec)

    inv_path = INPUT_DIR / "stac_inventory.json"
    with inv_path.open("w", encoding="utf-8") as stream:
        json.dump(inventory, stream, ensure_ascii=False, indent=2)

    print(f"Successfully downloaded and clipped {len(inventory['scenes']) * len(REQUIRED_BANDS)} GeoTIFFs.")
    print(f"Saved STAC inventory to {inv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
