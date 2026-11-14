"""Typed models for the Scientific Uncertainty Engine (Phase B)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SARQualityAssessment:
    field_id: str
    status: str  # "EVALUATED" | "NOT_EVALUATED" | "QA_FAILED"
    qa_passed: bool
    valid_pixels: int | None
    valid_coverage_ratio: float | None
    polygon_area_m2: float | None
    interior_area_m2: float | None
    spatial_dependence_note: str
    nodata_mask_verified: bool
    raster_resolution_m: float | None
    acquisition_geometry: dict[str, Any]
    processing_version: str | None
    noise_metadata: dict[str, Any]
    temporal_support: dict[str, Any]
    limitations: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RobustVHChangeResult:
    field_id: str
    status: str  # "OBSERVED" | "NOT_EVALUATED" | "BLOCKED_INCOMPATIBLE"
    compatible_observations: bool
    median_change_db: float | None
    pre_median_db: float | None
    warning_median_db: float | None
    post_median_db: float | None
    percentile_comparison: dict[str, Any]
    spatial_heterogeneity_iqr_db: float | None
    valid_pixel_distribution: dict[str, Any]
    damage_rate_convertible: bool = False
    limitations: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
