"""TW-08A: Real Sentinel-2 L2A multi-temporal vegetation & SCL QA pipeline over Yunlin AOI.

Strict scientific & repository guardrails:
- Reads only from `tw08/inputs/` and read-only geometry/manifest files in `tw01/taiwan-agricultural-demo-v1/`.
- Writes outputs strictly to `tw08/sentinel2-demo-v1/`.
- Does NOT modify `sar/`, `tw01/`, `tw03/`, `backend/`, `frontend/`, or 181 SAR candidate definitions.
- Preserves native 10 m (`NDVI`) and 20 m (`NDRE`, `LSWI`, `SCL`) grids without cross-resolution distortion.
- Does NOT apply duplicate -0.1 offset on Element84 COGs where `earthsearch:boa_offset_applied == True`.
- Does NOT infer crop type names, classification accuracy, crop damage, or causal disaster attribution.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import rasterio
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.plot import plotting_extent
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds
from rasterio.windows import Window
from scipy import stats
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
INPUT_DIR = ROOT / "inputs"
TW01_DIR = REPO_ROOT / "tw01" / "taiwan-agricultural-demo-v1"
OUT_DIR = ROOT / "sentinel2-demo-v1"

EXPECTED_CRS_EPSG = 32651
SHAPE_10M = (510, 512)
SHAPE_20M = (255, 256)
AOI_BOUNDS_32651 = (222140.0, 2622180.0, 227260.0, 2627280.0)

SCL_CLASS_NAMES: dict[int, str] = {
    0: "no_data",
    1: "saturated_or_defective",
    2: "dark_area_pixels",
    3: "cloud_shadows",
    4: "vegetation",
    5: "not_vegetated",
    6: "water",
    7: "unclassified",
    8: "cloud_medium_probability",
    9: "cloud_high_probability",
    10: "thin_cirrus",
    11: "snow_or_ice",
}

CLEAR_SCL_CLASSES = (4, 5, 6)
CLOUD_SHADOW_SCL_CLASSES = (3, 8, 9, 10)
SCALE_BOA = 0.0001  # Element84 `earthsearch:boa_offset_applied=True` already shifted DN by -1000.


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe_stat(arr: np.ndarray, fn: Any) -> float | None:
    vals = arr[np.isfinite(arr)]
    if vals.size == 0:
        return None
    return round(float(fn(vals)), 6)


def _summarize_array(arr: np.ndarray) -> dict[str, Any]:
    vals = arr[np.isfinite(arr)]
    if vals.size == 0:
        return {"count": 0, "mean": None, "std": None, "p10": None, "p25": None, "median": None, "p75": None, "p90": None}
    q10, q25, q50, q75, q90 = np.percentile(vals, [10, 25, 50, 75, 90])
    return {
        "count": int(vals.size),
        "mean": round(float(np.mean(vals)), 6),
        "std": round(float(np.std(vals)), 6),
        "p10": round(float(q10), 6),
        "p25": round(float(q25), 6),
        "median": round(float(q50), 6),
        "p75": round(float(q75), 6),
        "p90": round(float(q90), 6),
    }


def _normalized_diff(band_a: np.ndarray, band_b: np.ndarray, valid: np.ndarray) -> np.ndarray:
    num = band_a - band_b
    den = band_a + band_b
    out = np.full(band_a.shape, np.nan, dtype=np.float32)
    mask = valid & np.isfinite(num) & np.isfinite(den) & (np.abs(den) > 1e-6)
    out[mask] = (num[mask] / den[mask]).astype(np.float32)
    out[mask] = np.clip(out[mask], -1.0, 1.0)
    return out


def _save_float_geotiff(
    path: Path,
    array: np.ndarray,
    crs: Any,
    transform: Any,
    tags: dict[str, str],
) -> None:
    h, w = array.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(array.astype(np.float32), 1)
        dst.update_tags(**tags)


def _save_overlay_png(
    array: np.ndarray,
    src_crs: Any,
    src_transform: Any,
    out_png: Path,
    cmap_name: str,
    vmin: float,
    vmax: float,
) -> dict[str, Any]:
    h, w = array.shape
    left, bottom, right, top = rasterio.transform.array_bounds(h, w, src_transform)
    dst_crs = "EPSG:3857"
    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, dst_crs, w, h, left, bottom, right, top
    )
    pixels = np.full((dst_h, dst_w), np.nan, dtype=np.float32)
    reproject(
        array.astype(np.float32),
        pixels,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=np.nan,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    norm = plt.Normalize(vmin=vmin, vmax=vmax, clip=True)
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad(alpha=0.0)
    rgba = cmap(np.ma.masked_invalid(norm(pixels)), bytes=True)
    # Explicitly guarantee NaN pixels are transparent (alpha=0)
    rgba[np.isnan(pixels), 3] = 0
    Image.fromarray(rgba).save(out_png)
    west, south, east, north = transform_bounds(
        dst_crs, "EPSG:4326", *rasterio.transform.array_bounds(dst_h, dst_w, dst_transform)
    )
    return {
        "href": out_png.name,
        "crs": dst_crs,
        "render_range": [vmin, vmax],
        "coordinates_lon_lat": [
            [west, north],
            [east, north],
            [east, south],
            [west, south],
        ],
    }


def _parcel_slice_mask(
    geom: Any,
    grid_shape: tuple[int, int],
    grid_transform: Any,
) -> tuple[slice, slice, np.ndarray, bool]:
    """Compute exact boolean pixel footprint inside a tight bounding-box slice."""
    minx, miny, maxx, maxy = geom.bounds
    h, w = grid_shape
    inv = ~grid_transform
    c0f, r1f = inv * (minx, maxy)
    c1f, r0f = inv * (maxx, miny)
    c0 = max(0, int(np.floor(min(c0f, c1f))) - 1)
    c1 = min(w, int(np.ceil(max(c0f, c1f))) + 2)
    r0 = max(0, int(np.floor(min(r0f, r1f))) - 1)
    r1 = min(h, int(np.ceil(max(r0f, r1f))) + 2)
    if c1 <= c0 or r1 <= r0:
        return slice(0, 0), slice(0, 0), np.zeros((0, 0), dtype=bool), False

    sub_win = Window(c0, r0, c1 - c0, r1 - r0)
    sub_transform = rasterio.windows.transform(sub_win, grid_transform)
    sub_shape = (r1 - r0, c1 - c0)
    geo_list = [mapping(geom)]
    mask = geometry_mask(geo_list, out_shape=sub_shape, transform=sub_transform, invert=True, all_touched=False)
    fallback = False
    if not np.any(mask):
        mask = geometry_mask(geo_list, out_shape=sub_shape, transform=sub_transform, invert=True, all_touched=True)
        fallback = bool(np.any(mask))
    return slice(r0, r1), slice(c0, c1), mask, fallback


def load_and_validate_inputs(inventory: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate downloaded AOI GeoTIFFs and load native 10m & 20m arrays."""
    grid_info: dict[str, Any] = {}
    loaded_scenes: list[dict[str, Any]] = []

    for scene in inventory["scenes"]:
        stac_id = scene["stac_id"]
        if not scene.get("earthsearch_boa_offset_applied", False):
            raise ValueError(f"{stac_id}: expected earthsearch:boa_offset_applied=True; inspect offset rules.")

        arrays_10m: dict[str, np.ndarray] = {}
        arrays_20m: dict[str, np.ndarray] = {}
        for band_name, band_meta in scene["bands"].items():
            tif_path = INPUT_DIR / band_meta["filename"]
            if not tif_path.is_file():
                raise FileNotFoundError(f"Missing input raster: {tif_path}")
            if _sha256(tif_path) != band_meta["sha256"]:
                raise ValueError(f"SHA-256 mismatch on input raster: {tif_path}")

            with rasterio.open(tif_path) as ds:
                if ds.crs is None or ds.crs.to_epsg() != EXPECTED_CRS_EPSG:
                    raise ValueError(f"{tif_path}: CRS mismatch {ds.crs}")
                res_m = int(band_meta["resolution_m"])
                expected_shape = SHAPE_10M if res_m == 10 else SHAPE_20M
                if ds.shape != expected_shape:
                    raise ValueError(f"{tif_path}: shape {ds.shape} != {expected_shape}")
                bounds = tuple(round(v, 3) for v in ds.bounds)
                if bounds != AOI_BOUNDS_32651:
                    raise ValueError(f"{tif_path}: bounds {bounds} != {AOI_BOUNDS_32651}")

                key_res = f"{res_m}m"
                if key_res not in grid_info:
                    grid_info[key_res] = {
                        "crs": ds.crs,
                        "crs_epsg": EXPECTED_CRS_EPSG,
                        "shape": ds.shape,
                        "transform": ds.transform,
                    }
                elif list(ds.transform)[:6] != list(grid_info[key_res]["transform"])[:6]:
                    raise ValueError(f"{tif_path}: transform drift detected.")

                arr = ds.read(1)
                if res_m == 10:
                    arrays_10m[band_name] = arr
                else:
                    arrays_20m[band_name] = arr

        loaded_scenes.append(
            {
                "meta": scene,
                "arrays_10m": arrays_10m,
                "arrays_20m": arrays_20m,
            }
        )
    return loaded_scenes, grid_info


