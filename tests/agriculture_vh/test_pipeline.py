from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from scripts.agriculture_vh.compare_years import compare
from scripts.agriculture_vh.download_opera import select_minimum
from scripts.agriculture_vh.extract_vh import extract_one, power_to_db
from scripts.agriculture_vh.plot_timeseries import plot
from scripts.agriculture_vh.search_opera import normalize_product
from backend.app.services.agriculture_vh_evidence import build_evidence, run_tool


def _field():
    return {"type": "Feature", "geometry": mapping(box(120, 23, 120.003, 23.003)),
            "properties": {"field_id": "TEST-01", "interior_geometry": mapping(box(120.0004, 23.0004, 120.0026, 23.0026))}}


def _scene(year, day, burst="001-123456-IW1"):
    return {"granule_id": f"OPERA_L2_RTC-S1_T{burst}_{year}070{day}T000000Z_20261114T000000Z_S1A_30_v1.0",
            "acquisition_datetime": f"{year}-07-0{day}T00:00:00+00:00", "year": year,
            "platform": "SENTINEL-1A", "relative_orbit": "1", "orbit_direction": "DESCENDING",
            "polarization": "VV+VH", "product_version": "v1.0", "beam_mode": "IW",
            "burst_id": burst, "vh_url": "https://opera.asf.earthdatacloud.nasa.gov/x_VH.tif",
            "mask_url": "https://opera.asf.earthdatacloud.nasa.gov/x_mask.tif",
            "footprint_geojson": mapping(box(119.9, 22.9, 120.1, 23.1))}


def test_positive_linear_power_conversion():
    assert power_to_db(np.array([1.0, 0.1])).tolist() == pytest.approx([0.0, -10.0])
    with pytest.raises(ValueError):
        power_to_db(np.array([0.0]))


def test_asf_metadata_parses_real_product_convention_and_vh_assets():
    class Product:
        geometry = mapping(box(119.9, 22.9, 120.1, 23.1))
        properties = {
            "fileID": "OPERA_L2_RTC-S1_T001-123456-IW1_20250801T000000Z_20250802T000000Z_S1A_30_v1.0",
            "startTime": "2025-08-01T00:00:00Z", "platform": "Sentinel-1A",
            "relativeOrbit": 1, "flightDirection": "DESCENDING", "polarization": "VV+VH",
            "beamModeType": "IW", "processingLevel": "RTC",
            "url": "https://opera.asf.earthdatacloud.nasa.gov/example.h5",
            "additionalUrls": ["https://opera.asf.earthdatacloud.nasa.gov/example_VH.tif",
                               "https://opera.asf.earthdatacloud.nasa.gov/example_mask.tif"]}
    row = normalize_product(Product(), 2025, box(120, 23, 120.003, 23.003))
    assert row["year"] == 2025 and row["vh_url"].endswith("_VH.tif")
    assert row["mask_url"].endswith("_mask.tif")
    assert row["relative_orbit"] == 1 and row["orbit_direction"] == "DESCENDING"
    assert normalize_product(Product(), 2026, box(120, 23, 120.003, 23.003)) is None


def test_selection_requires_same_burst_orbit_and_real_two_year_dates():
    fields = {"features": [_field()]}
    rows = [_scene(2025, 1), _scene(2025, 2), _scene(2026, 1), _scene(2026, 2)]
    for row, date in zip(rows, ('2025-10-08', '2025-11-01', '2026-10-10', '2026-11-03')):
        row['acquisition_datetime'] = date + 'T00:00:00+00:00'
    selected, field_id = select_minimum(rows, fields, per_year=2)
    assert len(selected) == 4 and field_id == "TEST-01"
    rows[-1] = _scene(2026, 2, burst="002-123456-IW1")
    with pytest.raises(RuntimeError):
        select_minimum(rows, fields, per_year=2)


