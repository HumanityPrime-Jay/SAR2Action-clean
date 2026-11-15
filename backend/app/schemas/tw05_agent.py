"""Pydantic v2 contracts for TW-05 bounded Gemini Agent investigation endpoint (`POST /api/agent/tw05/investigate`).

Designed for:
1. Phase A backend-only integration of teammate `GeminiModelProvider` + `RealAgentRuntime`
2. Strict AOI / parcel / Evidence ID isolation and non-fabrication guardrails
3. Future `/studio` UI compatibility without requiring rework of backend shapes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.taiwan_agro import TwAgroReliefEstimateRequest

ALLOWED_TW05_CASE_IDS = {"TW-05-YUNLIN-AGRO", "TW-01"}
ALLOWED_TW05_AOI_IDS = {"TW-01-YUNLIN-5KM", "TW-05-YUNLIN-AGRO", "TW-01"}
ALLOWED_TW05_EVIDENCE_ID_PATTERN = r"^E-TW0(?:[137]|8A?)-[A-Za-z0-9_-]{2,80}$"


class Tw05InvestigationRequest(BaseModel):
    """Caller-pinned TW-05 agricultural investigation request."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default="TW-05-YUNLIN-AGRO", min_length=1, max_length=120)
    aoi_id: str = Field(default="TW-01-YUNLIN-5KM", min_length=1, max_length=120)
    parcel_feature_id: int | None = Field(default=None, ge=1)
    question: str = Field(
        default="請整合 Sentinel-1D、NISAR、Sentinel-2 與雲林救助公告，說明此區／此坵塊目前可確認的觀測事實、推論與未知事項。",
        min_length=1,
        max_length=1200,
    )
    agent_mode: Literal["gemini", "real", "deterministic"] = "gemini"
    session_id: str = Field(default="tw05-default", pattern=r"^[A-Za-z0-9_-]{1,72}$")
    user_relief_assumptions: TwAgroReliefEstimateRequest | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_query_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "question" not in data and "query" in data:
            copied = dict(data)
            copied["question"] = copied.pop("query")
            return copied
        return data

    @model_validator(mode="after")
    def validate_tw05_scope_and_parcel_binding(self) -> "Tw05InvestigationRequest":
        if self.case_id not in ALLOWED_TW05_CASE_IDS:
            raise ValueError(
                f"Cross-AOI case_id `{self.case_id}` rejected: TW-05 endpoint is locked to `TW-05-YUNLIN-AGRO` / `TW-01`."
            )
        if self.aoi_id not in ALLOWED_TW05_AOI_IDS:
            raise ValueError(
                f"Cross-AOI aoi_id `{self.aoi_id}` rejected: TW-05 endpoint is locked to `{sorted(ALLOWED_TW05_AOI_IDS)}`."
            )
        if self.user_relief_assumptions is not None:
            assump_pid = self.user_relief_assumptions.parcel_feature_id
            if (
                self.parcel_feature_id is not None
                and assump_pid is not None
                and assump_pid != self.parcel_feature_id
            ):
                raise ValueError(
                    f"Parcel binding mismatch: request locked parcel #{self.parcel_feature_id}, "
                    f"but user_relief_assumptions referenced #{assump_pid}."
                )
        return self


