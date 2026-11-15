"""FastAPI Router & Pure-Python Endpoint Handlers for Advanced Scientific Intelligence, Legal RAG, Farmer Agent & Dual-Mode GIS."""
# No `from __future__ import annotations` here: the request models are local to
# create_fastapi_router(), and FastAPI cannot resolve string annotations that point at
# local classes, so every POST body would be read as a required `req` query parameter.

import os
from typing import Any, Literal

from backend.app.advanced.dual_mode import AuthorityGISService, ModeCapabilityRegistry
from backend.app.advanced.farmer_agent import FarmerConversationService
from backend.app.advanced.indicator_explainer import (
    explain_current_indicator,
    get_indicator,
    list_all_indicators,
)
from backend.app.advanced.legal_rag import LegalDatabase, LegalRAGService
from backend.app.advanced.orchestrator import AdvancedOrchestrator, ScientificLegalOrchestrator

_orchestrator = AdvancedOrchestrator()
_sci_legal = ScientificLegalOrchestrator()
_legal_service = LegalRAGService()
_legal_db = LegalDatabase()
# Gemini only rephrases the rule-based draft; numbers and approval claims are guarded.
_farmer_service = FarmerConversationService(use_gemini=os.getenv("SAR2ACTION_LLM_PROVIDER", "").lower() == "gemini")
_mode_registry = ModeCapabilityRegistry()
_gis_service = AuthorityGISService()


def handle_investigate_advanced(payload: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("question") or "Analyze YL-CAND-03 VH change and legal relief status")
    field_id = str(payload.get("field_id") or "YL-CAND-03")
    aoi_id = str(payload.get("aoi_id") or "10009160")
    event_date = payload.get("event_date", "2026-10-23")
    include_catalog = bool(payload.get("include_catalog_search", False))
    return _orchestrator.investigate(
        question,
        field_id=field_id,
        aoi_id=aoi_id,
        event_date=event_date,
        include_catalog_search=include_catalog,
    )


def handle_legal_query(payload: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("question") or "")
    if not question.strip():
        raise ValueError("question is required")
    return _legal_service.query(
        question,
        event_date=payload.get("event_date"),
        region=payload.get("region"),
        crop=payload.get("crop"),
        available_evidence=payload.get("available_evidence"),
        top_k=int(payload.get("top_k", 5)),
    ).to_dict()


def handle_legal_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "")
    if not query.strip():
        raise ValueError("query is required")
    return _legal_service.retriever.hybrid_search(
        query,
        top_k=int(payload.get("top_k", 5)),
        use_reranker=bool(payload.get("use_reranker", True)),
    )


def handle_legal_sources() -> dict[str, Any]:
    return _legal_db.get_manifest_summary()


def handle_farmer_chat(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload.get("session_id") or "default-farmer-session")
    message = str(payload.get("message") or "")
    if not message.strip():
        raise ValueError("message is required")
    return _farmer_service.chat(
        session_id,
        message,
        selected_field_id=payload.get("selected_field_id"),
        optional_map_geometry=payload.get("optional_map_geometry"),
        optional_damage_geometry=payload.get("optional_damage_geometry"),
        optional_event_id=payload.get("optional_event_id"),
        crop=payload.get("crop"),
        lang=str(payload.get("lang") or "zh"),
    ).to_dict()


def handle_ui_modes() -> dict[str, Any]:
    return {"modes": _mode_registry.list_modes()}


def handle_ui_capabilities(mode: str = "FARMER", is_authenticated_authority: bool = False) -> dict[str, Any]:
    return _mode_registry.get_capabilities(mode, is_authenticated_authority=is_authenticated_authority)


def handle_list_indicators() -> dict[str, Any]:
    items = list_all_indicators()
    return {"count": len(items), "indicators": items}


def handle_get_indicator(indicator_id: str) -> dict[str, Any] | None:
    return get_indicator(indicator_id)


def handle_explain_indicator(payload: dict[str, Any]) -> dict[str, Any]:
    indicator_id = str(payload.get("indicator_id") or "")
    if not indicator_id:
        raise ValueError("indicator_id is required")
    return explain_current_indicator(
        indicator_id,
        mode=str(payload.get("mode") or "FARMER"),
        field_id=payload.get("field_id"),
        value=payload.get("value"),
        acquisition_date=payload.get("acquisition_date"),
        data_source=payload.get("data_source"),
        qa_status=payload.get("qa_status"),
    )


def handle_gis_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    return _gis_service.analyze_gis(
        field_ids=payload.get("field_ids"),
        polygon_geojson=payload.get("polygon_geojson"),
        buffer_m=payload.get("buffer_m"),
        aoi_id=str(payload.get("aoi_id") or "10009160"),
    )


def handle_gis_compare(payload: dict[str, Any]) -> dict[str, Any]:
    return _gis_service.compare_observations(
        sensor=str(payload.get("sensor") or "OPERA_S1"),
        field_id=str(payload.get("field_id") or "YL-CAND-03"),
        mode=str(payload.get("mode") or "SIDE_BY_SIDE"),
        compute_difference=bool(payload.get("compute_difference", False)),
    )


