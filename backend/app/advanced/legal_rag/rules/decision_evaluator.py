"""Legal Decision Evaluator (Section 7) — Preliminary Statutory Eligibility & Guardrails.

Outputs preliminary legal decision states (NOT government approval):
- ELIGIBILITY_POSSIBLE
- CONDITION_NOT_MET
- INSUFFICIENT_INFORMATION
- ANNOUNCEMENT_NOT_VERIFIED
- OUT_OF_SCOPE
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.app.advanced.legal_rag.rules.engine import evaluate_legal_rules


@dataclass
class LegalDecisionResult:
    decision_status: str
    applied_rules: list[str] = field(default_factory=list)
    confirmed_facts: dict[str, Any] = field(default_factory=dict)
    missing_facts: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    legal_citations: list[str] = field(default_factory=list)
    decision_limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegalDecisionEvaluator:
    """Deterministic preliminary legal condition evaluator backed by M0090019 rules."""

    DEFAULT_LIMITATIONS = [
        "DECISION_SUPPORT_ONLY：本評估僅為法規條件初步檢核，不代表鄉（鎮、市、區）公所或農業部核定資格。",
        "實際救助資格、被害面積與撥款金額，仍須由公所受理並依第12條勘查核定為準。",
    ]

    def evaluate(
        self,
        *,
        in_authorized_scope: bool = True,
        announcement_verified: bool | None = None,
        disaster_type: str | None = None,
        relief_type: str | None = None,
        applicant_verified: bool | None = None,
        actual_agricultural_production: bool | None = None,
        declared_relief_area_verified: bool | None = None,
        declared_relief_item_verified: bool | None = None,
        announcement_date: str | None = None,
        application_deadline: str | None = None,
        land_area_ha: float | None = None,
        loss_rate_pct: float | None = None,
        weather_param_or_severe_exception: bool | None = None,
        is_livestock_headcount: bool = False,
        crop_name: str | None = None,
        ground_evidence_verified: bool | None = None,
        applicable_version_verified: bool = True,
    ) -> LegalDecisionResult:
        if not in_authorized_scope:
            return LegalDecisionResult(
                decision_status="OUT_OF_SCOPE",
                applied_rules=["SCOPE_GUARD_M0090019_ONLY"],
                confirmed_facts={},
                missing_facts=["《農業天然災害救助辦法》授權法源範圍內之問題"],
                exceptions=[],
                legal_citations=[],
                decision_limitations=self.DEFAULT_LIMITATIONS,
            )

        rules = evaluate_legal_rules(
            disaster_type=disaster_type,
            relief_type=relief_type,
            applicant_verified=applicant_verified,
            actual_agricultural_production=actual_agricultural_production,
            declared_relief_area_verified=declared_relief_area_verified,
            declared_relief_item_verified=declared_relief_item_verified,
            announcement_date=announcement_date,
            application_deadline=application_deadline,
            land_area_ha=land_area_ha,
            loss_rate_pct=loss_rate_pct,
            weather_param_or_severe_exception=weather_param_or_severe_exception,
            is_livestock_headcount=is_livestock_headcount,
            crop_name=crop_name,
            ground_evidence_verified=ground_evidence_verified,
            applicable_version_verified=applicable_version_verified,
        )

        confirmed: dict[str, Any] = {}
        for k, v in (
            ("disaster_type", disaster_type),
            ("relief_type", relief_type),
            ("crop_name", crop_name),
            ("land_area_ha", land_area_ha),
            ("loss_rate_pct", loss_rate_pct),
            ("announcement_date", announcement_date),
            ("applicant_verified", applicant_verified),
            ("actual_agricultural_production", actual_agricultural_production),
            ("ground_evidence_verified", ground_evidence_verified),
        ):
            if v is not None:
                confirmed[k] = v

        rule_items = rules.get("rule_evaluations", [])
        applied = [f"{item['rule_id']}: {item['state']}" for item in rule_items]
        citations = sorted({item["citation_id"] for item in rule_items if item.get("citation_id")})
        exceptions: list[str] = []
        if weather_param_or_severe_exception:
            exceptions.append("第12-1條第1項第3款但書（災損天氣參數或特殊嚴重災害）")
        if is_livestock_headcount:
            exceptions.append("第12-1條第1項第3款但書（畜牧頭/隻數計價）")

        overall = rules.get("overall_status", "INSUFFICIENT_FACTS_FOR_ELIGIBILITY_DETERMINATION")
        missing = list(rules.get("missing_information", []))

        # Hard disqualifiers -> CONDITION_NOT_MET
        if overall == "NOT_ELIGIBLE_BASED_ON_GIVEN_FACTS" or (
            loss_rate_pct is not None
            and loss_rate_pct < 20.0
            and not weather_param_or_severe_exception
            and not is_livestock_headcount
        ):
            return LegalDecisionResult(
                decision_status="CONDITION_NOT_MET",
                applied_rules=applied,
                confirmed_facts=confirmed,
                missing_facts=missing,
                exceptions=exceptions,
                legal_citations=citations,
                decision_limitations=self.DEFAULT_LIMITATIONS,
            )

        # Unverified official announcement -> ANNOUNCEMENT_NOT_VERIFIED (unless already disqualified)
        if announcement_verified is False or (announcement_verified is None and not announcement_date):
            if "已驗證官方救助公告" not in missing:
                missing.append("已驗證官方救助公告")
            return LegalDecisionResult(
                decision_status="ANNOUNCEMENT_NOT_VERIFIED",
                applied_rules=applied,
                confirmed_facts=confirmed,
                missing_facts=missing,
                exceptions=exceptions,
                legal_citations=citations,
                decision_limitations=self.DEFAULT_LIMITATIONS,
            )

        # If the only unresolved item is appendix crop table verification while crop_name was supplied,
        # preliminary eligibility is possible subject to official appendix & survey verification.
        non_crop_missing = [m for m in missing if m != "Verified appendix crop category"]
        preliminary_ready = (
            overall == "PRECHECK_CONDITIONS_SATISFIED_DECISION_SUPPORT_ONLY"
            or (bool(crop_name) and not non_crop_missing and applicable_version_verified)
        )

        # Never promote INSUFFICIENT_INFORMATION to ELIGIBILITY_POSSIBLE
        if not applicable_version_verified or not preliminary_ready:
            return LegalDecisionResult(
                decision_status="INSUFFICIENT_INFORMATION",
                applied_rules=applied,
                confirmed_facts=confirmed,
                missing_facts=missing or ["完整地面勘查與法定要件"],
                exceptions=exceptions,
                legal_citations=citations,
                decision_limitations=self.DEFAULT_LIMITATIONS,
            )

        return LegalDecisionResult(
            decision_status="ELIGIBILITY_POSSIBLE",
            applied_rules=applied,
            confirmed_facts=confirmed,
            missing_facts=[],
            exceptions=exceptions,
            legal_citations=citations,
            decision_limitations=self.DEFAULT_LIMITATIONS,
        )
