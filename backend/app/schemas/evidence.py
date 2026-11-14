"""Pydantic v2 Evidence, Scene Pair Validation, Radar Fingerprint, and Evidence Story schemas.

Enforces SAR2Action's non-negotiable scientific guardrails:
1. Every quantitative claim links back to one or more EvidenceRecord IDs (`evidence_id`).
2. `validate_scene_pair` results strictly enforce consistency between `compatible` and `science_status`.
3. Missing polarizations (e.g., absent HV) are explicitly `None` (`null`) — never synthesized.
4. Combined Radar Change (`D = |ΔHH| + |ΔHV|`) carries its mandatory custom visualization disclaimer
   and is disallowed if either HH or HV is missing.
5. Radar change evidence always records `"cause_not_determined"` in `limitations` unless explicitly
   supported by an independent validated source.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScienceQualityStatus(StrEnum):
    """Mandatory Unknown-Aware epistemic states."""

    OBSERVED = "OBSERVED"
    COMPARABLE = "COMPARABLE"
    LIMITED = "LIMITED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PolarizationChannel(StrEnum):
    """Supported NISAR GCOV diagonal polarization channels."""

    HH = "HH"
    HV = "HV"
    VV = "VV"
    VH = "VH"


class EvidenceType(StrEnum):
    """Types of deterministic scientific evidence records."""

    SCENE_OBSERVATION = "scene_observation"
    PAIR_VALIDATION = "pair_validation"
    RADAR_CHANGE = "radar_change"
    RADAR_FINGERPRINT = "radar_fingerprint"


class StorySceneKey(StrEnum):
    """Five canonical scenes of the SAR2Action Evidence Story."""

    BEFORE = "before"
    THE_SHIFT = "the_shift"
    INVESTIGATE = "investigate"
    WHAT_WE_KNOW = "what_we_know"
    EVIDENCE_STORY = "evidence_story"


class DistributionStatsDb(BaseModel):
    """Deterministic statistical distribution of decibel values over valid pixels."""

    model_config = ConfigDict(extra="forbid")

    mean: float = Field(..., description="Arithmetic mean in dB across valid comparable pixels.")
    median: float = Field(..., description="Median (p50) in dB across valid comparable pixels.")
    std: float = Field(..., ge=0.0, description="Standard deviation in dB.")
    min: float = Field(..., description="Minimum value in dB.")
    max: float = Field(..., description="Maximum value in dB.")
    p10: float | None = Field(default=None, description="10th percentile in dB.")
    p25: float | None = Field(default=None, description="25th percentile in dB.")
    p50: float | None = Field(default=None, description="50th percentile (median) in dB.")
    p75: float | None = Field(default=None, description="75th percentile in dB.")
    p90: float | None = Field(default=None, description="90th percentile in dB.")

    @model_validator(mode="after")
    def validate_min_max_order(self) -> DistributionStatsDb:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) cannot exceed max ({self.max}).")
        return self


COMBINED_RADAR_CHANGE_DISCLAIMER = (
    "Custom visualization metric — not a hazard score, fire probability, "
    "damage score, or official burn-severity index."
)


class CombinedRadarChangeMetric(BaseModel):
    """Optional dual-polarization visualization metric D = |ΔHH| + |ΔHV|."""

    model_config = ConfigDict(extra="forbid")

    metric_name: Literal["Combined Radar Change"] = "Combined Radar Change"
    unit: str = "dB composite"
    unit_description: str = "custom change magnitude (sum of absolute dB changes)"
    disclaimer: Literal[
        "Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."
    ] = COMBINED_RADAR_CHANGE_DISCLAIMER
    stats: DistributionStatsDb


class ProcessingProvenanceMetadata(BaseModel):
    """Lineage and provenance metadata for reconstructing a calculation from raw NISAR granules."""

    model_config = ConfigDict(extra="allow")

    t0_acquisition_utc: str = Field(..., description="ISO-8601 UTC timestamp of T0 observation.")
    t1_acquisition_utc: str | None = Field(
        default=None, description="ISO-8601 UTC timestamp of T1 observation (if multi-temporal)."
    )
    product_type: str = Field(default="NISAR_L2_GCOV", description="NISAR product type.")
    frequency_band: Literal["L", "S"] = Field(default="L", description="Radar band.")
    frequency_group: str = Field(default="frequencyA", description="HDF5 frequency group.")
    orbit_pass_direction: str | None = Field(
        default=None, description="Ascending or Descending pass direction."
    )
    look_direction: str | None = Field(default=None, description="Left or Right look direction.")
    t0_crid: str | None = Field(default=None, description="Composite Release ID for T0.")
    t1_crid: str | None = Field(default=None, description="Composite Release ID for T1.")
    crs_epsg: int | None = Field(default=None, description="Target grid EPSG code.")
    pixel_spacing_m: tuple[float, float] | None = Field(
        default=None, description="(dx, dy) grid spacing in meters."
    )
    computed_at_utc: str | None = Field(
        default=None, description="ISO-8601 UTC timestamp when computation executed."
    )


class ScenePairValidationResult(BaseModel):
    """Deterministic return contract for `validate_scene_pair(scene_a, scene_b, aoi)`."""

    model_config = ConfigDict(extra="forbid")

    compatible: bool = Field(
        ...,
        description="True only if the scene pair passes mandatory scientific compatibility gates.",
    )
    validation_decision: Literal["PASS", "CONDITIONAL", "FAIL"] = Field(
        default="PASS",
        description="High-level decision: PASS, CONDITIONAL (needs HDF5/metadata verification), or FAIL.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Blocking incompatibility reasons when compatible is False.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal scientific caveats (e.g., partial valid coverage, missing optional metadata).",
    )
    valid_overlap_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction [0.0, 1.0] of AOI pixels with finite positive power and valid masks in both scenes (None if HDF5 grids not yet inspected).",
    )
    spatial_overlap_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Geometric bounding/footprint overlap ratio [0.0, 1.0] with the AOI or between scenes.",
    )
    available_polarizations: list[PolarizationChannel] = Field(
        default_factory=list,
        description="Polarization channels confirmed present in BOTH T0 and T1.",
    )
    scene_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Ordered [scene_a_id, scene_b_id] evaluated by the gate.",
    )
    t0_utc: str | None = Field(default=None, description="ISO-8601 UTC timestamp of T0 scene.")
    t1_utc: str | None = Field(default=None, description="ISO-8601 UTC timestamp of T1 scene.")
    frequency_band: str | None = Field(default="L", description="Radar band.")
    frequency_group: str | None = Field(default="frequencyA", description="GCOV HDF5 frequency group.")
    same_orbit_pass: bool | None = Field(
        default=None, description="Whether T0 and T1 share the same orbit pass direction."
    )
    same_look_direction: bool | None = Field(
        default=None, description="Whether T0 and T1 share the same radar look direction."
    )
    crs_compatible: bool | None = Field(default=True, description="Whether CRS/grids can be aligned.")
    grid_aligned: bool | None = Field(default=True, description="Whether pixel grids are aligned.")
    metadata_checks: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed per-check diagnostic outcomes.",
    )
    science_status: ScienceQualityStatus = Field(
        ...,
        description="Resulting Unknown-Aware epistemic status.",
    )

    @model_validator(mode="after")
    def enforce_gate_invariants(self) -> ScenePairValidationResult:
        if not self.compatible:
            self.validation_decision = "FAIL"
        if not self.compatible and self.science_status != ScienceQualityStatus.INSUFFICIENT_EVIDENCE:
            raise ValueError(
                "When compatible is False, science_status must be INSUFFICIENT_EVIDENCE."
            )
        if not self.compatible and not self.reasons:
            raise ValueError(
                "When compatible is False, at least one blocking reason must be provided in `reasons`."
            )
        if self.compatible and self.science_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE:
            raise ValueError(
                "When science_status is INSUFFICIENT_EVIDENCE, compatible must be False."
            )
        if (
            self.compatible
            and self.validation_decision == "PASS"
            and len(self.available_polarizations) == 0
        ):
            raise ValueError(
                "A PASS scene pair must have at least one confirmed shared polarization channel."
            )
        return self


class EvidenceRecord(BaseModel):
    """Canonical Evidence-First record for SAR2Action's Claim-to-Pixel Evidence Ledger."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(
        ...,
        pattern=r"^E-[A-Za-z0-9_-]+$",
        description="Unique evidence identifier (e.g., 'E-001' or 'E-0001').",
    )
    evidence_type: EvidenceType = Field(
        default=EvidenceType.RADAR_CHANGE,
        description="Category of deterministic scientific evidence.",
    )
    scene_ids: list[str] = Field(
        ...,
        min_length=1,
        description="NISAR granule/scene identifiers backing this evidence.",
    )
    roi_id: str = Field(..., description="AOI or ROI identifier.")
    geometry: dict[str, Any] | None = Field(
        default=None,
        description="GeoJSON geometry (Point, Polygon, MultiPolygon) in EPSG:4326.",
    )
    polarizations: list[PolarizationChannel] = Field(
        default_factory=list,
        description="Actual available polarization channels evaluated (never fabricated).",
    )
    t0_db: dict[PolarizationChannel, DistributionStatsDb] = Field(
        default_factory=dict,
        description="Per-polarization T0 backscatter statistics in dB.",
    )
    t1_db: dict[PolarizationChannel, DistributionStatsDb] = Field(
        default_factory=dict,
        description="Per-polarization T1 backscatter statistics in dB.",
    )
    delta_db: dict[PolarizationChannel, DistributionStatsDb] = Field(
        default_factory=dict,
        description="Per-polarization signed difference B(T1,p) - B(T0,p) in dB.",
    )
    magnitude_db: dict[PolarizationChannel, DistributionStatsDb] = Field(
        default_factory=dict,
        description="Per-polarization sign-agnostic magnitude |Δ(p)| in dB.",
    )
    combined_change_db: CombinedRadarChangeMetric | None = Field(
        default=None,
        description="Optional D = |ΔHH| + |ΔHV| metric when both HH and HV are available.",
    )
    summary_statistics: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional deterministic summary metrics (e.g., total/missing pixel counts).",
    )
    valid_pixel_count: int = Field(
        ...,
        ge=0,
        description="Number of valid, positive-power, unmasked comparable pixels.",
    )
    coverage_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction [0.0, 1.0] of ROI covered by valid comparable pixels.",
    )
    missing_data_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction [0.0, 1.0] of ROI with missing, masked, or invalid data.",
    )
    quality_status: ScienceQualityStatus = Field(
        ...,
        description="Mandatory Unknown-Aware epistemic state.",
    )
    algorithm_version: str = Field(
        default="change-v1",
        description="Version tag of the deterministic scientific algorithm.",
    )
    processing_metadata: ProcessingProvenanceMetadata | dict[str, Any] = Field(
        default_factory=dict,
        description="Provenance metadata (dates, CRID, EPSG, orbit, spacing).",
    )
    limitations: list[str] = Field(
        default_factory=lambda: ["cause_not_determined"],
        description="Mandatory scientific caveats attached to this evidence.",
    )
    selection_method: str | None = Field(
        default=None,
        description="AOI selection provenance method (e.g., PREDEFINED_EXTERNAL_CONTEXT, PREDEFINED_GEOGRAPHIC_AOI, EXPLORATORY_POST_HOC_RADAR_CHANGE).",
    )
    selection_time: str | None = Field(
        default=None,
        description="ISO-8601 timestamp or stage when the AOI was defined relative to radar change inspection.",
    )
    selection_basis: str | None = Field(
        default=None,
        description="Human-readable basis for AOI selection.",
    )

    @model_validator(mode="after")
    def enforce_science_contract(self) -> EvidenceRecord:
        # 1. Radar change / fingerprint evidence must always carry 'cause_not_determined'
        if self.evidence_type in (EvidenceType.RADAR_CHANGE, EvidenceType.RADAR_FINGERPRINT):
            if "cause_not_determined" not in self.limitations:
                self.limitations.append("cause_not_determined")

        # 2. Cannot include delta stats for polarizations not listed in `polarizations`
        declared = set(self.polarizations)
        for stats_dict_name, stats_dict in (
            ("t0_db", self.t0_db),
            ("t1_db", self.t1_db),
            ("delta_db", self.delta_db),
            ("magnitude_db", self.magnitude_db),
        ):
            extra_pols = set(stats_dict.keys()) - declared
            if extra_pols:
                raise ValueError(
                    f"{stats_dict_name} contains undeclared polarizations {extra_pols} "
                    f"not in polarizations={self.polarizations}."
                )

        # 3. Combined Radar Change requires both HH and HV to be present
        if self.combined_change_db is not None:
            if not ({PolarizationChannel.HH, PolarizationChannel.HV}.issubset(declared)):
                raise ValueError(
                    "Combined Radar Change (D = |ΔHH| + |ΔHV|) cannot be populated "
                    "unless both HH and HV polarizations are available."
                )

        return self


