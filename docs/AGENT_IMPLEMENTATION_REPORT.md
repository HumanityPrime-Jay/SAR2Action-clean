# SAR2Action D-team implementation report — 2026-11-12

> Phase 8 update (2026-11-13): [PHASE8_REAL_EVIDENCE_VALIDATION.md](PHASE8_REAL_EVIDENCE_VALIDATION.md) supersedes the Phase 7 cache-availability statement. B-team's three science JSON stores are now present; internal schema and cross-file validation passed, and Gemini completed a real cached-evidence investigation. External source HDF5 verification and real subregion ranking remain blocked. Earlier sections are historical snapshots.

> Phase 7 update: [PHASE7_GEMINI_NISAR_INTEGRATION.md](PHASE7_GEMINI_NISAR_INTEGRATION.md) reports the secure backend-only Gemini provider, real model tool calling, read-only ScienceEvidenceProvider, synthetic browser demo, and blocked B-team cache handoff. Gemini `gemini-3.1-flash-lite` was verified through real function calling; the six claimed B-team Evidence IDs were not verified because the three cache files are absent. Earlier sections are historical snapshots.

> Phase 6 update: [PHASE6_REAL_DATA_INTEGRATION.md](PHASE6_REAL_DATA_INTEGRATION.md) is the current handoff and demo-readiness report. B-team catalog metadata, QA sidecars and masks exist, but the signed change GeoTIFF, live manifest and full GCOV source pixels are absent. Live NISAR remains **BLOCKED**; the synthetic real-model demo remains operational. Final Phase 6 verification: 85 Python passed/6 skipped, frontend 9 passed, Chrome 3 passed, Q1–Q5 HTTP 5/5. Earlier sections are historical snapshots.

> Phase 5 update: [PHASE5_SCIENTIFIC_AGENT_VALIDATION.md](PHASE5_SCIENTIFIC_AGENT_VALIDATION.md) is the current scientific agent, runtime and test report. The real model now produces an evidence-bound Observed/Inferred/Unknown assessment and a visible investigation plan. Final Phase 5 verification: 83 Python passed/6 skipped, frontend 9 passed, Chrome 3 passed, 17/17 new real-model scenarios. No real NISAR change raster is present; Hermes chat remains blocked by actual 4,096-token server context. Earlier sections are historical snapshots.

> Phase 4 update: [PHASE4_REAL_AGENT_VALIDATION.md](PHASE4_REAL_AGENT_VALIDATION.md) supersedes the runtime and test status below. A real local Gemma model now selects restricted GIS tools through llama.cpp; Hermes Gateway health passes but Hermes chat inference is blocked by its 64K minimum context. The Phase 4 real-model benchmark completed 19/19 core synthetic-data tasks. No live NISAR handoff was available. The Phase 1–3 sections below are historical snapshots.

> Phase 3 update: see [PHASE3_VALIDATION_REPORT.md](PHASE3_VALIDATION_REPORT.md) for the executed host, HTTP and Chrome results. The Phase 1/2 status and test counts below are historical; Phase 3 adds explicit synthetic ranking in the root UI, automatic map/evidence/fingerprint synchronization, a schema-checked optional model function-call adapter, coverage/geodesic-area gates, a Windows demo launcher and updated test totals. Hermes remains offline without a configured, restricted model endpoint.

## Scope and initial state

The project has two separate applications. `SAR2Action_Agent_MVP` is a runnable synthetic D-team reference with FastAPI, deterministic radar analysis, evidence IDs, a schematic map, and five story frames. The repository root has the team's React/MapLibre UI and a separate FastAPI NISAR science service. No `.git` directory was present in either folder, so `git status` could not run and no branch or commit was created. Existing files and local data were preserved.

The root science service has case metadata and deterministic analysis code, but this workspace contains no `data/raw/scenes/*.h5` files and no persisted `data/cache` analysis. Thus the root app cannot demonstrate a real NISAR measurement here. The root integration refuses unsupported analysis instead of substituting the synthetic MVP data.

## A. Files changed

