"""FastAPI router for Earth Change Intelligence Platform."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.app.earth_intelligence.arena_gaps import EvidenceGapNavigator, HypothesisArenaService
from backend.app.earth_intelligence.catalog import EarthMemoryService, GlobalEventCatalog
from backend.app.earth_intelligence.discovery_story import EarthStoryService, GuidedDiscoveryService
from backend.app.earth_intelligence.lens_fingerprint import (
    RealityLensService,
    ScientificFingerprintService,
)
from backend.app.earth_intelligence.schemas import (
    CatalogSearchRequest,
    CatalogSearchResponse,
    EarthMemoryTimelineResponse,
    EarthStory,
    EvidenceGapResponse,
    FingerprintCompareRequest,
    FingerprintCompareResponse,
    GenerateStoryRequest,
    GlobalEventCatalogResponse,
    GuidedDiscoveryRequest,
    GuidedDiscoveryResponse,
    HypothesisArenaResponse,
    LensMode,
    RealityLensResponse,
    RunHypothesisExperimentRequest,
    RunHypothesisExperimentResponse,
    SimilarChangeResponse,
    StoryImportRequest,
    SurfaceFingerprint,
)


def create_earth_intelligence_router() -> APIRouter:
    router = APIRouter(prefix="/api/earth", tags=["Earth Change Intelligence"])

    catalog = GlobalEventCatalog()
    memory = EarthMemoryService(catalog)
    lens_svc = RealityLensService(catalog)
    fp_svc = ScientificFingerprintService(catalog)
    arena_svc = HypothesisArenaService(catalog)
    gap_svc = EvidenceGapNavigator(catalog)
    discovery_svc = GuidedDiscoveryService(catalog)
    story_svc = EarthStoryService(catalog, memory, arena_svc, gap_svc)

    @router.get("/events", response_model=GlobalEventCatalogResponse)
    def list_global_events(event_type: str | None = None, q: str | None = None) -> GlobalEventCatalogResponse:
        return catalog.list_events(event_type=event_type, q=q)

    @router.get("/events/{event_id}/timeline", response_model=EarthMemoryTimelineResponse)
    def get_event_timeline(event_id: str, field_id: str | None = None) -> EarthMemoryTimelineResponse:
        return memory.get_timeline(event_id=event_id, field_id=field_id)

    @router.get("/events/{event_id}/lens/{lens}", response_model=RealityLensResponse)
    def get_reality_lens(event_id: str, lens: LensMode, field_id: str | None = None) -> RealityLensResponse:
        return lens_svc.get_lens(event_id=event_id, lens=lens, field_id=field_id)

    @router.get("/fingerprint/{region_id}", response_model=SurfaceFingerprint)
    def get_surface_fingerprint(region_id: str) -> SurfaceFingerprint:
        fp = fp_svc.get_fingerprint(region_id)
        if fp is None:
            raise HTTPException(status_code=404, detail={"error_code": "FINGERPRINT_NOT_FOUND", "message": f"Unknown region_id: {region_id}"})
        return fp

    @router.post("/fingerprint/compare", response_model=FingerprintCompareResponse)
    def compare_fingerprints(req: FingerprintCompareRequest) -> FingerprintCompareResponse:
        return fp_svc.compare(req)

    @router.get("/fingerprint/{region_id}/similar", response_model=SimilarChangeResponse)
    def find_similar_changes(region_id: str) -> SimilarChangeResponse:
        return fp_svc.find_similar(region_id)

    @router.get("/hypotheses/{event_id}", response_model=HypothesisArenaResponse)
    def get_hypothesis_arena(event_id: str, field_id: str = "YL-CAND-03") -> HypothesisArenaResponse:
        return arena_svc.get_arena(event_id=event_id, field_id=field_id)

    @router.post("/hypotheses/experiment", response_model=RunHypothesisExperimentResponse)
    def run_hypothesis_experiment(req: RunHypothesisExperimentRequest) -> RunHypothesisExperimentResponse:
        return arena_svc.run_experiment(req)

    @router.get("/evidence-gaps/{event_id}", response_model=EvidenceGapResponse)
    def get_evidence_gaps(event_id: str, field_id: str = "YL-CAND-03") -> EvidenceGapResponse:
        return gap_svc.get_gaps(event_id=event_id, field_id=field_id)

    @router.post("/evidence-gaps/catalog-search", response_model=CatalogSearchResponse)
    def search_official_catalog(req: CatalogSearchRequest) -> CatalogSearchResponse:
        return gap_svc.search_catalog(req)

    @router.post("/guided-discovery", response_model=GuidedDiscoveryResponse)
    def guided_discovery(req: GuidedDiscoveryRequest) -> GuidedDiscoveryResponse:
        return discovery_svc.discover(req)

    @router.post("/stories/generate", response_model=EarthStory)
    def generate_earth_story(req: GenerateStoryRequest) -> EarthStory:
        return story_svc.generate(req)

    @router.post("/stories/import", response_model=EarthStory)
    def import_earth_story(req: StoryImportRequest) -> EarthStory:
        try:
            return story_svc.import_story(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/stories/{story_id}", response_model=EarthStory)
    def get_earth_story(story_id: str) -> EarthStory:
        story = story_svc.get_story(story_id)
        if story is None:
            raise HTTPException(status_code=404, detail={"error_code": "STORY_NOT_FOUND", "message": "Story not found"})
        return story

    @router.get("/stories/{story_id}/export.html")
    def export_earth_story_html(story_id: str) -> Response:
        doc = story_svc.export_html(story_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Story not found")
        return Response(content=doc, media_type="text/html; charset=utf-8")

    return router
