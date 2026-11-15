"""TW-05 Backend Service, Router & Missing-Asset Degradation Tests (`tests/backend/test_tw05_agro_api.py`).

Tests the FastAPI endpoint handlers (`get_tw_agro_overview`, `get_tw_agro_geojson`,
`get_tw_agro_asset_png`) and `TaiwanAgroService` directly against the real
`tw01/taiwan-agricultural-demo-v1/` and `tw03/nisar-demo-v1/` files without
touching any scientific engine code or synthesizing fallback values.
"""

from __future__ import annotations

import json
import pathlib
import shutil

import pytest
from fastapi import HTTPException

from backend.app.main import (
    compute_tw_agro_relief_estimate,
    get_tw_agro_asset_png,
    get_tw_agro_geojson,
    get_tw_agro_overview,
    get_tw_agro_relief_catalog,
)
from backend.app.schemas.taiwan_agro import TwAgroReliefEstimateRequest
from backend.app.services.taiwan_agro_service import (
    DEFAULT_TW01_DIR,
    DEFAULT_TW03_DIR,
    TaiwanAgroService,
)


def test_tw05_overview_loads_real_packages_dynamically() -> None:
    overview_model = get_tw_agro_overview()
    data = overview_model.model_dump(mode="json")

    assert data["workspace_id"] == "TW-05-YUNLIN-AGRO"
    assert data["farmland_total_parcel_count"] == 4863

    # Verify NISAR TW-03 dynamic values match tw03/nisar-demo-v1 files
    nisar = data["nisar_tw03"]
    assert nisar["available"] is True
    assert nisar["status"] == "verified_observation"
    assert nisar["evidence_id"] == "E-TW03-B82BA14BAC9F8501"
    assert nisar["valid_pixel_count"] == 63080
    assert nisar["total_reference_pixel_count"] == 64770
    assert abs(nisar["coverage_ratio"] - 0.973908) < 1e-6
    assert nisar["aoi_coverage_ratio"] == 1.0
    assert abs(nisar["polarization_stats"]["HH"]["delta_db"]["median"] - (-0.1541)) < 1e-4
    assert abs(nisar["polarization_stats"]["HV"]["delta_db"]["median"] - (-0.1181)) < 1e-4
    assert len(nisar["layers"]["delta_hh"]["coordinates_lon_lat"]) == 4
    assert "颱風前觀測" in nisar["observation_role_badge"]

    # Verify Sentinel-1D TW-01 dynamic values match tw01/taiwan-agricultural-demo-v1 files
    s1 = data["s1_tw01"]
    assert s1["available"] is True
    assert s1["status"] == "verified_observation"
    assert s1["evidence_id"] == "E-TW01-EA46045A8B43AC0E"
    assert s1["valid_pixel_count"] == 27785
    assert s1["coverage_ratio"] == 1.0
    assert abs(s1["polarization_stats"]["VV"]["delta_db"]["median"] - 0.2231) < 1e-4
    assert abs(s1["polarization_stats"]["VH"]["delta_db"]["median"] - 0.6917) < 1e-4
    assert len(s1["layers"]["delta_vv"]["coordinates_lon_lat"]) == 4
    assert "跨事件觀測" in s1["observation_role_badge"]

    # Verify 181 candidate parcels joined with candidate-parcels.geojson
    screening = data["parcel_screening_summary"]
    assert screening["available"] is True
    assert screening["total_farmland_parcels"] == 4863
    assert screening["eligible_parcels"] == 1070
    assert screening["candidate_count"] == 181
    assert screening["candidate_pixel_count"] == 5603
    assert len(screening["candidates"]) == 181
    first_c = screening["candidates"][0]
    assert first_c["parcel_no"]
    assert first_c["clipped_area_m2"] > 0
    assert abs(first_c["clipped_area_ha"] - round(first_c["clipped_area_m2"] / 10_000.0, 8)) < 1e-9

    # Verify Relief Info Card values, announcement dates/items, expired notice, and disclaimers
    relief = data["relief_info"]
    assert relief["yunlin_reported_loss_twd"] == 157740000
    assert "115年10月26日" in relief["applicable_items_summary"]
    assert "1151112527F" in relief["applicable_items_summary"]
    assert "洋蔥苗圃" in relief["applicable_items_summary"]
    assert "【受理期限已截止】" in relief["application_deadline_guidance"]
    assert "11月9日" in relief["application_deadline_guidance"]
    assert "11月13日" in relief["application_deadline_guidance"]
    assert "不自動判定救助資格" in relief["mandatory_disclaimer"]
    assert "afa.gov.tw" in relief["official_report_url"]

    # Scientific guardrails present
    joined_guardrails = " ".join(data["scientific_guardrails"])
    assert "不可直接相減" in joined_guardrails
    assert "颱風前觀測" in joined_guardrails


