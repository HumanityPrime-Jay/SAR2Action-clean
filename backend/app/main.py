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
from backend.app.api.gis import router as gis_router
from backend.app.schemas.taiwan_agro import (
    TwAgroOverviewResponse,
    TwAgroParcelOpticalMetrics,
    TwAgroReliefCatalog,
    TwAgroReliefEstimateRequest,
    TwAgroReliefEstimateResponse,
)
from backend.app.schemas.tw05_agent import (
    Tw05EvidenceCitation,
    Tw05InvestigationRequest,
    Tw05InvestigationResponse,
)
from backend.app.services.taiwan_agro_service import TaiwanAgroService
from backend.app.services.tw05_agent_adapter import TW05_TOOLS
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

app.include_router(gis_router)
science_service = ScienceService()
taiwan_agro_service = TaiwanAgroService()
agent_orchestrator = AgentOrchestrator(science_service, taiwan_agro_service)
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
    return {
        'agent': agent_orchestrator.model.status(),
        'gemini': agent_orchestrator.gemini_model.status(),
        'demo_available': True,
        'cached_evidence': ScienceEvidenceProvider('cache').status(),
        'spatial_manifest_configured': bool(os.environ.get('SAR2ACTION_SPATIAL_MANIFEST')),
        'tw05_agent_available': True,
        'tw05_tools': list(TW05_TOOLS.keys()),
        'legacy_agent_routes_enabled': True,
    }


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


# --- TW-05: Taiwan Yunlin Agricultural Surface Change Investigation (NISAR x Sentinel-1D) ---


@app.get("/api/tw-agro/overview", response_model=TwAgroOverviewResponse, tags=["TW-05 Agro"])
def get_tw_agro_overview() -> TwAgroOverviewResponse:
    """Return dynamic verified TW-01 (Sentinel-1D) + TW-03 (NISAR) Taiwan agricultural payload."""
    return taiwan_agro_service.get_overview()


@app.get("/api/tw-agro/geojson/{layer_name}", tags=["TW-05 Agro"])
def get_tw_agro_geojson(layer_name: str) -> Response:
    """Serve real GeoJSON boundaries/parcels (`aoi`, `farmland`, `candidate-parcels`, `nisar-aoi`)."""
    raw_bytes = taiwan_agro_service.get_geojson_bytes(layer_name)
    return Response(content=raw_bytes, media_type="application/geo+json")


@app.get("/api/tw-agro/assets/{package_id}/{filename}", tags=["TW-05 Agro"])
def get_tw_agro_asset_png(package_id: str, filename: str) -> Response:
    """Serve real transparent PNG radar overlays from TW-01 and TW-03 packages."""
    png_bytes = taiwan_agro_service.get_asset_png_bytes(package_id, filename)
    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/tw-agro/relief-catalog", response_model=TwAgroReliefCatalog, tags=["TW-07 Relief Estimator"])
def get_tw_agro_relief_catalog() -> TwAgroReliefCatalog:
    """Return versioned statutory cash relief schedule (MOA 115/06/29 Schedule II) and Yunlin announcements."""
    return taiwan_agro_service.get_relief_catalog()


@app.post("/api/tw-agro/relief-estimate", response_model=TwAgroReliefEstimateResponse, tags=["TW-07 Relief Estimator"])
def compute_tw_agro_relief_estimate(request: TwAgroReliefEstimateRequest) -> TwAgroReliefEstimateResponse:
    """Compute Phase 1 conditional statutory relief reference amount with strict epistemic separation."""
    return taiwan_agro_service.compute_relief_estimate(request)


@app.get("/api/tw-agro/parcels/{parcel_feature_id}/optical", response_model=TwAgroParcelOpticalMetrics, tags=["TW-08A Optical QA"])
def get_tw_agro_parcel_optical(parcel_feature_id: int) -> TwAgroParcelOpticalMetrics:
    """Return supplementary Sentinel-2 L2A multi-temporal metrics & QA gate status for one farmland parcel."""
    return taiwan_agro_service.get_parcel_optical_metrics(parcel_feature_id)


@app.post("/api/agent/tw05/investigate", response_model=Tw05InvestigationResponse, tags=["TW-05 Agent"])
def investigate_tw05_endpoint(request: Tw05InvestigationRequest) -> Tw05InvestigationResponse:
    """Run bounded Gemini Function Calling or deterministic tool pipeline over verified TW-05 data."""
    try:
        return agent_orchestrator.investigate_tw05(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/agent/tw05/evidence/{evidence_id}", response_model=Tw05EvidenceCitation, tags=["TW-05 Agent"])
def get_tw05_evidence_endpoint(evidence_id: str) -> Tw05EvidenceCitation:
    """Retrieve a verified TW-05 Evidence record after allowlist and cross-case validation."""
    try:
        item = agent_orchestrator.get_tw05_evidence(evidence_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_OR_CROSS_CASE_EVIDENCE_ID", "message": str(exc)},
        ) from exc
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "TW05_EVIDENCE_NOT_FOUND", "message": "TW-05 Agent Evidence ID not found"},
        )
    return item


from backend.app.advanced.api_router import create_fastapi_router
from backend.app.earth_intelligence import create_earth_intelligence_router

app.include_router(create_fastapi_router())
app.include_router(create_earth_intelligence_router())


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