def compute_scene_indices_and_qa(
    loaded_scenes: list[dict[str, Any]],
    grid_info: dict[str, Any],
    inside_10m: np.ndarray,
    inside_20m: np.ndarray,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Compute SCL QA stats and native 10m/20m vegetation indices per date."""
    crs = grid_info["10m"]["crs"]
    tf10 = grid_info["10m"]["transform"]
    tf20 = grid_info["20m"]["transform"]

    epoch_arrays: dict[str, dict[str, Any]] = {}
    epoch_reports: list[dict[str, Any]] = []

    aoi_px_10m = int(np.sum(inside_10m))
    aoi_px_20m = int(np.sum(inside_20m))

    for entry in loaded_scenes:
        meta = entry["meta"]
        date_str = meta["date"]
        ymd = date_str.replace("-", "")
        stac_id = meta["stac_id"]
        a10 = entry["arrays_10m"]
        a20 = entry["arrays_20m"]

        scl20 = a20["SCL"]
        scl10 = np.repeat(np.repeat(scl20, 2, axis=0), 2, axis=1)

        # SCL breakdown within TW-01 AOI polygon on native 20 m grid
        scl_counts: dict[str, int] = {}
        scl_fractions: dict[str, float] = {}
        for cls_id, cls_name in SCL_CLASS_NAMES.items():
            cnt = int(np.sum(inside_20m & (scl20 == cls_id)))
            scl_counts[f"{cls_id}_{cls_name}"] = cnt
            scl_fractions[f"{cls_id}_{cls_name}"] = round(cnt / aoi_px_20m, 6)

        clear_20m_scl = inside_20m & np.isin(scl20, CLEAR_SCL_CLASSES)
        cloud_20m_scl = inside_20m & np.isin(scl20, CLOUD_SHADOW_SCL_CLASSES)

        valid_10m = (
            inside_10m
            & np.isin(scl10, CLEAR_SCL_CLASSES)
            & (a10["B02"] > 0)
            & (a10["B03"] > 0)
            & (a10["B04"] > 0)
            & (a10["B08"] > 0)
        )
        valid_20m = (
            clear_20m_scl
            & (a20["B05"] > 0)
            & (a20["B8A"] > 0)
            & (a20["B11"] > 0)
            & (a20["B12"] > 0)
        )

        # Convert DN to BOA surface reflectance using verified Element84 scale only
        b02 = np.where(a10["B02"] > 0, a10["B02"].astype(np.float32) * SCALE_BOA, np.nan)
        b03 = np.where(a10["B03"] > 0, a10["B03"].astype(np.float32) * SCALE_BOA, np.nan)
        b04 = np.where(a10["B04"] > 0, a10["B04"].astype(np.float32) * SCALE_BOA, np.nan)
        b08 = np.where(a10["B08"] > 0, a10["B08"].astype(np.float32) * SCALE_BOA, np.nan)

        b05 = np.where(a20["B05"] > 0, a20["B05"].astype(np.float32) * SCALE_BOA, np.nan)
        b8a = np.where(a20["B8A"] > 0, a20["B8A"].astype(np.float32) * SCALE_BOA, np.nan)
        b11 = np.where(a20["B11"] > 0, a20["B11"].astype(np.float32) * SCALE_BOA, np.nan)

        ndvi_10m = _normalized_diff(b08, b04, valid_10m)
        ndre_20m = _normalized_diff(b8a, b05, valid_20m)
        lswi_20m = _normalized_diff(b8a, b11, valid_20m)

        # Save clipped index GeoTIFFs + SCL GeoTIFF + Map PNG overlay
        ndvi_tif = OUT_DIR / f"ndvi_{ymd}.tif"
        ndre_tif = OUT_DIR / f"ndre_{ymd}.tif"
        lswi_tif = OUT_DIR / f"lswi_{ymd}.tif"
        scl_tif = OUT_DIR / f"scl_{ymd}.tif"

        common_tags = {
            "stac_id": stac_id,
            "product_uri": str(meta["product_uri"]),
            "date_utc": date_str,
            "boa_offset_applied_at_source": "True",
            "reflectance_formula": "dn * 0.0001 (no duplicate -0.1 subtraction)",
        }
        _save_float_geotiff(ndvi_tif, ndvi_10m, crs, tf10, {**common_tags, "index": "NDVI", "resolution_m": "10"})
        _save_float_geotiff(ndre_tif, ndre_20m, crs, tf20, {**common_tags, "index": "NDRE", "resolution_m": "20"})
        _save_float_geotiff(lswi_tif, lswi_20m, crs, tf20, {**common_tags, "index": "LSWI", "resolution_m": "20"})

        with rasterio.open(
            scl_tif,
            "w",
            driver="GTiff",
            height=SHAPE_20M[0],
            width=SHAPE_20M[1],
            count=1,
            dtype="uint8",
            crs=crs,
            transform=tf20,
            nodata=0,
            compress="deflate",
        ) as dst:
            dst.write(scl20.astype(np.uint8), 1)
            dst.update_tags(**common_tags, index="SCL", resolution_m="20")

        ndvi_overlay = _save_overlay_png(
            ndvi_10m, crs, tf10, OUT_DIR / f"ndvi_{ymd}_overlay.png", "RdYlGn", -0.2, 0.9
        )

        valid_frac_10m = float(np.sum(valid_10m)) / aoi_px_10m
        valid_frac_20m = float(np.sum(valid_20m)) / aoi_px_20m
        cloud_frac_20m = float(np.sum(cloud_20m_scl)) / aoi_px_20m

        if valid_frac_10m >= 0.70:
            usability = "USABLE_CLEAR"
        elif valid_frac_10m >= 0.20:
            usability = "PARTIAL_CLOUD"
        else:
            usability = "CLOUD_OBSCURED_UNUSABLE"

        rgb = np.stack([b04, b03, b02], axis=-1)

        epoch_arrays[date_str] = {
            "ymd": ymd,
            "stac_id": stac_id,
            "usability": usability,
            "valid_frac_10m": valid_frac_10m,
            "valid_10m": valid_10m,
            "valid_20m": valid_20m,
            "ndvi": ndvi_10m,
            "ndre": ndre_20m,
            "lswi": lswi_20m,
            "scl20": scl20,
            "rgb_10m": rgb,
        }

        epoch_reports.append(
            {
                "date_utc": date_str,
                "acquisition_utc": meta["datetime_utc"],
                "stac_id": stac_id,
                "product_uri": meta["product_uri"],
                "platform": meta["platform"],
                "mgrs_tile": meta["mgrs_tile"],
                "processing_baseline": meta["processing_baseline"],
                "tile_cloud_cover_percent": meta["tile_cloud_cover_percent"],
                "earthsearch_boa_offset_applied": meta["earthsearch_boa_offset_applied"],
                "aoi_10m_pixels": aoi_px_10m,
                "aoi_20m_pixels": aoi_px_20m,
                "aoi_valid_pixels_10m": int(np.sum(valid_10m)),
                "aoi_valid_fraction_10m": round(valid_frac_10m, 6),
                "aoi_valid_pixels_20m": int(np.sum(valid_20m)),
                "aoi_valid_fraction_20m": round(valid_frac_20m, 6),
                "aoi_cloud_shadow_fraction_20m": round(cloud_frac_20m, 6),
                "usability_status": usability,
                "scl_counts_20m": scl_counts,
                "scl_fractions_20m": scl_fractions,
                "aoi_ndvi_stats_10m": _summarize_array(np.where(inside_10m, ndvi_10m, np.nan)),
                "aoi_ndre_stats_20m": _summarize_array(np.where(inside_20m, ndre_20m, np.nan)),
                "aoi_lswi_stats_20m": _summarize_array(np.where(inside_20m, lswi_20m, np.nan)),
                "outputs": {
                    "ndvi_tif": ndvi_tif.name,
                    "ndre_tif": ndre_tif.name,
                    "lswi_tif": lswi_tif.name,
                    "scl_tif": scl_tif.name,
                    "ndvi_overlay": ndvi_overlay,
                },
            }
        )

    return epoch_arrays, epoch_reports


def compute_delta_rasters(
    epoch_arrays: dict[str, dict[str, Any]],
    grid_info: dict[str, Any],
    inside_10m: np.ndarray,
    inside_20m: np.ndarray,
) -> list[dict[str, Any]]:
    """Compute signed multi-temporal optical changes across usable dates."""
    usable_dates = [d for d, info in epoch_arrays.items() if info["usability"] != "CLOUD_OBSCURED_UNUSABLE"]
    pairs: list[tuple[str, str]] = []
    if len(usable_dates) >= 2:
        for i in range(len(usable_dates)):
            for j in range(i + 1, len(usable_dates)):
                pairs.append((usable_dates[i], usable_dates[j]))

    crs = grid_info["10m"]["crs"]
    tf10 = grid_info["10m"]["transform"]
    tf20 = grid_info["20m"]["transform"]

    pair_records: list[dict[str, Any]] = []
    for d0, d1 in pairs:
        e0 = epoch_arrays[d0]
        e1 = epoch_arrays[d1]
        tag = f"{e0['ymd']}_{e1['ymd']}"

        dndvi = (e1["ndvi"] - e0["ndvi"]).astype(np.float32)
        dndre = (e1["ndre"] - e0["ndre"]).astype(np.float32)
        dlswi = (e1["lswi"] - e0["lswi"]).astype(np.float32)

        common_10 = inside_10m & e0["valid_10m"] & e1["valid_10m"]
        common_20 = inside_20m & e0["valid_20m"] & e1["valid_20m"]

        f_ndvi = OUT_DIR / f"delta_ndvi_{tag}.tif"
        f_ndre = OUT_DIR / f"delta_ndre_{tag}.tif"
        f_lswi = OUT_DIR / f"delta_lswi_{tag}.tif"
        _save_float_geotiff(f_ndvi, dndvi, crs, tf10, {"pair": f"{d0}->{d1}", "index": "delta_NDVI"})
        _save_float_geotiff(f_ndre, dndre, crs, tf20, {"pair": f"{d0}->{d1}", "index": "delta_NDRE"})
        _save_float_geotiff(f_lswi, dlswi, crs, tf20, {"pair": f"{d0}->{d1}", "index": "delta_LSWI"})
        overlay = _save_overlay_png(
            dndvi, crs, tf10, OUT_DIR / f"delta_ndvi_{tag}_overlay.png", "BrBG", -0.5, 0.5
        )

        pair_records.append(
            {
                "t0_date": d0,
                "t1_date": d1,
                "common_valid_fraction_10m": round(float(np.sum(common_10)) / int(np.sum(inside_10m)), 6),
                "common_valid_fraction_20m": round(float(np.sum(common_20)) / int(np.sum(inside_20m)), 6),
                "delta_ndvi_stats": _summarize_array(np.where(common_10, dndvi, np.nan)),
                "delta_ndre_stats": _summarize_array(np.where(common_20, dndre, np.nan)),
                "delta_lswi_stats": _summarize_array(np.where(common_20, dlswi, np.nan)),
                "outputs": {
                    "delta_ndvi_tif": f_ndvi.name,
                    "delta_ndre_tif": f_ndre.name,
                    "delta_lswi_tif": f_lswi.name,
                    "delta_ndvi_overlay": overlay,
                },
            }
        )

    return pair_records


def extract_parcel_timeseries(
    parcels_gdf: gpd.GeoDataFrame,
    tw01_sar_by_id: dict[int, dict[str, Any]],
    epoch_arrays: dict[str, dict[str, Any]],
    grid_info: dict[str, Any],
    key_pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Extract parcel-level multi-temporal optical indices & quality flags at native 10m & 20m."""
    projected = parcels_gdf.to_crs(grid_info["10m"]["crs"])
    tf10 = grid_info["10m"]["transform"]
    tf20 = grid_info["20m"]["transform"]
    dates = list(epoch_arrays.keys())

    rows: list[dict[str, Any]] = []
    for row in projected.itertuples():
        fid = int(row.parcel_feature_id)
        parcel_no = str(getattr(row, "PARCEL_NO", f"FEATURE-{fid}"))
        area_m2 = float(getattr(row, "clipped_area_m2", 0.0) or 0.0)
        area_ha = round(area_m2 / 10_000.0, 8)
        sar_rec = tw01_sar_by_id.get(fid)

        r10_sl, c10_sl, fp10, fb10 = _parcel_slice_mask(row.geometry, SHAPE_10M, tf10)
        r20_sl, c20_sl, fp20, fb20 = _parcel_slice_mask(row.geometry, SHAPE_20M, tf20)
        tot10 = int(np.sum(fp10))
        tot20 = int(np.sum(fp20))

        rec: dict[str, Any] = {
            "parcel_feature_id": fid,
            "parcel_no": parcel_no,
            "clipped_area_m2": area_m2,
            "clipped_area_ha": area_ha,
            "is_tw01_sar_candidate_181": sar_rec is not None,
            "sar_valid_pixel_count_30m": sar_rec["valid_pixel_count"] if sar_rec else None,
            "sar_coverage_fraction_30m": sar_rec["coverage_fraction"] if sar_rec else None,
            "sar_median_delta_vv_db": sar_rec["median_delta_db"]["VV"] if sar_rec else None,
            "sar_median_delta_vh_db": sar_rec["median_delta_db"]["VH"] if sar_rec else None,
            "total_pixels_10m": tot10,
            "total_pixels_20m": tot20,
            "all_touched_fallback_10m": fb10,
            "all_touched_fallback_20m": fb20,
        }

        per_date_medians: dict[str, dict[str, float | None]] = {}
        per_date_valid_flags: dict[str, dict[str, bool]] = {}

        for d in dates:
            ymd = epoch_arrays[d]["ymd"]
            e = epoch_arrays[d]
            if tot10 > 0:
                v10_sub = e["valid_10m"][r10_sl, c10_sl][fp10]
                v10_cnt = int(np.sum(v10_sub))
                cov10 = round(v10_cnt / tot10, 4)
                ndvi_vals = e["ndvi"][r10_sl, c10_sl][fp10 & e["valid_10m"][r10_sl, c10_sl]]
                ndvi_med = _safe_stat(ndvi_vals, np.median)
                ndvi_iqr = (
                    round(float(np.percentile(ndvi_vals, 75) - np.percentile(ndvi_vals, 25)), 6)
                    if ndvi_vals.size > 0
                    else None
                )
            else:
                v10_cnt, cov10, ndvi_med, ndvi_iqr = 0, 0.0, None, None

            if tot20 > 0:
                v20_sub = e["valid_20m"][r20_sl, c20_sl][fp20]
                v20_cnt = int(np.sum(v20_sub))
                cov20 = round(v20_cnt / tot20, 4)
                ndre_vals = e["ndre"][r20_sl, c20_sl][fp20 & e["valid_20m"][r20_sl, c20_sl]]
                lswi_vals = e["lswi"][r20_sl, c20_sl][fp20 & e["valid_20m"][r20_sl, c20_sl]]
                ndre_med = _safe_stat(ndre_vals, np.median)
                lswi_med = _safe_stat(lswi_vals, np.median)
            else:
                v20_cnt, cov20, ndre_med, lswi_med = 0, 0.0, None, None

            is_v10 = (v10_cnt >= 5) and (cov10 >= 0.80) and (ndvi_med is not None)
            is_v20 = (v20_cnt >= 2) and (cov20 >= 0.80) and (ndre_med is not None)

            rec[f"valid_px_10m_{ymd}"] = v10_cnt
            rec[f"cov_10m_{ymd}"] = cov10
            rec[f"is_valid_10m_{ymd}"] = is_v10
            rec[f"ndvi_med_{ymd}"] = ndvi_med
            rec[f"ndvi_iqr_{ymd}"] = ndvi_iqr

            rec[f"valid_px_20m_{ymd}"] = v20_cnt
            rec[f"cov_20m_{ymd}"] = cov20
            rec[f"is_valid_20m_{ymd}"] = is_v20
            rec[f"ndre_med_{ymd}"] = ndre_med
            rec[f"lswi_med_{ymd}"] = lswi_med

            per_date_medians[d] = {"ndvi": ndvi_med, "ndre": ndre_med, "lswi": lswi_med}
            per_date_valid_flags[d] = {"v10": is_v10, "v20": is_v20}

        for d0, d1 in key_pairs:
            tag = f"{epoch_arrays[d0]['ymd']}_{epoch_arrays[d1]['ymd']}"
            both_10 = per_date_valid_flags[d0]["v10"] and per_date_valid_flags[d1]["v10"]
            both_20 = per_date_valid_flags[d0]["v20"] and per_date_valid_flags[d1]["v20"]

            dndvi = (
                round(per_date_medians[d1]["ndvi"] - per_date_medians[d0]["ndvi"], 6)
                if both_10 and per_date_medians[d1]["ndvi"] is not None and per_date_medians[d0]["ndvi"] is not None
                else None
            )
            dndre = (
                round(per_date_medians[d1]["ndre"] - per_date_medians[d0]["ndre"], 6)
                if both_20 and per_date_medians[d1]["ndre"] is not None and per_date_medians[d0]["ndre"] is not None
                else None
            )
            dlswi = (
                round(per_date_medians[d1]["lswi"] - per_date_medians[d0]["lswi"], 6)
                if both_20 and per_date_medians[d1]["lswi"] is not None and per_date_medians[d0]["lswi"] is not None
                else None
            )
            rec[f"delta_ndvi_{tag}"] = dndvi
            rec[f"delta_ndre_{tag}"] = dndre
            rec[f"delta_lswi_{tag}"] = dlswi

        rows.append(rec)

    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _group_metric_summary(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], field: str) -> dict[str, Any]:
    va = np.array([r[field] for r in rows_a if r.get(field) is not None], dtype=float)
    vb = np.array([r[field] for r in rows_b if r.get(field) is not None], dtype=float)
    res: dict[str, Any] = {
        "candidate_181": _summarize_array(va),
        "other_farmland": _summarize_array(vb),
        "mannwhitney_u_pvalue": None,
        "ks_stat": None,
        "ks_pvalue": None,
    }
    if va.size >= 5 and vb.size >= 5:
        _, mw_p = stats.mannwhitneyu(va, vb, alternative="two-sided")
        ks_res = stats.ks_2samp(va, vb)
        res["mannwhitney_u_pvalue"] = float(f"{mw_p:.3e}")
        res["ks_stat"] = round(float(ks_res.statistic), 4)
        res["ks_pvalue"] = float(f"{ks_res.pvalue:.3e}")
    return res


