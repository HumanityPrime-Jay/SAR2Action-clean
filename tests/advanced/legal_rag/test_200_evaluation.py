"""200-Case Independent Legal RAG, LegalDecisionEvaluator, and Relief Estimation Tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.app.advanced.farmer_agent.field_area import SQ_M_PER_FEN, SQ_M_PER_HA
from backend.app.advanced.farmer_agent.relief_estimator import ReliefAmountEstimator
from backend.app.advanced.legal_rag import LegalDecisionEvaluator, LegalRAGService

BENCHMARK_DIR = Path(__file__).resolve().parent / "benchmark_200"


def test_benchmark_200_manifest_sha256_integrity():
    manifest = json.loads((BENCHMARK_DIR / "held_out_manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_cases"] == 200
    assert manifest["dev_count"] == 120
    assert manifest["final_held_out_count"] == 80
    for filename, expected_sha in manifest["sha256"].items():
        actual_sha = hashlib.sha256((BENCHMARK_DIR / filename).read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"SHA256 mismatch for {filename}"


def test_dev_120_retrieval_quality():
    svc = LegalRAGService()
    rows = [
        json.loads(line)
        for line in (BENCHMARK_DIR / "dev_120.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 120
    answerable = [r for r in rows if r["expected_status"] == "ANSWERED" and r["expected_articles"]]
    status_ok = 0
    r5 = 0
    cit_ok = 0
    for row in rows:
        ev = row.get("expected_rule_conditions") or {}
        resp = svc.query(row["question"], event_date=ev.get("event_date"))
        target_status = "ANSWERED" if row["expected_status"] == "HUMAN_REVIEW_REQUIRED" else row["expected_status"]
        if resp.status == target_status:
            status_ok += 1
        if resp.citation_verification.get("verified", False):
            cit_ok += 1
        if row["expected_status"] == "ANSWERED" and row["expected_articles"]:
            returned = [c["article"].removeprefix("第").removesuffix("條") for c in resp.citations[:5]]
            if any(a in returned for a in row["expected_articles"]):
                r5 += 1
    assert status_ok / len(rows) >= 0.98
    assert r5 / len(answerable) >= 0.95
    assert cit_ok == len(rows)


def test_legal_decision_evaluator_five_statuses():
    evaluator = LegalDecisionEvaluator()

    # 1. OUT_OF_SCOPE
    res_oos = evaluator.evaluate(in_authorized_scope=False)
    assert res_oos.decision_status == "OUT_OF_SCOPE"
    assert res_oos.legal_citations == []

    # 2. ANNOUNCEMENT_NOT_VERIFIED
    res_no_ann = evaluator.evaluate(
        in_authorized_scope=True,
        announcement_verified=False,
        disaster_type="颱風",
        loss_rate_pct=35.0,
        land_area_ha=1.0,
    )
    assert res_no_ann.decision_status == "ANNOUNCEMENT_NOT_VERIFIED"

    # 3. CONDITION_NOT_MET (loss < 20% without exception)
    res_low_loss = evaluator.evaluate(
        in_authorized_scope=True,
        announcement_verified=True,
        disaster_type="颱風",
        relief_type="現金救助",
        applicant_verified=True,
        actual_agricultural_production=True,
        declared_relief_area_verified=True,
        declared_relief_item_verified=True,
        land_area_ha=1.0,
        loss_rate_pct=15.0,
        weather_param_or_severe_exception=False,
    )
    assert res_low_loss.decision_status == "CONDITION_NOT_MET"

    # 4. INSUFFICIENT_INFORMATION (never promoted to ELIGIBILITY_POSSIBLE)
    res_insuff = evaluator.evaluate(
        in_authorized_scope=True,
        announcement_verified=True,
        disaster_type="颱風",
        relief_type="現金救助",
        land_area_ha=0.5,
        loss_rate_pct=None,
    )
    assert res_insuff.decision_status == "INSUFFICIENT_INFORMATION"
    assert res_insuff.missing_facts

    # 5. ELIGIBILITY_POSSIBLE (all core facts verified, >= 20% loss)
    res_ok = evaluator.evaluate(
        in_authorized_scope=True,
        announcement_verified=True,
        disaster_type="颱風",
        relief_type="現金救助",
        applicant_verified=True,
        actual_agricultural_production=True,
        declared_relief_area_verified=True,
        declared_relief_item_verified=True,
        announcement_date="2026-07-10",
        application_deadline="2026-07-24",
        crop_name="水稻",
        land_area_ha=1.2,
        loss_rate_pct=30.0,
        weather_param_or_severe_exception=False,
        ground_evidence_verified=True,
    )
    assert res_ok.decision_status == "ELIGIBILITY_POSSIBLE"
    assert "M0090019-ARTICLE-12-1" in res_ok.legal_citations

    # 6. Exception: loss < 20% still ELIGIBILITY_POSSIBLE if weather_param_or_severe_exception=True
    res_exc = evaluator.evaluate(
        in_authorized_scope=True,
        announcement_verified=True,
        disaster_type="豪雨",
        relief_type="現金救助",
        applicant_verified=True,
        actual_agricultural_production=True,
        declared_relief_area_verified=True,
        declared_relief_item_verified=True,
        announcement_date="2026-07-10",
        application_deadline="2026-07-24",
        crop_name="水稻",
        land_area_ha=0.8,
        loss_rate_pct=12.0,
        weather_param_or_severe_exception=True,
        ground_evidence_verified=True,
    )
    assert res_exc.decision_status == "ELIGIBILITY_POSSIBLE"
    assert res_exc.exceptions


def test_relief_amount_calculation_and_guards():
    estimator = ReliefAmountEstimator()

    # Synthetic unit conversion (3.5 分地 -> ha via SQ_M_PER_FEN / SQ_M_PER_HA) & calculation correctness
    area_ha = round((3.5 * SQ_M_PER_FEN) / SQ_M_PER_HA, 4)
    assert area_ha == 0.3395

    res_calc = estimator.calculate_potential_relief(
        crop="水稻",
        verified_announcement={"status": "VERIFIED_ANNOUNCEMENT_FOUND"},
        verified_appendix_rate_ntd_per_unit=20000.0,
        statutory_unit="公頃",
        eligible_area_ha=area_ha,
        area_source_label="FARMER_REPORTED",
        loss_rate_pct=30.0,
    )
    assert res_calc["status"] == "POTENTIAL_RELIEF_ESTIMATE"
    assert res_calc["POTENTIAL_RELIEF_ESTIMATE_NTD"] == 6790
    assert res_calc["is_approved_amount"] is False

    # Missing verified announcement -> blocked
    res_no_ann = estimator.calculate_potential_relief(
        crop="水稻",
        verified_announcement={"status": "NO_ANNOUNCEMENT_VERIFIED"},
        verified_appendix_rate_ntd_per_unit=20000.0,
        statutory_unit="公頃",
        eligible_area_ha=0.35,
        loss_rate_pct=30.0,
    )
    assert res_no_ann["status"] == "CANNOT_ESTIMATE_MISSING_REQUIREMENTS"
    assert res_no_ann["POTENTIAL_RELIEF_ESTIMATE_NTD"] is None

    # Unverified appendix rate (e.g. EXTRACTION_REQUIRES_REVIEW -> None) -> blocked
    res_no_rate = estimator.calculate_potential_relief(
        crop="水稻",
        verified_announcement={"status": "VERIFIED_ANNOUNCEMENT_FOUND"},
        verified_appendix_rate_ntd_per_unit=None,
        statutory_unit=None,
        eligible_area_ha=0.35,
        loss_rate_pct=30.0,
    )
    assert res_no_rate["status"] == "CANNOT_ESTIMATE_MISSING_REQUIREMENTS"

    # Below 20% loss without exception -> NOT_ELIGIBLE_BELOW_20_PERCENT
    res_below = estimator.calculate_potential_relief(
        crop="水稻",
        verified_announcement={"status": "VERIFIED_ANNOUNCEMENT_FOUND"},
        verified_appendix_rate_ntd_per_unit=20000.0,
        statutory_unit="公頃",
        eligible_area_ha=0.35,
        loss_rate_pct=15.0,
        exception_applies=False,
    )
    assert res_below["status"] == "NOT_ELIGIBLE_BELOW_20_PERCENT"
    assert res_below["POTENTIAL_RELIEF_ESTIMATE_NTD"] == 0

    # Below 20% loss WITH Article 12-1 exception -> allowed estimate
    res_exc = estimator.calculate_potential_relief(
        crop="水稻",
        verified_announcement={"status": "VERIFIED_ANNOUNCEMENT_FOUND"},
        verified_appendix_rate_ntd_per_unit=20000.0,
        statutory_unit="公頃",
        eligible_area_ha=0.35,
        loss_rate_pct=15.0,
        exception_applies=True,
    )
    assert res_exc["status"] == "POTENTIAL_RELIEF_ESTIMATE"
    assert res_exc["POTENTIAL_RELIEF_ESTIMATE_NTD"] == 7000
