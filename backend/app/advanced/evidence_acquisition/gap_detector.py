"""Evidence Gap Detection (Phase C1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidenceGapReport:
    field_id: str
    missing_observations: list[str] = field(default_factory=list)
    missing_crop_identity: list[str] = field(default_factory=list)
    missing_ground_truth: list[str] = field(default_factory=list)
    missing_weather_evidence: list[str] = field(default_factory=list)
    missing_compatible_products: list[str] = field(default_factory=list)
    missing_quality_metadata: list[str] = field(default_factory=list)

    @property
    def all_gaps(self) -> list[str]:
        return (
            self.missing_observations
            + self.missing_crop_identity
            + self.missing_ground_truth
            + self.missing_weather_evidence
            + self.missing_compatible_products
            + self.missing_quality_metadata
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["total_gaps"] = len(self.all_gaps)
        return data


def detect_evidence_gaps(
    field_id: str,
    *,
    sar_quality: dict[str, Any] | None = None,
    cross_crid_qa: dict[str, Any] | None = None,
    external_evidence: dict[str, Any] | None = None,
) -> EvidenceGapReport:
    """Deterministically detect scientific & evidentiary gaps."""
    ext = external_evidence or {}
    report = EvidenceGapReport(field_id=field_id)

    if sar_quality is None or sar_quality.get("status") == "NOT_EVALUATED":
        report.missing_quality_metadata.append("SAR spatial/radiometric quality metadata not evaluated")
    else:
        temporal = sar_quality.get("temporal_support") or {}
        if not temporal.get("strict_pre_warning_trend_available"):
            report.missing_observations.append("Additional 2026 pre-warning SAR acquisition needed for pre-event trend")
        if not (sar_quality.get("noise_metadata") or {}).get("unit_verified"):
            report.missing_quality_metadata.append("Raster unit/calibration tag verification missing")

    if not ext.get("crop_identity"):
        report.missing_crop_identity.append("Verified parcel-level crop type and planting/harvest calendar")
    if not ext.get("ground_truth"):
        report.missing_ground_truth.append("Geolocated field damage survey or cloud-free optical validation")
    if not ext.get("weather_evidence"):
        report.missing_weather_evidence.append("In-situ or high-resolution rainfall and soil moisture time series")

    if cross_crid_qa is None or not cross_crid_qa.get("crid_match"):
        report.missing_compatible_products.append("Reprocessed same-CRID NISAR pre/post scenes for radiometric delta")

    return report
