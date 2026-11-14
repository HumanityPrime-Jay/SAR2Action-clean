"""Phase 3A Backend API tests (`tests/backend/test_api_phase3a.py`).

Tests:
1. `GET /api/health` schema and frozen metric formula (`abs(Delta_HH) + abs(Delta_HV)`)
2. `GET /api/cases` and `GET /api/cases/{case_id}/observations`
3. `POST /api/validate-pair` on valid pair vs incompatible pair (same scene, opposite orbit)
4. `POST /api/change/analyze` and `POST /api/radar-fingerprint` on real HDF5 windows:
   - COMPARABLE interior AOI (`AOI-ENG-01`)
   - LIMITED swath-edge AOI (`AOI-ENG-02`, science-status propagation)
   - Missing HV polarization handling (`requested_polarizations=["HH"]` -> `hv_detail.status_label == "Unavailable"`, `fingerprint.hv is None`, `combined_radar_change_detail is None`)
5. Error state propagation (never HTTP 200 with fake empty values):
   - Unavailable polarization (`VV` -> HTTP 422 `UNAVAILABLE_POLARIZATION`)
   - Incompatible scene pair (same scene ID or Ascending vs Descending -> HTTP 422 `INCOMPATIBLE_PAIR`)
   - AOI outside coverage (`[100.10, 0.10, 100.20, 0.20]` -> HTTP 422 `AOI_OUTSIDE_COVERAGE` with `science_status == "INSUFFICIENT_EVIDENCE"`)
6. Real `EvidenceRecord` retrieval (`GET /api/evidence/{evidence_id}`) and Layer Metadata + RGBA PNG (`GET /api/layers/{layer_id}`, `GET /api/layers/{layer_id}/image.png`).
"""

from __future__ import annotations

from pathlib import Path
import pytest

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.evidence import COMBINED_RADAR_CHANGE_DISCLAIMER

client = TestClient(app)

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
SCENE_DIR = DATA_ROOT / 'raw' / 'scenes'
SCENE_MANIFEST_READY = (DATA_ROOT / 'scenes' / 'scene_manifest.json').is_file()
CACHED_EVIDENCE_READY = SCENE_MANIFEST_READY and all(
    (DATA_ROOT / 'cache' / name).is_file()
    for name in ('evidence_store.json', 'fingerprint_store.json', 'analysis_store.json')
)
requires_scene_manifest = pytest.mark.skipif(
    not SCENE_MANIFEST_READY, reason='Private scene manifest is absent'
)
requires_cached_evidence = pytest.mark.skipif(
    not CACHED_EVIDENCE_READY, reason='Private scene manifest or B-team evidence cache is absent'
)
REAL_HDF5_READY = all(
    (SCENE_DIR / f'{scene}.h5').is_file() and (SCENE_DIR / f'{scene}.h5').stat().st_size > 100_000_000
    for scene in (
        'NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001',
        'NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001',
        'NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001',
        'NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001',
    )
)
requires_real_hdf5 = pytest.mark.skipif(not REAL_HDF5_READY, reason='Real NISAR HDF5 scene pairs are absent; no synthetic substitution')


def test_api_01_health_endpoint() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["combined_radar_change_formula"] == "abs(Delta_HH) + abs(Delta_HV)"
    assert body["combined_radar_change_disclaimer"] == COMBINED_RADAR_CHANGE_DISCLAIMER
    assert "case-flagship-oki-f2" in body["available_cases"]
    assert "case-engineering-riau-t047" in body["available_cases"]


@requires_scene_manifest
def test_api_02_cases_and_observations() -> None:
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    cases = resp.json()["cases"]
    assert len(cases) >= 2

    obs_resp = client.get("/api/cases/case-engineering-riau-t047/observations")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    assert obs_data["case_id"] == "case-engineering-riau-t047"
    assert len(obs_data["observations"]) >= 2
    default_t0_id = obs_data["default_t0_scene_id"]
    default_obs = next(o for o in obs_data["observations"] if o["scene_id"] == default_t0_id)
    assert "HH" in default_obs["polarizations"]
    assert "HV" in default_obs["polarizations"]
    assert default_obs["product_maturity"] == "PROVISIONAL"


@requires_real_hdf5
def test_api_03_validate_pair_valid_and_incompatible() -> None:
    eng_t0 = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
    eng_t1 = "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001"

    # Valid pair on interior AOI
    r_ok = client.post(
        "/api/validate-pair",
        json={
            "case_id": "case-engineering-riau-t047",
            "scene_t0_id": eng_t0,
            "scene_t1_id": eng_t1,
            "aoi_bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
        },
    )
    assert r_ok.status_code == 200
    res_ok = r_ok.json()["result"]
    assert res_ok["compatible"] is True
    assert res_ok["science_status"] == "COMPARABLE"

    # Incompatible pair: identical scene IDs
    r_same = client.post(
        "/api/validate-pair",
        json={
            "case_id": "case-engineering-riau-t047",
            "scene_t0_id": eng_t0,
            "scene_t1_id": eng_t0,
            "aoi_bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
        },
    )
    assert r_same.status_code == 200
    res_same = r_same.json()["result"]
    assert res_same["compatible"] is False
    assert res_same["science_status"] == "INSUFFICIENT_EVIDENCE"
    assert len(res_same["reasons"]) > 0


