"""Typed data models for Autonomous Experimentation & Falsification (Workstream A).

All models are JSON-serializable via `.to_dict()` and use standard library
dataclasses/enums so they work both inside the full SAR2Action runtime and
in lightweight offline test environments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class HypothesisCategory(str, Enum):
    TYPHOON_SURFACE_CHANGE = "typhoon_surface_change"
    AGRICULTURAL_HARVEST = "agricultural_harvest"
    MOISTURE_VARIATION = "moisture_variation"
    OBSERVATION_ARTIFACT = "observation_artifact"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class HypothesisStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    PLAUSIBLE_UNCONFIRMED = "PLAUSIBLE_UNCONFIRMED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


class FeasibilityStatus(str, Enum):
    EXECUTABLE = "EXECUTABLE"
    BLOCKED_MISSING_DATA = "BLOCKED_MISSING_DATA"
    BLOCKED_UNSAFE_TOOL = "BLOCKED_UNSAFE_TOOL"
    BLOCKED_INVALID_INPUT = "BLOCKED_INVALID_INPUT"
    DUPLICATE_EXPERIMENT = "DUPLICATE_EXPERIMENT"


class ExperimentStatus(str, Enum):
    PLANNED = "PLANNED"
    EXECUTED = "EXECUTED"
    EVALUATED = "EVALUATED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    TIMED_OUT = "TIMED_OUT"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class EvidenceItem:
    evidence_id: str
    source: str
    summary: str
    field_id: str | None = None
    observation_type: str = "SAR_OBSERVATION"
    metrics: dict[str, Any] = field(default_factory=dict)
    verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolSpec:
    name: str
    description: str
    required_inputs: list[str]
    read_only: bool = True
    estimated_cost: float = 1.0
    source_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolTraceEntry:
    step: int
    timestamp_utc: str
    kind: str  # "tool_call" | "tool_result" | "validation" | "stop"
    tool: str
    status: str
    experiment_id: str | None = None
    source_references: list[str] = field(default_factory=list)
    duration_ms: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisState:
    hypothesis_id: str
    category: HypothesisCategory
    statement: str
    necessary_evidence: list[str]
    expected_observation: str
    possible_contradiction: str
    executable_tests: list[str]
    missing_tests: list[str]
    stop_conditions: list[str]
    status: HypothesisStatus = HypothesisStatus.UNRESOLVED
    observed_measurements: list[dict[str, Any]] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    alternative_explanations: list[str] = field(default_factory=list)
    direct_contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    test_outcomes: list[dict[str, Any]] = field(default_factory=list)
    executed_tests: list[str] = field(default_factory=list)
    untested_checks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["status"] = self.status.value
        return data


@dataclass
class ExperimentScoreBreakdown:
    """Deterministic heuristic priority score for tool/experiment selection.

    NOTE: This is NOT a statistical probability of scientific truth or success.
    """

    relevance_score: float
    data_availability_score: float
    executability_score: float
    discrimination_score: float
    estimated_cost_penalty: float
    duplication_risk_penalty: float
    total_priority_score: float
    rationale: dict[str, str]
    is_statistical_probability: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentPlan:
    experiment_id: str
    experiment_type: str
    hypothesis_id: str
    objective: str
    required_inputs: list[str]
    selected_tools: list[str]
    testable_prediction: str
    falsification_criterion: str
    expected_evidence: list[str]
    scientific_limitations: list[str]
    feasibility_status: FeasibilityStatus
    signature: str
    target_hypotheses: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    score: ExperimentScoreBreakdown | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["feasibility_status"] = self.feasibility_status.value
        if self.score is not None:
            data["score"] = self.score.to_dict()
        return data


@dataclass
class ExperimentResult:
    experiment_id: str
    experiment_type: str
    hypothesis_id: str
    status: ExperimentStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    tool_trace: list[ToolTraceEntry] = field(default_factory=list)
    error: str | None = None
    timed_out: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["tool_trace"] = [t.to_dict() for t in self.tool_trace]
        return data


@dataclass
class ExperimentEvaluation:
    experiment_id: str
    hypothesis_id: str
    verdict: str  # "DIRECT_CONTRADICTION" | "UNIQUENESS_CHALLENGED_NOT_FALSIFIED" | "NON_DISCRIMINATING" | "QA_FAILED" | "MISSING_EVIDENCE" | "INCONCLUSIVE" | "FAILED"
    falsification_triggered: bool
    qa_passed: bool
    discriminating: bool
    observed_measurements: list[dict[str, Any]]
    supporting_evidence_ids: list[str]
    alternative_explanations: list[str]
    direct_contradicting_evidence_ids: list[str]
    missing_evidence: list[str]
    executed_tests: list[str]
    untested_checks: list[str]
    hypothesis_status_after: HypothesisStatus
    rationale: str
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hypothesis_status_after"] = self.hypothesis_status_after.value
        return data


@dataclass
class InvestigationContext:
    research_question: str
    study_aoi: str
    case_id: str = "CHAMPI-YUNLIN-TAIXI"
    field_id: str = "YL-CAND-03"
    observations: list[dict[str, Any]] = field(default_factory=list)
    existing_evidence: list[EvidenceItem] = field(default_factory=list)
    competing_hypotheses: list[HypothesisState] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    executed_experiment_signatures: list[str] = field(default_factory=list)
    max_experiments: int = 3
    max_steps_per_experiment: int = 5
    timeout_seconds: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_question": self.research_question,
            "study_aoi": self.study_aoi,
            "case_id": self.case_id,
            "field_id": self.field_id,
            "observations": self.observations,
            "existing_evidence": [e.to_dict() for e in self.existing_evidence],
            "competing_hypotheses": [h.to_dict() for h in self.competing_hypotheses],
            "missing_evidence": list(self.missing_evidence),
            "available_tools": list(self.available_tools),
            "executed_experiment_signatures": list(self.executed_experiment_signatures),
            "max_experiments": self.max_experiments,
            "max_steps_per_experiment": self.max_steps_per_experiment,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class BoundedInvestigationResult:
    investigation_id: str
    case_id: str
    study_aoi: str
    field_id: str
    research_question: str
    status: str  # "COMPLETED_BOUNDED" | "STOPPED_MISSING_EVIDENCE" | "STOPPED_NO_EXECUTABLE_EXPERIMENTS"
    stop_reason: str
    experiments_planned: list[ExperimentPlan]
    experiments_executed: list[ExperimentResult]
    evaluations: list[ExperimentEvaluation]
    revised_hypotheses: list[HypothesisState]
    missing_evidence: list[str]
    tool_trace: list[ToolTraceEntry]
    evidence_ledger: list[EvidenceItem]
    scientific_limitations: list[str]
    crop_damage_confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "case_id": self.case_id,
            "study_aoi": self.study_aoi,
            "field_id": self.field_id,
            "research_question": self.research_question,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "experiments_planned": [p.to_dict() for p in self.experiments_planned],
            "experiments_executed": [r.to_dict() for r in self.experiments_executed],
            "evaluations": [e.to_dict() for e in self.evaluations],
            "revised_hypotheses": [h.to_dict() for h in self.revised_hypotheses],
            "missing_evidence": list(self.missing_evidence),
            "tool_trace": [t.to_dict() for t in self.tool_trace],
            "evidence_ledger": [e.to_dict() for e in self.evidence_ledger],
            "scientific_limitations": list(self.scientific_limitations),
        }
