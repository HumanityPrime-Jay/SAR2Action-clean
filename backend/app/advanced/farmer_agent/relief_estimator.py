"""Relief Amount Estimator (Phase 6) — strict pre-check & POTENTIAL_RELIEF_ESTIMATE only."""
from __future__ import annotations

from typing import Any

from backend.app.advanced.legal_rag.appendix_parser import AppendixLookupService


class ReliefAmountEstimator:
    """Estimate potential relief ONLY when verified crop, announcement, rate, area, and unit exist."""

    def __init__(self, appendix_lookup: AppendixLookupService | None = None):
        self.appendix_lookup = appendix_lookup or AppendixLookupService()

    def lookup_verified_appendix_rate(self, crop: str, relief_type: str = "CASH_RELIEF") -> dict[str, Any]:
        """Return appendix rate ONLY if verification_status == VERIFIED_FROM_OFFICIAL_PDF."""
        return self.appendix_lookup.lookup_rate(crop, relief_type=relief_type)

    def calculate_potential_relief(
        self,
        *,
        crop: str | None = None,
        verified_announcement: dict[str, Any] | None = None,
        verified_appendix_rate_ntd_per_unit: float | None = None,
        statutory_unit: str | None = None,
        eligible_area_ha: float | None = None,
        area_source_label: str = "UNVERIFIED",  # "FARMER_REPORTED" | "GOVERNMENT_VERIFIED"
        loss_rate_pct: float | None = None,
        exception_applies: bool = False,
    ) -> dict[str, Any]:
        missing: list[str] = []
        if not crop:
            missing.append("Verified crop item")
        if not verified_announcement or verified_announcement.get("status") != "VERIFIED_ANNOUNCEMENT_FOUND":
            missing.append("Verified official relief announcement for county/township/crop")
        if verified_appendix_rate_ntd_per_unit is None or not statutory_unit:
            missing.append("Verified official appendix relief rate and statutory unit (currently EXTRACTION_REQUIRES_REVIEW)")
        if eligible_area_ha is None or eligible_area_ha <= 0:
            missing.append("Eligible application area")
        if loss_rate_pct is None and not exception_applies:
            missing.append("Ground-verified loss rate (>=20% unless Article 12-1 exception applies)")
        elif loss_rate_pct is not None and loss_rate_pct < 20.0 and not exception_applies:
            return {
                "status": "NOT_ELIGIBLE_BELOW_20_PERCENT",
                "POTENTIAL_RELIEF_ESTIMATE_NTD": 0,
                "is_approved_amount": False,
                "citation_id": "M0090019-ARTICLE-12-1",
                "reason": "Loss rate is under 20% and no Article 12-1(1)(3) exception applies.",
            }

        if missing:
            return {
                "status": "CANNOT_ESTIMATE_MISSING_REQUIREMENTS",
                "POTENTIAL_RELIEF_ESTIMATE_NTD": None,
                "is_approved_amount": False,
                "missing_requirements": missing,
                "note": "不得將未核定的疑似面積或未驗證附表額度直接相乘作為可領金額。",
            }

        amount = round(eligible_area_ha * verified_appendix_rate_ntd_per_unit, 0)
        return {
            "status": "POTENTIAL_RELIEF_ESTIMATE",
            "POTENTIAL_RELIEF_ESTIMATE_NTD": amount,
            "is_approved_amount": False,
            "area_source_label": area_source_label,
            "formula": f"{eligible_area_ha} ({statutory_unit}) * {verified_appendix_rate_ntd_per_unit} NTD/{statutory_unit}",
            "limitations": [
                "此為依輸入條件試算之 POTENTIAL_RELIEF_ESTIMATE，並非政府核定撥款金額 (APPROVED_AMOUNT)。",
                "最終核定面積與金額以鄉（鎮、市、區）公所及主管機關勘查核定為準。",
            ],
        }
