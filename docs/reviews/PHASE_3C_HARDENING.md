# PHASE 3C — Science & Demo Hardening Report

**Date:** 2026-10-24
**Mode:** `PROJECT_MODE = PRE_COMPETITION_RND` (pre-competition R&D; **not** a final NASA Space Apps submission)
**Phase 4 (AI Agent):** **NOT STARTED.** I stopped here as instructed.

---

## 1. RFI Interpretation Correction (`isce-framework/isce3#294`)

- Every ratio claim (`400×`, `440×`, `316,000×`) and every ranking based on raw `rfiLikelihood` has been removed. A repo-wide scan of `.md/.py/.ts/.tsx` turns up **0** remaining hits.
- I checked F1 (`T119_F090`) and F2 (`T010_F176`) directly in the HDF5 files:
  - `/science/LSAR/GCOV/metadata/processingInformation/parameters/rfiMitigationApplied = False` in all four granules.
  - ISCE3 `softwareVersion = 0.25.16`.
  - Raw `_QA_STATS.h5` `rfiLikelihood` values range from `389.36` to `127,551,232.0`. That breaks the documented `[0,1]` range.
- Result: **`rfi_comparison_status = UNRELIABLE_METADATA`**. RFI is now treated only as known-limitation / QA context. It appears that way in the `CaseSummary` API, the UI ("RFI QA: UNRELIABLE_METADATA"), and the "What We Do Not Know" panel.

## 2. Filename Orbit-Fidelity Correction

- Fixed the "upgraded orbit ephemeris flag" wording everywhere.
- Per the official naming convention, the token after the CRID is orbit/pointing fidelity (`P/M/N/F` = Precise/Medium/Near Real-Time/Forecast). Next comes coverage (`F/P` = Full/Partial), then SDS location (`J` = JPL).
- F2 T0 `_N_F_J_` = Near Real-Time / Full / JPL. F2 T1 `_F_F_J_` = Forecast / Full / JPL. Inside the HDF5, `orbitType = MOE` for both.
- Added a parser (`parse_nisar_gcov_filename`) with unit tests for every code.

## 3. Flagship Re-Evaluation Without RFI Ranking

[`FLAGSHIP_LOCK.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_LOCK.md) re-scores F1 vs F2 on the 10 defensible criteria. Neither RFI nor frame-wide mean change magnitude is used as a primary criterion. **F2 (`T010_F176` ASC, 2026-09-06 → 09-18) stays the locked primary flagship.**

## 4. Authoritative Event Context

[`FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md) now has one provenance table per source: organization, publication date, event date, geographic specificity, what it supports, what it does not support, and URL. Sources include BMKG (~2026-09-10), BNPB (~2026-09-17), ANTARA/Polda Sumsel and BPBD.

> [!WARNING]
> The source URLs and the 2026 event details still need a human to check each record before anything is presented publicly. This R&D pass cannot independently confirm that the cited articles exist as described.

## 5. Post-Hoc Sub-Patch Language

- Every 2 km × 2 km high-change sub-patch is now labeled `selection_method = EXPLORATORY_POST_HOC_RADAR_CHANGE`, `selection_time = POST_HOC_INSPECTION`, with a `selection_basis` field. They are explicitly described as **not confirmatory wildfire evidence**.
- Custom AOIs drawn on the map get the same exploratory label automatically.

## 6. Predefined Event-Context AOI (`AOI-OKI-04`)

- `AOI-OKI-04` — Padang Sugihan peatland reserve & buffer, `[105.08, -2.92, 105.24, -2.76]`. Labeled `PREDEFINED_EXTERNAL_CONTEXT` and recorded in the event-context doc **before** the Change Engine ran on it.
- Result `E-FLAGSHIP-OKI-004`: `COMPARABLE`, 3,148,830 valid px (314.88 km², 100% coverage).
  - Median ΔHH = −0.2128 dB
  - Median ΔHV = −0.2056 dB
  - Combined median = 3.8693 dB composite
- **Honest reading:** these numbers are in the same range as the three geographic AOIs (ΔHH −0.16 to −0.24 dB). The pre-registered event-context AOI does **not** show a distinctly stronger regional signal than the non-event AOIs. This supports the "cause not determined" stance and does not support fire attribution.

## 7. Combined Radar Change Display

- Formula unchanged: `abs(Delta_HH) + abs(Delta_HV)`.
- Unit is `dB composite` ("custom change magnitude (sum of absolute dB changes)") in the API, `EvidenceRecord`, layer legend, Fingerprint panel and claims.
- The mandatory disclaimer is kept everywhere.

## 8. Manual UI QA (16 items) — PASS

