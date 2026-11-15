# Earth Change Intelligence Platform — Architecture & Overview

## Overview
SAR2Action has been upgraded with the **Earth Change Intelligence Platform**, integrating 8 interactive geospatial intelligence and scientific forensics capabilities directly into the existing React + FastAPI product without breaking existing workflows (`HomeScreen`, `MapScreen`, `CompareScreen`, `AssistScreen`, `InvestigationStudio`, GIS Polygon/TWD97, TW-05, Farmer/Authority, and Model-Free Legal RAG).

## Integrated Modules
1. **Interactive Earth Change Explorer (`EarthChangeExplorer`)**: MapLibre GL JS + 3D Globe synchronization, committed parcel GeoJSON (`YL-CAND-01`..`YL-CAND-06`), global event catalog search/filter, live SAR overlay opacity control, and abortable scientific investigation triggers.
2. **Earth Memory (`EarthMemoryTimeline`)**: Acquisition-based time machine separating real satellite passes from explicit `NO_OBSERVATION` gaps, with UTC + CST (`Asia/Taipei`) timestamps and cross-CRID (`P05023` vs `P05036`) compatibility warnings.
3. **Reality Lens (`RealityLensSelector`)**: Four-mode truth separation (`OBSERVED`, `HYPOTHESES`, `UNKNOWN`, `NEXT_EVIDENCE`) with `no_fake_confidence: true`.
4. **Change Fingerprint (`FingerprintViewer`)**: Multi-temporal VH backscatter signatures, explicit `NOT_AVAILABLE` markers for unmeasured bands (`HH/HV`, `VV`), compatibility-gated parcel comparison, and similarity search.
5. **Scientific Hypothesis Arena (`ScientificHypothesisArena`)**: Live competing hypothesis testing backed by `backend/app/advanced/experimentation` (`default_hypotheses`, `ScientificToolRegistry`, `design_experiment_plans`, `rank_experiment_plans`, `run_single_experiment`, `evaluate_experiment_against_hypothesis`, `apply_evaluations_to_hypotheses`).
6. **Evidence Gap Navigator (`EvidenceGapNavigator`)**: Stage-1 evidence gap planning (`SEARCH / VALIDATE / PLAN / REQUEST_APPROVAL`) powered by `SatelliteCatalogSearcher` with automatic downloads strictly blocked (`download_permitted: false`).
7. **AI Guided Discovery (`GuidedDiscoveryPanel`)**: Context-aware bilingual (`zh` / `en`) natural-language control with Gemini + deterministic fallback, `FARMER` / `AUTHORITY` modes, and 19 allowlisted `AIMapAction`s validated by `AIMapActionValidator`.
8. **Planetary Change Stories (`PlanetaryStoryPlayer`)**: 7-chapter interactive scientific narrative playback with camera/lens synchronization, persistent storage, JSON import/export, and standalone HTML export.

## Backend Entrypoint
- Router mounted in `backend/app/main.py` via `create_earth_intelligence_router()` under `/api/earth/*`.
- Package root: `backend/app/earth_intelligence/`.

## Frontend Entrypoint
- Screen registered in `frontend/src/App.tsx` (`Earth Intelligence` / `地球變化智慧`) with shared state in `frontend/src/earth/EarthContext.tsx`.
- Package root: `frontend/src/earth/`.