def test_tw05_geojson_and_png_assets_served() -> None:
    r_aoi = get_tw_agro_geojson("aoi")
    assert r_aoi.media_type == "application/geo+json"
    assert json.loads(r_aoi.body)["type"] == "Feature"

    r_cand = get_tw_agro_geojson("candidate-parcels")
    cand_fc = json.loads(r_cand.body)
    assert cand_fc["type"] == "FeatureCollection"
    assert len(cand_fc["features"]) == 181

    r_farm = get_tw_agro_geojson("farmland")
    farm_fc = json.loads(r_farm.body)
    assert farm_fc["type"] == "FeatureCollection"
    assert len(farm_fc["features"]) == 4863

    # PNGs have real PNG magic header
    for pkg, fname in [
        ("tw03", "delta_hh.png"),
        ("tw03", "delta_hv.png"),
        ("tw01", "delta_vv_overlay.png"),
        ("tw01", "delta_vh_overlay.png"),
        ("tw01", "farmland.png"),
    ]:
        r_png = get_tw_agro_asset_png(pkg, fname)
        assert r_png.media_type == "image/png"
        assert r_png.body[:8] == b"\x89PNG\r\n\x1a\n"

    # Security: path traversal or unknown asset raises HTTP 404
    with pytest.raises(HTTPException) as exc1:
        get_tw_agro_asset_png("tw01", "manifest.json")
    assert exc1.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        get_tw_agro_asset_png("tw03", "../manifest.json")
    assert exc2.value.status_code == 404

    with pytest.raises(HTTPException) as exc3:
        get_tw_agro_geojson("unknown")
    assert exc3.value.status_code == 404