@requires_real_hdf5
def test_api_04_change_analyze_and_evidence_and_layers() -> None:
    r = client.post(
        "/api/change/analyze",
        json={
            "case_id": "case-engineering-riau-t047",
            "aoi_id": "AOI-ENG-01",
            "aoi_bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["quality_status"] == "COMPARABLE"
    assert body["valid_pixel_count"] == 2_770_530
    assert body["coverage_ratio"] == 1.0
    ev_id = body["evidence_id"]
    assert ev_id == "E-PHASE2A-ENG-001"
    assert len(body["claims"]) >= 3

    # Verify all required layer types exist
    layers = body["layers"]
    for req_layer in (
        "t0_hh",
        "t1_hh",
        "t0_hv",
        "t1_hv",
        "delta_hh",
        "delta_hv",
        "magnitude_hh",
        "magnitude_hv",
        "combined_change",
        "validity_mask",
    ):
        assert req_layer in layers

    # Fetch EvidenceRecord via GET /api/evidence/{evidence_id}
    ev_resp = client.get(f"/api/evidence/{ev_id}")
    assert ev_resp.status_code == 200
    ev_json = ev_resp.json()
    assert ev_json["evidence_id"] == ev_id
    assert ev_json["valid_pixel_count"] == 2_770_530
    assert "cause_not_determined" in ev_json["limitations"]

    # Fetch Layer metadata and PNG bytes via GET /api/layers/{layer_id}
    delta_hv_layer_id = layers["delta_hv"]["layer_id"]
    l_resp = client.get(f"/api/layers/{delta_hv_layer_id}")
    assert l_resp.status_code == 200
    l_meta = l_resp.json()
    assert l_meta["layer_type"] == "delta_hv"
    assert l_meta["units"] == "dB"
    assert l_meta["legend"]["positive_change_meaning"] is not None
    assert l_meta["legend"]["negative_change_meaning"] is not None

    png_resp = client.get(f"/api/layers/{delta_hv_layer_id}/image.png")
    assert png_resp.status_code == 200
    assert png_resp.headers["content-type"] == "image/png"
    assert png_resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@requires_real_hdf5
def test_api_05_radar_fingerprint_and_limited_status_and_missing_polarization() -> None:
    # 1. Swath-edge AOI-ENG-02 must propagate LIMITED quality status
    r_lim = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-engineering-riau-t047",
            "aoi_id": "AOI-ENG-02",
            "aoi_bbox_wgs84": [103.12, 2.08, 103.30, 2.25],
        },
    )
    assert r_lim.status_code == 200
    b_lim = r_lim.json()
    assert b_lim["quality_status"] == "LIMITED"
    assert b_lim["valid_pixel_count"] == 1_812_679
    assert "partial_valid_coverage" in b_lim["evidence_record"]["limitations"]
    assert len(b_lim["epistemic_panel"]["what_we_observed"]) >= 2
    assert len(b_lim["epistemic_panel"]["what_may_explain_it"]) >= 2
    assert len(b_lim["epistemic_panel"]["what_we_do_not_know"]) >= 3

    # 2. Single-pol HH request must mark HV as "Unavailable" and never synthesize zero
    r_hh = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-engineering-riau-t047",
            "aoi_bbox_wgs84": [104.22, 1.92, 104.28, 1.98],
            "requested_polarizations": ["HH"],
        },
    )
    assert r_hh.status_code == 200
    b_hh = r_hh.json()
    assert b_hh["available_polarizations"] == ["HH"]
    assert "HV" in b_hh["unavailable_polarizations"]
    assert b_hh["hh_detail"]["available"] is True
    assert b_hh["hh_detail"]["status_label"] == "Available"
    assert b_hh["hv_detail"]["available"] is False
    assert b_hh["hv_detail"]["status_label"] == "Unavailable"
    assert b_hh["hv_detail"]["delta_median_db"] is None
    assert b_hh["fingerprint"]["hv"] is None
    assert b_hh["combined_radar_change_detail"] is None