class Tw05ObservedFact(BaseModel):
    """Single deterministic measurement or status verified against Evidence ledger."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    sensor_or_source: str
    metric_name: str
    metric_value: float | None = None
    verified_value_str: str
    unit: str
    statement: str
    epistemic_status: Literal["OBSERVED"] = "OBSERVED"
    evidence_ids: list[str] = Field(..., min_length=1)


class Tw05InferenceItem(BaseModel):
    """Bounded analytical hypothesis / inference separated from confirmed damage."""

    model_config = ConfigDict(extra="forbid")

    inference_id: str
    statement: str
    status: Literal["SUPPORTED_FOR_FOLLOWUP_ONLY", "UNRESOLVED", "BLOCKED"]
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    proposed_by_gemini: bool = False
    reason: str


class Tw05EvidenceCitation(BaseModel):
    """Auditable Evidence record returned by backend ledger for UI / Studio inspection."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_module: str
    sensor_or_authority: str
    acquisition_window: str
    summary: str
    provenance_status: str
    verified_metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class Tw05ToolTraceStep(BaseModel):
    """Execution step in the non-sensitive auditable tool trace."""

    model_config = ConfigDict(extra="forbid")

    step: int
    timestamp_utc: str
    kind: Literal["request", "planner", "tool_call", "tool_result", "validation", "final"]
    tool: str
    status: Literal["complete", "executed", "rejected", "failed", "blocked", "skipped"]
    validated_arguments: dict[str, Any] | None = None
    source_references: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    duration_ms: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class Tw05AgentErrorInfo(BaseModel):
    """Structured error payload when Gemini execution blocks or rejects calls."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    rejected_tool_count: int = 0
    unauthorized_tool_calls: int = 0


class Tw05EpistemicGuardrails(BaseModel):
    """Hard non-fabrication flags enforced across backend and Studio."""

    model_config = ConfigDict(extra="forbid")

    crop_type_label: Literal["UNKNOWN"] = "UNKNOWN"
    actual_damage_rate: Literal["UNKNOWN"] = "UNKNOWN"
    confirmed_typhoon_damage: Literal[False] = False
    official_relief_eligibility: Literal["UNKNOWN"] = "UNKNOWN"
    cross_sensor_direct_subtraction_allowed: Literal[False] = False
    optical_insufficient_parcel_flag: bool = False
    gemini_key_exposed_in_response: Literal[False] = False


class Tw05InvestigationResponse(BaseModel):
    """Unified Phase A backend response for POST /api/agent/tw05/investigate and future /studio UI."""

    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    status: Literal["completed", "blocked"]
    execution_mode: Literal[
        "GEMINI_FUNCTION_CALLING_LIVE",
        "GEMINI_FUNCTION_CALLING_MOCK",
        "DETERMINISTIC_TOOL_PIPELINE",
        "BLOCKED_NO_MODEL_CONFIGURED",
        "BLOCKED_MODEL_EXECUTION_FAILED",
        "BLOCKED_NO_VALID_TOOL_SELECTED",
        "BLOCKED_VALIDATION_FAILED",
    ]
    agent_mode: str
    model_provider: str
    model_name: str | None = None
    case_id: str
    aoi_id: str
    aoi_bbox_wgs84: list[float] = Field(..., min_length=4, max_length=4)
    locked_parcel_feature_id: int | None = None
    question: str
    observed_facts: list[Tw05ObservedFact] = Field(default_factory=list)
    inferences: list[Tw05InferenceItem] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_records: list[Tw05EvidenceCitation] = Field(default_factory=list)
    tool_trace: list[Tw05ToolTraceStep] = Field(default_factory=list)
    scientific_limitations: list[str] = Field(default_factory=list)
    error: Tw05AgentErrorInfo | None = None
    epistemic_guardrails: Tw05EpistemicGuardrails = Field(default_factory=Tw05EpistemicGuardrails)
    parcel_summary: dict[str, Any] | None = None
    relief_assessment: dict[str, Any] | None = None
    map_actions: list[dict[str, Any]] = Field(default_factory=list)

    # /studio future compatibility envelope (mirrors InvestigationV3Response contracts cleanly)
    data_mode: str
    provenance_status: str
    observation_timeline: list[dict[str, Any]] = Field(default_factory=list)
    available_sensors: list[dict[str, Any]] = Field(default_factory=list)
    observed_changes: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    hypothesis_tests: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_next_action: str
    qa: dict[str, Any] = Field(default_factory=dict)
    official_loss_context: dict[str, Any] = Field(default_factory=dict)
    expert_report: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def verify_evidence_citations_and_guardrails(self) -> "Tw05InvestigationResponse":
        registered = set(self.evidence_ids)
        record_ids = {rec.evidence_id for rec in self.evidence_records}
        if not record_ids <= registered:
            raise ValueError("evidence_records contains unregistered Evidence IDs")

        cited: set[str] = set()
        for fact in self.observed_facts:
            cited.update(fact.evidence_ids)
        for inf in self.inferences:
            cited.update(inf.supporting_evidence_ids)
            cited.update(inf.contradicting_evidence_ids)
        for item in self.observation_timeline:
            if isinstance(item.get("evidence_id"), str):
                cited.add(item["evidence_id"])
        for item in self.observed_changes:
            for key in ("evidence_id",):
                if isinstance(item.get(key), str):
                    cited.add(item[key])
            for ref in item.get("source_evidence_ids") or []:
                if isinstance(ref, str):
                    cited.add(ref)
        for item in self.hypotheses + self.hypothesis_tests:
            for key in ("evidence_ids", "supporting_evidence_ids", "contradicting_evidence_ids"):
                for ref in item.get(key) or []:
                    if isinstance(ref, str):
                        cited.add(ref)

        unknown_refs = cited - registered
        if unknown_refs:
            raise ValueError(f"TW-05 response cites unregistered Evidence IDs: {sorted(unknown_refs)}")
        return self
