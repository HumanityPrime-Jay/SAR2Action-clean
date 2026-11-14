"""Deterministic Legal Rule Engine for《農業天然災害救助辦法》(Phase F).

Uses four-valued logic: TRUE, FALSE, UNKNOWN, NOT_APPLICABLE.
Never defaults UNKNOWN to TRUE, never computes deadline without an official
announcement date, and never converts SAR VH dB to loss rate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RuleState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class RuleEvaluationItem:
    rule_id: str
    rule_name: str
    state: RuleState
    citation_id: str
    reason: str
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


def evaluate_legal_rules(
    *,
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
) -> dict[str, Any]:
    """Evaluate all 12 deterministic legal rule dimensions under M0090019."""
    items: list[RuleEvaluationItem] = []

    # 1. Disaster Type (Article 2, 3)
    if disaster_type in ("颱風", "豪雨", "寒流", "typhoon", "heavy_rain", "cold_surge"):
        s_dis = RuleState.TRUE
        r_dis = f"Disaster type '{disaster_type}' falls within natural disasters under Article 2/3."
        m_dis: list[str] = []
    elif disaster_type:
        s_dis = RuleState.UNKNOWN
        r_dis = f"Disaster type '{disaster_type}' requires official central authority recognition under Article 2/3."
        m_dis = ["Central authority natural disaster recognition"]
    else:
        s_dis = RuleState.UNKNOWN
        r_dis = "Disaster type not specified."
        m_dis = ["Disaster type"]
    items.append(RuleEvaluationItem("1_disaster_type", "Disaster Type", s_dis, "M0090019-ARTICLE-2", r_dis, m_dis))

    # 2. Relief Type (Article 4)
    if relief_type in ("現金救助", "低利貸款", "cash_relief", "low_interest_loan"):
        s_rel, r_rel, m_rel = RuleState.TRUE, f"Relief type '{relief_type}' is defined under Article 4.", []
    elif relief_type:
        s_rel, r_rel, m_rel = RuleState.FALSE, f"Relief type '{relief_type}' is not a statutory relief type under Article 4.", []
    else:
        s_rel, r_rel, m_rel = RuleState.UNKNOWN, "Relief type (cash relief vs low-interest loan) not specified.", ["Relief type"]
    items.append(RuleEvaluationItem("2_relief_type", "Relief Type", s_rel, "M0090019-ARTICLE-4", r_rel, m_rel))

    # 3. Applicant Category (Article 5, 12-1)
    if applicant_verified is True and actual_agricultural_production is True:
        s_app, r_app, m_app = RuleState.TRUE, "Applicant identity and actual agricultural production verified.", []
    elif applicant_verified is False or actual_agricultural_production is False:
        s_app, r_app, m_app = RuleState.FALSE, "Applicant lacks verified farmer eligibility or actual agricultural production (Article 5 / 12-1).", []
    else:
        s_app = RuleState.UNKNOWN
        r_app = "Applicant farmer identity and actual agricultural production proof are missing (farmland polygons alone do not establish farmer identity)."
        m_app = ["Applicant farmer identity", "Actual agricultural production proof"]
    items.append(RuleEvaluationItem("3_applicant_category", "Applicant Category", s_app, "M0090019-ARTICLE-5", r_app, m_app))

    # 4. Declared Relief Area (Article 6, 12)
    if declared_relief_area_verified is True:
        s_area_d, r_area_d, m_area_d = RuleState.TRUE, "Official relief area announcement verified for the parcel's township/county.", []
    elif declared_relief_area_verified is False:
        s_area_d, r_area_d, m_area_d = RuleState.FALSE, "Region is not in an officially announced relief area.", []
    else:
        s_area_d, r_area_d, m_area_d = RuleState.UNKNOWN, "Official relief area announcement not verified.", ["Official relief area announcement"]
    items.append(RuleEvaluationItem("4_declared_relief_area", "Declared Relief Area", s_area_d, "M0090019-ARTICLE-6", r_area_d, m_area_d))

    # 5. Declared Relief Item (Article 6, 12)
    if declared_relief_item_verified is True:
        s_item_d, r_item_d, m_item_d = RuleState.TRUE, "Official relief crop/item announcement verified.", []
    elif declared_relief_item_verified is False:
        s_item_d, r_item_d, m_item_d = RuleState.FALSE, "Crop/product is not in the officially announced relief items.", []
    else:
        s_item_d, r_item_d, m_item_d = RuleState.UNKNOWN, "Official relief item announcement not verified.", ["Official relief item announcement"]
    items.append(RuleEvaluationItem("5_declared_relief_item", "Declared Relief Item", s_item_d, "M0090019-ARTICLE-6", r_item_d, m_item_d))

    # 6. Application Deadline (Article 12-P1-I1: 10 working days from day after announcement, unless extended)
    if announcement_date and application_deadline:
        s_dl, r_dl, m_dl = RuleState.TRUE, f"Official announcement ({announcement_date}) and deadline ({application_deadline}) verified.", []
        deadline_status = "DEADLINE_VERIFIED"
    else:
        s_dl = RuleState.UNKNOWN
        r_dl = (
            "DEADLINE_UNKNOWN: Article 12 sets the deadline as 10 working days from the day after the official "
            "announcement (subject to extensions); cannot compute from typhoon date alone."
        )
        m_dl = ["Official announcement date", "Official working-day calendar / extension notice"]
        deadline_status = "DEADLINE_UNKNOWN"
    items.append(RuleEvaluationItem("6_application_deadline", "Application Deadline", s_dl, "M0090019-ARTICLE-12", r_dl, m_dl))

    # 7. Land Area Conditions (Article 6 / parcel area)
    if land_area_ha is not None and land_area_ha > 0:
        s_land, r_land, m_land = RuleState.TRUE, f"Land area {land_area_ha:.4f} ha recorded; statutory calculation unit still depends on crop/appendix.", []
    else:
        s_land, r_land, m_land = RuleState.UNKNOWN, "Verified parcel land area is missing.", ["Verified parcel area"]
    items.append(RuleEvaluationItem("7_land_area_conditions", "Land Area Conditions", s_land, "M0090019-ARTICLE-6", r_land, m_land))

    # 8. Loss Rate Conditions (Article 12-1-P1-I3: < 20% NOT eligible UNLESS exceptions apply)
    if loss_rate_pct is None:
        s_loss = RuleState.UNKNOWN
        r_loss = "LOSS_RATE_UNKNOWN: Field survey loss rate is missing; SAR VH dB change cannot be converted to loss percentage."
        m_loss = ["Ground-verified crop loss rate (%)"]
        loss_status = "LOSS_RATE_UNKNOWN"
    elif loss_rate_pct >= 20.0:
        s_loss, r_loss, m_loss = RuleState.TRUE, f"Reported/verified loss rate {loss_rate_pct:.1f}% meets >= 20% threshold.", []
        loss_status = "MEETS_20_PERCENT_THRESHOLD"
    else:
        if weather_param_or_severe_exception is True or is_livestock_headcount:
            s_loss = RuleState.TRUE
            r_loss = (
                f"Loss rate {loss_rate_pct:.1f}% is under 20%, but statutory exception under Article 12-1(1)(3) applies "
                "(Article 12(1)(3) / 12-2(3) weather-parameter or severe-disaster procedure, or headcount livestock)."
            )
            m_loss = []
            loss_status = "UNDER_20_PERCENT_EXCEPTION_APPLIES"
        elif weather_param_or_severe_exception is False and not is_livestock_headcount:
            s_loss = RuleState.FALSE
            r_loss = f"Loss rate {loss_rate_pct:.1f}% is under 20% and no Article 12-1(1)(3) exception applies."
            m_loss = []
            loss_status = "BELOW_20_PERCENT_NO_EXCEPTION"
        else:
            s_loss = RuleState.UNKNOWN
            r_loss = (
                f"Loss rate {loss_rate_pct:.1f}% is under 20%; eligibility depends on whether Article 12(1)(3) "
                "(weather parameters / severe disaster announcement) or livestock headcount exception applies."
            )
            m_loss = ["Whether Article 12(1)(3) weather-parameter/severe-disaster announcement applies"]
            loss_status = "UNDER_20_PERCENT_EXCEPTION_UNKNOWN"
    items.append(RuleEvaluationItem("8_loss_rate_conditions", "Loss Rate Conditions", s_loss, "M0090019-ARTICLE-12-1", r_loss, m_loss))

    # 9. Exceptions (Article 12(1)(3), 12-1(1)(3), 12-2)
    if weather_param_or_severe_exception is True:
        s_exc, r_exc, m_exc = RuleState.TRUE, "Article 12(1)(3) / 12-1(1)(3) exception applies.", []
    elif weather_param_or_severe_exception is False:
        s_exc, r_exc, m_exc = RuleState.NOT_APPLICABLE, "No statutory weather-parameter or severe-disaster exception triggered.", []
    else:
        s_exc, r_exc, m_exc = RuleState.UNKNOWN, "Applicability of Article 12(1)(3) / 12-1(1)(3) exceptions not yet verified.", ["Applicable exception status"]
    items.append(RuleEvaluationItem("9_exceptions", "Exceptions", s_exc, "M0090019-ARTICLE-12-1", r_exc, m_exc))

    # 10. Crop / Product Eligibility (Article 6 & Appendices)
    if crop_name:
        s_crop, r_crop, m_crop = RuleState.UNKNOWN, f"Crop '{crop_name}' stated; appendix table verification (EXTRACTION_REQUIRES_REVIEW) required for statutory category.", ["Verified appendix crop category"]
    else:
        s_crop, r_crop, m_crop = RuleState.UNKNOWN, "Crop / agricultural product type not identified.", ["Crop / product identity"]
    items.append(RuleEvaluationItem("10_crop_eligibility", "Crop / Product Eligibility", s_crop, "M0090019-ARTICLE-6", r_crop, m_crop))

    # 11. Required Evidence (Article 12: application form, planting/aquaculture proof or field inspection)
    if ground_evidence_verified is True:
        s_ev, r_ev, m_ev = RuleState.TRUE, "Required field/planting evidence verified.", []
    elif ground_evidence_verified is False:
        s_ev, r_ev, m_ev = RuleState.FALSE, "Required field/planting evidence missing or failed verification.", ["Valid planting/damage evidence"]
    else:
        s_ev, r_ev, m_ev = RuleState.UNKNOWN, "Required parcel planting/damage evidence not yet verified.", ["Planting/cultivation proof or field inspection"]
    items.append(RuleEvaluationItem("11_required_evidence", "Required Evidence", s_ev, "M0090019-ARTICLE-12", r_ev, m_ev))

    # 12. Applicable Version
    if applicable_version_verified:
        s_ver, r_ver, m_ver = RuleState.TRUE, "Applicable M0090019 revision verified for query/event date.", []
    else:
        s_ver, r_ver, m_ver = RuleState.UNKNOWN, "VERSION_NOT_VERIFIED for requested historical event date.", ["Verified historical law revision"]
    items.append(RuleEvaluationItem("12_applicable_version", "Applicable Version", s_ver, "M0090019-ARTICLE-1", r_ver, m_ver))

    all_missing = list(dict.fromkeys(m for it in items for m in it.missing_fields))
    has_false = any(it.state == RuleState.FALSE for it in items)
    all_true = all(it.state in (RuleState.TRUE, RuleState.NOT_APPLICABLE) for it in items)

    if has_false:
        overall = "NOT_ELIGIBLE_BASED_ON_GIVEN_FACTS"
    elif all_true:
        overall = "PRECHECK_CONDITIONS_SATISFIED_DECISION_SUPPORT_ONLY"
    else:
        overall = "INSUFFICIENT_FACTS_FOR_ELIGIBILITY_DETERMINATION"

    return {
        "overall_status": overall,
        "deadline_status": deadline_status,
        "loss_status": loss_status,
        "rule_evaluations": [it.to_dict() for it in items],
        "missing_information": all_missing,
    }
