"""Typed, evidence-bound result for a bounded scientific investigation."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HypothesisStatus(StrEnum):
    SUPPORTED_BY_AVAILABLE_EVIDENCE = 'SUPPORTED_BY_AVAILABLE_EVIDENCE'
    NOT_SUPPORTED_BY_AVAILABLE_EVIDENCE = 'NOT_SUPPORTED_BY_AVAILABLE_EVIDENCE'
    UNRESOLVED = 'UNRESOLVED'


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(min_length=1, max_length=120)
    aoi_id: str = Field(min_length=1, max_length=120)
    aoi_bbox_wgs84: list[float] = Field(min_length=4, max_length=4)
    question: str = Field(min_length=1, max_length=1200)
    data_mode: Literal['cache'] = 'cache'

    @model_validator(mode='after')
    def check_bbox(self):
        w, s, e, n = self.aoi_bbox_wgs84
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError('Invalid WGS84 AOI bounding box')
        return self


class EvidenceLinkedStatement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    statement: str
    evidence_ids: list[str] = Field(min_length=1)
    epistemic_status: Literal['OBSERVED', 'INFERRED']


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hypothesis_id: str
    statement: str
    status: HypothesisStatus
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    discriminating_observation: str
    limitation: str


class GraphNode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node_id: str
    node_type: Literal['claim', 'evidence', 'analysis', 'aoi', 'scene_pair', 'observation_metadata', 'provenance']
    label: str
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: str
    target: str
    relation: str


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    @model_validator(mode='after')
    def check_edges(self):
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)) or any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError('Evidence graph contains duplicate nodes or dangling edges')
        return self


class ToolStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: str
    status: Literal['complete', 'blocked']
    detail: str | None = None


class ObservationMetadata(BaseModel):
    """Mission neutral metadata. Empty fields mean unknown, not a cross-mission match."""
    model_config = ConfigDict(extra='forbid')
    mission: str
    sensor: str | None = None
    frequency_band: str | None = None
    polarization: list[str]
    acquisition_time: str | None = None
    orbit_direction: str | None = None
    product_type: str | None = None
    radiometric_convention: str | None = None
    spatial_resolution_m: float | None = None
    source_reference: str
    product_maturity: str | None = None
    data_license: str | None = None
    scientific_limitations: list[str]


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    investigation_id: str
    case_id: str
    aoi_id: str
    scene_pair: list[str] = Field(min_length=2, max_length=2)
    data_mode: Literal['cache']
    research_question: str
    observable_variables: list[str]
    observation_summary: list[EvidenceLinkedStatement]
    evidence_ids: list[str]
    hypotheses: list[Hypothesis]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    unresolved_questions: list[str]
    scientific_limitations: list[str]
    recommended_next_observation: list[str]
    map_actions: list[dict]
    tool_trace: list[ToolStep]
    validation_status: Literal['INTERNALLY_CONSISTENT_SOURCE_UNVERIFIED']
    evidence_graph: EvidenceGraph
    observation_metadata: list[ObservationMetadata]

    @model_validator(mode='after')
    def check_references(self):
        registered = set(self.evidence_ids)
        references = [eid for item in self.observation_summary for eid in item.evidence_ids]
        references += [eid for item in self.hypotheses for eid in item.supporting_evidence + item.contradicting_evidence]
        references += self.supporting_evidence + self.contradicting_evidence
        if not registered or any(eid not in registered for eid in references):
            raise ValueError('Investigation references unregistered evidence')
        return self
