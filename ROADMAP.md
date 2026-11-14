# SAR2Action — Engineering Roadmap (Phases 0–10)

> **Build Order:** `DATA → VALIDATION → SCIENCE → EVIDENCE → API → MAP → AGENT → STORY`  
> **Current Mode:** `PROJECT_MODE = PRE_COMPETITION_RND` (Transition to `COMPETITION_BUILD` upon 2026-10-28 full challenge release)

---

## Go / No-Go Engineering Gates

| Gate | Target Milestone | Go / No-Go Criterion | Mandatory Fallback Action |
| :--- | :--- | :--- | :--- |
| **Gate A** | End of Phase 1 (0–6 h in sprint) | At least one candidate AOI has $\ge 2$ scientifically comparable NISAR L-band Level-2 GCOV granules passing `validate_scene_pair`. | If Case A (Indonesia) fails comparability, immediately switch primary case to Case B (California 2026) or Case C (verified surface-change AOI). *Science quality > story preference.* |
| **Gate B** | End of Phase 3 (16 h in sprint) | Change raster ($\Delta\text{HH}, \Delta\text{HV}, |\Delta|$) and ROI statistical summaries match pixel-for-pixel with zero silent `NaN`-to-`0` coercion. | Freeze AI Agent work completely until the deterministic science and masking core passes 100% of unit tests. |
| **Gate C** | End of Phase 7 (28 h in sprint) | *Radar Reveal*, *Radar Fingerprint*, *Evidence Ledger*, and *Claim-to-Pixel* navigation are interactive and stable. | Drop complex story transition animations; ship clean static/stepped 5-scene cards with full Claim-to-Pixel links. |
| **Gate D** | End of Phase 8 (36 h in sprint) | Single-orchestrator AI Investigator achieves 100% `evidence_id` citation fidelity and 0% hallucinated numbers or forbidden causal claims across 20 test queries. | Switch default Investigator UI to deterministic Guided Investigation Workflows + pre-validated Evidence Cards so AI instability never compromises the demo. |

---

## Phase 0 — Audit, Architecture & Environment Setup (Current Phase)

- **Input:**
  - Master proposal `D:\NASA\NASA計劃書.docx`
  - Existing workspace `D:\NASA` and host Windows Python 3.13 / Node.js v24 environment
- **Output:**
  - `docs/development-log/INITIAL_AUDIT.md`
  - `ARCHITECTURE.md`
  - `SCIENCE_CONTRACT.md`
  - `EVIDENCE_SCHEMA.md` & Pydantic v2 implementation (`backend/app/schemas/evidence.py`)
  - `ROADMAP.md`
  - `docs/science/GATE_A_PLAN.md` & `docs/decisions/OPEN_QUESTIONS.md`
  - Clean `SAR2Action/` scaffold, `.gitignore`, `pyproject.toml`, and passing schema unit tests
- **Tests:**
  - `pytest tests/backend/test_evidence_schema.py` verifying schema invariants, null-polarization safety, and epistemic status rules
- **Scientific Acceptance Criteria:**
  - `SCIENCE_CONTRACT.md` explicitly codifies GCOV $\gamma^0$ physical meaning, decibel math, nodata propagation, null-polarization handling, `CHANGE != CAUSE`, and the 4 epistemic states (`OBSERVED`, `COMPARABLE`, `LIMITED`, `INSUFFICIENT_EVIDENCE`).
- **Fallback Plan:**
  - If any Windows binary dependency (`h5py`, `asf_search`) fails to install in `.venv`, use prebuilt `pip --only-binary :all:` wheels on Python 3.13.

---

## Phase 1 — NISAR Data Discovery & Gate A Verification

- **Input:**
  - Candidate AOI bounding boxes:
    1. **Case A:** Indonesia wildfire / peatland-related region (Sumatra / Kalimantan)
    2. **Case B:** 2026 California wildfire-related region
    3. **Case C:** High-signal NISAR L-band GCOV repeat-pass surface-change region
  - ASF DAAC / NASA Earthdata CMR search parameters for `NISAR_L2_GCOV` (including provisional/commissioned science and official sample products)
- **Output:**
  - `data/scenes/scene_manifest.json` recording for every candidate: AOI, granule ID, acquisition UTC, orbit/track/frame, look direction, available polarizations (`HHHH`, `HVHV`, `VVVV`), product maturity, `CRID`, grid spacing, spatial coverage, known quality issues, compatibility result, and rejection reason if rejected.
  - Local GCOV HDF5 metadata inspection report (`docs/sources/GATE_A_MANIFEST_REPORT.md`).
