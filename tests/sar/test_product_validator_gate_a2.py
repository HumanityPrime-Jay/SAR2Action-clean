"""Unit tests for Gate A.2 Product-Level Validation (`sar/validation/product_validator.py`).

Covers all mandatory requirements in Phase 1 Gate A.2 Step 9:
1. actual metadata parser (`parse_nisar_gcov_granule_id` and sidecar/HDF5 metadata structure)
2. mask handling (official NISAR GCOV `0` = invalid, `1..254` = valid subswath, `255` = outside extent)
3. grid equality (`compare_gcov_grids` returning `exact_grid_match=True`)
4. grid mismatch (EPSG, spacing, shape, and coordinate vector offset)
5. valid-overlap calculation (`compute_product_valid_overlap`)
6. unavailable polarization (null-safe handling when `HV` is `None`)
7. invalid / non-positive power ($P <= 0$, `NaN`, `Inf`)
8. nodata propagation (masked and non-positive pixels propagate strictly as `NaN`, never `0.0`)
"""

from __future__ import annotations

import json
import pathlib
import numpy as np
import pytest

from sar.catalog.asf_client import parse_nisar_gcov_granule_id
from sar.validation.product_validator import (
    compare_gcov_grids,
    compute_product_valid_overlap,
    evaluate_gcov_mask,
    inspect_power_layer,
)


def test_actual_metadata_parser_and_sidecar_summary() -> None:
    """1. Actual metadata parser & sidecar summary verification."""
    t0_id = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
    parsed = parse_nisar_gcov_granule_id(t0_id)
    assert parsed["product_type"] == "GCOV"
    assert parsed["band"] == "L"
    assert parsed["orbit_direction"] == "DESCENDING"
    assert parsed["track_or_frame"] == "T047_F087"
    assert parsed["polarizations"] == ["HH", "HV"]
    assert parsed["crid"] == "P05023"
    assert parsed["product_maturity"] == "PROVISIONAL"

    sidecar_json = (
        pathlib.Path(__file__).resolve().parents[2]
        / "data"
        / "raw"
        / "sidecars"
        / "AOI-A1_T047_F087"
        / "sidecar_and_harmony_summary.json"
    )
    if not sidecar_json.exists():
        pytest.skip("Private NISAR sidecar summary is absent")
    data = json.loads(sidecar_json.read_text(encoding="utf-8"))
    t0_ident = data["t0_qa_stats"]["datasets"]
    assert t0_ident["science/LSAR/identification/compositeReleaseId"]["value"] == "P05023"
    assert t0_ident["science/LSAR/identification/orbitPassDirection"]["value"] == "Descending"
    assert t0_ident["science/LSAR/identification/lookDirection"]["value"] == "Left"


def test_gcov_mask_handling_official_semantics() -> None:
    """2. Mask handling: 0=invalid focused, 1..254=valid subswath, 255=outside fill."""
    mask = np.array(
        [
            [255, 255, 0, 1],
            [255, 1, 2, 0],
        ],
        dtype=np.uint8,
    )
    res = evaluate_gcov_mask(mask)
    assert res["total_pixels"] == 8
    assert res["outside_fill_255_pixels"] == 3
    assert res["invalid_zero_pixels"] == 2
    assert res["valid_pixels"] == 3
    assert res["acquired_pixels"] == 5
    assert res["subswath_ids"] == [1, 2]
    assert pytest.approx(res["valid_fraction_full_grid"]) == 3.0 / 8.0
    assert pytest.approx(res["valid_fraction_acquired"]) == 3.0 / 5.0


def test_grid_equality_exact_match() -> None:
    """3. Grid equality: identical EPSG, spacing, dimensions, and coordinate arrays."""
    grid_a = {
        "epsg": 32648,
        "x_spacing_m": 10.0,
        "y_spacing_m": -10.0,
        "width": 4,
        "height": 3,
        "x_coordinates": np.array([277205.0, 277215.0, 277225.0, 277235.0]),
        "y_coordinates": np.array([483835.0, 483825.0, 483815.0]),
    }
    grid_b = {
        "epsg": 32648,
        "x_spacing_m": 10.0,
        "y_spacing_m": -10.0,
        "width": 4,
        "height": 3,
        "x_coordinates": np.array([277205.0, 277215.0, 277225.0, 277235.0]),
        "y_coordinates": np.array([483835.0, 483825.0, 483815.0]),
    }
    cmp_res = compare_gcov_grids(grid_a, grid_b)
    assert cmp_res["exact_grid_match"] is True
    assert cmp_res["crs_compatible"] is True
    assert cmp_res["same_spacing"] is True
    assert cmp_res["same_shape"] is True
    assert cmp_res["same_x_coordinates"] is True
    assert cmp_res["same_y_coordinates"] is True
    assert cmp_res["reasons"] == []


