"""Pydantic v2 API schemas for the SAR2Action Phase 3A Deterministic Evidence API.

Enforces Rule 2.1:
- No quantitative value may be invented by the API layer.
- All science values originate from NISAR product metadata, the deterministic Change Engine,
  or the Evidence Store.
- Error states (`INSUFFICIENT_EVIDENCE`, `LIMITED`, `COMPARABLE`, incompatible pair,
  unavailable polarization, AOI outside coverage) are explicitly typed and never masked
  as empty HTTP 200 responses.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.evidence import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    DistributionStatsDb,
    EvidenceRecord,
    PolarizationChannel,
    RadarFingerprint,
    ScenePairValidationResult,
    ScienceQualityStatus,
)


class HealthResponse(BaseModel):
    """Response schema for `GET /api/health`."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    project: str = "SAR2Action — NISAR Earth Change Intelligence"
    project_mode: str = "PRE_COMPETITION_RND"
    demo_mode: Literal["LIVE", "CACHED_REAL_DATA"] = "LIVE"
    rfi_comparison_status: str = "UNRELIABLE_METADATA"
    algorithm_version: str = "sar2action-change-engine-v1.0.0"
    combined_radar_change_formula: str = "abs(Delta_HH) + abs(Delta_HV)"
    combined_radar_change_unit: str = "dB composite"
    combined_radar_change_disclaimer: str = COMBINED_RADAR_CHANGE_DISCLAIMER
    evidence_count: int = Field(..., ge=0)
    available_cases: list[str]


class PresetAOI(BaseModel):
    """Scientifically justified preset AOI within a case."""

    model_config = ConfigDict(extra="forbid")

    aoi_id: str
    name: str
    description: str
    bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    default_evidence_id: str | None = None
    selection_method: Literal[
        "PREDEFINED_EXTERNAL_CONTEXT",
        "PREDEFINED_GEOGRAPHIC_AOI",
        "EXPLORATORY_POST_HOC_RADAR_CHANGE",
    ] = "PREDEFINED_GEOGRAPHIC_AOI"
    selection_time: str = "PRE_ANALYSIS"
    selection_basis: str = ""


class CaseSummary(BaseModel):
    """Summary of an available engineering or flagship case (`GET /api/cases`)."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    title: str
    case_role: Literal["PRIMARY_FLAGSHIP", "ENGINEERING_VALIDATION", "BACKUP_FLAGSHIP"]
    region_name: str
    track_number: int
    frame_number: int
    orbit_pass_direction: Literal["ASCENDING", "DESCENDING"]
    look_direction: Literal["LEFT", "RIGHT"]
    polarizations: list[PolarizationChannel]
    product_maturity: str
    crid: str
    is_full_frame: bool
    default_t0_scene_id: str
    default_t1_scene_id: str
    t0_acquisition_utc: str
    t1_acquisition_utc: str
    t0_orbit_pointing_fidelity: str | None = None
    t1_orbit_pointing_fidelity: str | None = None
    rfi_comparison_status: str = "UNRELIABLE_METADATA"
    default_aoi_bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    illuminated_bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    crs_epsg: int
    pixel_spacing_m: list[float] = Field(..., min_length=2, max_length=2)
    local_hdf5_ready: bool
    scientific_scope_note: str
    preset_aois: list[PresetAOI] = Field(default_factory=list)


class CasesListResponse(BaseModel):
    """Response for `GET /api/cases`."""

    model_config = ConfigDict(extra="forbid")

    cases: list[CaseSummary]


class ObservationRecord(BaseModel):
    """Single NISAR GCOV observation metadata (`GET /api/cases/{case_id}/observations`)."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    case_id: str
    acquisition_start_utc: str
    acquisition_end_utc: str
    acquisition_date: str
    track_or_frame: str
    orbit_pass_direction: str
    look_direction: str
    polarizations: list[PolarizationChannel]
    product_maturity: str
    crid: str | None
    processing_version: str | None
    is_full_frame: bool
    approx_file_size_bytes: int | None
    bbox_wgs84: list[float] | None
    local_hdf5_available: bool
    local_hdf5_path: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class CaseObservationsResponse(BaseModel):
    """Response for `GET /api/cases/{case_id}/observations`."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    default_t0_scene_id: str
    default_t1_scene_id: str
    observations: list[ObservationRecord]


class ValidatePairRequest(BaseModel):
    """Request body for `POST /api/validate-pair`."""

    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    scene_t0_id: str
    scene_t1_id: str
    aoi_bbox_wgs84: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326.",
    )


class ValidatePairResponse(BaseModel):
    """Response for `POST /api/validate-pair`."""

    model_config = ConfigDict(extra="forbid")

    validation_level: Literal["PRODUCT_HDF5", "CATALOG_METADATA"]
    result: ScenePairValidationResult
    product_validation_summary: dict[str, Any] | None = None


class AnalyzeChangeRequest(BaseModel):
    """Request body for `POST /api/change/analyze`."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    scene_t0_id: str | None = None
    scene_t1_id: str | None = None
    aoi_id: str | None = None
    aoi_bbox_wgs84: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326.",
    )
    requested_polarizations: list[PolarizationChannel] | None = Field(
        default=None,
        description="Optional subset of polarizations (e.g. ['HH', 'HV']). Raises 422 if unavailable.",
    )