class PolarizationChangeBreakdown(BaseModel):
    """Per-polarization summary displayed in the Radar Fingerprint panel."""

    model_config = ConfigDict(extra="forbid")

    polarization: PolarizationChannel
    t0_mean_db: float
    t1_mean_db: float
    delta_mean_db: float
    magnitude_mean_db: float = Field(..., ge=0.0)
    t0_median_db: float | None = None
    t1_median_db: float | None = None
    delta_median_db: float | None = None


class RadarFingerprint(BaseModel):
    """Structured response for Experience 2: Radar Fingerprint.

    Explicitly supports `None` (`null`) for unavailable polarizations (e.g., `hv=None`)
    so the backend and UI never synthesize missing radar channels.
    """

    model_config = ConfigDict(extra="forbid")

    fingerprint_id: str = Field(..., description="Unique identifier for this fingerprint query.")
    evidence_id: str = Field(
        ...,
        pattern=r"^E-[A-Za-z0-9_-]+$",
        description="Linked EvidenceRecord ID in the Evidence Ledger.",
    )
    roi_id: str = Field(..., description="Point, polygon, or AOI identifier.")
    t0_acquisition_utc: str
    t1_acquisition_utc: str
    available_polarizations: list[PolarizationChannel]
    hh: PolarizationChangeBreakdown | None = Field(
        default=None, description="HH metrics if available; None if HH is unavailable."
    )
    hv: PolarizationChangeBreakdown | None = Field(
        default=None, description="HV metrics if available; None if HV is unavailable."
    )
    combined_radar_change_db: float | None = Field(
        default=None,
        ge=0.0,
        description="Mean D = |ΔHH| + |ΔHV| if both HH and HV exist; otherwise None.",
    )
    valid_pixel_count: int = Field(..., ge=0)
    valid_coverage_ratio: float = Field(..., ge=0.0, le=1.0)
    missing_data_ratio: float = Field(..., ge=0.0, le=1.0)
    pair_compatibility: ScenePairValidationResult
    quality_status: ScienceQualityStatus
    processing_metadata: ProcessingProvenanceMetadata | dict[str, Any] = Field(
        default_factory=dict
    )
    what_we_observed: list[str] = Field(default_factory=list)
    possible_interpretations: list[str] = Field(default_factory=list)
    what_we_do_not_know: list[str] = Field(
        default_factory=lambda: [
            "NISAR GCOV backscatter intensity alone does not determine whether wildfire was the cause.",
            "Radar-observed surface change is not equivalent to burn severity or burned area.",
            "Two radar observations cannot establish long-term vegetation recovery or underground peat combustion.",
        ]
    )

    @model_validator(mode="after")
    def verify_null_polarization_safety(self) -> RadarFingerprint:
        avail = set(self.available_polarizations)
        if PolarizationChannel.HH not in avail and self.hh is not None:
            raise ValueError("HH is not in available_polarizations; `hh` must be None.")
        if PolarizationChannel.HV not in avail and self.hv is not None:
            raise ValueError("HV is not in available_polarizations; `hv` must be None.")
        if self.combined_radar_change_db is not None and not (
            {PolarizationChannel.HH, PolarizationChannel.HV}.issubset(avail)
        ):
            raise ValueError(
                "combined_radar_change_db must be None when either HH or HV is unavailable."
            )
        return self


