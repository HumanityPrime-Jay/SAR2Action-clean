from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

BBox = tuple[float, float, float, float]

class BoundingBox(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode='after')
    def valid(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError('Invalid bbox: west < east and south < north required')
        if (self.east-self.west) > 5 or (self.north-self.south) > 5:
            raise ValueError('AOI exceeds demo analysis limit (5 degrees per axis)')
        return self

class Scene(BaseModel):
    scene_id: str = Field(min_length=3, max_length=180)
    acquired_at: datetime
    polarizations: list[Literal['HH','HV','VV','VH']]
    orbit_track: str
    look_direction: Literal['left','right']
    grid_id: str
    product_maturity: str
    crid: str
    source_granule: str
    simulated: bool = False

class ScenePairRequest(BaseModel):
    scene_before: str
    scene_after: str

class ChangeRequest(ScenePairRequest):
    polarization: Literal['HH','HV','VV','VH'] = 'HV'
    bbox: BoundingBox

class QueryRequest(ChangeRequest):
    query: str = Field(default='Analyze surface change in this area.', max_length=1200)
    locale: Literal['zh-TW','en'] = 'zh-TW'
    audience: Literal['general','technical'] = 'general'
    session_id: str = Field(default='default', pattern=r'^[\w-]{1,72}$')
    intent: Literal['investigate','fingerprint','story','explain'] = 'investigate'

class StoryRequest(BaseModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    locale: Literal['zh-TW','en'] = 'zh-TW'
    audience: Literal['general','technical'] = 'general'

class Evidence(BaseModel):
    evidence_id: str
    scene_ids: tuple[str,str]
    bbox: BoundingBox
    acquired_at: tuple[str,str]
    polarization: str
    stats: dict
    quality: dict
    method_version: str
    limitations: list[str]
    source_granules: list[str]
    data_kind: Literal['synthetic','nisar']
    created_at: datetime

class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    quantitative: bool = False

class MapAction(BaseModel):
    type: Literal['map.focus_bbox','map.highlight_aoi','map.set_layer','fingerprint.open','evidence.open','story.open']
    payload: dict

    @model_validator(mode='after')
    def allowlisted_payload(self):
        if self.type in ('map.focus_bbox','map.highlight_aoi'):
            BoundingBox.model_validate(self.payload.get('bbox'))
        if self.type == 'map.set_layer' and self.payload.get('layer_id') not in ('before','after','difference','quality'):
            raise ValueError('Layer not allowlisted')
        if self.type in ('fingerprint.open','evidence.open') and not isinstance(self.payload.get('evidence_id'),str):
            raise ValueError('Missing evidence ID')
        return self

class AgentResult(BaseModel):
    run_id: str
    mode: Literal['fixture','live']
    status: Literal['completed','blocked','failed']
    observed_facts: list[Claim]
    possible_interpretations: list[str]
    unknowns: list[str]
    evidence_refs: list[str]
    map_actions: list[MapAction]
    warnings: list[str]
    provenance: dict
    steps: list[dict]
    narrative: str
    fingerprint: dict | None = None
    story: dict | None = None

class StoryFrame(BaseModel):
    key: str
    title: str
    caption: str
    evidence_ids: list[str]
    bbox: BoundingBox
    layer_id: Literal['before','after','difference','quality']
    time_label: str

class EvidenceStory(BaseModel):
    story_id: str
    evidence_ids: list[str]
    source_signature: str
    status: Literal['current','stale'] = 'current'
    locale: str
    audience: str
    frames: list[StoryFrame]
    mode: Literal['fixture','live']