- **Tests:**
  - `pytest tests/sar/test_catalog_manifest.py` validating manifest schema completeness and HDF5 group/dataset path inspection (`/science/LSAR/GCOV/grids/frequencyA/...`).
- **Scientific Acceptance Criteria:**
  - Primary case selected strictly on having $\ge 2$ repeat-pass NISAR L-band GCOV observations with matching frequency band, shared diagonal polarization(s), compatible viewing geometry, and high valid-pixel overlap.
- **Fallback Plan:**
  - If Case A lacks $\ge 2$ comparable scenes, promote Case B; if Case B also lacks coverage, promote Case C. Never fabricate synthetic satellite scenes or use optical data masquerading as NISAR.

---

## Phase 2 — Deterministic Scene Pair Validator (`sar/validation`)

- **Input:**
  - Two NISAR GCOV scene metadata/grid descriptors (`scene_a`, `scene_b`) and target `aoi` geometry (GeoJSON / `shapely` polygon).
- **Output:**
  - Deterministic function `validate_scene_pair(scene_a, scene_b, aoi) -> ScenePairValidationResult`.
  - Automated gate blocking any downstream change calculation when `compatible == False`.
- **Tests:**
  - `pytest tests/sar/test_pair_validator.py` testing:
    - Valid repeat-pass pair $\rightarrow$ `compatible=True, science_status="COMPARABLE"`
    - Identical timestamp $\rightarrow$ rejected (`INSUFFICIENT_EVIDENCE`)
    - Zero polarization intersection (e.g., `HH` vs `VV`) $\rightarrow$ rejected (`INSUFFICIENT_EVIDENCE`)
    - Opposite look direction / pass direction $\rightarrow$ rejected (`INSUFFICIENT_EVIDENCE`)
    - Insufficient valid pixel overlap ($< 10\%$) $\rightarrow$ rejected (`INSUFFICIENT_EVIDENCE`)
    - Partial overlap ($10\%\text{–}50\%$) or single-pol intersection $\rightarrow$ `compatible=True, science_status="LIMITED"` with explicit warnings.
- **Scientific Acceptance Criteria:**
  - 100% deterministic rejection of physically or geometrically non-comparable pairs; zero possibility of LLM or API override when `compatible == False`.
- **Fallback Plan:**
  - If two scenes have minor grid offset within the same UTM zone, reproject/align onto the $T_0$ reference grid via `rasterio.warp` and record `"grid_resampled_to_reference"` in `limitations`.

---

## Phase 3 — Radiometric Change & Statistics Engine (`sar/change`, `sar/statistics`)

- **Input:**
  - Validated GCOV scene pair ($T_0, T_1$) passing `validate_scene_pair`, plus optional user ROI geometry.
- **Output:**
  - Aligned float32 GeoTIFF/COG layers in `data/processed/`:
    - $B(T_0, p) = 10\log_{10}(P(T_0, p))$
    - $B(T_1, p) = 10\log_{10}(P(T_1, p))$
    - $\Delta(p) = B(T_1, p) - B(T_0, p)$
    - $|\Delta(p)|$
    - Optional $D = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}|$ (*Combined Radar Change*) when both `HH` and `HV` exist
    - Explicit Uncertainty / Validity Mask raster (`OBSERVED`, `COMPARABLE`, `LIMITED`, `INSUFFICIENT_EVIDENCE`)
  - Deterministic ROI summary statistics (`DistributionStatsDb`, pixel counts, coverage ratios).
- **Tests:**
  - `pytest tests/sar/test_change_math.py` and `pytest tests/sar/test_roi_statistics.py`:
    - Known synthetic power arrays ($P(T_0)=0.1 \rightarrow -10\text{ dB}$, $P(T_1)=0.05 \rightarrow -13.0103\text{ dB}$, $\Delta = -3.0103\text{ dB}$).
    - Non-positive power ($P \le 0$), `NaN`, `_FillValue`, and shadow/layover mask propagation to `NaN` (never `0.0`).
    - Bit-for-bit repeatability on identical inputs (**Gate B**).
- **Scientific Acceptance Criteria:**
  - Pixel-level decibel math and ROI statistics are 100% reproducible, sign-agnostic magnitude is preserved alongside signed $\Delta$, and missing data is never conflated with zero change.
- **Fallback Plan:**
  - If full-scene NISAR granules exceed memory budgets during interactive slicing, pre-crop AOI tiles during ingestion so runtime ROI queries operate on memory-mapped windowed rasters in $< 200\text{ ms}$.

---

## Phase 4 — Evidence Engine & Provenance Ledger (`backend/app/evidence`, `sar/provenance`)