def test_tw05_missing_data_never_synthesizes_values(tmp_path: pathlib.Path) -> None:
    tw01_copy = tmp_path / "tw01"
    tw03_copy = tmp_path / "tw03"
    tw01_copy.mkdir()
    tw03_copy.mkdir()

    # Case A: completely missing manifests -> both sensors marked unavailable
    svc_empty = TaiwanAgroService(tw01_dir=tw01_copy, tw03_dir=tw03_copy)
    ov_empty = svc_empty.get_overview()
    assert ov_empty.nisar_tw03.available is False
    assert ov_empty.nisar_tw03.status == "missing_manifest"
    assert ov_empty.nisar_tw03.valid_pixel_count is None
    assert ov_empty.nisar_tw03.polarization_stats == {}
    assert ov_empty.s1_tw01.available is False
    assert ov_empty.parcel_screening_summary.available is False
    assert ov_empty.parcel_screening_summary.candidates == []

    # Case B: status != verified_observation and missing overlay PNG in tw03
    shutil.copy(DEFAULT_TW03_DIR / "manifest.json", tw03_copy / "manifest.json")
    manifest = json.loads((tw03_copy / "manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = "insufficient_evidence"
    (tw03_copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Copy valid tw01 manifest without PNG overlays
    shutil.copy(DEFAULT_TW01_DIR / "manifest.json", tw01_copy / "manifest.json")

    svc_degraded = TaiwanAgroService(tw01_dir=tw01_copy, tw03_dir=tw03_copy)
    ov_deg = svc_degraded.get_overview()
    assert ov_deg.nisar_tw03.available is False
    assert ov_deg.nisar_tw03.status == "insufficient_evidence"
    assert len(ov_deg.nisar_tw03.missing_assets) > 0
    assert ov_deg.s1_tw01.available is False
    assert "delta_vv_overlay.png" in ov_deg.s1_tw01.missing_assets
    assert ov_deg.s1_tw01.polarization_stats == {}
    assert ov_deg.parcel_screening_summary.available is False


def test_tw07_relief_catalog_and_conditional_estimator() -> None:
    catalog = get_tw_agro_relief_catalog().model_dump(mode="json")
    assert catalog["schedule_version_id"] == "MOA-RELIEF-SCHEDULE-1150629-V1"
    assert catalog["regulation_amendment_date_roc"] == "115年6月29日"
    assert catalog["as_of_date_iso"] == "2026-11-14"
    assert "115/11/09" in catalog["primary_deadline_expired_warning"]
    assert "落花生" in catalog["statutory_exception_notice"]
    assert abs(catalog["farmland_total_area_ha"] - 1876.87) < 0.05
    assert abs(catalog["candidate_total_area_ha"] - 95.433) < 0.05

    items_by_id = {item["item_id"]: item for item in catalog["items"]}
    assert items_by_id["grains_3_peanut_sweetpotato"]["rate_twd_per_ha"] == 36000
    assert items_by_id["onion_nursery"]["rate_twd_per_ha"] == 373000
    assert items_by_id["onion_nursery"]["announcement_doc_id"] == "MOA-1151112552B"
    assert items_by_id["excluded_bamboo_shoot"]["announced_in_yunlin_11510"] is False

    fw_ids = {f["framework_id"] for f in catalog["framework_separation"]}
    assert fw_ids == {"government_cash_relief", "agricultural_insurance", "economic_production_loss"}

    # Pick top candidate parcel from overview
    overview = get_tw_agro_overview()
    top_parcel = overview.parcel_screening_summary.candidates[0]

    # Guardrail 1: unknown crop blocks estimation
    res_unknown = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="unknown_crop",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_unknown.calculation_allowed is False
    assert res_unknown.result_status == "BLOCKED_UNKNOWN_CROP"
    assert res_unknown.conditional_reference_amount_twd is None

    # Guardrail 2: excluded bamboo shoot in 1151112527F blocks estimation
    res_bamboo = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="excluded_bamboo_shoot",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_bamboo.calculation_allowed is False
    assert res_bamboo.result_status == "BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM"
    assert res_bamboo.conditional_reference_amount_twd is None
    assert "排除" in (res_bamboo.blocked_reason or "")

    # Guardrail 3: below 20% threshold refuses payout (never multiplies by %)
    res_below20 = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="below_20_percent",
        )
    )
    assert res_below20.calculation_allowed is False
    assert res_below20.result_status == "BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD"
    assert res_below20.conditional_reference_amount_twd is None

    # Guardrail 4: area exceeding parcel GeoJSON clipped area is rejected
    res_oversize = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=top_parcel.clipped_area_ha + 0.5,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_oversize.calculation_allowed is False
    assert res_oversize.result_status == "BLOCKED_INVALID_AREA"

    # Valid conditional calculation: statutory rate * approved area (never multiplied by 20%)
    res_ok = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_ok.calculation_allowed is True
    assert res_ok.result_status == "CONDITIONAL_REFERENCE_ESTIMATE"
    assert "非核定可領金額" in res_ok.result_label
    expected_twd = round(36000 * top_parcel.clipped_area_ha)
    assert res_ok.conditional_reference_amount_twd == expected_twd
    assert res_ok.confirmed_facts["parcel_no"] == top_parcel.parcel_no
    assert "SAR" in res_ok.satellite_observations["sar_db_prohibition"]
    assert len(res_ok.unconfirmed_eligibility) >= 3
    assert "2026-11-14" in res_ok.deadline_and_exception_notice

    # Onion nursery 115/10/30 announcement standalone calculation (373,000 * 0.5 ha = 186,500)
    res_onion = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=None,
            crop_item_id="onion_nursery",
            assumed_approved_area_ha=0.5,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_onion.calculation_allowed is True
    assert res_onion.conditional_reference_amount_twd == 186500

    # Invalid parcel ID raises HTTP 404
    with pytest.raises(HTTPException) as exc_nf:
        compute_tw_agro_relief_estimate(
            TwAgroReliefEstimateRequest(
                parcel_feature_id=99999999,
                crop_item_id="grains_3_peanut_sweetpotato",
                assumed_approved_area_ha=0.5,
                assumed_loss_threshold="meets_20_percent",
            )
        )
    assert exc_nf.value.status_code == 404


def test_tw071_statutory_qa_exceptions_min_area_and_cross_aoi_boundary() -> None:
    catalog = get_tw_agro_relief_catalog().model_dump(mode="json")
    assert "第5條" in catalog["statutory_basis_articles"]
    assert "第12條" in catalog["statutory_basis_articles"]
    assert "第12條之1" in catalog["statutory_basis_articles"]
    assert catalog["min_application_area_ha"] == 0.01

    items_by_id = {item["item_id"]: item for item in catalog["items"]}
    # Verify 115/06/29 Schedule II placement fixes:
    # 樹豆 in grains_1 (28,000), 小米 in grains_3 (36,000), 空心菜/莧菜 in veg_2 (41,000), 馬鈴薯 in veg_3 (47,000)
    assert any("樹豆" in ex for ex in items_by_id["grains_1"]["examples"])
    assert not any("樹豆" in ex for ex in items_by_id["grains_3_peanut_sweetpotato"]["examples"])
    assert any("小米" in ex for ex in items_by_id["grains_3_peanut_sweetpotato"]["examples"])
    assert any("空心菜" in ex for ex in items_by_id["veg_2"]["examples"])
    assert any("莧菜" in ex for ex in items_by_id["veg_2"]["examples"])
    assert any("馬鈴薯" in ex for ex in items_by_id["veg_3"]["examples"])
    assert items_by_id["grains_1"]["rate_twd_per_ha"] == 28000
    assert items_by_id["veg_2"]["rate_twd_per_ha"] == 41000
    assert items_by_id["veg_3"]["rate_twd_per_ha"] == 47000

    overview = get_tw_agro_overview()
    top_parcel = overview.parcel_screening_summary.candidates[0]

    # Unannounced other crop is blocked
    res_unannounced = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="unannounced_other_crop",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_unannounced.calculation_allowed is False
    assert res_unannounced.result_status == "BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM"

    # Article 12 simplified procedure / Article 12-1 proviso exception allows estimation even when general 20% threshold option isn't used
    res_art12 = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=top_parcel.parcel_feature_id,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=top_parcel.clipped_area_ha,
            assumed_loss_threshold="article_12_simplified_exception",
        )
    )
    assert res_art12.calculation_allowed is True
    assert res_art12.result_status == "CONDITIONAL_REFERENCE_ESTIMATE"
    assert res_art12.conditional_reference_amount_twd == round(36000 * top_parcel.clipped_area_ha)
    assert "第12條" in (res_art12.formula_display or "")

    # Cross-AOI boundary parcel (#205) flagged as touches_aoi_boundary; blocks larger area unless override checked
    boundary_candidates = [
        c for c in overview.parcel_screening_summary.candidates if c.parcel_feature_id == 205
    ]
    assert len(boundary_candidates) == 1
    p205 = boundary_candidates[0]
    assert p205.touches_aoi_boundary is True
    assert "AOI" in res_art12.confirmed_facts["parcel_area_nature"]

    oversized_boundary_area = round(p205.clipped_area_ha + 0.5, 4)
    res_boundary_blocked = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=205,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=oversized_boundary_area,
            assumed_loss_threshold="meets_20_percent",
            allow_cross_aoi_boundary_area=False,
        )
    )
    assert res_boundary_blocked.calculation_allowed is False
    assert res_boundary_blocked.result_status == "BLOCKED_INVALID_AREA"

    res_boundary_allowed = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=205,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=oversized_boundary_area,
            assumed_loss_threshold="meets_20_percent",
            allow_cross_aoi_boundary_area=True,
        )
    )
    assert res_boundary_allowed.calculation_allowed is True
    assert res_boundary_allowed.conditional_reference_amount_twd == round(
        36000 * oversized_boundary_area
    )

    # Article 5 Paragraph 2 Subparagraph 5: < 0.01 ha parcel (#43 in farmland.geojson ~0.0010 ha) is blocked unless adjacent merge checked
    res_small_blocked = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=43,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=0.0010,
            assumed_loss_threshold="meets_20_percent",
            adjacent_land_merged_meets_001ha=False,
        )
    )
    assert res_small_blocked.calculation_allowed is False
    assert res_small_blocked.result_status == "BLOCKED_BELOW_MIN_AREA_001_HA"

    res_small_merged = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=43,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=0.0010,
            assumed_loss_threshold="meets_20_percent",
            adjacent_land_merged_meets_001ha=True,
        )
    )
    assert res_small_merged.calculation_allowed is True
    assert res_small_merged.conditional_reference_amount_twd == round(36000 * 0.0010)


