"""SAR2Action Phase 3A — FastAPI Deterministic Evidence API (`backend/app/main.py`).

Exposes deterministic NISAR L-band Level-2 GCOV change analysis, scene-pair validation,
Radar Fingerprint statistics, Claim-to-Evidence records, and georeferenced RGBA map overlays.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Literal
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response

from backend.app.schemas.api import (
    AnalyzeChangeRequest,
    AnalyzeChangeResponse,
    CaseObservationsResponse,
    CasesListResponse,
    HealthResponse,
    LayerMetadataResponse,
    RadarFingerprintRequest,
    RadarFingerprintResponse,
    ValidatePairRequest,
    ValidatePairResponse,
)
from backend.app.schemas.evidence import EvidenceRecord
from backend.app.services.science_service import ScienceService
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
from backend.app.services.science_evidence_provider import ScienceSourceUnavailable
from backend.app.schemas.investigation import InvestigationRequest, InvestigationResult, EvidenceGraph
from backend.app.services.scientific_investigator import ScientificInvestigator
from backend.app.services.agriculture_vh_evidence import run_tool as run_agriculture_vh_tool
from backend.app.schemas.investigation_v2 import InvestigationV2Request, InvestigationV2Response
from backend.app.services.investigation_v2 import InvestigationV2Service, get_catalog_evidence, load_catalog
from backend.app.schemas.investigation_v3 import InvestigationV3Request, InvestigationV3Response
from backend.app.services.investigation_v3 import InvestigationV3Service, get_champi_evidence
from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest, StoryRequest as AgentStoryRequest
from backend.app.services.spatial_ranking import SpatialRequest, SpatialDataUnavailable
from fastapi import HTTPException

app = FastAPI(
    title="SAR2Action — Deterministic NISAR Evidence API",
    version="1.0.0",
    description=(
        "Deterministic scientific API for NISAR L-band Level-2 GCOV multi-temporal change analysis, "
        "Radar Fingerprint generation, and Claim-to-Pixel Evidence provenance."
    ),
)

# SAR2ACTION_CORS_ORIGINS: comma-separated origins. Unset keeps the local-dev default ("*");
# set it to an empty string when the frontend is served from this same app (Cloud Run).
_cors_origins = [o.strip() for o in os.environ.get("SAR2ACTION_CORS_ORIGINS", "*").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

science_service = ScienceService()
agent_orchestrator = AgentOrchestrator(science_service)
scientific_investigator = ScientificInvestigator(science=science_service)
investigation_v2 = InvestigationV2Service()
investigation_v3 = InvestigationV3Service()
investigation_results: dict[str, InvestigationResult] = {}
investigation_results_lock = threading.Lock()


class AgricultureVHToolRequest(BaseModel):
    tool: Literal['get_field_vh_timeseries', 'compare_seasonal_backscatter',
                  'check_event_temporal_alignment', 'evaluate_field_hypotheses',
                  'find_missing_observations', 'calculate_temporal_changes',
                  'compare_five_fields']
    field_id: str | None = None


@app.post('/api/agent/agriculture-vh/tool', tags=['Agent'])
def agriculture_vh_tool(request: AgricultureVHToolRequest) -> dict:
    """Deterministic read-only adapter over observed OPERA VH Evidence JSON."""
    return run_agriculture_vh_tool(request.tool, request.field_id)


@app.post('/api/agent/investigate-v2', response_model=InvestigationV2Response, tags=['Agent'])
def investigate_tw01_v2(request: InvestigationV2Request) -> InvestigationV2Response:
    try:
        return investigation_v2.investigate(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail='Gemini hypothesis proposal unavailable') from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/agent/investigate-v3', response_model=InvestigationV3Response, tags=['Agent'])
def investigate_champi_v3(request: InvestigationV3Request) -> InvestigationV3Response:
    try:
        return investigation_v3.investigate(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail='Gemini investigation planner unavailable') from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/agent/champi/evidence/{evidence_id}', tags=['Agent'])
def get_champi_evidence_record(evidence_id: str):
    try:
        item = get_champi_evidence(evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail='CHAMPI Evidence ID not found')
    return item


@app.get('/api/agent/tw01/catalog', tags=['Agent'])
def get_tw01_catalog():
    return load_catalog()


@app.get('/api/agent/tw01/evidence/{evidence_id}', tags=['Agent'])
def get_tw01_evidence(evidence_id: str):
    item = get_catalog_evidence(evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail='TW-01 Evidence ID not found')
    return item


@app.post('/api/agent/scientific-investigation', response_model=InvestigationResult, tags=['Agent'])
def run_scientific_investigation(request: InvestigationRequest) -> InvestigationResult:
    try:
        result = scientific_investigator.investigate(request)
    except (ScienceSourceUnavailable, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with investigation_results_lock:
        if len(investigation_results) >= 128:
            investigation_results.pop(next(iter(investigation_results)))
        investigation_results[result.investigation_id] = result
    return result


@app.get('/api/agent/scientific-investigation/{investigation_id}/evidence-graph',
         response_model=EvidenceGraph, tags=['Agent'])
def get_investigation_evidence_graph(investigation_id: str) -> EvidenceGraph:
    with investigation_results_lock:
        result = investigation_results.get(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail='Investigation not found in this process')
    return result.evidence_graph


@app.get('/api/agent/status', tags=['Agent'])
def agent_status():
    return {'agent': agent_orchestrator.model.status(), 'demo_available': True,
            'cached_evidence': ScienceEvidenceProvider('cache').status(),
            'spatial_manifest_configured': bool(__import__('os').environ.get('SAR2ACTION_SPATIAL_MANIFEST'))}


@app.get('/api/agent/operations/{session_id}', tags=['Agent'])
def agent_operations(session_id: str):
    if not session_id.replace('-', '').replace('_', '').isalnum() or len(session_id) > 72:
        raise HTTPException(status_code=400, detail='Invalid session ID')
    return {'session_id': session_id, 'events': agent_orchestrator.operations.get(session_id, [])}


@app.post('/api/agent/cancel/{session_id}', tags=['Agent'])
def agent_cancel(session_id: str):
    if not session_id.replace('-', '').replace('_', '').isalnum() or len(session_id) > 72:
        raise HTTPException(status_code=400, detail='Invalid session ID')
    agent_orchestrator.cancel(session_id)
    return {'session_id': session_id, 'status': 'cancellation_requested'}


@app.post('/api/agent/spatial/rank', tags=['Agent'])
def rank_spatial_regions(request: SpatialRequest):
    try:
        return agent_orchestrator.spatial.run(request)
    except SpatialDataUnavailable as exc:
        raise HTTPException(status_code=422, detail={'error_code': 'SPATIAL_DATA_UNAVAILABLE', 'message': str(exc)}) from exc


@app.get('/api/agent/spatial/evidence/{evidence_id}', tags=['Agent'])
def spatial_evidence(evidence_id: str):
    result = agent_orchestrator.spatial.evidence.get(evidence_id)
    if result is None:
        raise HTTPException(status_code=404, detail='Spatial evidence not found')
    return result


class CompareRegionsRequest(BaseModel):
    first_evidence_id: str
    second_evidence_id: str


@app.post('/api/agent/spatial/compare', tags=['Agent'])
def compare_spatial_regions(request: CompareRegionsRequest):
    try:
        return agent_orchestrator.spatial.compare_change_regions(request.first_evidence_id, request.second_evidence_id)
    except SpatialDataUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/agent/investigate', tags=['Agent'])
def investigate_with_agent(request: InvestigateRequest):
    try:
        return agent_orchestrator.investigate(request)
    except SpatialDataUnavailable as exc:
        raise HTTPException(status_code=422, detail={
            'error_code': 'LIVE_SPATIAL_DATA_UNAVAILABLE', 'message': str(exc)}) from exc


@app.post('/api/agent/story', tags=['Agent'])
def build_agent_story(request: AgentStoryRequest):
    try:
        return agent_orchestrator.build_story(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/agent/story/{story_id}', tags=['Agent'])
def get_agent_story(story_id: str):
    result = agent_orchestrator.get_story(story_id)
    if result is None:
        raise HTTPException(status_code=404, detail='Story not found')
    return result


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def get_health() -> HealthResponse:
    """Return service health and frozen scientific metric specification."""
    return science_service.get_health()


class SetDemoModeRequest(BaseModel):
    demo_mode: Literal["LIVE", "CACHED_REAL_DATA"]


@app.post("/api/demo-mode", response_model=HealthResponse, tags=["Health"])
def set_demo_mode(req: SetDemoModeRequest) -> HealthResponse:
    """Switch between `DEMO_MODE = LIVE | CACHED_REAL_DATA` for demo resilience."""
    science_service.set_demo_mode(req.demo_mode)
    return science_service.get_health()


@app.get("/api/cases", response_model=CasesListResponse, tags=["Cases"])
def list_cases() -> CasesListResponse:
    """Return available flagship and engineering validation cases."""
    return CasesListResponse(cases=science_service.get_cases())


@app.get(
    "/api/cases/{case_id}/observations",
    response_model=CaseObservationsResponse,
    tags=["Cases"],
)
def get_case_observations(case_id: str) -> CaseObservationsResponse:
    """Return NISAR GCOV observations, acquisition timestamps, polarizations, maturity, and metadata."""
    return science_service.get_case_observations(case_id)


@app.post("/api/validate-pair", response_model=ValidatePairResponse, tags=["Validation"])
def validate_pair(request: ValidatePairRequest) -> ValidatePairResponse:
    """Run deterministic product-level or catalog-level NISAR scene pair validation."""
    return science_service.validate_pair(request)


@app.post("/api/change/analyze", response_model=AnalyzeChangeResponse, tags=["Change Engine"])
def analyze_change(request: AnalyzeChangeRequest) -> AnalyzeChangeResponse:
    """Execute deterministic windowed NISAR GCOV change analysis over an AOI."""
    return science_service.analyze_change(request)


@app.post(
    "/api/radar-fingerprint",
    response_model=RadarFingerprintResponse,
    tags=["Radar Fingerprint"],
)
def compute_radar_fingerprint(request: RadarFingerprintRequest) -> RadarFingerprintResponse:
    """Compute AOI Radar Fingerprint distributions, epistemic summary, and EvidenceRecord."""
    return science_service.compute_radar_fingerprint(request)


@app.get("/api/evidence/{evidence_id}", response_model=EvidenceRecord, tags=["Evidence"])
def get_evidence_record(evidence_id: str) -> EvidenceRecord:
    """Retrieve a complete persisted EvidenceRecord by ID (`E-...`)."""
    return science_service.get_evidence(evidence_id)


@app.get("/api/layers/{layer_id}", response_model=LayerMetadataResponse, tags=["Layers"])
def get_layer_metadata(layer_id: str) -> LayerMetadataResponse:
    """Retrieve layer type, units, source scenes, timestamps, color interpretation, and limitations."""
    return science_service.get_layer_metadata(layer_id)


@app.get("/api/layers/{layer_id}/image.png", tags=["Layers"])
def get_layer_image(layer_id: str) -> Response:
    """Serve the georeferenced EPSG:4326 RGBA PNG overlay for MapLibre GL JS."""
    png_bytes = science_service.get_layer_png_bytes(layer_id)
    return Response(content=png_bytes, media_type="image/png")


from backend.app.advanced.api_router import create_fastapi_router

app.include_router(create_fastapi_router())


# Serve the built React app (frontend/dist) from the same origin as the API. Mounted last so
# every /api route above takes precedence. Absent in local dev, where Vite serves the frontend.
_frontend_dist = Path(os.environ.get(
    "SAR2ACTION_FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if _frontend_dist.is_dir():
    @app.get("/studio", include_in_schema=False)
    def studio_page() -> FileResponse:
        """Investigation Studio is a client-side page; its JSON assets stay under /studio/."""
        return FileResponse(_frontend_dist / "index.html")

    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
