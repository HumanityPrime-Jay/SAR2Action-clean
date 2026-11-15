"""Typed Request/Response schemas for Earth Change Intelligence Platform."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "Agriculture",
    "Flooding",
    "Forest Change",
    "Wildfire",
    "Glacier",
    "Earthquake / Ground Deformation",
    "Volcanic Activity",
    "Coastal Change",
]

ChangeAnalysisStatus = Literal[
    "CATALOG_DISCOVERED",
    "OBSERVATION_AVAILABLE",
    "COMPARISON_COMPATIBLE",
    "CHANGE_ANALYZED",
]

DemoMode = Literal[
    "RECORDED_REAL_DATA",
    "LIVE_DETERMINISTIC",
    "LIVE_GEMINI",
    "CATALOG_ONLY",
    "DATA_UNAVAILABLE",
]

LensMode = Literal["OBSERVED", "HYPOTHESES", "UNKNOWN", "NEXT_EVIDENCE"]
UserMode = Literal["FARMER", "AUTHORITY"]

ALLOWED_MAP_ACTIONS = (
    "FLY_TO_REGION",
    "SELECT_EVENT",
    "SELECT_FIELD",
    "SELECT_AOI",
    "SHOW_LAYER",
    "HIDE_LAYER",
    "SET_LAYER_OPACITY",
    "OPEN_TIMELINE",
    "PLAY_TIMELINE",
    "PAUSE_TIMELINE",
    "SET_TIMELINE_DATE",
    "OPEN_REALITY_LENS",
    "COMPARE_OBSERVATIONS",
    "COMPARE_FIELDS",
    "OPEN_HYPOTHESIS_ARENA",
    "RUN_INVESTIGATION",
    "OPEN_EVIDENCE",
    "SHOW_FINGERPRINT",
    "GENERATE_EARTH_STORY",
)

MapActionName = Literal[
    "FLY_TO_REGION",
    "SELECT_EVENT",
    "SELECT_FIELD",
    "SELECT_AOI",
    "SHOW_LAYER",
    "HIDE_LAYER",
    "SET_LAYER_OPACITY",
    "OPEN_TIMELINE",
    "PLAY_TIMELINE",
    "PAUSE_TIMELINE",
    "SET_TIMELINE_DATE",
    "OPEN_REALITY_LENS",
    "COMPARE_OBSERVATIONS",
    "COMPARE_FIELDS",
    "OPEN_HYPOTHESIS_ARENA",
    "RUN_INVESTIGATION",
    "OPEN_EVIDENCE",
    "SHOW_FINGERPRINT",
    "GENERATE_EARTH_STORY",
]


class ProvenanceMeta(BaseModel):
    data_status: DemoMode
    evidence_ids: list[str] = Field(default_factory=list)
    scientific_limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error_code: str | None = None


class GlobalEventRecord(BaseModel):
    event_id: str
    event_name: str
    event_name_zh: str
    event_type: EventType
    country: str
    region: str
    center_lon: float
    center_lat: float
    default_zoom: float = 11.5
    aoi_bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    aoi_geometry: dict[str, Any]
    observation_sources: list[str]
    sensor: str
    polarization: list[str]
    acquisition_dates: list[str]
    product_versions: list[str]
    available_layers: list[str]
    change_analysis_status: ChangeAnalysisStatus
    demo_mode: DemoMode
    scientific_qa: dict[str, Any]
    evidence_ids: list[str]
    data_provenance: list[str]
    story_available: bool
    summary: str
    summary_zh: str


class GlobalEventCatalogResponse(BaseModel):
    events: list[GlobalEventRecord]
    supported_event_types: list[EventType]
    total: int
    provenance: ProvenanceMeta


class AcquisitionPoint(BaseModel):
    acquisition_id: str
    acquisition_time_utc: str
    acquisition_time_local: str
    date_label: str
    sensor: str
    polarization: str
    product_version: str
    source: str
    qa_status: str
    warning_phase: str
    compatible_with_baseline: bool
    compatibility_note: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    overlay_url: str | None = None
    evidence_id: str | None = None


class ObservationGap(BaseModel):
    start_utc: str
    end_utc: str
    gap_days: float
    status: Literal["NO_OBSERVATION"] = "NO_OBSERVATION"
    note: str


class EarthMemoryTimelineResponse(BaseModel):
    event_id: str
    field_id: str | None = None
    acquisitions: list[AcquisitionPoint]
    observation_gaps: list[ObservationGap]
    cross_sensor_warnings: list[str]
    provenance: ProvenanceMeta


class RealityLensFeature(BaseModel):
    feature_id: str
    label: str
    geometry: dict[str, Any] | None = None
    scale: Literal["PARCEL", "REGION", "CATALOG"]
    status: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class RealityLensResponse(BaseModel):
    event_id: str
    lens: LensMode
    title: str
    subtitle: str
    legend_items: list[dict[str, str]]
    features: list[RealityLensFeature]
    no_fake_confidence: bool = True
    spatial_qa_available: bool
    provenance: ProvenanceMeta


class SurfaceFingerprint(BaseModel):
    region_id: str
    event_id: str
    label: str
    sensor: str
    polarizations: list[str]
    product_version: str
    observation_count: int
    vh_temporal_signature: list[dict[str, Any]]
    hh_hv_signature: dict[str, Any] | str = "NOT_AVAILABLE"
    temporal_difference_db: float | None = None
    seasonal_reference_db: float | None = None
    spatial_heterogeneity: float | str = "NOT_AVAILABLE"
    valid_pixel_ratio: float | str = "NOT_AVAILABLE"
    qa_status: str
    missing_evidence: list[str]
    feature_vector: dict[str, float | None]
    evidence_ids: list[str]


class FingerprintCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_region_id: str
    target_region_id: str
    event_id: str = "CHAMPI-YUNLIN-TAIXI"


class FingerprintCompareResponse(BaseModel):
    source: SurfaceFingerprint
    target: SurfaceFingerprint
    comparable: bool
    incompatibility_reasons: list[str]
    normalized_feature_distance: float | None = None
    temporal_pattern_similarity: float | None = None
    scientific_caution: str
    provenance: ProvenanceMeta


class SimilarChangeCandidate(BaseModel):
    region_id: str
    label: str
    comparable: bool
    normalized_feature_distance: float | None = None
    temporal_pattern_similarity: float | None = None
    incompatibility_reason: str | None = None
    causal_warning: str


class SimilarChangeResponse(BaseModel):
    query_region_id: str
    candidates: list[SimilarChangeCandidate]
    provenance: ProvenanceMeta


class HypothesisArenaCard(BaseModel):
    hypothesis_id: str
    title: str
    description: str
    status: str
    supporting_evidence: list[str]
    alternative_explanations: list[str]
    direct_contradictions: list[str]
    missing_evidence: list[str]
    test_outcomes: list[dict[str, Any]]
    available_experiments: list[dict[str, Any]]


class HypothesisArenaResponse(BaseModel):
    event_id: str
    field_id: str
    research_question: str
    hypotheses: list[HypothesisArenaCard]
    recommended_next_experiment: dict[str, Any] | None = None
    provenance: ProvenanceMeta


class RunHypothesisExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = "CHAMPI-YUNLIN-TAIXI"
    field_id: str = "YL-CAND-03"
    hypothesis_id: str
    experiment_type: str | None = None
    propose_only: bool = False


class RunHypothesisExperimentResponse(BaseModel):
    event_id: str
    field_id: str
    hypothesis_id: str
    executed: bool
    status: str
    experiment_type: str
    summary: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    hypothesis_status_after: str
    evaluation_outcome: str
    reason_if_not_executable: str | None = None
    provenance: ProvenanceMeta


class EvidenceGapItem(BaseModel):
    gap_id: str
    title: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    why_missing: str
    research_value: str
    where_to_find: str
    recommended_action: Literal["SEARCH", "VALIDATE", "PLAN", "REQUEST_APPROVAL"]


class EvidenceGapResponse(BaseModel):
    event_id: str
    field_id: str
    gaps: list[EvidenceGapItem]
    stage_one_policy: str = "SEARCH / VALIDATE / PLAN / REQUEST_APPROVAL only; bulk raw SAR download requires explicit approval."
    provenance: ProvenanceMeta


class CatalogSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = "CHAMPI-YUNLIN-TAIXI"
    product_family: Literal["OPERA_RTC_S1", "NISAR_GCOV", "SENTINEL1_SLC"] = "OPERA_RTC_S1"
    start_utc: str = "2026-10-01T00:00:00Z"
    end_utc: str = "2026-11-10T23:59:59Z"
    polarization: str | None = "VH"
    live_network: bool = True


class CatalogSearchResponse(BaseModel):
    event_id: str
    product_family: str
    search_executed: bool
    network_status: str
    scenes: list[dict[str, Any]]
    compatibility_summary: str
    download_permitted: bool = False
    provenance: ProvenanceMeta


class AIMapAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: MapActionName
    params: dict[str, Any] = Field(default_factory=dict)


class GuidedDiscoveryContext(BaseModel):
    event_id: str | None = None
    region: str | None = None
    aoi: str | None = None
    selected_field_id: str | None = None
    observation_id: str | None = None
    timeline_position: str | None = None
    active_layers: list[str] = Field(default_factory=list)
    selected_lens: LensMode = "OBSERVED"
    user_mode: UserMode = "FARMER"
    lang: Literal["zh", "en"] = "zh"


class GuidedDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=1, max_length=600)
    context: GuidedDiscoveryContext = Field(default_factory=GuidedDiscoveryContext)
    prefer_gemini: bool = True


class GuidedDiscoveryResponse(BaseModel):
    query: str
    user_mode: UserMode
    execution_mode: str
    answer: str
    actions: list[AIMapAction]
    validated_actions_count: int
    rejected_actions: list[str] = Field(default_factory=list)
    facts_used: list[str] = Field(default_factory=list)
    provenance: ProvenanceMeta


class StoryChapter(BaseModel):
    chapter_number: int
    chapter_code: str
    title: str
    narrative: str
    camera: dict[str, Any]
    lens: LensMode
    timeline_date: str | None = None
    active_layers: list[str] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EarthStory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story_id: str
    event_id: str
    field_id: str
    title: str
    created_at_utc: str
    user_mode: UserMode = "AUTHORITY"
    chapters: list[StoryChapter]
    provenance: ProvenanceMeta


class GenerateStoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = "CHAMPI-YUNLIN-TAIXI"
    field_id: str = "YL-CAND-03"
    user_mode: UserMode = "AUTHORITY"
    lang: Literal["zh", "en"] = "zh"


class StoryImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story: EarthStory