I drove a real FastAPI (`127.0.0.1:8000`) and Vite (`127.0.0.1:5173`) stack with headless Chrome via [`run_phase3c_ui_qa_and_screenshots.py`](file:///D:/NASA/SAR2Action/scripts/run_phase3c_ui_qa_and_screenshots.py). Screenshots are in [`docs/demo/screenshots/`](file:///D:/NASA/SAR2Action/docs/demo/screenshots/) along with `ui_qa_verification_summary.json`.

| # | Item | Result |
|---|---|---|
| 1 | Flagship case load | PASS |
| 2 | Engineering case switch | PASS |
| 3–4 | T0 / T1 layers | PASS |
| 5 | T0/T1 swipe | PASS |
| 6–7 | ΔHH / ΔHV | PASS |
| 8 | Combined Radar Change (dB composite + disclaimer) | PASS |
| 9 | Validity mask | PASS |
| 10 | Custom AOI drawing (live HDF5) | PASS |
| 11 | Radar Fingerprint panel | PASS |
| 12 | Observed / May Explain / Do Not Know | PASS |
| 13 | Claim → EvidenceRecord inspector | PASS |
| 14 | Outside-coverage refusal | PASS |
| 15 | Missing HV → "Unavailable" | PASS |
| 16 | Console errors | PASS. The only failed request is the deliberate HTTP 422 science-gate refusal. |

**Defects the QA found and I fixed:**
1. **Stale results after a refusal (science-relevant).** After an outside-coverage refusal, the previous AOI's fingerprint stayed on screen next to the rejected bbox. The UI now clears the fingerprint, evidence and claims when a request fails. Regression assertions were added to Vitest and the browser QA.
2. **Basemap.** The keyless CARTO tile URL now serves "API KEY REQUIRED" placeholder tiles. I switched to dimmed OSM standard tiles, which is acceptable for low-volume R&D. A competition deployment needs a keyed or self-hosted provider.
3. **Favicon.** A missing favicon caused a 404 console error. I added an inline icon.

## 9. Demo Performance

Full table: [`DEMO_PERFORMANCE.md`](file:///D:/NASA/SAR2Action/docs/demo/DEMO_PERFORMANCE.md).

| Operation | Median time |
|---|---|
| Preset AOI (cached) | ~15 ms |
| Layer metadata + PNG | ~113 ms |
| Evidence retrieval | ~94 ms |
| Custom 5 km AOI (cold) | 1.7 s |
| Custom 10 km AOI (cold) | 3.5 s |
| Custom 30 km AOI (cold) | 11.3 s, ~968 MiB peak Python allocation |
| Any repeated custom AOI | ~15–21 ms |

**Cache fix:** the first benchmark showed repeated custom AOIs were never served from cache. The cache check was limited to preset IDs. It now serves any previously computed AOI whose PNGs exist on disk.

> [!NOTE]
> A cold 30 km AOI takes ~11 s and almost 1 GiB. For the demo, use presets or AOIs of 10 km or smaller, or pre-warm the cache.

## 10. Demo Fallback (`DEMO_MODE = LIVE | CACHED_REAL_DATA`)

- Set via the `SAR2ACTION_DEMO_MODE` environment variable or `POST /api/demo-mode` with body `{"demo_mode": ...}`.
- `CACHED_REAL_DATA` serves only results previously computed from the real NISAR granules, for all 6 preset AOIs. If an AOI isn't cached and the HDF5 files are offline, it refuses with `CACHED_AOI_NOT_FOUND`. It never synthesizes data.
- Covered by the backend test `test_api_08`.

## 11. Science Status Display

A status bar is always visible below the scene banner. It shows:
- `PROVISIONAL`, `CAUSE NOT DETERMINED` and `DEMO_MODE` badges.
- The required three-sentence non-attribution statement, word for word.

## 12. Tests

| Suite | Result |
|---|---|
| Python `pytest` (science + backend) | 52 passed (including new `test_api_08` for AOI-OKI-04, dB composite and demo mode) |
| Frontend `vitest` | 6 passed (new test 6: status badges, non-attribution text, dB composite, plus stale-clear assertions in test 3) |
| `vite build` (TypeScript) | passes |

## 13. Updated / New Artifacts

- **Science docs:** `FLAGSHIP_LOCK.md`, `FLAGSHIP_EVENT_CONTEXT.md`, `FLAGSHIP_CASE_SELECTION.md`, `FLAGSHIP_CHANGE_VALIDATION.md`
- **Code:** `sar/catalog/models.py`, backend schemas, `science_service.py`, `layer_renderer.py`, `main.py`, frontend `App.tsx`, `api.ts`, `RadarMapCanvas.tsx`, `styles.css`, `index.html`
- **Scripts:** `run_phase2c_flagship_validation.py` (adds AOI-OKI-04 and post-hoc labels), `run_demo_performance_benchmark.py`, `run_phase3c_ui_qa_and_screenshots.py`
- **Data:** refreshed `data/cache/*` stores and PNGs for the 6 presets, 44 flagship GeoTIFFs, `flagship_validation_summary.json`, `phase3c_performance_benchmark.json`

## 14. Open Risks Before Phase 4 / COMPETITION_BUILD

1. A human needs to verify the external event sources (URLs, dates).
2. The regional signal is weak (about −0.2 dB) and the pre-registered event AOI does not stand out. The demo story should present this as change detection with honest uncertainty, not fire mapping.
3. Basemap provider licensing for the public demo.
4. Cold large-AOI latency and memory. Consider a size cap of 10–15 km or downsampled preview layers.
5. The environment still uses `--system-site-packages`. Pin versions before the final build.
6. Every result comes from PROVISIONAL `P05023` products and must be re-checked if a reprocessed CRID is released.