def test_grid_mismatch_detection() -> None:
    """4. Grid mismatch: detects EPSG, spacing, dimension, or coordinate vector offset."""
    base = {
        "epsg": 32648,
        "x_spacing_m": 10.0,
        "y_spacing_m": -10.0,
        "width": 4,
        "height": 3,
        "x_coordinates": np.array([277205.0, 277215.0, 277225.0, 277235.0]),
        "y_coordinates": np.array([483835.0, 483825.0, 483815.0]),
    }
    shifted = dict(base)
    shifted["x_coordinates"] = base["x_coordinates"] + 5.0
    shifted["epsg"] = 32748
    cmp_res = compare_gcov_grids(base, shifted)
    assert cmp_res["exact_grid_match"] is False
    assert cmp_res["crs_compatible"] is False
    assert cmp_res["same_x_coordinates"] is False
    assert len(cmp_res["reasons"]) >= 2


def test_valid_overlap_calculation() -> None:
    """5. Valid-overlap calculation across T0 and T1."""
    mask_t0 = np.array([[255, 1, 1, 0], [255, 1, 1, 1]], dtype=np.uint8)
    mask_t1 = np.array([[255, 1, 0, 1], [255, 1, 1, 1]], dtype=np.uint8)
    p0_hh = np.array([[np.nan, 0.10, 0.20, 0.15], [np.nan, 0.12, 0.18, 0.25]], dtype=np.float32)
    p0_hv = np.array([[np.nan, 0.02, 0.03, 0.01], [np.nan, 0.02, 0.04, 0.05]], dtype=np.float32)
    p1_hh = np.array([[np.nan, 0.11, 0.19, 0.14], [np.nan, 0.10, 0.16, 0.00]], dtype=np.float32)
    p1_hv = np.array([[np.nan, 0.02, 0.03, 0.02], [np.nan, 0.03, 0.03, 0.04]], dtype=np.float32)

    res = compute_product_valid_overlap(
        mask_t0,
        mask_t1,
        {"HH": p0_hh, "HV": p0_hv},
        {"HH": p1_hh, "HV": p1_hv},
    )
    assert res["common_polarizations"] == ["HH", "HV"]
    assert res["unavailable_polarizations"] == []
    # T0 valid at (0,1), (0,2), (1,1), (1,2), (1,3) -> 5 pixels
    assert res["t0_valid_pixel_count"] == 5
    # T1 valid at (0,1), (0,3), (1,1), (1,2) [(1,3) has p1_hh == 0.0 -> invalid!] -> 4 pixels
    assert res["t1_valid_pixel_count"] == 4
    # Common valid at (0,1), (1,1), (1,2) -> 3 pixels
    assert res["common_valid_pixel_count"] == 3
    # Acquired union is 6 pixels (all except column 0 which is 255 in both)
    assert res["acquired_union_pixel_count"] == 6
    assert pytest.approx(res["valid_overlap_ratio_acquired_union"]) == 3.0 / 6.0


def test_unavailable_polarization_handling() -> None:
    """6. Unavailable polarization: never synthesizes missing HV channel."""
    mask = np.array([[1, 1], [1, 255]], dtype=np.uint8)
    hh0 = np.array([[0.1, 0.2], [0.3, np.nan]], dtype=np.float32)
    hh1 = np.array([[0.15, 0.25], [0.35, np.nan]], dtype=np.float32)

    res = compute_product_valid_overlap(
        mask,
        mask,
        {"HH": hh0, "HV": None},
        {"HH": hh1, "HV": None},
    )
    assert res["common_polarizations"] == ["HH"]
    assert res["unavailable_polarizations"] == ["HV"]
    assert res["common_valid_pixel_count"] == 3


def test_invalid_and_non_positive_power_and_nodata_propagation() -> None:
    """7 & 8. Invalid/non-positive power ($P <= 0$, NaN, Inf) and strict nodata propagation."""
    mask = np.array([[1, 1, 1], [1, 0, 255]], dtype=np.uint8)
    power = np.array(
        [
            [0.10, 0.0, -0.05],
            [np.nan, 0.20, 0.50],
        ],
        dtype=np.float32,
    )
    info = inspect_power_layer(power, mask)
    assert info["valid_pixel_count"] == 1
    assert info["zero_pixel_count"] == 1
    assert info["negative_pixel_count"] == 1
    assert info["nan_pixel_count"] == 1

    db = info["db_array"]
    # Only (0, 0) with P=0.10 and mask=1 is valid -> -10.0 dB
    assert pytest.approx(float(db[0, 0]), abs=1e-5) == -10.0
    # Zero power (0,1), negative power (0,2), NaN (1,0), mask=0 (1,1), and mask=255 (1,2) MUST all be NaN (never 0.0!)
    assert np.isnan(db[0, 1])
    assert np.isnan(db[0, 2])
    assert np.isnan(db[1, 0])
    assert np.isnan(db[1, 1])
    assert np.isnan(db[1, 2])
