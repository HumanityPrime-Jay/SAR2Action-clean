"""Pydantic v2 schemas for TW-05: Taiwan Agricultural Surface Change Investigation UI.

Strictly serves verified measurements and metadata read dynamically from:
- `tw01/taiwan-agricultural-demo-v1/` (Sentinel-1D OPERA L2 RTC-S1)
- `tw03/nisar-demo-v1/` (NASA-ISRO NISAR L2 GCOV)

No statistics may be hardcoded or fabricated when files are absent or unverified.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TwAgroDistributionStats(BaseModel):
    """Summary distribution statistics (dB) read from TW-01 / TW-03 JSON manifests."""

    model_config = ConfigDict(extra="forbid")

    mean: float
    median: float
    std: float
    min: float
    max: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


class TwAgroPolarizationStats(BaseModel):
    """Per-polarization T0, T1, and Signed Delta distributions."""

    model_config = ConfigDict(extra="forbid")

    polarization: Literal["HH", "HV", "VV", "VH"]
    available: bool
    t0_db: TwAgroDistributionStats | None = None
    t1_db: TwAgroDistributionStats | None = None
    delta_db: TwAgroDistributionStats | None = None
    magnitude_db: TwAgroDistributionStats | None = None
    positive_change_fraction: float | None = None
    negative_change_fraction: float | None = None


class TwAgroLegendStop(BaseModel):
    """Color stop for a radar change overlay legend."""

    model_config = ConfigDict(extra="forbid")

    value: float
    color: str
    label: str


class TwAgroLayerOverlay(BaseModel):
    """MapLibre georeferenced PNG overlay metadata and 4-corner coordinates."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    polarization: Literal["HH", "HV", "VV", "VH"]
    title: str
    units: str = "dB"
    overlay_url: str
    geotiff_filename: str | None = None
    render_range_db: list[float] = Field(..., min_length=2, max_length=2)
    coordinates_lon_lat: list[list[float]] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="MapLibre image source corners: [top-left, top-right, bottom-right, bottom-left]",
    )
    bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    legend_stops: list[TwAgroLegendStop] = Field(default_factory=list)
    positive_change_meaning: str | None = None
    negative_change_meaning: str | None = None
    prohibited_labels_notice: str
    overlay_sha256: str | None = None


class TwAgroSceneProvenance(BaseModel):
    """Source satellite scene metadata and cryptographic hash."""

    model_config = ConfigDict(extra="forbid")

    epoch: Literal["T0", "T1"]
    scene_id: str
    granule_id: str
    acquisition_utc: str
    source_url: str
    metadata_url: str | None = None
    sha256: str | None = None
    track_frame_note: str
    processor_version: str | None = None


class TwAgroParcelOpticalEpoch(BaseModel):
    """Single Sentinel-2 L2A acquisition optical summary for one farmland parcel."""

    model_config = ConfigDict(extra="forbid")

    date_utc: str
    stac_id: str | None = None
    usability_status: Literal["USABLE_CLEAR", "PARTIAL_CLOUD", "CLOUD_OBSCURED_UNUSABLE"]
    valid_px_10m: int
    total_px_10m: int
    cov_10m: float
    is_valid_10m: bool
    ndvi_med: float | None = None
    ndvi_iqr: float | None = None
    valid_px_20m: int
    total_px_20m: int
    cov_20m: float
    is_valid_20m: bool
    ndre_med: float | None = None
    lswi_med: float | None = None


class TwAgroParcelOpticalMetrics(BaseModel):
    """Per-parcel multi-temporal Sentinel-2 L2A evidence and strict QA gates."""

    model_config = ConfigDict(extra="forbid")

    parcel_feature_id: int
    parcel_no: str
    clipped_area_m2: float
    clipped_area_ha: float
    is_tw01_sar_candidate_181: bool
    quality_gate_status: Literal["SUFFICIENT_CLEAR_BOTH", "INSUFFICIENT_OPTICAL_EVIDENCE"]
    quality_gate_label: str
    insufficient_reason: str | None = None
    usable_clear_dates: list[str]
    all_touched_fallback_10m: bool
    all_touched_fallback_20m: bool
    epochs: list[TwAgroParcelOpticalEpoch]
    delta_ndvi_20261011_20261105: float | None = None
    delta_ndre_20261011_20261105: float | None = None
    delta_lswi_20261011_20261105: float | None = None
    crop_type_label: Literal["UNKNOWN"] = "UNKNOWN"
    actual_damage_rate: Literal["UNKNOWN"] = "UNKNOWN"
    scientific_note: str


class TwAgroSentinel2SceneSummary(BaseModel):
    """AOI-level Sentinel-2 L2A scene QA summary including SCL 4/5/6 breakdown."""

    model_config = ConfigDict(extra="forbid")

    date_utc: str
    acquisition_utc: str
    stac_id: str
    platform: str
    tile_cloud_cover_percent: float
    aoi_valid_fraction_10m: float
    aoi_valid_fraction_20m: float
    aoi_cloud_shadow_fraction_20m: float
    usability_status: Literal["USABLE_CLEAR", "PARTIAL_CLOUD", "CLOUD_OBSCURED_UNUSABLE"]
    scl4_vegetation_fraction_20m: float
    scl5_not_vegetated_fraction_20m: float
    scl6_water_fraction_20m: float
    aoi_ndvi_median_10m: float | None = None
    aoi_ndre_median_20m: float | None = None
    aoi_lswi_median_20m: float | None = None
    overlay_url: str | None = None
    overlay_coordinates_lon_lat: list[list[float]] | None = None


