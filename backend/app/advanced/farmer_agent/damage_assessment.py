"""Agricultural Damage Assessment Service (Phase 4).

Strictly separates:
- FIELD_AREA
- FARMER_REPORTED_AFFECTED_AREA
- SATELLITE_CHANGE_CANDIDATE_AREA
- GROUND_VERIFIED_DAMAGED_AREA
- ESTIMATED_YIELD_LOSS
- ESTIMATED_FINANCIAL_LOSS
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.advanced.uncertainty import analyze_robust_vh_change, assess_sar_quality

ROOT = Path(__file__).resolve().parents[4]


class AgriculturalDamageAssessmentService:
    """Assess satellite change candidates, farmer reports, and yield loss with strict uncertainty."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = data_root or ROOT

    def assess_damage_evidence(
        self,
        *,
        field_id: str | None = None,
        field_area_ha: float | None = None,
        farmer_reported_affected_area_ha: float | None = None,
        ground_verified_damaged_area_ha: float | None = None,
    ) -> dict[str, Any]:
        sar_qa = assess_sar_quality(field_id, data_root=self.data_root) if field_id else None
        vh = analyze_robust_vh_change(field_id, data_root=self.data_root) if field_id else None

        # Current OPERA dataset provides field-level summary statistics only, not validated pixel damage masks
        satellite_status = "SATELLITE_DAMAGE_AREA_NOT_ESTIMABLE"
        satellite_candidate_area_ha = None
        change_candidate_signal = None
        if vh and vh.status == "OBSERVED":
            change_candidate_signal = {
                "kind": "CHANGE_CANDIDATE",
                "median_change_db": vh.median_change_db,
                "unit": "dB",
                "evidence_ids": vh.evidence_ids,
            }

        return {
            "FIELD_AREA": {"value_ha": field_area_ha, "status": "MEASURED" if field_area_ha else "UNKNOWN"},
            "FARMER_REPORTED_AFFECTED_AREA": {
                "value_ha": farmer_reported_affected_area_ha,
                "label": "FARMER_REPORTED",
                "status": "FARMER_REPORTED" if farmer_reported_affected_area_ha is not None else "NOT_PROVIDED",
            },
            "SATELLITE_CHANGE_CANDIDATE_AREA": {
                "value_ha": satellite_candidate_area_ha,
                "status": satellite_status,
                "change_candidate_signal": change_candidate_signal,
                "reason": (
                    "Only field-scale summary statistics are available; without validated pixel-level "
                    "damage classification and crop labels, satellite damaged area cannot be estimated."
                ),
            },
            "GROUND_VERIFIED_DAMAGED_AREA": {
                "value_ha": ground_verified_damaged_area_ha,
                "label": "GOVERNMENT_VERIFIED" if ground_verified_damaged_area_ha is not None else "NOT_VERIFIED",
                "status": "VERIFIED" if ground_verified_damaged_area_ha is not None else "MISSING_GROUND_TRUTH",
            },
            "sar_quality": sar_qa.to_dict() if sar_qa else None,
            "limitations": [
                "Cannot convert SAR VH dB change into damaged area or crop damage rate.",
                "Farmer-reported area is NOT equivalent to government-verified damaged area.",
            ],
        }

    def estimate_crop_yield_loss(
        self,
        *,
        crop: str | None = None,
        affected_area_ha: float | None = None,
        historical_yield_kg_per_ha: float | None = None,
        verified_loss_ratio: float | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Estimate yield loss ONLY when verified crop, yield, area, and loss ratio exist."""
        missing: list[str] = []
        if not crop:
            missing.append("Verified crop type")
        if affected_area_ha is None or affected_area_ha <= 0:
            missing.append("Affected/damaged area (ha)")
        if historical_yield_kg_per_ha is None or historical_yield_kg_per_ha <= 0:
            missing.append("Historical baseline yield (kg/ha)")
        if verified_loss_ratio is None or not (0.0 <= verified_loss_ratio <= 1.0):
            missing.append("Verifiable crop loss ratio (0.0 - 1.0)")

        if missing:
            return {
                "status": "YIELD_LOSS_UNKNOWN",
                "ESTIMATED_YIELD_LOSS_KG": None,
                "missing_data": missing,
                "reason": "Cannot estimate crop yield loss without verified crop, yield baseline, and loss ratio; SAR VH dB cannot be converted to kg.",
            }

        loss_kg = round(affected_area_ha * historical_yield_kg_per_ha * verified_loss_ratio, 2)
        return {
            "status": "ESTIMATED",
            "ESTIMATED_YIELD_LOSS_KG": loss_kg,
            "formula": "affected_area_ha * historical_yield_kg_per_ha * verified_loss_ratio",
            "inputs": {
                "crop": crop,
                "affected_area_ha": affected_area_ha,
                "historical_yield_kg_per_ha": historical_yield_kg_per_ha,
                "verified_loss_ratio": verified_loss_ratio,
            },
            "unit": "kg",
            "source": source or "User/official provided baseline",
            "assumptions": ["Assumes uniform loss ratio across the specified affected area."],
            "confidence_limitations": ["Subject to field inspection and actual harvest verification."],
        }