def test_extract_reads_real_tiff_pixels_and_mask(tmp_path: Path):
    scene = _scene(2025, 1)
    base = scene["granule_id"]
    transform = from_origin(120, 23.003, 30 / 111000, 30 / 111000)
    paths = {"vh": tmp_path / (base + "_VH.tif"), "mask": tmp_path / (base + "_mask.tif")}
    for layer, array in (("vh", np.full((12, 12), 0.1, dtype="float32")),
                         ("mask", np.zeros((12, 12), dtype="uint8"))):
        with rasterio.open(paths[layer], "w", driver="GTiff", width=12, height=12,
                           count=1, dtype=array.dtype, crs="EPSG:4326", transform=transform) as dst:
            dst.write(array, 1)
            if layer == "vh":
                dst.update_tags(PRODUCT_TYPE="RTC-S1", ACQUISITION_MODE="IW", RADAR_BAND="C", LAYER_NAME="VH",
                                PROCESSING_INFORMATION_OUTPUT_BACKSCATTER_EXPRESSION_CONVENTION="linear backscatter intensity",
                                PROCESSING_INFORMATION_OUTPUT_BACKSCATTER_NORMALIZATION_CONVENTION="gamma0",
                                PROCESSING_INFORMATION_RADIOMETRIC_TERRAIN_CORRECTION_APPLIED="True")
            else:
                dst.update_tags(LAYER_DESCRIPTION="Mask Layer. Values: 0: not masked; 1: shadow; 2: layover; 3: layover and shadow; 255: invalid/fill value")
    # OPERA requires projected ~30 m pixels: reproject test files to UTM.
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    projected = {}
    for layer in paths:
        source = paths[layer]
        target = tmp_path / ("utm_" + source.name)
        with rasterio.open(source) as src:
            new_transform, width, height = calculate_default_transform(src.crs, "EPSG:32651", src.width, src.height, *src.bounds, resolution=30)
            with rasterio.open(target, "w", driver="GTiff", width=width, height=height,
                               count=1, dtype=src.dtypes[0], crs="EPSG:32651", transform=new_transform) as dst:
                reproject(src.read(1), rasterio.band(dst, 1), src_transform=src.transform,
                          src_crs=src.crs, dst_transform=new_transform, dst_crs="EPSG:32651",
                          resampling=Resampling.nearest)
                dst.update_tags(**src.tags())
        projected[layer] = target
    # Rename projected files to the expected OPERA names.
    files = {}
    for layer, source in projected.items():
        target = tmp_path / paths[layer].name
        source.replace(target)
        files[layer] = {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    result = extract_one(scene, files, _field())
    assert result["vh_median_db"] == pytest.approx(-10, abs=0.01)
    assert result["valid_pixel_count"] >= 8
    assert result["evidence_id"].startswith("E-YL-VH-")


def test_comparison_never_claims_causation_or_interpolates():
    rows = []
    for year in (2025, 2026):
        for day, value in ((1, -12), (2, -13)):
            rows.append({"field_id": "F1", "year": year, "acquisition_datetime": f"{year}-07-0{day}T00:00:00+00:00",
                         "vh_median_db": value + (1 if year == 2026 else 0), "qa_flags": [],
                         "relative_orbit": "1", "orbit_direction": "DESCENDING", "burst_id": "B",
                         "product_version": "v1", "platform": "S1A", "evidence_id": f"E-{year}-{day}"})
    result = compare(rows, persist=False)
    assert result["interpolation"] == "NONE"
    assert result["fields"][0]["typhoon_causation"] == "UNKNOWN"
    assert all(p["median_vh_difference_db"] == 1 for p in result["fields"][0]["date_matched_pairs"])


def test_no_data_plot_is_rejected(tmp_path):
    with pytest.raises((RuntimeError, ImportError, ModuleNotFoundError)):
        plot([], tmp_path / "fake.png")
    assert not (tmp_path / "fake.png").exists()


def test_agent_returns_unknown_without_observed_evidence():
    result = run_tool("get_field_vh_timeseries", "FIELD-NOT-IN-SOURCE")
    assert result["status"] == "UNKNOWN"
    assert result["evidence_ids"] == []