- **Input:**
  - Outputs from `validate_scene_pair`, `compute_change_map`, and `summarize_selection` / `get_radar_fingerprint`.
- **Output:**
  - Persistent JSON Evidence Ledger (`data/cache/evidence_store.json`) and lookup service (`EvidenceStore`) minting immutable `EvidenceRecord` objects (`E-0001`, `E-0002`, ...) with full provenance metadata (`CRID`, acquisition UTCs, EPSG, pixel spacing, algorithm version, limitations).
- **Tests:**
  - `pytest tests/backend/test_evidence_store.py` verifying CRUD persistence, deterministic ID resolution, and full Claim-to-Pixel provenance reconstruction.
- **Scientific Acceptance Criteria:**
  - Every `EvidenceRecord` contains sufficient metadata to reconstruct the exact scene pair, AOI geometry, polarization, $T_0 / T_1 / \Delta$ statistics, valid pixel count, and processing version.
- **Fallback Plan:**
  - In-memory + atomic JSON file write store is zero-dependency and crash-safe; no database server required.

---

## Phase 5 — FastAPI Deterministic Backend (`backend/app/api`)

- **Input:**
  - HTTP requests from the WebGIS frontend and tool calls from the single AI orchestrator.
- **Output:**
  - FastAPI application serving:
    - `GET /api/v1/aois`
    - `GET /api/v1/aois/{aoi_id}/scenes`
    - `POST /api/v1/pairs/validate`
    - `POST /api/v1/change/compute`
    - `POST /api/v1/fingerprint`
    - `GET /api/v1/evidence/{evidence_id}`
    - `GET /api/v1/tiles/...` or static COG/PNG overlay endpoints with world/bounds metadata.
- **Tests:**
  - `pytest tests/backend/test_api_endpoints.py` using FastAPI `TestClient` to verify status codes, schema conformance, and rejection of incompatible scene pairs.
- **Scientific Acceptance Criteria:**
  - Every quantitative API response includes a valid `evidence_id` and `ScienceQualityStatus`; incompatible pairs return a structured refusal (`INSUFFICIENT_EVIDENCE`).
- **Fallback Plan:**
  - Serve pre-rendered PNG/WebP colormapped overlays with exact WGS84 bounding-box coordinates alongside raw float GeoTIFF statistics if dynamic tile rendering adds latency.

---

## Phase 6 — Experience 1: Radar Reveal UI (`frontend/src/radar-reveal`, `frontend/src/map`)

- **Input:**
  - FastAPI scene pair metadata, raster overlays, and validity masks.
- **Output:**
  - 2D MapLibre GL JS interface providing:
    - `T0` & `T1` GCOV $\gamma^0$ (dB) views
    - Interactive split-screen swipe (`T0 ↔ T1`)
    - Positive change ($+\Delta$), negative change ($-\Delta$), and sign-agnostic magnitude ($|\Delta|$) views
    - Distinct visual treatment for **Invalid / Missing / Insufficient Evidence** areas
    - Scene pair compatibility status badge
    - Toggleable External Context Layer (`ENABLE_EXTERNAL_CONTEXT`).
- **Tests:**
  - Component & state tests verifying legend labels use `Radar-Observed Change (dB)` and never display `Burn Severity`, `Fire Risk`, or `Damage Probability`.
- **Scientific Acceptance Criteria:**
  - Non-SAR users can visually distinguish positive change, negative change, stable comparable areas, and missing/non-comparable regions within 10 seconds.
- **Fallback Plan:**
  - If WebGL custom shader swipe has browser quirks, use MapLibre dual-map synchronized canvas or clip-path slider (`Gate C`).

---

## Phase 7 — Experience 2: Radar Fingerprint UI (`frontend/src/radar-fingerprint`)

- **Input:**
  - User map click (point buffer), drawn polygon, or predefined ROI selection.
- **Output:**
  - Right-hand **Radar Fingerprint** panel displaying:
    - *What changed? How much? Can we trust this comparison?*
    - `T0 UTC`, `T1 UTC`, available polarizations
    - `HH T0`, `HH T1`, `ΔHH`, `|ΔHH|`
    - `HV T0`, `HV T1`, `ΔHV`, `|ΔHV|` (or explicit `HV: Unavailable in this scene pair` badge when `hv == null`)
    - Valid pixel count, comparable coverage %, missing-data %
    - Linked `evidence_id` pill and the 3 structured epistemic cards (*What We Observed*, *Possible Interpretation*, *What We Do Not Know*).
- **Tests:**
  - UI & schema integration tests with both dual-pol (`HH+HV`) and single-pol (`HH`-only) fixtures to prove zero crashes and zero fabricated values when `HV` is `null`.