def analyze_candidate_vs_farmland(
    rows_4863: list[dict[str, Any]],
    epoch_arrays: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare optical time series between 181 SAR candidates and other farmland parcels."""
    cand_rows = [r for r in rows_4863 if r["is_tw01_sar_candidate_181"]]
    other_all = [r for r in rows_4863 if not r["is_tw01_sar_candidate_181"]]
    # Size-matched non-candidate group: total_pixels_10m >= 5 and area >= 0.16 ha (comparable to 181 candidates min 0.1679 ha)
    other_size_matched = [
        r for r in other_all if r["total_pixels_10m"] >= 5 and r["clipped_area_m2"] >= 1600.0
    ]

    dates = list(epoch_arrays.keys())
    c181_validity: dict[str, Any] = {}
    all4863_validity: dict[str, Any] = {}
    for d in dates:
        ymd = epoch_arrays[d]["ymd"]
        v10_c = sum(1 for r in cand_rows if r[f"is_valid_10m_{ymd}"])
        v20_c = sum(1 for r in cand_rows if r[f"is_valid_20m_{ymd}"])
        v10_a = sum(1 for r in rows_4863 if r[f"is_valid_10m_{ymd}"])
        v20_a = sum(1 for r in rows_4863 if r[f"is_valid_20m_{ymd}"])
        c181_validity[d] = {
            "valid_10m_strict_ge5px_80pct": v10_c,
            "valid_10m_any_pixel": sum(1 for r in cand_rows if r[f"valid_px_10m_{ymd}"] > 0),
            "valid_20m_strict_ge2px_80pct": v20_c,
            "valid_20m_any_pixel": sum(1 for r in cand_rows if r[f"valid_px_20m_{ymd}"] > 0),
        }
        all4863_validity[d] = {
            "valid_10m_strict_ge5px_80pct": v10_a,
            "valid_10m_any_pixel": sum(1 for r in rows_4863 if r[f"valid_px_10m_{ymd}"] > 0),
            "valid_20m_strict_ge2px_80pct": v20_a,
        }

    # Three clear dates multi-date co-availability for 181 candidates
    clear_ymds = [epoch_arrays[d]["ymd"] for d in dates if epoch_arrays[d]["usability"] == "USABLE_CLEAR"]
    c181_all_clear_valid_10m = sum(
        1 for r in cand_rows if all(r[f"is_valid_10m_{ymd}"] for ymd in clear_ymds)
    )
    c181_all_clear_valid_20m = sum(
        1 for r in cand_rows if all(r[f"is_valid_20m_{ymd}"] for ymd in clear_ymds)
    )
    f4863_all_clear_valid_10m = sum(
        1 for r in rows_4863 if all(r[f"is_valid_10m_{ymd}"] for ymd in clear_ymds)
    )

    metrics_to_compare = [
        f"ndvi_med_{epoch_arrays[d]['ymd']}" for d in dates if epoch_arrays[d]["usability"] != "CLOUD_OBSCURED_UNUSABLE"
    ] + [
        f"ndre_med_{epoch_arrays[d]['ymd']}" for d in dates if epoch_arrays[d]["usability"] != "CLOUD_OBSCURED_UNUSABLE"
    ] + [
        f"lswi_med_{epoch_arrays[d]['ymd']}" for d in dates if epoch_arrays[d]["usability"] != "CLOUD_OBSCURED_UNUSABLE"
    ] + [
        "delta_ndvi_20261011_20261105",
        "delta_ndre_20261011_20261105",
        "delta_lswi_20261011_20261105",
    ]

    vs_all_other = {m: _group_metric_summary(cand_rows, other_all, m) for m in metrics_to_compare if m in cand_rows[0]}
    vs_size_matched = {
        m: _group_metric_summary(cand_rows, other_size_matched, m) for m in metrics_to_compare if m in cand_rows[0]
    }

    # Spearman correlations within the 181 SAR candidates: SAR ΔVV / ΔVH / |Δ| vs optical deltas
    correlations: dict[str, Any] = {}
    opt_delta_fields = [
        "delta_ndvi_20261011_20261105",
        "delta_ndre_20261011_20261105",
        "delta_lswi_20261011_20261105",
    ]
    for opt_f in opt_delta_fields:
        valid_c = [
            r
            for r in cand_rows
            if r.get(opt_f) is not None and r.get("sar_median_delta_vv_db") is not None
        ]
        if len(valid_c) >= 10:
            vv = np.array([r["sar_median_delta_vv_db"] for r in valid_c], dtype=float)
            vh = np.array([r["sar_median_delta_vh_db"] for r in valid_c], dtype=float)
            abs_max = np.maximum(np.abs(vv), np.abs(vh))
            opt_v = np.array([r[opt_f] for r in valid_c], dtype=float)
            r_vv, p_vv = stats.spearmanr(vv, opt_v)
            r_vh, p_vh = stats.spearmanr(vh, opt_v)
            r_abs, p_abs = stats.spearmanr(abs_max, opt_v)
            r_abs_opt, p_abs_opt = stats.spearmanr(abs_max, np.abs(opt_v))
            correlations[opt_f] = {
                "n_valid": len(valid_c),
                "spearman_vv_vs_opt": {"rho": round(float(r_vv), 4), "pvalue": float(f"{p_vv:.3e}")},
                "spearman_vh_vs_opt": {"rho": round(float(r_vh), 4), "pvalue": float(f"{p_vh:.3e}")},
                "spearman_max_abs_sar_vs_opt": {"rho": round(float(r_abs), 4), "pvalue": float(f"{p_abs:.3e}")},
                "spearman_max_abs_sar_vs_abs_opt": {
                    "rho": round(float(r_abs_opt), 4),
                    "pvalue": float(f"{p_abs_opt:.3e}"),
                },
            }

    # Diagnostic breakdown by SAR direction (signed ΔVV / ΔVH) vs clear-pair optical deltas (10-11 -> 11-05)
    sar_neg_vv = [r for r in cand_rows if (r.get("sar_median_delta_vv_db") or 0.0) <= -3.0]
    sar_pos_vv = [r for r in cand_rows if (r.get("sar_median_delta_vv_db") or 0.0) >= 3.0]
    sar_neg_vh = [r for r in cand_rows if (r.get("sar_median_delta_vh_db") or 0.0) <= -3.0]
    sar_pos_vh = [r for r in cand_rows if (r.get("sar_median_delta_vh_db") or 0.0) >= 3.0]

    def _subgroup_ndvi(sub: list[dict[str, Any]]) -> dict[str, Any]:
        vals_1105 = np.array(
            [r["delta_ndvi_20261011_20261105"] for r in sub if r.get("delta_ndvi_20261011_20261105") is not None],
            dtype=float,
        )
        ndre_1105 = np.array(
            [r["delta_ndre_20261011_20261105"] for r in sub if r.get("delta_ndre_20261011_20261105") is not None],
            dtype=float,
        )
        lswi_1105 = np.array(
            [r["delta_lswi_20261011_20261105"] for r in sub if r.get("delta_lswi_20261011_20261105") is not None],
            dtype=float,
        )
        return {
            "parcel_count": len(sub),
            "delta_ndvi_1011_1105": _summarize_array(vals_1105),
            "frac_ndvi_drop_ge_015_by_1105": round(float(np.mean(vals_1105 <= -0.15)), 4)
            if vals_1105.size > 0
            else None,
            "delta_ndre_1011_1105": _summarize_array(ndre_1105),
            "delta_lswi_1011_1105": _summarize_array(lswi_1105),
        }

    # Check how often strong NDVI changes (>= 0.15 drop or abs change) occur on the clear pair (10-11 -> 11-05)
    c181_dndvi_05 = np.array(
        [r["delta_ndvi_20261011_20261105"] for r in cand_rows if r.get("delta_ndvi_20261011_20261105") is not None],
        dtype=float,
    )
    oth_dndvi_05 = np.array(
        [
            r["delta_ndvi_20261011_20261105"]
            for r in other_size_matched
            if r.get("delta_ndvi_20261011_20261105") is not None
        ],
        dtype=float,
    )

    return {
        "counts": {
            "total_farmland_parcels": len(rows_4863),
            "candidate_181_parcels": len(cand_rows),
            "other_farmland_parcels": len(other_all),
            "other_size_matched_parcels_ge1600m2": len(other_size_matched),
            "usable_clear_dates": [d for d in dates if epoch_arrays[d]["usability"] == "USABLE_CLEAR"],
            "candidate_181_all_clear_dates_valid_10m": c181_all_clear_valid_10m,
            "candidate_181_all_clear_dates_valid_20m": c181_all_clear_valid_20m,
            "farmland_4863_all_clear_dates_valid_10m": f4863_all_clear_valid_10m,
        },
        "per_date_parcel_validity": {
            "candidate_181": c181_validity,
            "farmland_4863": all4863_validity,
        },
        "distribution_comparison": {
            "candidate_181_vs_all_other_farmland": vs_all_other,
            "candidate_181_vs_size_matched_farmland": vs_size_matched,
            "ndvi_drop_rates_comparison": {
                "candidate_181_n_valid_clear_pair_1011_1105": int(c181_dndvi_05.size),
                "size_matched_other_n_valid_clear_pair_1011_1105": int(oth_dndvi_05.size),
                "candidate_181_delta_ndvi_1011_1105_le_neg015": round(float(np.mean(c181_dndvi_05 <= -0.15)), 4)
                if c181_dndvi_05.size > 0
                else None,
                "size_matched_other_delta_ndvi_1011_1105_le_neg015": round(float(np.mean(oth_dndvi_05 <= -0.15)), 4)
                if oth_dndvi_05.size > 0
                else None,
                "candidate_181_abs_delta_ndvi_1011_1105_ge_015": round(
                    float(np.mean(np.abs(c181_dndvi_05) >= 0.15)), 4
                )
                if c181_dndvi_05.size > 0
                else None,
                "size_matched_other_abs_delta_ndvi_1011_1105_ge_015": round(
                    float(np.mean(np.abs(oth_dndvi_05) >= 0.15)), 4
                )
                if oth_dndvi_05.size > 0
                else None,
            },
        },
        "sar_optical_correlations_within_181": correlations,
        "sar_direction_subgroups_within_181": {
            "sar_vv_le_neg3db": _subgroup_ndvi(sar_neg_vv),
            "sar_vv_ge_pos3db": _subgroup_ndvi(sar_pos_vv),
            "sar_vh_le_neg3db": _subgroup_ndvi(sar_neg_vh),
            "sar_vh_ge_pos3db": _subgroup_ndvi(sar_pos_vh),
        },
    }


def generate_diagnostic_figures(
    epoch_arrays: dict[str, dict[str, Any]],
    epoch_reports: list[dict[str, Any]],
    grid_info: dict[str, Any],
    aoi_32651: Any,
    candidates_32651: gpd.GeoDataFrame,
    rows_4863: list[dict[str, Any]],
) -> list[str]:
    """Create 3 diagnostic figures inspecting cloud masks, vegetation indices, and SAR comparisons."""
    tf10 = grid_info["10m"]["transform"]
    tf20 = grid_info["20m"]["transform"]
    ext10 = plotting_extent(np.zeros(SHAPE_10M), tf10)
    ext20 = plotting_extent(np.zeros(SHAPE_20M), tf20)
    xlim = (aoi_32651.bounds[0], aoi_32651.bounds[2])
    ylim = (aoi_32651.bounds[1], aoi_32651.bounds[3])

    dates = list(epoch_arrays.keys())

    # Figure 1: 4-date True Color RGB (10m) + SCL Cloud Classification (20m)
    scl_colors = [
        "#000000", "#ff0004", "#3c3c3c", "#643c14", "#1b9e3e", "#d2b450",
        "#1f78b4", "#9e9e9e", "#ffd966", "#ffffff", "#7fd4ff", "#00ffff",
    ]
    scl_cmap = ListedColormap(scl_colors)

    fig1, axes1 = plt.subplots(2, 4, figsize=(15, 7.8), layout="constrained")
    for idx, (d, rep) in enumerate(zip(dates, epoch_reports, strict=True)):
        info = epoch_arrays[d]
        rgb = np.clip(info["rgb_10m"] / 0.25, 0.0, 1.0)
        ax_rgb = axes1[0, idx]
        ax_rgb.imshow(rgb, extent=ext10)
        aoi_32651_g = gpd.GeoSeries([aoi_32651], crs=grid_info["10m"]["crs"])
        aoi_32651_g.boundary.plot(ax=ax_rgb, color="#facc15", linewidth=1.1)
        ax_rgb.set(xlim=xlim, ylim=ylim)
        ax_rgb.set_title(
            f"{d} RGB (10 m)\nTile cloud={rep['tile_cloud_cover_percent']:.1f}%",
            fontsize=10,
        )
        ax_rgb.set_axis_off()

        ax_scl = axes1[1, idx]
        ax_scl.imshow(info["scl20"], extent=ext20, cmap=scl_cmap, vmin=-0.5, vmax=11.5, interpolation="nearest")
        aoi_32651_g.boundary.plot(ax=ax_scl, color="#111827", linewidth=1.1)
        ax_scl.set(xlim=xlim, ylim=ylim)
        ax_scl.set_title(
            f"SCL (20 m) • AOI Clear={rep['aoi_valid_fraction_10m']*100:.1f}%\n{rep['usability_status']}",
            fontsize=9.5,
        )
        ax_scl.set_axis_off()

    fig1.suptitle(
        "TW-08A | Yunlin 5 × 5 km AOI Sentinel-2 L2A Cloud Screening (10 m RGB & 20 m SCL)\n"
        "Clear mask = SCL in {4: Veg, 5: Bare/Soil, 6: Water}; only 2026-10-11 and 2026-11-05 are USABLE_CLEAR in AOI",
        fontsize=12,
        fontweight="bold",
    )
    fig1_path = OUT_DIR / "s2_multitemporal_rgb_scl_overview.png"
    fig1.savefig(fig1_path, dpi=170)
    plt.close(fig1)

    # Figure 2: Native-resolution NDVI (10m) & NDRE/LSWI (20m) across USABLE_CLEAR dates
    ndvi_dates = [d for d in dates if epoch_arrays[d]["usability"] == "USABLE_CLEAR"]
    d0, d1 = ndvi_dates[0], ndvi_dates[-1]
    fig2, axes2 = plt.subplots(2, 3, figsize=(14.5, 9.2), layout="constrained")
    cmap_ndvi = plt.get_cmap("RdYlGn").copy()
    cmap_ndvi.set_bad("#1e293b")
    cmap_div = plt.get_cmap("BrBG").copy()
    cmap_div.set_bad("#1e293b")
    cmap_lswi = plt.get_cmap("RdBu").copy()
    cmap_lswi.set_bad("#1e293b")

    # Top row: native 10m NDVI(d0), NDVI(d1), ΔNDVI(d0 -> d1)
    for idx, d in enumerate([d0, d1]):
        ax = axes2[0, idx]
        im = ax.imshow(epoch_arrays[d]["ndvi"], extent=ext10, cmap=cmap_ndvi, vmin=-0.1, vmax=0.85)
        candidates_32651.boundary.plot(ax=ax, color="#0ea5e9", linewidth=0.55)
        ax.set(xlim=xlim, ylim=ylim, title=f"NDVI (10 m) • {d}")
        ax.set_axis_off()
        fig2.colorbar(im, ax=ax, shrink=0.76)

    dndvi = (epoch_arrays[d1]["ndvi"] - epoch_arrays[d0]["ndvi"]).astype(np.float32)
    im_dndvi = axes2[0, 2].imshow(dndvi, extent=ext10, cmap=cmap_div, vmin=-0.4, vmax=0.4)
    candidates_32651.boundary.plot(ax=axes2[0, 2], color="#ef4444", linewidth=0.65)
    axes2[0, 2].set(xlim=xlim, ylim=ylim, title=f"ΔNDVI (10 m) • {d0} → {d1}")
    axes2[0, 2].set_axis_off()
    fig2.colorbar(im_dndvi, ax=axes2[0, 2], shrink=0.76)

    # Bottom row: native 20m NDRE(d0), ΔNDRE(d0 -> d1), ΔLSWI(d0 -> d1)
    im_ndre0 = axes2[1, 0].imshow(epoch_arrays[d0]["ndre"], extent=ext20, cmap=cmap_ndvi, vmin=-0.05, vmax=0.65)
    candidates_32651.boundary.plot(ax=axes2[1, 0], color="#0ea5e9", linewidth=0.55)
    axes2[1, 0].set(xlim=xlim, ylim=ylim, title=f"NDRE (20 m) • {d0}")
    axes2[1, 0].set_axis_off()
    fig2.colorbar(im_ndre0, ax=axes2[1, 0], shrink=0.76)

    dndre = (epoch_arrays[d1]["ndre"] - epoch_arrays[d0]["ndre"]).astype(np.float32)
    im_dndre = axes2[1, 1].imshow(dndre, extent=ext20, cmap=cmap_div, vmin=-0.35, vmax=0.35)
    candidates_32651.boundary.plot(ax=axes2[1, 1], color="#ef4444", linewidth=0.65)
    axes2[1, 1].set(xlim=xlim, ylim=ylim, title=f"ΔNDRE (20 m) • {d0} → {d1}")
    axes2[1, 1].set_axis_off()
    fig2.colorbar(im_dndre, ax=axes2[1, 1], shrink=0.76)

    dlswi = (epoch_arrays[d1]["lswi"] - epoch_arrays[d0]["lswi"]).astype(np.float32)
    im_dlswi = axes2[1, 2].imshow(dlswi, extent=ext20, cmap=cmap_lswi, vmin=-0.35, vmax=0.35)
    candidates_32651.boundary.plot(ax=axes2[1, 2], color="#111827", linewidth=0.65)
    axes2[1, 2].set(xlim=xlim, ylim=ylim, title=f"ΔLSWI (20 m) • {d0} → {d1}")
    axes2[1, 2].set_axis_off()
    fig2.colorbar(im_dlswi, ax=axes2[1, 2], shrink=0.76)

    fig2.suptitle(
        "TW-08A | Yunlin Clear-Sky Sentinel-2 L2A NDVI (10 m), NDRE & LSWI (20 m) vs TW-01 181 SAR Candidates (Outlines)\n"
        "Cloud/Shadow & 2026-10-16 / 2026-10-26 Cloud-Obscured Scenes Excluded (No Synthetic Gap-Filling)",
        fontsize=11.5,
        fontweight="bold",
    )
    fig2_path = OUT_DIR / "s2_ndvi_ndre_lswi_timeseries_map.png"
    fig2.savefig(fig2_path, dpi=170)
    plt.close(fig2)

    # Figure 3: Parcel-level NDVI trajectories + ΔNDVI distribution + SAR ΔVH vs ΔNDVI scatter comparison
    cand_rows = [r for r in rows_4863 if r["is_tw01_sar_candidate_181"]]
    other_size = [r for r in rows_4863 if not r["is_tw01_sar_candidate_181"] and r["clipped_area_m2"] >= 1600.0]

    fig3, axes3 = plt.subplots(1, 3, figsize=(15.5, 4.9), layout="constrained")
    clear_ymds = [epoch_arrays[d]["ymd"] for d in ndvi_dates]
    pair_tag = f"{clear_ymds[0]}_{clear_ymds[-1]}"
    dndvi_col = f"delta_ndvi_{pair_tag}"
    dlswi_col = f"delta_lswi_{pair_tag}"

    # Panel A: Median & IQR NDVI trajectory for 181 candidates vs size-matched other farmland
    x_pos = np.arange(len(ndvi_dates))
    for grp_rows, label_txt, color in [
        (cand_rows, f"TW-01 SAR Candidates (total={len(cand_rows)})", "#ef4444"),
        (other_size, f"Other Farmland ≥0.16 ha (total={len(other_size)})", "#38bdf8"),
    ]:
        meds, q25s, q75s = [], [], []
        for ymd in clear_ymds:
            vals = np.array([r[f"ndvi_med_{ymd}"] for r in grp_rows if r.get(f"is_valid_10m_{ymd}")], dtype=float)
            q25, q50, q75 = np.percentile(vals, [25, 50, 75])
            meds.append(q50)
            q25s.append(q25)
            q75s.append(q75)
        axes3[0].plot(x_pos, meds, marker="o", linewidth=2.2, color=color, label=label_txt)
        axes3[0].fill_between(x_pos, q25s, q75s, alpha=0.18, color=color)
    axes3[0].set_xticks(x_pos)
    axes3[0].set_xticklabels(ndvi_dates)
    axes3[0].set_ylim(0.05, 0.85)
    axes3[0].set_ylabel("Parcel Median NDVI (10 m)")
    axes3[0].set_title("A. Clear-Date NDVI Trajectory (Median & IQR)")
    axes3[0].grid(alpha=0.25)
    axes3[0].legend(fontsize=8.5, loc="lower left")

    # Panel B: Clear-pair ΔNDVI (d0 -> d1) distribution comparison
    dndvi_c = np.array([r[dndvi_col] for r in cand_rows if r.get(dndvi_col) is not None], dtype=float)
    dndvi_o = np.array([r[dndvi_col] for r in other_size if r.get(dndvi_col) is not None], dtype=float)
    bins = np.linspace(-0.6, 0.5, 36)
    axes3[1].hist(
        dndvi_o,
        bins=bins,
        density=True,
        alpha=0.55,
        color="#38bdf8",
        label=f"Other ≥0.16 ha (n={dndvi_o.size}, med={np.median(dndvi_o):+.3f})",
    )
    axes3[1].hist(
        dndvi_c,
        bins=bins,
        density=True,
        alpha=0.60,
        color="#ef4444",
        label=f"181 Candidates (n={dndvi_c.size}, med={np.median(dndvi_c):+.3f})",
    )
    axes3[1].axvline(0.0, color="#111827", linestyle="--", linewidth=1)
    axes3[1].set_xlabel(f"ΔNDVI ({d0} → {d1})")
    axes3[1].set_ylabel("Probability Density")
    axes3[1].set_title(f"B. Clear-Pair ΔNDVI Distribution ({d0} → {d1})")
    axes3[1].grid(alpha=0.25)
    axes3[1].legend(fontsize=8.0)

    # Panel C: Within-181 Scatter of SAR ΔVH vs ΔNDVI (colored by ΔLSWI)
    sc_rows = [r for r in cand_rows if r.get(dndvi_col) is not None]
    x_vh = np.array([r["sar_median_delta_vh_db"] for r in sc_rows], dtype=float)
    y_ndvi = np.array([r[dndvi_col] for r in sc_rows], dtype=float)
    c_lswi = np.array(
        [r[dlswi_col] if r.get(dlswi_col) is not None else 0.0 for r in sc_rows],
        dtype=float,
    )
    rho_vh, p_vh = stats.spearmanr(x_vh, y_ndvi)
    sc = axes3[2].scatter(
        x_vh,
        y_ndvi,
        c=c_lswi,
        cmap="coolwarm_r",
        vmin=-0.35,
        vmax=0.35,
        s=28,
        alpha=0.88,
        edgecolors="#1e293b",
        linewidths=0.35,
    )
    axes3[2].axhline(0.0, color="#475569", linestyle=":", linewidth=1)
    axes3[2].axvline(0.0, color="#475569", linestyle=":", linewidth=1)
    axes3[2].set_xlabel("TW-01 Sentinel-1D Median ΔVH (dB, 10-14→10-26)")
    axes3[2].set_ylabel(f"Sentinel-2 ΔNDVI ({d0} → {d1})")
    axes3[2].set_title(f"C. SAR ΔVH vs Optical ΔNDVI (n={len(sc_rows)}, ρ={rho_vh:+.3f}, p={p_vh:.3f})")
    axes3[2].grid(alpha=0.25)
    fig3.colorbar(sc, ax=axes3[2], label=f"ΔLSWI (20 m, {d0}→{d1})", shrink=0.85)

    fig3.suptitle(
        "TW-08A | Cross-Sensor Exploratory Comparison: Sentinel-2 Optical Indices vs TW-01 SAR Candidates\n"
        "Descriptive Co-Variation Only — No Crop Labels, Classification Accuracy, or Causal Damage Claims",
        fontsize=11.5,
        fontweight="bold",
    )
    fig3_path = OUT_DIR / "s2_vs_sar_candidate_comparison.png"
    fig3.savefig(fig3_path, dpi=170)
    plt.close(fig3)

    return [fig1_path.name, fig2_path.name, fig3_path.name]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inv_path = INPUT_DIR / "stac_inventory.json"
    with inv_path.open("r", encoding="utf-8") as stream:
        inventory = json.load(stream)

    loaded_scenes, grid_info = load_and_validate_inputs(inventory)
    crs = grid_info["10m"]["crs"]
    tf10 = grid_info["10m"]["transform"]
    tf20 = grid_info["20m"]["transform"]

    aoi_gdf = gpd.read_file(TW01_DIR / "aoi.geojson").to_crs(crs)
    aoi_geom = aoi_gdf.geometry.iloc[0]
    inside_10m = geometry_mask([mapping(aoi_geom)], out_shape=SHAPE_10M, transform=tf10, invert=True)
    inside_20m = geometry_mask([mapping(aoi_geom)], out_shape=SHAPE_20M, transform=tf20, invert=True)

    epoch_arrays, epoch_reports = compute_scene_indices_and_qa(loaded_scenes, grid_info, inside_10m, inside_20m)
    pair_records = compute_delta_rasters(epoch_arrays, grid_info, inside_10m, inside_20m)

    # Read TW-01 181 SAR candidate metadata & 4,863 parcels (read-only)
    with (TW01_DIR / "manifest.json").open("r", encoding="utf-8") as stream:
        tw01_manifest = json.load(stream)
    tw01_sar_by_id = {
        int(c["parcel_feature_id"]): c
        for c in tw01_manifest["analysis"]["parcel_screening"]["candidates"]
    }

    cand_gdf = gpd.read_file(TW01_DIR / "candidate-parcels.geojson")
    farmland_gdf = gpd.read_file(TW01_DIR / "farmland.geojson")

    # Determine key optical date pairs for CSV columns (using clear dates)
    usable_dates = [d for d, info in epoch_arrays.items() if info["usability"] != "CLOUD_OBSCURED_UNUSABLE"]
    key_pairs = [
        (usable_dates[i], usable_dates[j])
        for i in range(len(usable_dates))
        for j in range(i + 1, len(usable_dates))
    ]

    # Stage 1: 181 TW-01 candidate parcels first
    rows_181 = extract_parcel_timeseries(cand_gdf, tw01_sar_by_id, epoch_arrays, grid_info, key_pairs)
    csv_181_path = OUT_DIR / "candidate_181_multitemporal_metrics.csv"
    write_csv(csv_181_path, rows_181)

    # Stage 2: Expand to all 4,863 farmland parcels
    rows_4863 = extract_parcel_timeseries(farmland_gdf, tw01_sar_by_id, epoch_arrays, grid_info, key_pairs)
    csv_4863_path = OUT_DIR / "farmland_4863_multitemporal_metrics.csv"
    write_csv(csv_4863_path, rows_4863)

    comparison = analyze_candidate_vs_farmland(rows_4863, epoch_arrays)
    figure_names = generate_diagnostic_figures(
        epoch_arrays, epoch_reports, grid_info, aoi_geom, cand_gdf.to_crs(crs), rows_4863
    )

    # Compute SHA-256 for every artifact in OUT_DIR
    artifact_sha256: dict[str, str] = {}
    for p in sorted(OUT_DIR.iterdir()):
        if p.is_file() and p.name != "manifest.json":
            artifact_sha256[p.name] = _sha256(p)

    # Ground-truth audit on farmland.geojson properties
    farmland_columns = [c for c in farmland_gdf.columns if c != "geometry"]

    manifest = {
        "schema_version": "tw08a-sentinel2-feasibility/1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "real_multispectral_observation_qa",
        "aoi_name": "雲林縣虎尾／土庫／元長農田調查示範區 (TW-01 Yunlin 5 x 5 km AOI)",
        "aoi_crs": f"EPSG:{EXPECTED_CRS_EPSG}",
        "aoi_bounds_epsg32651": list(AOI_BOUNDS_32651),
        "grids": {
            "native_10m_bands": {
                "bands": ["B02", "B03", "B04", "B08"],
                "indices": ["NDVI = (B08 - B04) / (B08 + B04)"],
                "spacing_m": [10, 10],
                "shape": list(SHAPE_10M),
                "transform": list(tf10)[:6],
            },
            "native_20m_bands": {
                "bands": ["B05", "B8A", "B11", "B12", "SCL"],
                "indices": ["NDRE = (B8A - B05) / (B8A + B05)", "LSWI = (B8A - B11) / (B8A + B11)"],
                "spacing_m": [20, 20],
                "shape": list(SHAPE_20M),
                "transform": list(tf20)[:6],
            },
        },
        "radiometry_and_cloud_masking": {
            "stac_source": inventory["stac_endpoint"],
            "collection": inventory["collection"],
            "earthsearch_boa_offset_applied_verified": True,
            "reflectance_conversion": "reflectance = uint16_dn * 0.0001 where uint16_dn > 0 (verified on SCL=4 vegetation pixels; no duplicate -0.1 subtraction)",
            "scl_clear_classes": list(CLEAR_SCL_CLASSES),
            "scl_cloud_shadow_classes": list(CLOUD_SHADOW_SCL_CLASSES),
            "no_synthetic_gap_filling": True,
        },
        "scenes": epoch_reports,
        "temporal_index_deltas": pair_records,
        "ground_truth_and_classification_audit": {
            "farmland_geojson_columns": farmland_columns,
            "ground_truth_labels_available": False,
            "classifier_trained": False,
            "reason": "MOA open farmland layer (I75 RID=44143) contains only parcel_feature_id, PARCEL_NO, and clipped_area_m2 with zero parcel-level 2026 crop-type labels. Supervised classification accuracy or crop identification is strictly withheld.",
        },
        "parcel_analysis": comparison,
        "csv_outputs": {
            "candidate_181": csv_181_path.name,
            "farmland_4863": csv_4863_path.name,
        },
        "diagnostic_figures": figure_names,
        "scientific_limitations": [
            "No parcel-level 2026 crop-type ground truth exists; NDVI/NDRE/LSWI patterns cannot establish crop species or relief eligibility.",
            "2026-10-16 (95.21% cloud/shadow) and 2026-10-26 (66.34% cloud/shadow) Sentinel-2 acquisitions are heavily cloud-obscured over the 5x5 km AOI and excluded from change/trajectory analysis rather than gap-filled.",
            "Cross-sensor co-variation between TW-01 Sentinel-1D delta dB and Sentinel-2 delta NDVI/LSWI is descriptive only and does not prove typhoon crop damage.",
            "TW-01 181 SAR candidates, NISAR tw03/, sar/ engine, and TW-07 relief rules were kept read-only and unmodified.",
        ],
        "artifact_sha256": artifact_sha256,
    }

    manifest_path = OUT_DIR / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)

    print("TW-08A build complete:")
    for rep in epoch_reports:
        print(
            f"  - {rep['date_utc']} ({rep['stac_id']}): AOI clear={rep['aoi_valid_fraction_10m']*100:.2f}%, "
            f"cloud/shadow={rep['aoi_cloud_shadow_fraction_20m']*100:.2f}%, status={rep['usability_status']}"
        )
    print(f"  - Exported {len(rows_181)} candidate rows -> {csv_181_path.name}")
    print(f"  - Exported {len(rows_4863)} farmland rows -> {csv_4863_path.name}")
    print(f"  - Manifest written -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
