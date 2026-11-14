# ADR-0001: Phase 0 Architectural & Scientific Foundation Decisions

- **Date:** 2026-10-23
- **Status:** Accepted
- **Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`

---

## Context
We are building the technical foundation for **SAR2Action — NISAR Earth Change Intelligence** ahead of the full NASA Space Apps 2026 challenge release on 2026-10-28, guided by `D:\NASA\NASA計劃書.docx`.

## Decisions Made

1. **Science-Outward Engineering Order:**
   We enforce the strict build order `DATA → VALIDATION → SCIENCE → EVIDENCE → API → MAP → AGENT → STORY`. No AI or UI layer may synthesize or bypass scientific validation.
2. **Deterministic Scene Pair Gate (`validate_scene_pair`):**
   Every multi-temporal operation is gated by a deterministic compatibility check. If `compatible == False`, `science_status` is set to `INSUFFICIENT_EVIDENCE` and change computation stops immediately.
3. **Sign-Agnostic Radiometric Change Math:**
   We compute both signed change $\Delta(p) = B(T_1, p) - B(T_0, p)$ and sign-agnostic magnitude $|\Delta(p)|$ on valid positive $\gamma^0$ power ($P > 0$), plus optional $D = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}|$ labeled strictly as `Combined Radar Change` (*custom visualization metric — not a hazard score or official burn-severity index*).
4. **Null-Safe Polarization Handling:**
   Schemas (`EvidenceRecord`, `RadarFingerprint`) and UI components explicitly represent unavailable polarizations as `None` / `null` (`HV unavailable`) and never interpolate or fabricate missing channels.
5. **Single Orchestrator Agent + Deterministic Tools:**
   We reject multi-agent swarms and arbitrary code-execution tools. A single orchestrator LLM invokes 8 deterministic Python tools and formats responses into 4 mandatory sections (*Observation*, *Possible Interpretation*, *Unknown / Limitation*, *Evidence*).
6. **File/JSON Evidence Ledger & 2D MapLibre GL JS Stack:**
   We avoid unnecessary PostGIS or 3D globe complexity in MVP, using a deterministic JSON Evidence Store (`evidence_store.json`), pre-compiled Windows geospatial wheels (`rasterio`, `geopandas`, `shapely`, `pyproj`, `h5py`), FastAPI, and 2D MapLibre GL JS.
