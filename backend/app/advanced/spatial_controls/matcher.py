"""Spatial Reference Field Matching (Phase B3).

Matches comparable candidate fields by AOI, geometry/area, baseline VH,
acquisition date, orbit, polarization, and product version, while explicitly
reporting sample-size limitations and prohibiting causal inference claims.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]


@dataclass
class SpatialMatchingResult:
    target_field_id: str
    aoi_id: str
    status: str  # "MATCHED" | "NOT_EVALUATED"
    matched_fields: list[dict[str, Any]]
    excluded_fields: list[dict[str, Any]]
    matching_criteria: dict[str, Any]
    scientific_limitations: list[str] = field(default_factory=list)
    causal_inference_completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def match_spatial_reference_fields(
    target_field_id: str,
    *,
    aoi_id: str = "10009160",
    max_area_ratio: float = 3.0,
    max_baseline_diff_db: float = 6.0,
    data_root: Path | None = None,
) -> SpatialMatchingResult:
    """Find comparable spatial reference fields from verified farmland candidates."""
    base = data_root or ROOT
    comp_path = base / "data" / "exports" / "yunlin_vh_2025_2026" / "field_comparison.json"
    criteria = {
        "aoi_id": aoi_id,
        "polarization": "VH",
        "orbit_track": "T105-224320-IW3",
        "product_version": "OPERA_L2_RTC-S1_v1.0",
        "max_area_ratio": max_area_ratio,
        "max_baseline_diff_db": max_baseline_diff_db,
        "require_matched_acquisition_dates": True,
    }
    if not comp_path.is_file():
        return SpatialMatchingResult(
            target_field_id=target_field_id,
            aoi_id=aoi_id,
            status="NOT_EVALUATED",
            matched_fields=[],
            excluded_fields=[],
            matching_criteria=criteria,
            scientific_limitations=["field_comparison.json not available."],
            causal_inference_completed=False,
        )

    comp = json.loads(comp_path.read_text(encoding="utf-8"))
    fields = comp.get("fields", [])
    target = next((f for f in fields if f.get("field_id") == target_field_id), None)
    if target is None:
        return SpatialMatchingResult(
            target_field_id=target_field_id,
            aoi_id=aoi_id,
            status="NOT_EVALUATED",
            matched_fields=[],
            excluded_fields=[],
            matching_criteria=criteria,
            scientific_limitations=[f"Target field {target_field_id} not found in verified candidates."],
            causal_inference_completed=False,
        )

    target_area = float(target.get("field_area_m2") or 0.0)
    target_obs_2026 = target.get("observations", {}).get("2026", [])
    target_baseline = target_obs_2026[0]["vh_median_db"] if target_obs_2026 else None
    target_dates = {o.get("acquisition_utc") for o in target_obs_2026}

    matched: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for cand in fields:
        cid = cand.get("field_id")
        if cid == target_field_id:
            continue
        cand_area = float(cand.get("field_area_m2") or 0.0)
        cand_obs_2026 = cand.get("observations", {}).get("2026", [])
        cand_baseline = cand_obs_2026[0]["vh_median_db"] if cand_obs_2026 else None
        cand_dates = {o.get("acquisition_utc") for o in cand_obs_2026}

        reasons: list[str] = []
        if target_area > 0 and cand_area > 0:
            ratio = max(target_area / cand_area, cand_area / target_area)
            if ratio > max_area_ratio:
                reasons.append(f"Area ratio {ratio:.2f} exceeds max_area_ratio={max_area_ratio}")
        if target_baseline is not None and cand_baseline is not None:
            diff = abs(target_baseline - cand_baseline)
            if diff > max_baseline_diff_db:
                reasons.append(f"Baseline VH diff {diff:.2f} dB exceeds {max_baseline_diff_db} dB")
        if target_dates != cand_dates:
            reasons.append("Acquisition dates do not match target field")
        if not (cand.get("spatial_support") or {}).get("assessment", "").startswith("PASS"):
            reasons.append("Spatial support QA did not pass")

        entry = {
            "field_id": cid,
            "field_area_m2": cand_area,
            "baseline_2026_vh_db": cand_baseline,
            "pre_to_warning_db": (cand.get("2026_pre_to_warning_window") or {}).get("median_difference_db"),
            "distance_to_target_m": (target.get("distance_to_other_fields_m") or {}).get(cid),
            "crop_label": cand.get("crop_label"),
        }
        if reasons:
            excluded.append({**entry, "exclusion_reasons": reasons})
        else:
            matched.append(entry)

    limitations = [
        f"Only {len(fields)} candidate farmland polygons exist in the Taixi dataset; small sample size limits statistical power.",
        "Candidate fields lack verified crop-type and management labels.",
        "Spatial reference matching is exploratory and does NOT constitute formal causal inference.",
    ]

    return SpatialMatchingResult(
        target_field_id=target_field_id,
        aoi_id=aoi_id,
        status="MATCHED",
        matched_fields=matched,
        excluded_fields=excluded,
        matching_criteria=criteria,
        scientific_limitations=limitations,
        causal_inference_completed=False,
    )