def test_tw072_precision_unknown_full_area_and_article12_separation() -> None:
    overview = get_tw_agro_overview()
    p4183 = next(
        c for c in overview.parcel_screening_summary.candidates if c.parcel_feature_id == 4183
    )
    assert p4183.clipped_area_m2 == 4539.78
    assert p4183.clipped_area_ha == 0.453978

    # Precision regression on #4183: 36,000 * 0.453978 = 16,343.208 -> rounds to NT$16,343 (never 16,344)
    res_4183 = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=4183,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=p4183.clipped_area_ha,
            assumed_loss_threshold="meets_20_percent",
        )
    )
    assert res_4183.calculation_allowed is True
    assert res_4183.conditional_reference_amount_twd == 16343
    assert "0.453978 公頃" in (res_4183.formula_display or "")

    # 0.01 ha threshold checks application land area, while full cadastral/application areas remain UNKNOWN
    assert res_4183.confirmed_facts["parcel_full_cadastral_area_ha"] == "UNKNOWN"
    assert res_4183.confirmed_facts["parcel_application_land_area_ha"] == "UNKNOWN"
    assert "UNKNOWN" in res_4183.confirmed_facts["parcel_min_001ha_eligibility_from_aoi_clip"]

    # Even on < 0.01 ha AOI clip parcel (#43), if assumed full application land area >= 0.01 ha is supplied
    # with cross-boundary override, Article 5 does NOT falsely reject based on AOI clipped_area_ha
    res_small_clip_large_app = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=43,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=0.0200,
            assumed_loss_threshold="meets_20_percent",
            allow_cross_aoi_boundary_area=True,
            adjacent_land_merged_meets_001ha=False,
        )
    )
    assert res_small_clip_large_app.calculation_allowed is True
    assert res_small_clip_large_app.conditional_reference_amount_twd == 720

    # Article 12 simplified procedure 3-way separation: user scenario assumption vs official vs authority
    res_art12 = compute_tw_agro_relief_estimate(
        TwAgroReliefEstimateRequest(
            parcel_feature_id=4183,
            crop_item_id="grains_3_peanut_sweetpotato",
            assumed_approved_area_ha=p4183.clipped_area_ha,
            assumed_loss_threshold="article_12_simplified_exception",
        )
    )
    assert res_art12.calculation_allowed is True
    assert res_art12.conditional_reference_amount_twd == 16343
    assert "使用者情境假設" in res_art12.user_assumptions["article_12_user_scenario_assumption"]
    assert "UNCONFIRMED" in res_art12.confirmed_facts["article_12_official_announcement_applicability"]
    assert "不能單靠勾選" in res_art12.confirmed_facts["article_12_competent_authority_determination"]