class TwAgroSentinel2ClearDelta(BaseModel):
    """Clear-pair multi-temporal optical change summary (2026-10-11 -> 2026-11-05)."""

    model_config = ConfigDict(extra="forbid")

    t0_date: str
    t1_date: str
    common_valid_fraction_10m: float
    common_valid_fraction_20m: float
    delta_ndvi_median: float | None = None
    delta_ndre_median: float | None = None
    delta_lswi_median: float | None = None
    overlay_url: str
    overlay_coordinates_lon_lat: list[list[float]]


class TwAgroSentinel2Package(BaseModel):
    """Supplementary TW-08A Sentinel-2 L2A package loaded read-only from verified v1 manifest."""

    model_config = ConfigDict(extra="forbid")

    package_id: Literal["s2_tw08"] = "s2_tw08"
    available: bool
    status: str
    schema_version: str | None = None
    failure_reason: str | None = None
    missing_assets: list[str] = Field(default_factory=list)
    title: str
    role_notice: str
    boa_offset_verified: bool = False
    grid_alignment_note: str
    scl_semantics_note: str
    ground_truth_labels_available: bool = False
    classifier_trained: bool = False
    usable_clear_dates: list[str] = Field(default_factory=list)
    total_farmland_parcels: int | None = None
    farmland_sufficient_count: int | None = None
    farmland_insufficient_count: int | None = None
    candidate_181_count: int | None = None
    candidate_sufficient_count: int | None = None
    candidate_insufficient_count: int | None = None
    sar_vh_delta_ndvi_spearman_rho: float | None = None
    sar_vh_delta_ndvi_spearman_p: float | None = None
    scenes: list[TwAgroSentinel2SceneSummary] = Field(default_factory=list)
    clear_delta: TwAgroSentinel2ClearDelta | None = None
    diagnostic_figure_urls: dict[str, str] = Field(default_factory=dict)
    scientific_limitations: list[str] = Field(default_factory=list)


class TwAgroCandidateParcel(BaseModel):
    """Single farmland parcel candidate flagged by exploratory 3 dB screening."""

    model_config = ConfigDict(extra="forbid")

    parcel_feature_id: int
    parcel_no: str
    clipped_area_m2: float
    clipped_area_ha: float
    touches_aoi_boundary: bool = Field(
        default=False,
        description="True when parcel polygon touches the 5 x 5 km AOI clipping boundary",
    )
    valid_pixel_count: int
    coverage_fraction: float
    median_delta_vv_db: float
    median_delta_vh_db: float
    max_abs_median_delta_db: float
    dominant_channel: Literal["VV", "VH"]
    centroid_lon_lat: list[float] = Field(..., min_length=2, max_length=2)
    bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    optical_s2: TwAgroParcelOpticalMetrics | None = None


class TwAgroSensorPackage(BaseModel):
    """Self-contained sensor product status, metrics, overlays, and provenance."""

    model_config = ConfigDict(extra="forbid")

    package_id: Literal["nisar_tw03", "s1_tw01"]
    schema_version: str
    status: str
    available: bool
    missing_assets: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    evidence_id: str | None = None
    sensor_name: str
    band_name: str
    product_type: str
    algorithm_version: str | None = None
    observation_role_badge: str
    observation_window_note: str
    crs_epsg: int | None = None
    pixel_spacing_m: list[float] = Field(default_factory=list)
    grid_shape: list[int] = Field(default_factory=list)
    t0_acquisition_utc: str | None = None
    t1_acquisition_utc: str | None = None
    polarizations: list[str] = Field(default_factory=list)
    valid_pixel_count: int | None = None
    total_reference_pixel_count: int | None = None
    coverage_ratio: float | None = None
    aoi_coverage_ratio: float | None = None
    valid_area_km2: float | None = None
    valid_area_ha: float | None = None
    scenes: list[TwAgroSceneProvenance] = Field(default_factory=list)
    polarization_stats: dict[str, TwAgroPolarizationStats] = Field(default_factory=dict)
    layers: dict[str, TwAgroLayerOverlay] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    not_supported_claims: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)
    mask_rule: str | None = None
    asset_sha256: dict[str, str] = Field(default_factory=dict)