- **Scientific Acceptance Criteria:**
  - Numbers displayed in the Radar Fingerprint UI match the backing `EvidenceRecord` in `evidence_store.json` to the exact decimal place.
- **Fallback Plan:**
  - Pre-compute fingerprints for 3–5 curated benchmark ROIs in addition to live arbitrary polygon drawing so live demo latency is guaranteed $< 50\text{ ms}$.

---

## Phase 8 — Single-Orchestrator AI Investigator & Guardrails (`backend/app/tools`, `frontend/src/agent`)

- **Input:**
  - User natural-language question (e.g., *"What happened here?"*, *"Is this wildfire damage?"*, *"Can we compare these two scenes?"*) and current map selection state.
- **Output:**
  - Single-agent orchestrator invoking deterministic Python tools (`list_nisar_observations`, `validate_scene_pair`, `compute_change_map`, `summarize_selection`, `get_radar_fingerprint`, `inspect_provenance`, `set_map_view`, `build_evidence_story`) and returning a structured `AgentInvestigationResponse` with four mandatory sections:
    1. **Observation**
    2. **Possible interpretation**
    3. **Unknown / limitation**
    4. **Evidence (`[E-xxxx]`)**
- **Tests:**
  - `pytest tests/agent/test_agent_guardrails.py`:
    - 20 benchmark user questions (100% of quantitative claims must cite a valid `evidence_id`).
    - 10 scientific trap questions (*"How many hectares burned?"*, *"Is underground peat burning?"*, *"Has the forest recovered?"*) — must explicitly refuse causal overreach and state: `Current evidence is insufficient to support that conclusion.`
- **Scientific Acceptance Criteria:**
  - Zero hallucinated dB values, dates, areas, scene IDs, or causal wildfire claims.
- **Fallback Plan:**
  - **Gate D Fallback:** If live LLM latency or API connectivity degrades during the demo, seamlessly fall back to a deterministic template-backed Investigator engine that calls the exact same 8 Python tools and formats the 4-section epistemic response deterministically.

---

## Phase 9 — Experience 3: Five-Scene Evidence Story & Claim-to-Pixel (`frontend/src/story`)

- **Input:**
  - Set of verified `EvidenceRecord` IDs from the user's investigation session.
- **Output:**
  - Interactive 5-scene **Evidence Story**:
    - **Scene 1 — Before:** $T_0$ NISAR GCOV observation, acquisition UTC, product metadata, AOI.
    - **Scene 2 — The Shift:** *Radar Reveal* showing $+\Delta$, $-\Delta$, $|\Delta|$, and unknown mask.
    - **Scene 3 — Investigate:** Selected anomaly ROI and its *Radar Fingerprint*.
    - **Scene 4 — What We Know / What We Don't Know:** Side-by-side Evidence Ledger & explicit epistemic boundary summary.
    - **Scene 5 — Evidence Story:** Shareable interactive summary where clicking any `[E-xxxx]` claim zooms the map to the ROI, activates the exact scene pair and polarization layer, and opens the provenance card (**One claim → One evidence trail**).
- **Tests:**
  - End-to-end verification that every `EvidenceClaim` in all 5 scenes resolves to an existing `EvidenceRecord` in `evidence_store.json` and restores the exact map view state.
- **Scientific Acceptance Criteria:**
  - 100% of quantitative statements in the story are backed by clickable `evidence_id` links; zero unlinked claims.
- **Fallback Plan:**
  - Allow exporting the 5-scene Evidence Story as a self-contained static JSON/HTML bundle for offline judge review.

---

## Phase 10 — End-to-End Verification, Usability Testing & Competition Lock

- **Input:**
  - Complete SAR2Action stack running against the Gate A verified NISAR GCOV dataset.
- **Output:**
  - Full automated test suite report (`pytest`)
  - 5-user non-SAR usability test log (*Find change*, *Interpret change*, *Inspect evidence*, *Explain unknown*, *Generate story*)
  - 3-minute pitch script & demo walkthrough aligned with `NASA計劃書.docx` Section 31.
- **Tests:**
  - Full regression suite (`pytest`) + 20 Agent fidelity queries + 10 scientific boundary trap tests.
- **Scientific Acceptance Criteria:**
  - Passes all four acceptance pillars in `NASA計劃書.docx` Section 30 (*Science repeatability*, *Data QA rejection of bad pairs*, *100% Agent evidence_id fidelity*, *Scientific Boundary trap refusal*, and *Non-SAR Usability*).
- **Fallback Plan:**
  - Feature freeze at hour 42 (`LOCK`); record local offline cache of all processed rasters and evidence ledger entries so the live demo operates with zero external network dependency.