class DeterministicClaim(BaseModel):
    """Deterministic Claim-to-Evidence item (Section 3.5: one claim -> one evidence trail)."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    statement: str
    evidence_id: str
    case_id: str
    roi_id: str
    scene_ids: list[str]
    aoi_bbox_wgs84: list[float]
    polarization: PolarizationChannel | None = None
    metric_name: str
    metric_value: float
    unit: str = "dB"
    valid_pixel_count: int
    valid_area_km2: float
    algorithm_version: str
    calculation_formula: str
    target_layer_type: str


class LayerLegendSpec(BaseModel):
    """Scientific legend specification for a map layer (Section 3.2)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    units: str
    min_value: float
    max_value: float
    palette_type: Literal["single_epoch_db", "signed_diverging_db", "magnitude_sequential_db", "validity_mask"]
    stops: list[dict[str, Any]]
    positive_change_meaning: str | None = None
    negative_change_meaning: str | None = None
    invalid_observation_meaning: str = (
        "Invalid / unavailable observation (mask == 0 partially focused, mask == 255 outside swath, or non-positive power) — excluded as NaN."
    )
    prohibited_labels_notice: str = (
        "Radar backscatter or change in dB only — never labeled as wildfire, burn severity, damage, or risk."
    )


class LayerMetadataResponse(BaseModel):
    """Response for `GET /api/layers/{layer_id}`."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    case_id: str
    evidence_id: str
    roi_id: str
    layer_type: Literal[
        "t0_hh",
        "t1_hh",
        "t0_hv",
        "t1_hv",
        "delta_hh",
        "delta_hv",
        "magnitude_hh",
        "magnitude_hv",
        "combined_change",
        "validity_mask",
    ]
    title: str
    polarization: PolarizationChannel | None = None
    units: str
    source_scenes: list[str]
    t0_acquisition_utc: str
    t1_acquisition_utc: str | None = None
    bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    crs_epsg: int
    width: int
    height: int
    image_url: str
    color_interpretation: str
    legend: LayerLegendSpec
    disclaimer: str | None = None
    limitations: list[str]


class AnalyzeChangeResponse(BaseModel):
    """Response for `POST /api/change/analyze`."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["completed"] = "completed"
    case_id: str
    roi_id: str
    evidence_id: str
    quality_status: ScienceQualityStatus
    scene_t0_id: str
    scene_t1_id: str
    t0_acquisition_utc: str
    t1_acquisition_utc: str
    aoi_bbox_wgs84: list[float]
    available_polarizations: list[PolarizationChannel]
    unavailable_polarizations: list[PolarizationChannel]
    valid_pixel_count: int
    valid_area_km2: float
    valid_area_ha: float
    coverage_ratio: float
    missing_data_ratio: float
    layers: dict[str, LayerMetadataResponse]
    claims: list[DeterministicClaim]
    evidence_record: EvidenceRecord
    selection_method: str = "PREDEFINED_GEOGRAPHIC_AOI"
    selection_time: str = "PRE_ANALYSIS"
    selection_basis: str = ""
    demo_mode: Literal["LIVE", "CACHED_REAL_DATA"] = "LIVE"
    cache_hit: bool = False


class RadarFingerprintRequest(BaseModel):
    """Request body for `POST /api/radar-fingerprint`."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    scene_t0_id: str | None = None
    scene_t1_id: str | None = None
    aoi_id: str | None = None
    aoi_bbox_wgs84: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326.",
    )
    requested_polarizations: list[PolarizationChannel] | None = None


class PolarizationFingerprintDetail(BaseModel):
    """Detailed polarization distribution for the Radar Fingerprint panel (Section 3.3)."""

    model_config = ConfigDict(extra="forbid")

    polarization: PolarizationChannel
    available: bool = True
    status_label: Literal["Available", "Unavailable"] = "Available"
    t0_median_db: float | None = None
    t0_mean_db: float | None = None
    t1_median_db: float | None = None
    t1_mean_db: float | None = None
    delta_median_db: float | None = None
    delta_mean_db: float | None = None
    delta_distribution_db: DistributionStatsDb | None = None
    magnitude_median_db: float | None = None
    magnitude_mean_db: float | None = None
    magnitude_distribution_db: DistributionStatsDb | None = None
    positive_change_fraction: float | None = None
    negative_change_fraction: float | None = None


class EpistemicSummaryPanel(BaseModel):
    """Non-AI deterministic 'What We Observed / What May Explain It / What We Do Not Know' panel (Section 3.4)."""

    model_config = ConfigDict(extra="forbid")

    what_we_observed: list[str]
    what_may_explain_it: list[str]
    what_we_do_not_know: list[str]


class RadarFingerprintResponse(BaseModel):
    """Response for `POST /api/radar-fingerprint`."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: RadarFingerprint
    case_id: str
    roi_id: str
    evidence_id: str
    quality_status: ScienceQualityStatus
    t0_acquisition_utc: str
    t1_acquisition_utc: str
    aoi_bbox_wgs84: list[float]
    available_polarizations: list[PolarizationChannel]
    unavailable_polarizations: list[PolarizationChannel]
    hh_detail: PolarizationFingerprintDetail
    hv_detail: PolarizationFingerprintDetail
    combined_radar_change_detail: dict[str, Any] | None = None
    valid_pixel_count: int
    valid_area_m2: float
    valid_area_ha: float
    valid_area_km2: float
    coverage_ratio: float
    missing_invalid_fraction: float
    epistemic_panel: EpistemicSummaryPanel
    claims: list[DeterministicClaim]
    layers: dict[str, LayerMetadataResponse]
    evidence_record: EvidenceRecord
    selection_method: str = "PREDEFINED_GEOGRAPHIC_AOI"
    selection_time: str = "PRE_ANALYSIS"
    selection_basis: str = ""
    demo_mode: Literal["LIVE", "CACHED_REAL_DATA"] = "LIVE"
    cache_hit: bool = False
