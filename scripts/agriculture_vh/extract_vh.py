"""Pixel-level OPERA VH gamma0 extraction with strict product/mask QA."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import box, shape

from .common import OUTPUT, resolve_raster_path, write_csv, write_json

MIN_VALID_PIXELS = 8
MIN_COVERAGE = 0.8
TIME_COLUMNS = ["field_id", "year", "acquisition_datetime", "vh_median_db", "vh_mean_db",
                "vh_p25_db", "vh_p75_db", "valid_pixel_count", "interior_pixel_count",
                "valid_coverage_ratio", "platform", "relative_orbit", "orbit_direction",
                "burst_id", "product_version", "source_scene_id", "source_vh_sha256",
                "evidence_id", "qa_flags"]


def power_to_db(values: np.ndarray) -> np.ndarray:
    positive = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(positive)) or np.any(positive <= 0):
        raise ValueError("Only finite positive linear power can be converted to dB")
    return 10 * np.log10(positive)


def _tag(tags: dict, key: str) -> str:
    return str(tags.get(key, tags.get(key.lower(), "")))


def _validate_tags(tags: dict, scene: dict) -> list[str]:
    warnings = []
    checks = {"PRODUCT_TYPE": ("RTC-S1", "RTC"), "ACQUISITION_MODE": ("IW",),
              "RADAR_BAND": ("C",)}
    for key, allowed in checks.items():
        value = _tag(tags, key)
        if value and value.upper() not in allowed:
            raise RuntimeError(f"Raster {key}={value} is not OPERA VH RTC-S1")
        if not value:
            raise RuntimeError("Missing required OPERA raster tag " + key)
    if _tag(tags, "LAYER_NAME").upper() not in ("VH", "RTC-S1 VH BACKSCATTER"):
        raise RuntimeError("Raster layer is not OPERA VH backscatter")
    if (_tag(tags, "PROCESSING_INFORMATION_OUTPUT_BACKSCATTER_EXPRESSION_CONVENTION").lower()
            != "linear backscatter intensity" or
            _tag(tags, "PROCESSING_INFORMATION_OUTPUT_BACKSCATTER_NORMALIZATION_CONVENTION").lower()
            != "gamma0" or
            _tag(tags, "PROCESSING_INFORMATION_RADIOMETRIC_TERRAIN_CORRECTION_APPLIED").lower()
            != "true"):
        raise RuntimeError("Raster is not verified linear gamma0 RTC")
    platform = _tag(tags, "PLATFORM").upper().replace("SENTINEL-", "SENTINEL-")
    if platform and scene["platform"] and platform != scene["platform"].upper():
        raise RuntimeError("Raster platform disagrees with scene inventory")
    burst = _tag(tags, "BURST_ID").upper().replace("T", "", 1).replace("_", "-")
    if burst and burst != scene["burst_id"].upper():
        raise RuntimeError("Raster burst disagrees with scene inventory")
    track = _tag(tags, "TRACK_NUMBER")
    if track and str(int(track)) != str(int(scene["relative_orbit"])):
        raise RuntimeError("Raster track disagrees with scene inventory")
    direction = _tag(tags, "ORBIT_PASS_DIRECTION").upper()
    if direction and direction != scene["orbit_direction"].upper():
        raise RuntimeError("Raster orbit direction disagrees with scene inventory")
    version = _tag(tags, "PRODUCT_VERSION")
    if version and version.lstrip("v") != scene["product_version"].lstrip("v"):
        raise RuntimeError("Raster product version disagrees with scene inventory")
    return warnings


def extract_one(scene: dict, files: dict, field: dict) -> dict:
    vh_path = resolve_raster_path(files["vh"]["path"])
    mask_path = resolve_raster_path(files["mask"]["path"])
    for layer, path in (("vh", vh_path), ("mask", mask_path)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != files[layer]["sha256"]:
            raise RuntimeError("Source COG digest mismatch")
    if not vh_path.name.endswith("_VH.tif") or "OPERA_L2_RTC-S1_" not in vh_path.name:
        raise RuntimeError("VH file name does not identify OPERA RTC-S1 VH")
    geom_wgs84 = field["properties"]["interior_geometry"]
    with rasterio.open(vh_path) as vh, rasterio.open(mask_path) as mask:
        if not vh.crs or vh.count != 1 or not mask.crs or mask.count != 1:
            raise RuntimeError("Raster CRS or band count invalid")
        if vh.crs != mask.crs or vh.transform != mask.transform or vh.shape != mask.shape:
            raise RuntimeError("VH and mask grids do not align")
        if not (25 <= abs(vh.res[0]) <= 35 and 25 <= abs(vh.res[1]) <= 35):
            raise RuntimeError("Raster is not nominal 30 m OPERA RTC-S1")
        tags = vh.tags()
        flags = _validate_tags(tags, scene)
        mask_description = _tag(mask.tags(), "LAYER_DESCRIPTION")
        if "0: not masked" not in mask_description or "255: invalid/fill value" not in mask_description:
            raise RuntimeError("OPERA mask semantics not verified")
        unit = (_tag(tags, "UNIT") or _tag(tags, "UNITS")).lower()
        if "db" in unit or "decibel" in unit:
            raise RuntimeError("Raster is already in dB; OPERA linear gamma0 convention cannot be assumed")
        if not unit:
            flags.append("UNIT_VERIFIED_FROM_RASTER_PROCESSING_TAGS_LINEAR_GAMMA0")
        raster_geom = transform_geom("EPSG:4326", vh.crs, geom_wgs84)
        if not box(*vh.bounds).covers(shape(raster_geom)):
            raise RuntimeError("Field interior extends beyond VH raster grid")
        # Pixel-center inclusion in a 35 m inward buffer avoids boundary mixing.
        inside = geometry_mask([raster_geom], out_shape=vh.shape, transform=vh.transform, invert=True)
        interior_n = int(inside.sum())
        powers = vh.read(1, masked=True)
        mask_values = mask.read(1, masked=True)
        valid = (inside & ~np.ma.getmaskarray(powers) & ~np.ma.getmaskarray(mask_values)
                 & np.isfinite(np.asarray(powers)) & (np.asarray(powers) > 0)
                 & (np.asarray(mask_values) == 0))
        n = int(valid.sum())
        ratio = n / interior_n if interior_n else 0.0
        if interior_n < MIN_VALID_PIXELS or n < MIN_VALID_PIXELS or ratio < MIN_COVERAGE:
            flags.append("INSUFFICIENT_SPATIAL_SUPPORT")
        values = power_to_db(np.asarray(powers)[valid]) if n else np.array([])
    evidence_hash = hashlib.sha256((field["properties"]["field_id"] + "|" + scene["granule_id"]
                                   + "|" + files["vh"]["sha256"]).encode()).hexdigest()[:16].upper()
    stat = lambda f: round(float(f(values)), 5) if n else None
    return {"field_id": field["properties"]["field_id"], "year": scene["year"],
            "acquisition_datetime": scene["acquisition_datetime"],
            "vh_median_db": stat(np.median), "vh_mean_db": stat(np.mean),
            "vh_p25_db": stat(lambda x: np.percentile(x, 25)),
            "vh_p75_db": stat(lambda x: np.percentile(x, 75)),
            "valid_pixel_count": n, "interior_pixel_count": interior_n,
            "valid_coverage_ratio": round(ratio, 5), "platform": scene["platform"],
            "relative_orbit": scene["relative_orbit"], "orbit_direction": scene["orbit_direction"],
            "burst_id": scene["burst_id"], "product_version": scene["product_version"],
            "source_scene_id": scene["granule_id"], "source_vh_sha256": files["vh"]["sha256"],
            "evidence_id": "E-YL-VH-" + evidence_hash, "qa_flags": flags}


def extract(downloads: list[dict], fields: dict) -> list[dict]:
    observations = [extract_one(item["scene"], item["files"], field)
                    for item in downloads for field in fields["features"]
                    if shape(item["scene"]["footprint_geojson"]).covers(shape(field["properties"]["interior_geometry"]))]
    observations.sort(key=lambda row: (row["field_id"], row["acquisition_datetime"]))
    write_csv(OUTPUT / "vh_timeseries.csv", [{**r, "qa_flags": "|".join(r["qa_flags"])} for r in observations], TIME_COLUMNS)
    write_json(OUTPUT / "vh_timeseries.json", {"status": "OBSERVED_OPERA_RTC_S1",
                                                "mean_definition": "Arithmetic mean of valid pixel dB values",
                                                "observations": observations})
    return observations