def test_tw08_sentinel2_supplementary_overview_and_parcel_optical(tmp_path: pathlib.Path) -> None:
    from backend.app.main import get_tw_agro_asset_png, get_tw_agro_parcel_optical

    overview = get_tw_agro_overview()
    assert overview.s2_tw08 is not None
    s2 = overview.s2_tw08
    assert s2.available is True
    assert s2.boa_offset_verified is True
    assert s2.ground_truth_labels_available is False
    assert s2.classifier_trained is False
    assert len(s2.scenes) == 4
    assert s2.total_farmland_parcels == 4863
    assert s2.farmland_sufficient_count == 3166
    assert s2.farmland_insufficient_count == 1697
    assert s2.candidate_181_count == 181
    assert s2.candidate_sufficient_count == 119
    assert s2.candidate_insufficient_count == 62
    assert s2.clear_delta is not None
    assert s2.clear_delta.t0_date == "2026-10-11"
    assert s2.clear_delta.t1_date == "2026-11-05"

    by_date = {sc.date_utc: sc for sc in s2.scenes}
    assert by_date["2026-10-11"].usability_status == "USABLE_CLEAR"
    assert by_date["2026-10-16"].usability_status == "CLOUD_OBSCURED_UNUSABLE"
    assert by_date["2026-10-26"].usability_status == "CLOUD_OBSCURED_UNUSABLE"
    assert by_date["2026-11-05"].usability_status == "USABLE_CLEAR"
    assert "SCL={4,5,6}" in s2.scl_semantics_note

    # All 181 candidates carry per-parcel optical metrics strictly partitioned 119 sufficient vs 62 insufficient
    candidates = overview.parcel_screening_summary.candidates
    assert len(candidates) == 181
    suff_cands = [c for c in candidates if c.optical_s2 and c.optical_s2.quality_gate_status == "SUFFICIENT_CLEAR_BOTH"]
    insuff_cands = [
        c for c in candidates if c.optical_s2 and c.optical_s2.quality_gate_status == "INSUFFICIENT_OPTICAL_EVIDENCE"
    ]
    assert len(suff_cands) == 119
    assert len(insuff_cands) == 62
    for c in candidates:
        assert c.optical_s2 is not None
        assert c.optical_s2.crop_type_label == "UNKNOWN"
        assert c.optical_s2.actual_damage_rate == "UNKNOWN"

    # Sufficient candidate (#74) vs INSUFFICIENT OPTICAL EVIDENCE candidate (#174)
    p74_opt = get_tw_agro_parcel_optical(74)
    assert p74_opt.quality_gate_status == "SUFFICIENT_CLEAR_BOTH"
    assert p74_opt.usable_clear_dates == ["2026-10-11", "2026-11-05"]
    assert p74_opt.delta_ndvi_20261011_20261105 is not None
    assert p74_opt.crop_type_label == "UNKNOWN"
    assert p74_opt.actual_damage_rate == "UNKNOWN"

    p174_opt = get_tw_agro_parcel_optical(174)
    assert p174_opt.quality_gate_status == "INSUFFICIENT_OPTICAL_EVIDENCE"
    assert p174_opt.quality_gate_label == "INSUFFICIENT OPTICAL EVIDENCE"
    assert "2026-11-05" in (p174_opt.insufficient_reason or "")
    assert p174_opt.delta_ndvi_20261011_20261105 is None

    # Non-candidate farmland parcel (#43) is also queryable via /optical
    p43_opt = get_tw_agro_parcel_optical(43)
    assert p43_opt.is_tw01_sar_candidate_181 is False
    assert p43_opt.crop_type_label == "UNKNOWN"
    assert p43_opt.actual_damage_rate == "UNKNOWN"

    with pytest.raises(HTTPException) as exc_opt_nf:
        get_tw_agro_parcel_optical(99999999)
    assert exc_opt_nf.value.status_code == 404

    # Security allowlist on /assets/tw08/*
    png_resp = get_tw_agro_asset_png("tw08", "ndvi_20261011_overlay.png")
    assert png_resp.body.startswith(b"\x89PNG")
    for bad_name in ("manifest.json", "../sentinel2-qa-v2/qa_v2_manifest.json", "ndvi_20261011.tif"):
        with pytest.raises(HTTPException) as exc_asset:
            get_tw_agro_asset_png("tw08", bad_name)
        assert exc_asset.value.status_code == 404

    # Missing tw08 directory degrades gracefully without crash or synthetic values
    degraded_svc = TaiwanAgroService(tw08_dir=tmp_path / "missing_tw08")
    degraded_ov = degraded_svc.get_overview()
    assert degraded_ov.s2_tw08 is None
    with pytest.raises(HTTPException) as exc_missing:
        degraded_svc.get_parcel_optical_metrics(74)
    assert exc_missing.value.status_code == 404



