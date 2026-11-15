"""Deterministic Robust VH Change Analysis (Phase B2).

Never fabricates imagery and never converts dB change into crop damage percentage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.advanced.uncertainty.models import RobustVHChangeResult
from backend.app.advanced.uncertainty.sar_quality import _load_field_comparison


def analyze_robust_vh_change(
    field_id: str,
    *,
    data_root: Path | None = None,
    field_record: dict[str, Any] | None = None,
) -> RobustVHChangeResult:
    """Compute robust VH change metrics (median, IQR, percentiles) from verified observations."""
    record = field_record
    if record is None:
        comp = _load_field_comparison(data_root)
        if comp:
            record = next((f for f in comp.get("fields", []) if f.get("field_id") == field_id), None)

    if record is None:
        return RobustVHChangeResult(
            field_id=field_id,
            status="NOT_EVALUATED",
            compatible_observations=False,
            median_change_db=None,
            pre_median_db=None,
            warning_median_db=None,
            post_median_db=None,
            percentile_comparison={},
            spatial_heterogeneity_iqr_db=None,
            valid_pixel_distribution={},
            damage_rate_convertible=False,
            limitations=["No verified VH observations found for field."],
            evidence_ids=[],
        )

    obs_2026 = record.get("observations", {}).get("2026", [])
    pre = next((o for o in obs_2026 if o.get("warning_relation") == "PRE_WARNING"), None)
    warn = next((o for o in obs_2026 if o.get("warning_relation") == "WARNING_WINDOW"), None)
    post = next((o for o in obs_2026 if o.get("warning_relation") == "POST_WARNING"), None)

    pre_to_warn = record.get("2026_pre_to_warning_window") or {}
    median_change = pre_to_warn.get("median_difference_db")

    percentile_comparison: dict[str, Any] = {}
    for label, obs in (("pre_warning", pre), ("warning_window", warn), ("post_warning", post)):
        if obs:
            p25 = obs.get("vh_p25_db")
            p75 = obs.get("vh_p75_db")
            percentile_comparison[label] = {
                "p25_db": p25,
                "median_db": obs.get("vh_median_db"),
                "p75_db": p75,
                "iqr_db": round(p75 - p25, 5) if p25 is not None and p75 is not None else None,
            }

    warn_iqr = (percentile_comparison.get("warning_window") or {}).get("iqr_db")
    valid_dist = {
        o.get("warning_relation"): {
            "valid_pixel_count": o.get("valid_pixel_count"),
            "interior_pixel_count": o.get("interior_pixel_count"),
            "valid_coverage_ratio": o.get("valid_coverage_ratio"),
        }
        for o in obs_2026
    }

    return RobustVHChangeResult(
        field_id=field_id,
        status="OBSERVED" if median_change is not None else "NOT_EVALUATED",
        compatible_observations=True,
        median_change_db=median_change,
        pre_median_db=pre.get("vh_median_db") if pre else None,
        warning_median_db=warn.get("vh_median_db") if warn else None,
        post_median_db=post.get("vh_median_db") if post else None,
        percentile_comparison=percentile_comparison,
        spatial_heterogeneity_iqr_db=warn_iqr,
        valid_pixel_distribution=valid_dist,
        damage_rate_convertible=False,
        limitations=[
            "SAR VH dB change reflects backscatter variation, NOT crop damage rate or yield loss percentage.",
            "Only field-level summary statistics are verified; pixel-level damage classification is not established.",
        ],
        evidence_ids=list(record.get("evidence_ids", [])),
    )
