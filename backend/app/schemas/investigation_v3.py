"""Bounded Typhoon CHAMPI investigation contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvestigationV3Request(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: Literal['CHAMPI-YUNLIN-TAIXI'] = 'CHAMPI-YUNLIN-TAIXI'
    aoi_id: Literal['10009160'] = '10009160'
    question: str = Field(default='Did agricultural radar observations in Taixi change after Typhoon Champi, and how does the 2026 VH series compare with 2025?', min_length=1, max_length=1200)
    agent_mode: Literal['deterministic', 'gemini'] = 'deterministic'
    field_id: Literal['YL-CAND-01', 'YL-CAND-02', 'YL-CAND-03', 'YL-CAND-04', 'YL-CAND-05'] = 'YL-CAND-01'


class InvestigationV3Response(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str
    aoi_id: str
    investigation_id: str
    question: str
    data_mode: str
    observation_timeline: list[dict]
    observation_statistics: dict
    vh_timeseries: dict | None
    vh_comparison: dict | None
    available_sensors: list[dict]
    observed_changes: list[dict]
    hypotheses: list[dict]
    hypothesis_tests: list[dict]
    evidence_ids: list[str]
    scientific_limitations: list[str]
    missing_evidence: list[str]
    recommended_next_action: str
    provenance_status: str
    tool_trace: list[dict]
    qa: dict
    official_loss_context: dict
    expert_report: dict
    field_comparison: dict | None = None
    temporal_changes: dict | None = None

    @model_validator(mode='after')
    def verified_references(self):
        registered = set(self.evidence_ids)
        cited = {x['evidence_id'] for x in self.observation_timeline if x.get('evidence_id')}
        for item in self.hypotheses + self.hypothesis_tests:
            cited.update(item.get('supporting_evidence_ids', []))
            cited.update(item.get('contradicting_evidence_ids', []))
            cited.update(item.get('evidence_ids', []))
        for item in self.observed_changes:
            cited.update(item.get('source_evidence_ids', []))
        if self.vh_timeseries:
            cited.update(item.get('evidence_id') for item in self.vh_timeseries.get('observations', []))
        if self.field_comparison:
            cited.update(self.field_comparison.get('evidence_ids', []))
        if self.temporal_changes:
            cited.update(self.temporal_changes.get('evidence_ids', []))
        if not cited <= registered:
            raise ValueError('Investigation cites an unregistered Evidence ID')
        return self