def handle_agent_chat(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "FARMER").upper()
    message = str(payload.get("message") or "")
    if not message.strip():
        raise ValueError("message is required")
    if mode == "AUTHORITY":
        res = _sci_legal.analyze(
            message,
            field_id=str(payload.get("field_id") or "YL-CAND-03"),
            aoi_id=str(payload.get("aoi_id") or "10009160"),
            event_date=payload.get("event_date", "2026-10-23"),
        )
        return {"mode": "AUTHORITY", **res.to_dict()}
    return {"mode": "FARMER", **handle_farmer_chat(payload)}


def handle_map_action(payload: dict[str, Any]) -> dict[str, Any]:
    return _gis_service.build_map_action(
        str(payload.get("action_type") or ""),
        payload.get("payload"),
    )


def create_fastapi_router():
    """Build FastAPI APIRouter lazily so core modules stay importable without FastAPI installed."""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    router = APIRouter(tags=["Advanced Intelligence"])

    class InvestigateAdvancedReq(BaseModel):
        question: str = Field(min_length=1, max_length=1500)
        field_id: str = "YL-CAND-03"
        aoi_id: str = "10009160"
        event_date: str | None = "2026-10-23"
        include_catalog_search: bool = False

    class LegalQueryReq(BaseModel):
        question: str = Field(min_length=1, max_length=1200)
        event_date: str | None = None
        region: str | None = None
        crop: str | None = None
        available_evidence: dict[str, Any] | None = None
        top_k: int = 5

    class LegalSearchReq(BaseModel):
        query: str = Field(min_length=1, max_length=500)
        top_k: int = 5
        use_reranker: bool = True

    class FarmerChatReq(BaseModel):
        session_id: str = "default-farmer-session"
        message: str = Field(min_length=1, max_length=1200)
        selected_field_id: str | None = None
        optional_map_geometry: dict[str, Any] | None = None
        optional_damage_geometry: dict[str, Any] | None = None
        optional_event_id: str | None = None
        crop: str | None = Field(default=None, max_length=40)
        lang: Literal["zh", "en"] = "zh"

    class ExplainIndicatorReq(BaseModel):
        indicator_id: str
        mode: str = "FARMER"
        field_id: str | None = None
        value: Any = None
        acquisition_date: str | None = None
        data_source: str | None = None
        qa_status: str | None = None

    class GisAnalyzeReq(BaseModel):
        field_ids: list[str] | None = None
        polygon_geojson: dict[str, Any] | None = None
        buffer_m: float | None = None
        aoi_id: str = "10009160"

    class GisCompareReq(BaseModel):
        sensor: str = "OPERA_S1"
        field_id: str = "YL-CAND-03"
        mode: str = "SIDE_BY_SIDE"
        compute_difference: bool = False

    class AgentChatReq(BaseModel):
        mode: str = "FARMER"
        session_id: str = "default-session"
        message: str = Field(min_length=1, max_length=1500)
        field_id: str | None = "YL-CAND-03"
        selected_field_id: str | None = None
        aoi_id: str = "10009160"
        event_date: str | None = "2026-10-23"

    class MapActionReq(BaseModel):
        action_type: str
        payload: dict[str, Any] | None = None

    @router.post("/api/agent/investigate-advanced")
    def investigate_advanced(req: InvestigateAdvancedReq):
        return handle_investigate_advanced(req.model_dump())

    @router.post("/api/agent/legal-query")
    def legal_query(req: LegalQueryReq):
        return handle_legal_query(req.model_dump())

    @router.post("/api/agent/legal-search")
    def legal_search(req: LegalSearchReq):
        return handle_legal_search(req.model_dump())

    @router.get("/api/agent/legal-sources")
    def legal_sources():
        return handle_legal_sources()

    @router.post("/api/farmer/chat")
    def farmer_chat(req: FarmerChatReq):
        return handle_farmer_chat(req.model_dump())

    @router.get("/api/ui/modes")
    def ui_modes():
        return handle_ui_modes()

    @router.get("/api/ui/capabilities")
    def ui_capabilities(mode: str = "FARMER"):
        try:
            return handle_ui_capabilities(mode=mode, is_authenticated_authority=False)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/api/indicators")
    def list_indicators():
        return handle_list_indicators()

    @router.get("/api/indicators/{indicator_id}")
    def get_indicator_route(indicator_id: str):
        item = handle_get_indicator(indicator_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Indicator not found")
        return item

    @router.post("/api/indicators/explain")
    def explain_indicator(req: ExplainIndicatorReq):
        return handle_explain_indicator(req.model_dump())

    @router.post("/api/gis/analyze")
    def gis_analyze(req: GisAnalyzeReq):
        return handle_gis_analyze(req.model_dump())

    @router.post("/api/gis/compare")
    def gis_compare(req: GisCompareReq):
        return handle_gis_compare(req.model_dump())

    @router.post("/api/agent/chat")
    def agent_chat(req: AgentChatReq):
        return handle_agent_chat(req.model_dump())

    @router.post("/api/agent/map-action")
    def map_action(req: MapActionReq):
        try:
            return handle_map_action(req.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
