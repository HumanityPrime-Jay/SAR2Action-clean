"""Unit tests for Phase 1 Catalog Metadata Models, Pair Screening, and `validate_scene_pair` v1.

Covers all 10 mandatory test cases specified in Phase 1 Step 9:
1. two compatible metadata records
2. same acquisition date
3. no spatial overlap
4. nonmatching band/product
5. no shared polarization
6. missing polarization metadata
7. incompatible orbit direction
8. missing optional metadata
9. BETA vs PROVISIONAL mismatch
10. null CRID / unknown processing version
"""

from __future__ import annotations

from typing import Any
import pytest

from backend.app.schemas.evidence import PolarizationChannel, ScienceQualityStatus
from sar.catalog.asf_client import parse_nisar_gcov_granule_id
from sar.catalog.models import CatalogScreeningStatus, NormalizedSceneMetadata
from sar.validation.pair_validator import screen_candidate_pairs, validate_scene_pair


def _make_scene(**overrides: Any) -> NormalizedSceneMetadata:
    base: dict[str, Any] = {
        "candidate_id": "Case_B",
        "aoi_id": "AOI-B1",
        "aoi_name": "California Test AOI",
        "event_context": "Unit test fixture",
        "scene_id": "NISAR_L2_PR_GCOV_001_005_A_012_2000_DHDH_A_20260801T112000_20260801T112035_P05000_F_N_J_001",
        "product_short_name": "NISAR_L2_GCOV_PROVISIONAL_V1",
        "product_type": "GCOV",
        "acquisition_start_utc": "2026-08-01T11:20:00Z",
        "acquisition_end_utc": "2026-08-01T11:20:35Z",
        "band": "L",
        "polarizations": ["HH", "HV"],
        "orbit_direction": "ASCENDING",
        "look_direction": "Right",
        "track_or_frame": "T005_F012",
        "relative_orbit": 5,
        "frame_number": 12,
        "product_maturity": "PROVISIONAL",
        "crid": "P05000",
        "processing_version": "1",
        "grid_spacing_m": 20.0,
        "bbox": [-122.0, 39.8, -121.2, 40.6],
    }
    base.update(overrides)
    return NormalizedSceneMetadata(**base)


def test_case_01_two_compatible_metadata_records() -> None:
    """Case 1: Two complete, compatible metadata records -> PASS / COMPARABLE."""
    s0 = _make_scene()
    s1 = _make_scene(
        scene_id="NISAR_L2_PR_GCOV_002_005_A_012_2000_DHDH_A_20260813T112002_20260813T112037_P05000_F_N_J_001",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        acquisition_end_utc="2026-08-13T11:20:37Z",
    )
    res = validate_scene_pair(s0, s1, aoi=[-121.9, 39.9, -121.3, 40.5])
    assert res.compatible is True
    assert res.validation_decision == "PASS"
    assert res.science_status == ScienceQualityStatus.COMPARABLE
    assert res.available_polarizations == [PolarizationChannel.HH, PolarizationChannel.HV]
    assert res.reasons == []
    assert res.warnings == []