- `backend/app/services/agent_orchestrator.py` — new single orchestrator over the root science service.
- `backend/app/main.py` — agent investigation and story endpoints.
- `frontend/src/components/AgentPanel.tsx` — context-aware investigator, evidence actions, trace, story navigation and export.
- `frontend/src/App.tsx` — mounts the panel and prevents stale AOI fingerprint responses from overwriting current results.
- `frontend/src/styles.css` — investigator layout and keyboard focus styling.
- `tests/agent/test_orchestrator.py` — deterministic flow, QA, evidence forgery, stale story and AOI validation checks.
- `README.md` — links the integration status and this report.
- `SAR2Action_Agent_MVP/frontend/index.html`, `backend/app/main.py`, `backend/app/agent.py` — explicit permanent simulated-data notice.
- This report.

## B. Implemented behavior and limits

The root `/api/agent/investigate` endpoint accepts case, AOI, optional polarization, session and question. It calls the existing scene-pair validator, then the existing deterministic Radar Fingerprint API. It accepts claims only from that API and checks evidence ID, scene IDs, pixel count and units against the persisted evidence record. It returns typed, allowlisted map actions for the actual AOI and registered layer. No model-generated code, shell command or free-form tool name is executed.

The React investigator reads current case, AOI and polarization. It can run/cancel an analysis request, show the actual returned tool trace, open an evidence claim, focus the AOI, switch registered layers and generate a five-scene story. A story is marked stale on context changes in the UI and on subsequent session changes in the backend. Story JSON can be exported. Fingerprint requests use a monotonically increasing request ID so a slower prior AOI response cannot replace newer data.

The root agent currently uses deterministic intent handling and narration. It is **not** a verified Hermes-powered agent. Its trace records completed tools after the response; live streamed progress and server-side cancellation/timeouts remain unimplemented. Its session/story store is in process memory. The existing standalone MVP remains the offline synthetic demo; it has a schematic canvas rather than C's MapLibre map.

## C. Hermes status