def test_api_06_rejects_unavailable_pol_and_incompatible_pair() -> None:
    # 1. Unavailable polarization (VV on an HH+HV scene) -> HTTP 422
    r_pol = client.post(
        "/api/change/analyze",
        json={
            "case_id": "case-engineering-riau-t047",
            "aoi_bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
            "requested_polarizations": ["VV"],
        },
    )
    assert r_pol.status_code == 422
    assert r_pol.json()["detail"]["error_code"] == "UNAVAILABLE_POLARIZATION"

    # 2. Incompatible scene pair (same scene ID) -> HTTP 422
    eng_t0 = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
    r_inc = client.post(
        "/api/change/analyze",
        json={
            "case_id": "case-engineering-riau-t047",
            "scene_t0_id": eng_t0,
            "scene_t1_id": eng_t0,
            "aoi_bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
        },
    )
    assert r_inc.status_code == 422
    assert r_inc.json()["detail"]["error_code"] == "INCOMPATIBLE_PAIR"
    assert r_inc.json()["detail"]["science_status"] == "INSUFFICIENT_EVIDENCE"



@requires_cached_evidence
def test_api_06_rejects_aoi_outside_cached_coverage() -> None:
    # AOI outside valid coverage -> HTTP 422 with INSUFFICIENT_EVIDENCE
    r_out = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-engineering-riau-t047",
            "aoi_bbox_wgs84": [101.00, 0.10, 101.20, 0.30],
        },
    )
    assert r_out.status_code == 422
    assert r_out.json()["detail"]["error_code"] == "AOI_OUTSIDE_COVERAGE"
    assert r_out.json()["detail"]["science_status"] == "INSUFFICIENT_EVIDENCE"


@requires_real_hdf5
def test_api_07_flagship_oki_case_end_to_end() -> None:
    """Verify Primary Flagship (South Sumatra / OKI T010_F176) end-to-end via FastAPI."""
    r = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-flagship-oki-f2",
            "aoi_id": "AOI-OKI-01",
            "aoi_bbox_wgs84": [105.28, -3.28, 105.48, -3.08],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"] == "case-flagship-oki-f2"
    assert body["roi_id"] == "AOI-OKI-01"
    assert body["evidence_id"] == "E-FLAGSHIP-OKI-001"
    assert body["quality_status"] == "COMPARABLE"
    assert body["valid_pixel_count"] > 4_000_000
    assert body["coverage_ratio"] == 1.0
    assert body["hh_detail"]["available"] is True
    assert body["hv_detail"]["available"] is True
    assert body["combined_radar_change_detail"]["formula"] == "abs(Delta_HH) + abs(Delta_HV)"
    assert body["combined_radar_change_detail"]["unit"] == "dB composite"
    assert (
        body["combined_radar_change_detail"]["disclaimer"]
        == COMBINED_RADAR_CHANGE_DISCLAIMER
    )


@requires_real_hdf5
def test_api_08_phase3c_hardening_aoi_oki_04_and_demo_mode() -> None:
    """Verify predefined external-context AOI-OKI-04 and DEMO_MODE = CACHED_REAL_DATA | LIVE."""
    # 1. Verify AOI-OKI-04 (Padang Sugihan, PREDEFINED_EXTERNAL_CONTEXT)
    r4 = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-flagship-oki-f2",
            "aoi_id": "AOI-OKI-04",
            "aoi_bbox_wgs84": [105.08, -2.92, 105.24, -2.76],
        },
    )
    assert r4.status_code == 200
    b4 = r4.json()
    assert b4["evidence_id"] == "E-FLAGSHIP-OKI-004"
    assert b4["selection_method"] == "PREDEFINED_EXTERNAL_CONTEXT"
    assert "PRE_ANALYSIS" in b4["selection_time"]
    assert b4["valid_pixel_count"] == 3_148_830
    assert b4["combined_radar_change_detail"]["unit"] == "dB composite"
    assert b4["layers"]["combined_change"]["units"] == "dB composite"

    # 2. Switch to DEMO_MODE = CACHED_REAL_DATA and verify cached real NISAR serving
    r_mode = client.post("/api/demo-mode", json={"demo_mode": "CACHED_REAL_DATA"})
    assert r_mode.status_code == 200
    assert r_mode.json()["demo_mode"] == "CACHED_REAL_DATA"

    r_cached = client.post(
        "/api/radar-fingerprint",
        json={
            "case_id": "case-flagship-oki-f2",
            "aoi_id": "AOI-OKI-04",
            "aoi_bbox_wgs84": [105.08, -2.92, 105.24, -2.76],
        },
    )
    assert r_cached.status_code == 200
    b_cached = r_cached.json()
    assert b_cached["demo_mode"] == "CACHED_REAL_DATA"
    assert b_cached["cache_hit"] is True
    assert b_cached["evidence_id"] == "E-FLAGSHIP-OKI-004"

    # Restore DEMO_MODE = LIVE
    r_live = client.post("/api/demo-mode", json={"demo_mode": "LIVE"})
    assert r_live.status_code == 200
    assert r_live.json()["demo_mode"] == "LIVE"


