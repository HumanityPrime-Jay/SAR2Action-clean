"""Typed models for the Farmer Intelligence Agent."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class FarmerIntent(str, Enum):
    FIND_MY_FIELD = "FIND_MY_FIELD"
    CHECK_FIELD_AREA = "CHECK_FIELD_AREA"
    CHECK_POSSIBLE_DAMAGE = "CHECK_POSSIBLE_DAMAGE"
    ESTIMATE_DAMAGED_AREA = "ESTIMATE_DAMAGED_AREA"
    ESTIMATE_CROP_LOSS = "ESTIMATE_CROP_LOSS"
    ESTIMATE_FINANCIAL_LOSS = "ESTIMATE_FINANCIAL_LOSS"
    CHECK_RELIEF_PROGRAMS = "CHECK_RELIEF_PROGRAMS"
    ESTIMATE_RELIEF_AMOUNT = "ESTIMATE_RELIEF_AMOUNT"
    HOW_TO_APPLY = "HOW_TO_APPLY"
    CHECK_APPLICATION_DEADLINE = "CHECK_APPLICATION_DEADLINE"
    REQUIRED_DOCUMENTS = "REQUIRED_DOCUMENTS"
    EXPLAIN_SATELLITE_RESULT = "EXPLAIN_SATELLITE_RESULT"
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    FOLLOW_UP_QUESTION = "FOLLOW_UP_QUESTION"


@dataclass
class FarmerSessionState:
    session_id: str
    selected_field_id: str | None = None
    county: str | None = None
    township: str | None = None
    crop: str | None = None
    disaster_event: str | None = "Typhoon CHAMPI"
    field_area_m2: float | None = None
    field_area_ha: float | None = None
    farmer_reported_damage_ratio: float | None = None
    farmer_reported_affected_area_ha: float | None = None
    farmer_reported_condition: str | None = None
    verified_announcement_status: str = "ANNOUNCEMENT_NOT_VERIFIED"
    pending_question: str | None = None
    completed_tools: list[str] = field(default_factory=list)
    application_readiness: dict[str, bool] = field(default_factory=dict)
    turn_count: int = 0
    last_intent: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResultCard:
    card_type: str
    title: str
    data: dict[str, Any]
    sources: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SuggestedAction:
    type: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FarmerChatResponse:
    reply: str
    conversation_state: str
    intent: str
    suggested_actions: list[dict[str, Any]] = field(default_factory=list)
    result_cards: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    session_state: dict[str, Any] = field(default_factory=dict)
    # "en" only when the reply was actually translated; otherwise the Chinese reply is returned as is.
    reply_language: str = "zh"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