Official project: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). [Official releases](https://github.com/NousResearch/hermes-agent/releases) list v0.23.1 as the latest stable release checked today. [Windows installation documentation](https://hermes-agent.nousresearch.com/docs/getting-started/installation) supports native Windows; WSL2 is also documented. Local global `hermes` is v0.14.0; the isolated `D:\SAR2Action\venv_hermes` has v0.19.0 on Python 3.11.9. `venv_hermes\Scripts\hermes.exe doctor` completed and `gateway status` reported stopped. There is no configured model, provider credential, or isolated tool-deny profile. Attempting `pip install hermes-agent==0.23.1` in `venv_hermes` failed because package-index DNS resolution was unavailable. No model call, gateway `/v1/models` call or denied-tool test succeeded. Hermes is disabled in the application. The MVP's optional adapter remains default-off; do not set `HERMES_SAFE_PROFILE_VERIFIED` until the gateway's terminal/file/web/browser/skills permissions have been independently disabled and tested.

## D. Start commands

Root app, after installing project dependencies in a working Python environment and supplying valid NISAR HDF5 files or validated caches:

```powershell
cd D:\SAR2Action
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The root Vite proxy points `/api` at port 8000. The root `.venv` points to a missing Python 3.13 installation; `venv` is the working Python 3.11 environment used for the targeted tests here.

Standalone synthetic demo:

```powershell
cd D:\SAR2Action\SAR2Action_Agent_MVP
$env:PYTHONPATH='backend'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The fixed banner reads **SIMULATED DATA — NOT NASA OBSERVATIONS**.

## E. Verification performed

- Baseline root React `npm run build`: passed.
- After integration, root `npm run build`: passed (TypeScript and Vite; 500 kB bundle-size warning).
- Root `npm test -- --reporter=dot`: 6 tests passed.
- Root `venv\Scripts\python.exe -m pytest tests/agent tests/backend/test_evidence_schema.py tests/sar -q`: 49 passed, 1 skipped. This includes 12 targeted agent/evidence tests and 14 scene catalog/pair tests.
- `venv\Scripts\python.exe -m py_compile` of the new backend files: passed.
- MVP `node --check frontend/app.js` and Python `compileall`: passed.
- MVP direct deterministic smoke: compatible pair, HV median delta +2.064 dB, evidence `SYN-0A8862623DBDD326`, five current story frames. These are **synthetic fixture values**, not NASA observations.
- MVP invalid live-manifest check: setting `SAR2ACTION_LIVE_MANIFEST` to a missing file raised `DataUnavailable`; no synthetic fallback occurred.
- Root full `pytest tests -q`, MVP FastAPI `TestClient`, local Uvicorn HTTP and browser interaction checks could not complete: this sandbox denies local socket access. Python's Windows asyncio event-loop initialization blocks in `socketpair`; `127.0.0.1:8765` returned a socket permission error. These are unverified, not passing tests.
- Running root tests with global Python 3.11 initially failed collection because that environment lacks `h5py` and `asf_search`; the project `venv` has them.

## F. Tool call example

```json
{"case_id":"case-flagship-oki-f2","aoi_bbox_wgs84":[105.28,-3.28,105.48,-3.08],"query":"Find the largest radar change","session_id":"demo-1"}
```

The orchestrator trace has `list_nisar_observations`, `validate_scene_pair`, `get_radar_fingerprint`, `inspect_provenance`, and `dispatch_map_actions`. Actual root values require local HDF5 data. The synthetic MVP direct smoke produced the evidence ID shown above; do not use that ID as real NISAR evidence.

## G. Evidence ledger example

The synthetic MVP evidence `SYN-0A8862623DBDD326` links its AOI, two synthetic scene IDs and timestamps, HV polarization, deterministic pairwise dB method, valid-pixel QA and explicit causal limitations. Its measured +2.064 dB median difference came from fixture arrays. The root agent only emits science-service claims if their evidence ID, source scene IDs, valid pixel count and units match its persisted evidence record.

## H. Story example

The root agent story contains **The Region**, **The Change**, **The Evidence**, **What We Know**, and **Why It Matters**. Each frame includes a narrative, AOI/map layer state, evidence ID, visualization type and source scene IDs. Clicking a frame changes the registered map layer; changing the AOI marks the story stale. The root story flow is unit-tested with a fake science service but has not been browser-tested with real NISAR data in this sandbox.

## I. Real NISAR handoff

For the standalone D-team adapter, ask B for two quality-masked, co-registered EPSG:4326 GeoTIFFs of one calibrated GCOV polarization and A-approved metadata. Run `python scripts/ingest_nisar_geotiff_pair.py --help` from `SAR2Action_Agent_MVP`, then supply actual scene IDs, UTC times, granules, orbit track, look, CRID, maturity, polarization and `--input-units power|db`. The importer converts positive linear power to dB via `10*log10(P)` and rejects grid mismatch. Point `SAR2ACTION_LIVE_MANIFEST` to the generated manifest before starting the MVP. An invalid manifest fails startup; it never falls back to synthetic data.

For the root production app, place B's validated original NISAR GCOV HDF5 files under `data/raw/scenes` with exact scene IDs from the catalog, run existing pair QA and fingerprint endpoints, then inspect the evidence record and map overlays. Do not label root results as operational until A validates radiometry, masks, orbit/geometry, temporal comparability and causal wording.

## J. Remaining risks and priorities

1. Supply and validate real NISAR HDF5 scenes. Root end-to-end science analysis cannot be demonstrated without them.
2. Re-run backend API, live HTTP and browser interaction tests on a host allowing local sockets. Verify map camera, evidence click, five story scenes and export.
3. Update and configure Hermes in its isolated environment, then prove tool denial before enabling any model inference. Current installed versions have unrestricted built-in terminal/file tools by default.
4. Add server-side request timeouts/cancellation, durable session/story persistence and live progress events if needed for a public deployment.
5. Implement a scientifically valid maximum-change subregion search when B exposes georeferenced per-pixel statistics. The current investigator analyzes the selected AOI and focuses it; it cannot truthfully identify the greatest-change location within that AOI yet.
6. Perform A/B/C integration review. The root API and C's MapLibre component were preserved, but no Git history exists here to identify teammate ownership or review a commit diff.

---

## Phase 2 update — 2026-11-12

### IMPLEMENTED

- Added `backend/app/services/spatial_ranking.py`: explicit `fixture` or `live` mode, four-neighbour connected components, magnitude/validity mask gates, minimum pixel and approximate area gates, deterministic ranking, WGS84 candidate bboxes, evidence IDs, pairwise comparison and safe focus action. A single isolated extreme pixel is excluded. The fixture generates three spatial patches and is permanently labelled **SIMULATED DATA — NOT NASA OBSERVATIONS**.
- Added a strict [B→D spatial raster manifest](SPATIAL_RANKING_CONTRACT.md). Live mode requires aligned EPSG:4326 signed dB change and valid-mask GeoTIFFs, SHA-256 checksums, scene/timestamp/polarization metadata, and a matching existing parent EvidenceRecord with comparable quality. Missing or mismatched live inputs fail without synthetic fallback. This contract was tested with generated test GeoTIFFs and a stub parent record; **no actual B-team change raster or NISAR HDF5 was loaded**.
- Integrated `analyze_spatial_changes`, `rank_change_regions`, `focus_change_region`, and `compare_change_regions` into the single orchestrator and FastAPI. New routes: `POST /api/agent/spatial/rank`, `GET /api/agent/spatial/evidence/{id}`, `POST /api/agent/spatial/compare`, `GET /api/agent/status`, and `GET /api/agent/operations/{session}`. Existing science routes are preserved.
- Added `backend/app/services/claim_validator.py`. Root science claims now require a persisted evidence ID, matching source scenes, ROI, algorithm, valid-pixel count, unit, and exact metric value from the EvidenceRecord. Forged metric values are rejected. Ranked claims are derived only from the spatial evidence store. Claims are marked `OBSERVED`; uncertainty remains explicit. No GCOV change is translated into wildfire, peat fire, uplift, subsidence or recovery conclusions.
- Added `backend/app/services/model_provider.py`, a bounded OpenAI-compatible **intent-only** adapter. It sends no tool definitions and explicitly sets `tool_choice: none`; outputs are accepted only if exactly `rank` or `investigate`. It has a 5-second request timeout, one retry, health/inference probe and deterministic fallback. Hermes provider mode refuses to configure unless `SAR2ACTION_HERMES_SAFE_PROFILE_VERIFIED=true` is explicitly set after independent tool-denial testing. No model-created measurement, code or GIS action can enter the executor.
- Improved React investigator with Agent Online/Offline and Demo Mode indicators; live tool traces from the operations endpoint; ranked cards; candidate highlights and selected-region outline on the existing MapLibre map; focus, evidence, pairwise dB comparison, and a two-observation Fingerprint view. The UI retains completed results while a retry runs, aborts/ignores stale AOI requests, and exposes explicit errors. Fixture mode hides the root NISAR overlay and labels its own analysis. The static claim about an observed wildfire-period radar change was replaced with dates from a successfully loaded fingerprint or a no-data message.
- Extended the five-scene story with source-linked region map state, English/Traditional Chinese narrative, Public/Scientific depth, regeneration, JSON export and stale checks when AOI or evidence changes. Stories generated from synthetic ranking keep a visible simulated-data notice.
- Added a Playwright end-to-end spec and runner configuration for AOI investigation, ranking, map focus, Fingerprint, Evidence, comparison and story switching. It is **authored but not executed** in this sandbox.

### TESTED

- `venv\Scripts\python.exe -m pytest tests/agent tests/backend/test_agent_api_direct.py tests/backend/test_evidence_schema.py tests/sar -q`: **64 passed, 1 skipped**. Includes spatial connected-region behavior, single-pixel rejection, deterministic evidence IDs, live-manifest contract using test rasters, timestamp refusal, intent adapter with mock HTTP, forged scientific value refusal, API-handler flow, and story staleness.
- `npm test -- --reporter=dot`: **9 passed**. Includes React ranked-result interaction, AOI stale-story behavior, and separation of synthetic mode from root NISAR layers.
- `npm run build`: TypeScript and Vite passed; only the existing large-bundle warning remains.
- `venv\Scripts\python.exe -m py_compile` on all new/changed Python backend modules: passed.
- Direct orchestrator smoke with explicit fixture: Chinese “找出變化最大的三個地方” returned three ranked candidates, safe map focus, a traceable Evidence ID for each, and five Chinese Scientific Mode story scenes. This is **synthetic integration evidence**.
- Direct FastAPI route-handler tests passed without HTTP sockets. These do not substitute for an actual HTTP/browser test.

### BLOCKED

- Hermes isolated environment remains v0.19.0 on Python 3.11.9. The [official latest stable release](https://github.com/NousResearch/hermes-agent/releases) is v0.23.1. Upgrade attempted in `venv_hermes` but the package index was unreachable (`No matching distribution found` with no version list). `hermes status` shows no selected model or provider credential and Gateway stopped. `/v1/models` could not be reached. No actual model inference or Hermes tool-calling denial test was performed. Hermes remains disabled. Official documentation supports [native Windows and WSL2](https://hermes-agent.nousresearch.com/docs/user-guide/windows-wsl-quickstart); its [API server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server) exposes built-in tools, so it must not be enabled here without a verified restricted profile.
- Local HTTP server/client and Python asyncio `socketpair` are blocked by the managed Windows sandbox. `127.0.0.1:8000` and `127.0.0.1:8642` returned socket permission errors. Uvicorn and FastAPI HTTP endpoints were **not** verified over the network.
- Playwright is not installed locally, and the npm registry DNS lookup failed. `npm run test:e2e` reported `playwright is not recognized`; no Playwright screenshot or browser result was produced. The spec is at `frontend/e2e/agent-spatial-flow.spec.ts` and will run only after dependency/browser installation on a normal Windows host.
- No readable root `data/raw/scenes/*.h5` files or per-pixel dB change GeoTIFFs exist in this checkout. `data/processed/phase2c_flagship` contains masks and summary references to missing change rasters. Thus real NISAR region ranking, real fingerprint synchronization for ranked regions, and full judged end-to-end science flow remain unverified.

### NOT IMPLEMENTED

- Server-side cancellation of a running heavy raster calculation; browser abort currently prevents stale display but cannot stop CPU work already started in a worker thread.
- Durable session/evidence/story storage and authenticated multi-user isolation. Current stores are process-local for the agent/spatial layer.
- A verified Hermes Gateway, actual provider inference, and Hermes built-in-tool denial test. The mock HTTP model test proves adapter behavior only.
- Live real-NISAR spatial result screenshot or externally validated scientific ranking. Approximate WGS84 area should be replaced by a B-approved projected area calculation for production decisions.

### Phase 2 files added or changed

`backend/app/services/spatial_ranking.py`, `model_provider.py`, `claim_validator.py`, `agent_orchestrator.py`, `backend/app/main.py`, `frontend/src/components/AgentPanel.tsx`, `RadarMapCanvas.tsx`, `frontend/src/App.tsx`, `styles.css`, `vite.config.ts`, `package.json`, `playwright.config.ts`, `frontend/e2e/agent-spatial-flow.spec.ts`, `frontend/src/__tests__/AgentPanel.test.tsx`, `App.test.tsx`, `tests/agent/test_spatial_ranking.py`, `test_orchestrator.py`, `tests/backend/test_agent_api_direct.py`, `docs/SPATIAL_RANKING_CONTRACT.md`, `README.md`, and this report.

### Run the browser verification on an unrestricted Windows host

In separate PowerShell windows:

```powershell
cd D:\SAR2Action
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd D:\SAR2Action\frontend
npm run dev
```

```powershell
cd D:\SAR2Action\frontend
npm install -D @playwright/test@1.65.0
npx playwright install chromium
npm run test:e2e
```

The Playwright spec saves `agent-spatial-story.png` in its test output after the five-scene flow. Install/runtime and screenshots have not been verified here. The [official Playwright installation guide](https://playwright.dev/docs/browsers) covers browser installation.

### Next integration priority

B should provide the two aligned change/mask GeoTIFFs and the manifest in `SPATIAL_RANKING_CONTRACT.md`, backed by an A-approved root EvidenceRecord. Then run the live ranking, HTTP and Playwright suites on an unrestricted Windows machine, review the derived candidate regions with A, and only afterward consider enabling a Hermes profile whose built-in tools have been independently denied.