class EvidenceClaim(BaseModel):
    """A single quantitative or observational statement linked to one or more Evidence IDs."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., description="Unique claim identifier (e.g., 'C-001').")
    statement: str = Field(..., min_length=1, description="Human-readable scientific statement.")
    evidence_ids: list[str] = Field(
        ...,
        min_length=1,
        description="At least one backing EvidenceRecord ID (e.g., ['E-001']).",
    )
    target_roi_id: str = Field(..., description="AOI/ROI ID to focus when the claim is clicked.")
    target_scene_ids: list[str] = Field(..., min_length=1)
    target_polarization: PolarizationChannel | None = None
    target_layer_mode: Literal[
        "t0", "t1", "swipe", "delta", "magnitude", "combined", "uncertainty_mask"
    ] = "delta"


class StoryScene(BaseModel):
    """One of the five canonical scenes in an Evidence Story."""

    model_config = ConfigDict(extra="forbid")

    scene_number: int = Field(..., ge=1, le=5)
    scene_key: StorySceneKey
    title: str
    narrative: str
    claims: list[EvidenceClaim] = Field(default_factory=list)
    what_we_know: list[str] = Field(default_factory=list)
    what_we_do_not_know: list[str] = Field(default_factory=list)


class EvidenceStory(BaseModel):
    """Five-scene scientific story where every quantitative claim links back to radar evidence."""

    model_config = ConfigDict(extra="forbid")

    story_id: str
    title: str
    aoi_id: str
    quality_status: ScienceQualityStatus
    scenes: list[StoryScene] = Field(..., min_length=5, max_length=5)
    evidence_ledger_ids: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def verify_five_canonical_scenes(self) -> EvidenceStory:
        expected_keys = [
            StorySceneKey.BEFORE,
            StorySceneKey.THE_SHIFT,
            StorySceneKey.INVESTIGATE,
            StorySceneKey.WHAT_WE_KNOW,
            StorySceneKey.EVIDENCE_STORY,
        ]
        actual_keys = [s.scene_key for s in self.scenes]
        if actual_keys != expected_keys:
            raise ValueError(
                f"EvidenceStory scenes must follow the exact 5-scene sequence {expected_keys}, "
                f"got {actual_keys}."
            )
        return self


class AgentInvestigationResponse(BaseModel):
    """Enforces the mandatory 4-section epistemic response structure for the AI Investigator."""

    model_config = ConfigDict(extra="forbid")

    observation: list[str] = Field(
        ..., description="1. Observation: What the NISAR GCOV data actually show."
    )
    possible_interpretation: list[str] = Field(
        ...,
        description="2. Possible interpretation: Physical scattering mechanisms that could explain the change.",
    )
    unknown_and_limitations: list[str] = Field(
        ...,
        description="3. Unknown / limitation: What cannot be concluded from the radar evidence.",
    )
    evidence_ids: list[str] = Field(
        ...,
        description="4. Evidence: Backing EvidenceRecord IDs used to answer the query.",
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True when current evidence is insufficient to support a conclusion.",
    )
    refusal_message: str | None = Field(
        default=None,
        description="Set to 'Current evidence is insufficient to support that conclusion.' when applicable.",
    )
