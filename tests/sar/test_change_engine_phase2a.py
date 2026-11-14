"""Phase 2A unit and regression tests for the deterministic SAR2Action Change Engine (`sar/change/`).

Covers all 17 mandatory test specifications in Phase 2A.8:
1. linear power -> dB
2. signed delta
3. magnitude
4. combined metric & mandatory disclaimer
5. mask == 0 exclusion (regression test for finite positive power with mask == 0)
6. mask == 255 exclusion
7. NaN exclusion
8. zero power exclusion
9. negative power exclusion
10. common-valid intersection
11. missing HH
12. missing HV
13. AOI partly outside coverage
14. AOI fully outside coverage
15. grid mismatch refusal
16. deterministic repeated output
17. EvidenceRecord contents (including real HDF5 windowed validation on T047_F087)
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

from backend.app.schemas.evidence import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    PolarizationChannel,
    ScienceQualityStatus,
)
from sar.change import (
    GCOVSceneWindow,
    GridDefinition,
    GridMismatchError,
    MASK_RULE_SPECIFICATION,
    aoi_to_window,
    build_multitemporal_valid_masks,
    compute_combined_radar_change,
    compute_magnitude_db,
    compute_signed_delta_db,
    compute_valid_pixel_mask,
    linear_power_to_db,
    run_aoi_change_analysis,
    run_in_memory_change_analysis,
    verify_grids_compatible,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
T0_H5 = (
    ROOT
    / "data"
    / "raw"
    / "scenes"
    / "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001.h5"
)
T1_H5 = (
    ROOT
    / "data"
    / "raw"
    / "scenes"
    / "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001.h5"
)


def _make_test_grid(width: int = 10, height: int = 10, epsg: int = 32648) -> GridDefinition:
    x_coords = 400005.0 + 10.0 * np.arange(width, dtype=np.float64)
    y_coords = 200095.0 - 10.0 * np.arange(height, dtype=np.float64)
    return GridDefinition(
        epsg=epsg,
        width=width,
        height=height,
        x_spacing_m=10.0,
        y_spacing_m=-10.0,
        x_coordinates=x_coords,
        y_coordinates=y_coords,
    )


def _make_scene_window(
    *,
    scene_id: str,
    start_utc: str,
    grid: GridDefinition,
    mask: np.ndarray,
    hh: np.ndarray | None,
    hv: np.ndarray | None,
    aoi_utm_bbox: list[float] | None = None,
) -> GCOVSceneWindow:
    if aoi_utm_bbox is None:
        min_x, min_y, max_x, max_y = grid.bounds_utm
        aoi_utm_bbox = [min_x, min_y, max_x, max_y]
    window = aoi_to_window(aoi_utm_bbox, grid, aoi_crs=f"EPSG:{grid.epsg}")
    avail_pols: list[str] = []
    if hh is not None:
        avail_pols.append("HH")
    if hv is not None:
        avail_pols.append("HV")
    looks = np.full(mask.shape, 4.84, dtype=np.float32)
    return GCOVSceneWindow(
        scene_id=scene_id,
        file_path=None,
        acquisition_start_utc=start_utc,
        acquisition_end_utc=start_utc,
        orbit_pass_direction="Descending",
        look_direction="Left",
        track_number=47,
        frame_number=87,
        crid="P05023",
        product_version="1.0.11",
        is_full_frame=False,
        data_maturity="PROVISIONAL",
        frequency_group="frequencyA",
        available_polarizations=avail_pols,
        grid=grid,
        window=window,
        mask=mask,
        power={"HH": hh, "HV": hv},
        number_of_looks=looks,
        window_ram_bytes=int(mask.nbytes + (hh.nbytes if hh is not None else 0) + (hv.nbytes if hv is not None else 0)),
        full_frame_equivalent_bytes=14_351_261_184,
    )


def test_01_linear_power_to_db() -> None:
    """1. Linear power -> dB conversion on known positive values."""
    power = np.array([[1.0, 0.1], [0.01, 10.0]], dtype=np.float32)
    mask = np.ones((2, 2), dtype=np.uint8)
    db = linear_power_to_db(power, mask=mask)
    expected = np.array([[0.0, -10.0], [-20.0, 10.0]], dtype=np.float32)
    np.testing.assert_allclose(db, expected, rtol=0.0, atol=1e-5)


def test_02_signed_delta_db() -> None:
    """2. Signed delta preserves positive and negative sign."""
    t0_db = np.array([[-10.0, -20.0], [-15.0, -12.0]], dtype=np.float32)
    t1_db = np.array([[-13.5, -16.0], [-15.0, -8.5]], dtype=np.float32)
    delta = compute_signed_delta_db(t0_db, t1_db)
    expected = np.array([[-3.5, +4.0], [0.0, +3.5]], dtype=np.float32)
    np.testing.assert_allclose(delta, expected, rtol=0.0, atol=1e-5)


def test_03_magnitude_db() -> None:
    """3. Magnitude is strictly non-negative |Delta| while preserving NaN."""
    delta = np.array([[-3.5, +4.0], [np.nan, -0.25]], dtype=np.float32)
    mag = compute_magnitude_db(delta)
    assert np.isclose(mag[0, 0], 3.5)
    assert np.isclose(mag[0, 1], 4.0)
    assert np.isnan(mag[1, 0])
    assert np.isclose(mag[1, 1], 0.25)


def test_04_combined_radar_change_metric_and_disclaimer() -> None:
    """4. Combined Radar Change D = |Delta_HH| + |Delta_HV| with mandatory disclaimer."""
    d_hh = np.array([[-2.0, +1.5], [np.nan, -3.0]], dtype=np.float32)
    d_hv = np.array([[-3.5, -2.5], [1.0, np.nan]], dtype=np.float32)
    layer = compute_combined_radar_change(d_hh, d_hv)
    assert layer is not None
    assert layer.metric_name == "Combined Radar Change"
    assert (
        layer.disclaimer
        == "Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."
    )
    assert layer.disclaimer == COMBINED_RADAR_CHANGE_DISCLAIMER
    assert np.isclose(layer.data[0, 0], 5.5)
    assert np.isclose(layer.data[0, 1], 4.0)
    assert np.isnan(layer.data[1, 0])
    assert np.isnan(layer.data[1, 1])


def test_05_mask_zero_exclusion_regression() -> None:
    """5. Regression test: finite positive power with `mask == 0` MUST be excluded (never 0 dB change)."""
    mask = np.array([[0, 1], [0, 2]], dtype=np.uint8)
    # All pixels have finite positive linear power!
    power_t0 = np.array([[0.25, 0.10], [0.50, 0.01]], dtype=np.float32)
    power_t1 = np.array([[0.50, 0.20], [0.10, 0.02]], dtype=np.float32)

    valid_t0 = compute_valid_pixel_mask(mask, power_t0)
    assert bool(valid_t0[0, 0]) is False
    assert bool(valid_t0[1, 0]) is False
    assert bool(valid_t0[0, 1]) is True
    assert bool(valid_t0[1, 1]) is True

    bundle = build_multitemporal_valid_masks(
        mask, mask, {"HH": power_t0}, {"HH": power_t1}
    )
    assert bundle.diagnostics["per_polarization"]["HH"]["t0_mask_zero_with_finite_positive_power_rejected"] == 2
    assert bundle.diagnostics["per_polarization"]["HH"]["t1_mask_zero_with_finite_positive_power_rejected"] == 2

    db_t0 = linear_power_to_db(power_t0, mask=mask)
    db_t1 = linear_power_to_db(power_t1, mask=mask)
    delta = compute_signed_delta_db(db_t0, db_t1, common_valid_mask=bundle.common_valid_by_pol["HH"])
    assert np.isnan(delta[0, 0])
    assert np.isnan(delta[1, 0])
    assert np.isclose(delta[0, 1], 10.0 * np.log10(2.0), atol=1e-4)


def test_06_mask_255_exclusion() -> None:
    """6. Pixels with `mask == 255` (outside radar acquisition extent) are strictly excluded."""
    mask = np.array([[255, 1], [255, 255]], dtype=np.uint8)
    power = np.array([[0.1, 0.1], [0.2, 0.3]], dtype=np.float32)
    db = linear_power_to_db(power, mask=mask)
    assert np.isnan(db[0, 0])
    assert np.isnan(db[1, 0])
    assert np.isnan(db[1, 1])
    assert np.isclose(db[0, 1], -10.0)


def test_07_nan_power_exclusion() -> None:
    """7. NaN power values are excluded even when `mask == 1`."""
    mask = np.ones((2, 2), dtype=np.uint8)
    power = np.array([[np.nan, 0.1], [0.01, np.nan]], dtype=np.float32)
    db = linear_power_to_db(power, mask=mask)
    assert np.isnan(db[0, 0])
    assert np.isnan(db[1, 1])
    assert int(np.isfinite(db).sum()) == 2


def test_08_zero_power_exclusion() -> None:
    """8. Zero power (P == 0.0) is excluded without runtime warnings and becomes NaN."""
    mask = np.ones((2, 2), dtype=np.uint8)
    power = np.array([[0.0, 0.1], [0.0, 1.0]], dtype=np.float32)
    db = linear_power_to_db(power, mask=mask)
    assert np.isnan(db[0, 0])
    assert np.isnan(db[1, 0])
    assert np.isclose(db[0, 1], -10.0)
    assert np.isclose(db[1, 1], 0.0)


def test_09_negative_power_exclusion() -> None:
    """9. Negative power (P < 0.0) is excluded and becomes NaN."""
    mask = np.ones((2, 2), dtype=np.uint8)
    power = np.array([[-0.05, 0.1], [-10.0, 0.01]], dtype=np.float32)
    db = linear_power_to_db(power, mask=mask)
    assert np.isnan(db[0, 0])
    assert np.isnan(db[1, 0])
    assert np.isclose(db[0, 1], -10.0)
    assert np.isclose(db[1, 1], -20.0)


def test_10_common_valid_intersection() -> None:
    """10. Common validity requires validity in BOTH T0 and T1 across shared channels."""
    m0 = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    m1 = np.array([[1, 255], [1, 1]], dtype=np.uint8)
    p0_hh = np.array([[0.1, 0.1], [0.1, 0.1]], dtype=np.float32)
    p1_hh = np.array([[0.2, 0.2], [0.2, 0.0]], dtype=np.float32)  # (1,1) has zero power in T1
    bundle = build_multitemporal_valid_masks(m0, m1, {"HH": p0_hh}, {"HH": p1_hh})
    # (0,0): valid in both -> True
    # (0,1): m1 is 255 -> False
    # (1,0): m0 is 0 -> False
    # (1,1): p1_hh is 0.0 -> False
    expected = np.array([[True, False], [False, False]], dtype=bool)
    np.testing.assert_array_equal(bundle.common_valid_mask, expected)
    np.testing.assert_array_equal(bundle.missing_invalid_mask, ~expected)


def test_11_missing_hh_polarization() -> None:
    """11. Missing HH sets HH outputs and Combined Radar Change to None without fabricating HH."""
    grid = _make_test_grid(4, 4)
    mask = np.ones((4, 4), dtype=np.uint8)
    hv0 = np.full((4, 4), 0.02, dtype=np.float32)
    hv1 = np.full((4, 4), 0.04, dtype=np.float32)

    w0 = _make_scene_window(scene_id="S0", start_utc="2026-07-23T11:26:05Z", grid=grid, mask=mask, hh=None, hv=hv0)
    w1 = _make_scene_window(scene_id="S1", start_utc="2026-09-21T11:26:03Z", grid=grid, mask=mask, hh=None, hv=hv1)

    res = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-NO-HH", evidence_id="E-NO-HH")
    assert res.available_polarizations == ["HV"]
    assert "HH" in res.unavailable_polarizations
    assert res.t0_hh_db is None
    assert res.t1_hh_db is None
    assert res.delta_hh_db is None
    assert res.magnitude_hh_db is None
    assert res.combined_radar_change is None
    assert res.evidence_record.combined_change_db is None
    assert PolarizationChannel.HH not in res.evidence_record.polarizations
    assert "hh_polarization_unavailable" in res.evidence_record.limitations
    assert res.evidence_record.quality_status == ScienceQualityStatus.LIMITED


def test_12_missing_hv_polarization() -> None:
    """12. Missing HV sets HV outputs and Combined Radar Change to None without fabricating HV."""
    grid = _make_test_grid(4, 4)
    mask = np.ones((4, 4), dtype=np.uint8)
    hh0 = np.full((4, 4), 0.10, dtype=np.float32)
    hh1 = np.full((4, 4), 0.05, dtype=np.float32)

    w0 = _make_scene_window(scene_id="S0", start_utc="2026-07-23T11:26:05Z", grid=grid, mask=mask, hh=hh0, hv=None)
    w1 = _make_scene_window(scene_id="S1", start_utc="2026-09-21T11:26:03Z", grid=grid, mask=mask, hh=hh1, hv=None)

    res = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-NO-HV", evidence_id="E-NO-HV")
    assert res.available_polarizations == ["HH"]
    assert "HV" in res.unavailable_polarizations
    assert res.t0_hv_db is None
    assert res.t1_hv_db is None
    assert res.delta_hv_db is None
    assert res.magnitude_hv_db is None
    assert res.combined_radar_change is None
    assert res.evidence_record.combined_change_db is None
    assert PolarizationChannel.HV not in res.evidence_record.polarizations
    assert "hv_polarization_unavailable" in res.evidence_record.limitations
    assert res.evidence_record.quality_status == ScienceQualityStatus.LIMITED


def test_13_aoi_partly_outside_coverage() -> None:
    """13. AOI partly outside scene grid clips cleanly and marks `partly_outside_grid=True`."""
    grid = _make_test_grid(10, 10)  # UTM x: [400000..400100], y: [200000..200100]
    # Request a box where half is outside to the west (x: [399950..400050], y: [200000..200100])
    aoi_utm = [399950.0, 200000.0, 400050.0, 200100.0]
    win = aoi_to_window(aoi_utm, grid, aoi_crs="EPSG:32648")
    assert win.fully_outside_grid is False
    assert win.partly_outside_grid is True
    assert win.requested_pixel_count == 100
    assert win.window_pixel_count == 50  # 10 rows x 5 cols inside the grid

    mask = np.ones(win.shape, dtype=np.uint8)
    hh0 = np.full(win.shape, 0.1, dtype=np.float32)
    hh1 = np.full(win.shape, 0.2, dtype=np.float32)
    hv0 = np.full(win.shape, 0.02, dtype=np.float32)
    hv1 = np.full(win.shape, 0.04, dtype=np.float32)

    w0 = _make_scene_window(
        scene_id="S0", start_utc="2026-07-23T11:26:05Z", grid=grid, mask=mask, hh=hh0, hv=hv0, aoi_utm_bbox=aoi_utm
    )
    w1 = _make_scene_window(
        scene_id="S1", start_utc="2026-09-21T11:26:03Z", grid=grid, mask=mask, hh=hh1, hv=hv1, aoi_utm_bbox=aoi_utm
    )
    res = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-PARTIAL", evidence_id="E-PARTIAL")
    assert res.evidence_record.valid_pixel_count == 50
    assert np.isclose(res.evidence_record.coverage_ratio, 0.50)
    assert np.isclose(res.evidence_record.missing_data_ratio, 0.50)
    assert "aoi_partly_outside_coverage" in res.evidence_record.limitations
    assert res.evidence_record.quality_status == ScienceQualityStatus.LIMITED


def test_14_aoi_fully_outside_coverage() -> None:
    """14. AOI fully outside coverage returns 0 valid pixels and `INSUFFICIENT_EVIDENCE`."""
    grid = _make_test_grid(10, 10)  # UTM x: [400000..400100], y: [200000..200100]
    aoi_utm = [500000.0, 300000.0, 500100.0, 300100.0]
    win = aoi_to_window(aoi_utm, grid, aoi_crs="EPSG:32648")
    assert win.fully_outside_grid is True
    assert win.window_pixel_count == 0

    empty_mask = np.empty((0, 0), dtype=np.uint8)
    empty_f = np.empty((0, 0), dtype=np.float32)
    w0 = _make_scene_window(
        scene_id="S0", start_utc="2026-07-23T11:26:05Z", grid=grid, mask=empty_mask, hh=empty_f, hv=empty_f, aoi_utm_bbox=aoi_utm
    )
    w1 = _make_scene_window(
        scene_id="S1", start_utc="2026-09-21T11:26:03Z", grid=grid, mask=empty_mask, hh=empty_f, hv=empty_f, aoi_utm_bbox=aoi_utm
    )
    res = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-OUTSIDE", evidence_id="E-OUTSIDE")
    assert res.evidence_record.valid_pixel_count == 0
    assert res.evidence_record.coverage_ratio == 0.0
    assert res.evidence_record.missing_data_ratio == 1.0
    assert res.evidence_record.quality_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert "aoi_fully_outside_coverage" in res.evidence_record.limitations


def test_15_grid_mismatch_refusal() -> None:
    """15. Grid mismatch between T0 and T1 is refused with `GridMismatchError`."""
    g0 = _make_test_grid(10, 10, epsg=32648)
    g_wrong_epsg = _make_test_grid(10, 10, epsg=32748)
    with pytest.raises(GridMismatchError, match="EPSG mismatch"):
        verify_grids_compatible(g0, g_wrong_epsg)

    g_wrong_shape = _make_test_grid(12, 10, epsg=32648)
    with pytest.raises(GridMismatchError, match="Grid shape mismatch"):
        verify_grids_compatible(g0, g_wrong_shape)

    g_offset = GridDefinition(
        epsg=32648,
        width=10,
        height=10,
        x_spacing_m=10.0,
        y_spacing_m=-10.0,
        x_coordinates=g0.x_coordinates + 5.0,
        y_coordinates=g0.y_coordinates,
    )
    with pytest.raises(GridMismatchError, match="xCoordinates"):
        verify_grids_compatible(g0, g_offset)


def test_16_deterministic_repeated_output() -> None:
    """16. Running the Change Engine repeatedly produces bit-for-bit identical arrays and stats."""
    grid = _make_test_grid(8, 8)
    rng = np.random.default_rng(42)
    mask0 = rng.choice([0, 1, 1, 1, 255], size=(8, 8)).astype(np.uint8)
    mask1 = rng.choice([0, 1, 1, 1, 255], size=(8, 8)).astype(np.uint8)
    hh0 = rng.uniform(0.01, 0.5, size=(8, 8)).astype(np.float32)
    hh1 = rng.uniform(0.01, 0.5, size=(8, 8)).astype(np.float32)
    hv0 = rng.uniform(0.002, 0.1, size=(8, 8)).astype(np.float32)
    hv1 = rng.uniform(0.002, 0.1, size=(8, 8)).astype(np.float32)

    w0 = _make_scene_window(scene_id="S0", start_utc="2026-07-23T11:26:05Z", grid=grid, mask=mask0, hh=hh0, hv=hv0)
    w1 = _make_scene_window(scene_id="S1", start_utc="2026-09-21T11:26:03Z", grid=grid, mask=mask1, hh=hh1, hv=hv1)

    res_a = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-DET", evidence_id="E-DET-1")
    res_b = run_in_memory_change_analysis(win_t0=w0, win_t1=w1, roi_id="ROI-DET", evidence_id="E-DET-1")

    np.testing.assert_array_equal(res_a.delta_hh_db, res_b.delta_hh_db)
    np.testing.assert_array_equal(res_a.delta_hv_db, res_b.delta_hv_db)
    np.testing.assert_array_equal(res_a.magnitude_hh_db, res_b.magnitude_hh_db)
    np.testing.assert_array_equal(res_a.magnitude_hv_db, res_b.magnitude_hv_db)
    assert res_a.combined_radar_change is not None and res_b.combined_radar_change is not None
    np.testing.assert_array_equal(res_a.combined_radar_change.data, res_b.combined_radar_change.data)
    assert res_a.aoi_statistics == res_b.aoi_statistics


@pytest.mark.skipif(not (T0_H5.exists() and T1_H5.exists()), reason="Local Gate A.2 HDF5 files required")
def test_17_real_hdf5_window_and_evidence_record_contents() -> None:
    """17. End-to-end windowed Change Engine execution on real NISAR L2 GCOV T047_F087 scenes."""
    # Select a 15 km x 15 km AOI window inside the active T047_F087 swath including a swath edge
    # where `mask == 0` pixels with finite positive power occur:
    # [104.20°E..104.35°E, 1.90°N..2.05°N]
    aoi_bbox = [104.20, 1.90, 104.35, 2.05]
    res = run_aoi_change_analysis(
        T0_H5,
        T1_H5,
        aoi_bbox,
        roi_id="ENG-T047-F087-BINTAN-15KM",
        evidence_id="E-PHASE2A-ENG-001",
    )

    ev = res.evidence_record
    assert ev.evidence_id == "E-PHASE2A-ENG-001"
    assert len(ev.scene_ids) == 2
    assert ev.polarizations == [PolarizationChannel.HH, PolarizationChannel.HV]
    assert ev.valid_pixel_count > 1_000_000
    assert "cause_not_determined" in ev.limitations
    assert "provisional_product" in ev.limitations
    assert ev.combined_change_db is not None
    assert ev.combined_change_db.disclaimer == COMBINED_RADAR_CHANGE_DISCLAIMER
    assert ev.summary_statistics["mask_rule"] == MASK_RULE_SPECIFICATION
    assert ev.summary_statistics["valid_area_km2"] > 100.0
    assert res.window_ram_bytes < 100_000_000  # Window uses < 100 MB vs ~28.7 GB full pair!
    assert "HH" in ev.summary_statistics["per_polarization"]
    assert "HV" in ev.summary_statistics["per_polarization"]
    hh_stats = ev.summary_statistics["per_polarization"]["HH"]
    for key in (
        "valid_pixel_count",
        "valid_area_km2",
        "missing_invalid_fraction",
        "median_t0_db",
        "median_t1_db",
        "median_delta_db",
        "mean_delta_db",
        "p10_delta_db",
        "p25_delta_db",
        "p50_delta_db",
        "p75_delta_db",
        "p90_delta_db",
        "median_abs_change_db",
        "positive_change_fraction",
        "negative_change_fraction",
    ):
        assert hh_stats[key] is not None
