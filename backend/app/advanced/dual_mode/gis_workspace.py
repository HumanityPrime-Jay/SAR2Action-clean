"""Authority Professional GIS Workspace & Controlled Map Actions (Sections 4-6, 11-12)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from backend.app.advanced.farmer_agent.field_area import (
    FarmerFieldService,
    SQ_M_PER_HA,
    geodesic_ring_area_m2,
    validate_ring,
)
from backend.app.advanced.spatial_controls import match_spatial_reference_fields
from backend.app.advanced.uncertainty import analyze_robust_vh_change, assess_sar_quality

ROOT = Path(__file__).resolve().parents[4]

ALLOWED_MAP_ACTIONS = {
    "SHOW_LAYER",
    "HIDE_LAYER",
    "ZOOM_TO_AOI",
    "SELECT_FIELD",
    "COMPARE_OBSERVATIONS",
    "OPEN_TIMELINE",
    "DISPLAY_STATISTICS",
}


class AuthorityGISService:
    """Professional GIS analysis, cross-CRID compare guard, and structured map actions."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = data_root or ROOT
        self.field_service = FarmerFieldService(self.data_root)

    def analyze_gis(
        self,
        *,
        field_ids: list[str] | None = None,
        polygon_geojson: dict[str, Any] | None = None,
        buffer_m: float | None = None,
        aoi_id: str = "10009160",
    ) -> dict[str, Any]:
        target_fields = field_ids or ["YL-CAND-03"]
        polygon_result = None
        if polygon_geojson is not None:
            area_res = self.field_service.calculate_field_area(geojson_geometry=polygon_geojson)
            if not area_res.is_valid:
                return {"status": "INVALID_POLYGON", "error": area_res.warnings, "area_ha": None}
            polygon_result = area_res.to_dict()
            if buffer_m is not None and buffer_m > 0 and area_res.area_m2 is not None:
                # Approximate geodesic buffer area expansion using circular isoperimetric bound
                r_eq = math.sqrt(area_res.area_m2 / math.pi)
                buf_area_m2 = round(math.pi * ((r_eq + buffer_m) ** 2), 2)
                polygon_result["buffer_m"] = buffer_m
                polygon_result["buffered_area_m2_approx"] = buf_area_m2

        field_stats: list[dict[str, Any]] = []
        for fid in target_fields:
            qa = assess_sar_quality(fid, data_root=self.data_root)
            vh = analyze_robust_vh_change(fid, data_root=self.data_root)
            field_stats.append({
                "field_id": fid,
                "sar_quality": qa.to_dict(),
                "vh_analysis": vh.to_dict(),
                "scale_note": "dB medians are computed on linear gamma0 before 10*log10 conversion; never averaged directly in dB without noting.",
            })

        cross_field = match_spatial_reference_fields(target_fields[0], aoi_id=aoi_id, data_root=self.data_root)
        return {
            "status": "ANALYZED",
            "aoi_id": aoi_id,
            "polygon_analysis": polygon_result,
            "field_statistics": field_stats,
            "cross_field_analysis": cross_field.to_dict(),
            "dashboard_summary": {
                "aoi_summary": {"aoi_id": aoi_id, "field_count": len(field_stats)},
                "scientific_limitations": cross_field.scientific_limitations,
            },
        }

    def compare_observations(
        self,
        *,
        sensor: str = "OPERA_S1",
        field_id: str = "YL-CAND-03",
        mode: str = "SIDE_BY_SIDE",
        compute_difference: bool = False,
    ) -> dict[str, Any]:
        upper_sensor = sensor.upper()
        if upper_sensor == "NISAR":
            qa_path = self.data_root / "data" / "exports" / "typhoon_champi" / "science_qa.json"
            qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
            comp = qa.get("comparability", {})
            crid_match = bool(comp.get("crid_match"))
            if compute_difference and not crid_match:
                return {
                    "status": "BLOCKED_CROSS_CRID_INCOMPATIBLE",
                    "sensor": "NISAR",
                    "compare_mode": mode,
                    "difference_allowed": False,
                    "reason": (
                        "NISAR 2026-10-16 (P05023 provisional) and 2026-10-28 (P05036 validated) "
                        "have not passed cross-CRID radiometric equivalence QA; unverified difference or damage area is blocked."
                    ),
                    "observations": qa.get("observations", {}),
                }
            return {
                "status": "SEPARATE_OBSERVATIONS_ONLY",
                "sensor": "NISAR",
                "compare_mode": mode,
                "difference_allowed": crid_match,
                "observations": qa.get("observations", {}),
            }

        vh = analyze_robust_vh_change(field_id, data_root=self.data_root)
        return {
            "status": vh.status,
            "sensor": "OPERA_S1",
            "field_id": field_id,
            "compare_mode": mode,
            "difference_allowed": vh.compatible_observations,
            "vh_change": vh.to_dict(),
        }

    def build_map_action(self, action_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        upper = action_type.upper()
        if upper not in ALLOWED_MAP_ACTIONS:
            raise ValueError(f"Unsupported map action '{action_type}'. Allowed: {sorted(ALLOWED_MAP_ACTIONS)}")
        return {
            "action_type": upper,
            "payload": dict(payload or {}),
            "execution_mode": "CONTROLLED_FRONTEND_DISPATCH",
        }
