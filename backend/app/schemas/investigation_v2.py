"""Typed TW-01 scientific investigation contract; unavailable values stay null."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvestigationV2Request(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = 'TW-01'
    aoi_id: str = 'TW-01'
    aoi_bbox_wgs84: list[float] | None = Field(default=None, min_length=4, max_length=4)
    question: str = Field(default='Did Typhoon Chambi damage farmland in Yunlin, Taiwan?',
                          min_length=1, max_length=1200)
    agent_mode: Literal['deterministic', 'gemini'] = 'deterministic'

    @model_validator(mode='after')
    def validate_scope(self):
        if self.case_id != 'TW-01' or self.aoi_id != 'TW-01':
            raise ValueError('TW-01 investigation cannot cite another case or AOI')
        if self.aoi_bbox_wgs84:
            w, s, e, n = self.aoi_bbox_wgs84
            if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
                raise ValueError('Invalid WGS84 AOI bbox')
        return self


class TimelineObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mission: str
    acquisition_start_utc: str
    relation_to_event: Literal['PRE_EVENT', 'POST_EVENT', 'UNKNOWN']
    evidence_id: str
    catalog_verified: bool
    raster_available: bool
    tw01_coverage_verified: bool | None


class HypothesisAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hypothesis_id: str
    statement: str
    status: Literal['SUPPORTED_BY_AVAILABLE_EVIDENCE', 'NOT_SUPPORTED_BY_AVAILABLE_EVIDENCE', 'UNRESOLVED']
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    reason: str
    proposed_by_gemini: bool


class InvestigationV2Response(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str
    aoi_id: str
    investigation_id: str
    question: str
    data_mode: Literal['CATALOG_ONLY', 'TW03_PROVISIONAL_OBSERVED', 'TW03_VERIFIED']
    observation_timeline: list[TimelineObservation]
    available_sensors: list[dict]
    observed_changes: list[dict]
    hypotheses: list[HypothesisAssessment]
    evidence_ids: list[str]
    scientific_limitations: list[str]
    missing_evidence: list[str]
    recommended_next_action: str
    provenance_status: str
    tool_trace: list[dict]
    qa: dict[str, object]
    cross_sensor_direct_subtraction_allowed: bool
    expert_report: dict[str, list[str]]

    @model_validator(mode='after')
    def validate_evidence_references(self):
        registered = set(self.evidence_ids)
        timeline_ids = {item.evidence_id for item in self.observation_timeline}
        observed_ids = {eid for item in self.observed_changes
                        for eid in [item.get('evidence_id'), *item.get('source_evidence_ids', [])] if eid}
        hypothesis_ids = {eid for item in self.hypotheses
                          for eid in item.supporting_evidence_ids + item.contradicting_evidence_ids}
        if not timeline_ids <= registered or not observed_ids <= registered or not hypothesis_ids <= registered:
            raise ValueError('V2 report cites unregistered Evidence ID')
        return self
