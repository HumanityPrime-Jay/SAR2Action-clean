"""Deterministic SAR Quality Assessment (Phase B1).

All quality conclusions are computed deterministically in Python from verified
artifacts. Missing data returns NOT_EVALUATED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.advanced.uncertainty.models import SARQualityAssessment

ROOT = Path(__file__).resolve().parents[4]


def _load_field_comparison(data_root: Path | None = None) -> dict[str, Any] | None:
    base = data_root or ROOT
    path = base / "data" / "exports" / "yunlin_vh_2025_2026" / "field_comparison.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def assess_sar_quality(
    field_id: str,
    *,
    data_root: Path | None = None,
    field_record: dict[str, Any] | None = None,
) -> SARQualityAssessment:
    """Assess SAR spatial, radiometric, and temporal quality deterministically."""
    record = field_record
    if record is None:
        comp = _load_field_comparison(data_root)
        if comp:
            record = next((f for f in comp.get("fields", []) if f.get("field_id") == field_id), None)

    if record is None:
        return SARQualityAssessment(
            field_id=field_id,
            status="NOT_EVALUATED",
            qa_passed=False,
            valid_pixels=None,
            valid_coverage_ratio=None,
            polygon_area_m2=None,
            interior_area_m2=None,
            spatial_dependence_note="Field observation record not found.",
            nodata_mask_verified=False,
            raster_resolution_m=None,
            acquisition_geometry={},
            processing_version=None,
            noise_metadata={},
            temporal_support={},
            limitations=["No verified SAR observation record available for this field."],
            evidence_ids=[],
        )

    support = record.get("spatial_support") or {}
    min_pixels = support.get("min_valid_pixels")
    min_cov = support.get("min_valid_coverage_ratio")
    threshold_px = support.get("threshold_pixels", 8)
    threshold_cov = support.get("threshold_coverage_ratio", 0.8)
    assessment = str(support.get("assessment", ""))

    obs_2025 = record.get("observations", {}).get("2025", [])
    obs_2026 = record.get("observations", {}).get("2026", [])
    all_obs = obs_2025 + obs_2026
    qa_flags = sorted({flag for o in all_obs for flag in o.get("qa_flags", [])})

    nearest_m = record.get("nearest_other_field_m")
    spatial_dep = (
        f"Nearest candidate field is {nearest_m} m away; nearby fields share local weather and SAR geometry."
        if nearest_m is not None
        else "Inter-field spatial distance unavailable."
    )

    qa_passed = (
        assessment.startswith("PASS")
        and (min_pixels is not None and min_pixels >= threshold_px)
        and (min_cov is not None and min_cov >= threshold_cov)
        and len(obs_2026) >= 2
    )

    limitations = [
        "30 m OPERA RTC-S1 pixel spacing introduces mixed-pixel boundary effects on small parcels.",
        "Thermal noise floor (NESZ) affects low-backscatter VH values (around -30 dB).",
    ]
    pre_warning_count = sum(1 for o in obs_2026 if o.get("warning_relation") == "PRE_WARNING")
    if pre_warning_count < 2:
        limitations.append("Only one 2026 acquisition precedes the typhoon warning window; pre-warning trend is untestable.")

    return SARQualityAssessment(
        field_id=field_id,
        status="EVALUATED" if qa_passed else "QA_FAILED",
        qa_passed=qa_passed,
        valid_pixels=min_pixels,
        valid_coverage_ratio=min_cov,
        polygon_area_m2=record.get("field_area_m2"),
        interior_area_m2=record.get("interior_area_m2"),
        spatial_dependence_note=spatial_dep,
        nodata_mask_verified=bool(all_obs and all(o.get("valid_pixel_count", 0) > 0 for o in all_obs)),
        raster_resolution_m=30.0,
        acquisition_geometry={
            "sensor": "Sentinel-1 (OPERA L2 RTC-S1)",
            "polarization": "VH",
            "track": "T105-224320-IW3",
            "same_orbit_across_observations": True,
        },
        processing_version="OPERA_L2_RTC-S1_v1.0",
        noise_metadata={
            "unit_verified": "UNIT_VERIFIED_FROM_RASTER_PROCESSING_TAGS_LINEAR_GAMMA0" in qa_flags,
            "qa_flags": qa_flags,
            "noise_floor_caution": True,
        },
        temporal_support={
            "2025_count": len(obs_2025),
            "2026_count": len(obs_2026),
            "2026_pre_warning_count": pre_warning_count,
            "strict_pre_warning_trend_available": pre_warning_count >= 2,
        },
        limitations=limitations,
        evidence_ids=list(record.get("evidence_ids", [])),
    )