def test_case_02_same_acquisition_date() -> None:
    """Case 2: Same acquisition date/timestamp -> FAIL / INSUFFICIENT_EVIDENCE."""
    s0 = _make_scene()
    s1 = _make_scene(
        scene_id="NISAR_L2_PR_GCOV_001_005_A_012_2000_DHDH_A_20260801T112000_20260801T112035_P05000_F_N_J_002",
        acquisition_start_utc="2026-08-01T11:20:00Z",
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is False
    assert res.validation_decision == "FAIL"
    assert res.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert res.metadata_checks["temporal_distinct"] == "FAIL"
    assert any("timestamp" in r.lower() for r in res.reasons)


def test_case_03_no_spatial_overlap() -> None:
    """Case 3: Disjoint spatial footprints -> FAIL / INSUFFICIENT_EVIDENCE."""
    s0 = _make_scene(bbox=[-122.0, 39.8, -121.2, 40.6])
    s1 = _make_scene(
        scene_id="NISAR_L2_PR_GCOV_002_099_A_040_2000_DHDH_A_20260813T112002_20260813T112037_P05000_F_N_J_001",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        bbox=[101.0, 0.2, 102.0, 1.2],
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is False
    assert res.validation_decision == "FAIL"
    assert res.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert res.metadata_checks["spatial_overlap"] == "FAIL"
    assert any("spatial overlap" in r.lower() for r in res.reasons)


def test_case_04_nonmatching_band_or_product() -> None:
    """Case 4: Nonmatching radar band (S vs L) or product type (GUNW vs GCOV) -> FAIL."""
    s0 = _make_scene()
    s1_wrong_band = _make_scene(
        scene_id="SCENE_S_BAND",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        band="S",
        product_type="GUNW",
    )
    res = validate_scene_pair(s0, s1_wrong_band)
    assert res.compatible is False
    assert res.validation_decision == "FAIL"
    assert res.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert res.metadata_checks["band_check"] == "FAIL"
    assert res.metadata_checks["product_type_check"] == "FAIL"


def test_case_05_no_shared_polarization() -> None:
    """Case 5: Known disjoint polarizations (HH vs VV) -> FAIL / INSUFFICIENT_EVIDENCE."""
    s0 = _make_scene(polarizations=["HH", "HV"])
    s1 = _make_scene(
        scene_id="SCENE_VV_ONLY",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        polarizations=["VV", "VH"],
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is False
    assert res.validation_decision == "FAIL"
    assert res.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert res.available_polarizations == []
    assert res.metadata_checks["polarization_check"] == "FAIL"


def test_case_06_missing_polarization_metadata() -> None:
    """Case 6: Missing polarization metadata (None) -> WARNING / CONDITIONAL (not invented!)."""
    s0 = _make_scene(polarizations=None)
    s1 = _make_scene(
        scene_id="SCENE_T1_NO_POL_META",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        polarizations=None,
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is True
    assert res.validation_decision == "CONDITIONAL"
    assert res.science_status == ScienceQualityStatus.LIMITED
    assert res.available_polarizations == []
    assert res.metadata_checks["polarization_check"] == "CONDITIONAL"
    assert any("polarization list is missing" in w.lower() for w in res.warnings)


def test_case_07_incompatible_orbit_direction() -> None:
    """Case 7: ASCENDING vs DESCENDING orbit pass direction -> FAIL / INSUFFICIENT_EVIDENCE."""
    s0 = _make_scene(orbit_direction="ASCENDING")
    s1 = _make_scene(
        scene_id="SCENE_T1_DESCENDING",
        acquisition_start_utc="2026-08-13T23:20:02Z",
        orbit_direction="DESCENDING",
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is False
    assert res.validation_decision == "FAIL"
    assert res.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    assert res.same_orbit_pass is False
    assert res.metadata_checks["orbit_direction_check"] == "FAIL"


def test_case_08_missing_optional_metadata() -> None:
    """Case 8: Missing optional metadata (look_direction, track_or_frame, grid_spacing_m) -> CONDITIONAL."""
    s0 = _make_scene(look_direction=None, track_or_frame=None, grid_spacing_m=None)
    s1 = _make_scene(
        scene_id="SCENE_T1_OPT_MISSING",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        look_direction=None,
        track_or_frame=None,
        grid_spacing_m=None,
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is True
    assert res.validation_decision == "CONDITIONAL"
    assert res.science_status == ScienceQualityStatus.LIMITED
    assert res.metadata_checks["look_direction_check"] == "CONDITIONAL"
    assert res.metadata_checks["track_frame_check"] == "CONDITIONAL"
    assert res.metadata_checks["grid_spacing_check"] == "CONDITIONAL"
    assert len(res.warnings) >= 3


def test_case_09_beta_vs_provisional_mismatch() -> None:
    """Case 9: BETA vs PROVISIONAL product maturity mismatch -> WARNING / CONDITIONAL."""
    s0 = _make_scene(
        product_short_name="NISAR_L2_GCOV_BETA_V1",
        product_maturity="BETA",
    )
    s1 = _make_scene(
        scene_id="SCENE_T1_PROVISIONAL",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        product_short_name="NISAR_L2_GCOV_PROVISIONAL_V1",
        product_maturity="PROVISIONAL",
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is True
    assert res.validation_decision == "CONDITIONAL"
    assert res.science_status == ScienceQualityStatus.LIMITED
    assert res.metadata_checks["maturity_check"] == "CONDITIONAL"
    assert any("maturity mismatch" in w.lower() for w in res.warnings)


def test_case_10_null_crid_and_unknown_processing_version() -> None:
    """Case 10: Null CRID and unknown processing version -> WARNING / CONDITIONAL."""
    s0 = _make_scene(crid=None, processing_version=None)
    s1 = _make_scene(
        scene_id="SCENE_T1_NULL_CRID",
        acquisition_start_utc="2026-08-13T11:20:02Z",
        crid=None,
        processing_version=None,
    )
    res = validate_scene_pair(s0, s1)
    assert res.compatible is True
    assert res.validation_decision == "CONDITIONAL"
    assert res.science_status == ScienceQualityStatus.LIMITED
    assert res.metadata_checks["crid_check"] == "CONDITIONAL"
    assert res.metadata_checks["processing_version_check"] == "CONDITIONAL"
    assert any("crid is null/unknown" in w.lower() for w in res.warnings)


def test_screen_candidate_pairs_never_emits_comparable_label() -> None:
    """Verify `screen_candidate_pairs` outputs CATALOG_SCREENED / CONDITIONAL / FAIL."""
    s0 = _make_scene()
    s1 = _make_scene(
        scene_id="NISAR_L2_PR_GCOV_002_005_A_012_2000_DHDH_A_20260813T112002_20260813T112037_P05000_F_N_J_001",
        acquisition_start_utc="2026-08-13T11:20:02Z",
    )
    s2_bad = _make_scene(
        scene_id="NISAR_L2_PR_GCOV_002_005_D_012_2000_DHDH_A_20260814T232002_20260814T232037_P05000_F_N_J_001",
        acquisition_start_utc="2026-08-14T23:20:02Z",
        orbit_direction="DESCENDING",
    )
    pairs = screen_candidate_pairs([s0, s1, s2_bad], aoi_bbox=[-121.9, 39.9, -121.3, 40.5])
    assert len(pairs) == 3
    assert pairs[0].screening_status == CatalogScreeningStatus.CATALOG_SCREENED
    assert pairs[0].screening_status.value != "COMPARABLE"
    assert pairs[-1].screening_status == CatalogScreeningStatus.FAIL


def test_parse_nisar_gcov_granule_id() -> None:
    parsed = parse_nisar_gcov_granule_id(
        "NISAR_L2_PR_GCOV_003_048_A_019_2000_DHDH_A_20260210T114500_20260210T114536_P05000_F_N_J_001.h5"
    )
    assert parsed["product_type"] == "GCOV"
    assert parsed["band"] == "L"
    assert parsed["orbit_direction"] == "ASCENDING"
    assert parsed["track_or_frame"] == "T048_F019"
    assert parsed["polarizations"] == ["HH", "HV"]
    assert parsed["crid"] == "P05000"
    assert parsed["product_maturity"] == "PROVISIONAL"


def test_scene_manifest_csv_integrity() -> None:
    import csv
    import pathlib
    from sar.catalog.candidate_search import MANIFEST_CSV_COLUMNS

    csv_path = pathlib.Path(__file__).resolve().parents[2] / "data" / "scenes" / "scene_manifest.csv"
    if not csv_path.exists():
        pytest.skip("Private scene manifest CSV is absent")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == MANIFEST_CSV_COLUMNS
        rows = list(reader)
    assert len(rows) >= 100
    assert all(r["product_short_name"] == "NISAR_L2_GCOV_PROVISIONAL_V1" for r in rows)
    assert any(r["candidate_id"] == "Case_A" for r in rows)
    assert any(r["candidate_id"] == "Case_B" for r in rows)
    assert any(r["candidate_id"] == "Case_C" for r in rows)


def test_parse_nisar_gcov_filename_orbit_fidelity_and_coverage() -> None:
    """Verify official NISAR L2 GCOV naming convention fields after CRID:
    - <A>: P = Precise, M = Medium, N = Near Real-Time, F = Forecast
    - <C>: F = Full, P = Partial
    - <L>: J = JPL
    """
    from sar.catalog import parse_nisar_gcov_filename, parse_nisar_gcov_granule_id

    # 1. Flagship T0: P05023_N_F_J_001 -> Near Real-Time, Full, JPL
    f2_t0 = "NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001.h5"
    m_t0 = parse_nisar_gcov_filename(f2_t0)
    assert m_t0.crid == "P05023"
    assert m_t0.orbit_pointing_fidelity_code == "N"
    assert m_t0.orbit_pointing_fidelity == "Near Real-Time"
    assert m_t0.coverage_code == "F"
    assert m_t0.coverage_indicator == "Full"
    assert m_t0.is_full_frame is True
    assert m_t0.sds_location_code == "J"
    assert m_t0.sds_location == "JPL"

    # 2. Flagship T1: P05023_F_F_J_001 -> Forecast (NOT upgraded), Full, JPL
    f2_t1 = "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001"
    m_t1 = parse_nisar_gcov_filename(f2_t1)
    assert m_t1.crid == "P05023"
    assert m_t1.orbit_pointing_fidelity_code == "F"
    assert m_t1.orbit_pointing_fidelity == "Forecast"
    assert m_t1.coverage_code == "F"
    assert m_t1.coverage_indicator == "Full"
    assert m_t1.is_full_frame is True
    assert m_t1.sds_location_code == "J"
    assert m_t1.sds_location == "JPL"

    # 3. Engineering T0: P05023_N_P_J_001 -> Near Real-Time, Partial, JPL
    eng_t0 = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
    m_eng = parse_nisar_gcov_filename(eng_t0)
    assert m_eng.orbit_pointing_fidelity_code == "N"
    assert m_eng.orbit_pointing_fidelity == "Near Real-Time"
    assert m_eng.coverage_code == "P"
    assert m_eng.coverage_indicator == "Partial"
    assert m_eng.is_full_frame is False

    # 4. Precise (P) and Medium (M) fidelity tokens
    p_id = "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_P_F_J_001"
    m_id = "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_M_P_J_001"
    assert parse_nisar_gcov_filename(p_id).orbit_pointing_fidelity == "Precise"
    assert parse_nisar_gcov_filename(m_id).orbit_pointing_fidelity == "Medium"
    assert parse_nisar_gcov_filename(m_id).coverage_indicator == "Partial"

    # Also verify parse_nisar_gcov_granule_id dict output
    d_t1 = parse_nisar_gcov_granule_id(f2_t1)
    assert d_t1["orbit_pointing_fidelity_code"] == "F"
    assert d_t1["orbit_pointing_fidelity"] == "Forecast"
    assert d_t1["coverage_code"] == "F"
    assert d_t1["coverage_indicator"] == "Full"
    assert d_t1["sds_location"] == "JPL"



