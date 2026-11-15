"""Financial Loss Calculator aligned with《農業天然災害救助辦法》Article 9 (Phase 5)."""
from __future__ import annotations

from typing import Any


class AgriculturalLossCalculator:
    """Separately compute Production Loss, Revenue Loss, and Article 9 Statutory Loss Estimate."""

    def estimate_agricultural_loss(
        self,
        *,
        crop_category: str | None = None,  # "short_term_replantable" | "short_term_non_replantable" | "long_term_no_harvest" | "long_term_with_harvest"
        area_ha: float | None = None,
        total_production_cost_ntd_per_ha: float | None = None,
        harvest_labor_cost_ntd_per_ha: float | None = None,
        establishment_cost_ntd_per_ha: float | None = None,
        expected_revenue_loss_ntd: float | None = None,
        potential_relief_amount_ntd: float | None = None,
    ) -> dict[str, Any]:
        missing: list[str] = []
        if area_ha is None or area_ha <= 0:
            missing.append("Affected area (ha)")
        if not crop_category:
            missing.append("Crop category under Article 9 (short-term replantable / non-replantable / long-term)")

        statutory_loss_ntd: float | None = None
        production_loss_ntd: float | None = None
        formula_used: str | None = None

        if not missing:
            if crop_category == "short_term_replantable":
                if total_production_cost_ntd_per_ha is None:
                    missing.append("Total production cost per ha (NTD/ha)")
                else:
                    statutory_loss_ntd = round(area_ha * total_production_cost_ntd_per_ha * 0.5, 0)
                    production_loss_ntd = round(area_ha * total_production_cost_ntd_per_ha, 0)
                    formula_used = "Article 9(1)(1): area_ha * total_production_cost_per_ha * 50%"
            elif crop_category in ("short_term_non_replantable", "long_term_with_harvest"):
                if total_production_cost_ntd_per_ha is None or harvest_labor_cost_ntd_per_ha is None:
                    missing.append("Total production cost and harvest labor cost per ha (NTD/ha)")
                else:
                    net_cost = max(0.0, total_production_cost_ntd_per_ha - harvest_labor_cost_ntd_per_ha)
                    statutory_loss_ntd = round(area_ha * net_cost, 0)
                    production_loss_ntd = round(area_ha * total_production_cost_ntd_per_ha, 0)
                    formula_used = "Article 9(1)(1): area_ha * (total_production_cost_per_ha - harvest_labor_cost_per_ha)"
            elif crop_category == "long_term_no_harvest":
                if establishment_cost_ntd_per_ha is None:
                    missing.append("Orchard/perennial establishment cost (成園費 NTD/ha)")
                else:
                    statutory_loss_ntd = round(area_ha * establishment_cost_ntd_per_ha, 0)
                    production_loss_ntd = statutory_loss_ntd
                    formula_used = "Article 9(1)(1): area_ha * establishment_cost_per_ha"
            else:
                missing.append(f"Unsupported Article 9 crop_category: {crop_category}")

        return {
            "status": "MISSING_DATA" if missing else "CALCULATED",
            "estimated_production_loss_ntd": production_loss_ntd,
            "estimated_revenue_loss_ntd": expected_revenue_loss_ntd,
            "legally_defined_agricultural_loss_ntd": statutory_loss_ntd,
            "potential_government_relief_amount_ntd": potential_relief_amount_ntd,
            "formula": formula_used,
            "citation_id": "M0090019-ARTICLE-9",
            "missing_data": missing,
            "note": "Market revenue loss is kept strictly separate from Article 9 statutory agricultural loss.",
        }