class TwAgroParcelScreeningSummary(BaseModel):
    """Sentinel-1D exploratory farmland screening funnel and 181 candidate parcels."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    missing_assets: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    total_farmland_parcels: int | None = None
    eligible_parcels: int | None = None
    candidate_count: int | None = None
    criteria: str | None = None
    candidate_pixel_count: int | None = None
    candidate_pixel_criteria: str | None = None
    mandatory_non_damage_notice: str
    candidates: list[TwAgroCandidateParcel] = Field(default_factory=list)


class TwAgroReliefCardInfo(BaseModel):
    """Official agricultural disaster relief notice & county-level background."""

    model_config = ConfigDict(extra="forbid")

    title: str
    official_source_name: str
    official_report_url: str
    moa_open_data_url: str
    moa_relief_portal_url: str
    reporting_scope: str | None = None
    yunlin_reported_loss_twd: int | None = None
    applicable_items_summary: str
    application_deadline_guidance: str
    competent_authority: str
    mandatory_disclaimer: str


class TwAgroReliefScheduleItem(BaseModel):
    """Versioned statutory cash relief item under MOA 115/06/29 Schedule II."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    display_name: str
    statutory_category: str
    item_group: Literal["crop", "facility", "excluded", "unannounced", "unconfirmed"]
    rate_twd_per_ha: int | None = None
    unit: str
    examples: list[str] = Field(default_factory=list)
    announced_in_yunlin_11510: bool
    announcement_doc_id: str | None = None
    regulation_version: str
    statutory_conditions: str | None = None
    special_note: str | None = None
    exclusion_reason: str | None = None


class TwAgroDisasterAnnouncement(BaseModel):
    """Official MOA disaster relief announcement record."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    doc_number: str
    county: str
    disaster_event: str
    applicable_items_text: str
    excluded_items_text: str
    application_start_roc: str
    application_end_roc: str
    application_start_iso: str
    application_end_iso: str
    expired_as_of_reference_date: bool
    statutory_exception: str
    competent_authority: str
    official_url: str


class TwAgroFrameworkSeparationItem(BaseModel):
    """Distinguishes government relief, agricultural insurance, and economic loss."""

    model_config = ConfigDict(extra="forbid")

    framework_id: Literal["government_cash_relief", "agricultural_insurance", "economic_production_loss"]
    title: str
    basis: str
    calculation_rule: str
    in_scope: bool


class TwAgroReliefCatalog(BaseModel):
    """Versioned statutory relief rates, Yunlin announcements, and cadastral hectare totals."""

    model_config = ConfigDict(extra="forbid")

    schedule_version_id: str
    regulation_title: str
    regulation_amendment_date_roc: str
    regulation_amendment_date_iso: str
    statutory_basis_articles: list[str]
    min_application_area_ha: float = 0.01
    min_application_area_rule: str
    statutory_loss_threshold_fraction: float
    statutory_loss_threshold_rule: str
    official_law_url: str
    official_afa_schedule_url: str
    as_of_date_iso: str
    primary_deadline_expired_warning: str
    statutory_exception_notice: str
    farmland_total_area_ha: float | None = None
    candidate_total_area_ha: float | None = None
    announcements: list[TwAgroDisasterAnnouncement]
    items: list[TwAgroReliefScheduleItem]
    framework_separation: list[TwAgroFrameworkSeparationItem]


class TwAgroReliefEstimateRequest(BaseModel):
    """Inputs for TW-07 Phase 1 conditional statutory relief reference estimation."""

    model_config = ConfigDict(extra="forbid")

    parcel_feature_id: int | None = None
    crop_item_id: str = "unknown_crop"
    assumed_approved_area_ha: float | None = None
    assumed_loss_threshold: Literal[
        "unverified",
        "below_20_percent",
        "meets_20_percent",
        "article_12_simplified_exception",
    ] = "unverified"
    allow_cross_aoi_boundary_area: bool = False
    adjacent_land_merged_meets_001ha: bool = False


class TwAgroReliefEstimateResponse(BaseModel):
    """Strict 4-tier epistemic separation output for conditional relief reference estimation."""

    model_config = ConfigDict(extra="forbid")

    calculation_allowed: bool
    result_status: Literal[
        "CONDITIONAL_REFERENCE_ESTIMATE",
        "BLOCKED_UNKNOWN_CROP",
        "BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM",
        "BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD",
        "BLOCKED_BELOW_MIN_AREA_001_HA",
        "BLOCKED_INVALID_AREA",
    ]
    result_label: str
    blocked_reason: str | None = None
    conditional_reference_amount_twd: int | None = None
    formula_display: str | None = None
    confirmed_facts: dict[str, Any]
    user_assumptions: dict[str, Any]
    satellite_observations: dict[str, Any]
    unconfirmed_eligibility: list[str]
    deadline_and_exception_notice: str
    non_approval_disclaimer: str
    framework_separation_notice: str


class TwAgroOverviewResponse(BaseModel):
    """Unified payload for GET /api/tw-agro/overview."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: Literal["TW-05-YUNLIN-AGRO"] = "TW-05-YUNLIN-AGRO"
    title: str
    region_name: str
    aoi_bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    geojson_urls: dict[str, str]
    farmland_preview_url: str | None = None
    farmland_total_parcel_count: int | None = None
    nisar_tw03: TwAgroSensorPackage
    s1_tw01: TwAgroSensorPackage
    parcel_screening_summary: TwAgroParcelScreeningSummary
    s2_tw08: TwAgroSentinel2Package | None = None
    relief_info: TwAgroReliefCardInfo
    relief_catalog: TwAgroReliefCatalog | None = None
    scientific_guardrails: list[str]
