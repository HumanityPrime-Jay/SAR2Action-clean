# Phase 8 — cached NISAR evidence integration

Validated on Windows, 2026-11-13. The B-team handoff is now present in `D:\SAR2Action\data\cache`. The Agent can use its precomputed AOI evidence through the read-only `ScienceEvidenceProvider`. This mode is **NISAR CACHED EVIDENCE**, not live HDF5 computation or within-AOI spatial ranking.

## Handoff verification

The [machine-readable audit](phase8_cached_evidence_validation.json) read all three JSON stores without modifying them. It found 12 typed Evidence records, 12 Fingerprints, 12 Analyses and 108 Claims. All six guide-listed Evidence IDs exist. Pydantic schemas, unique IDs, claim measurements and units, AOI/scene/date/evidence links, HH/HV medians, mask counts, pixel-area arithmetic and scientific limitations passed internal consistency checks. The three input SHA-256 hashes are recorded in the audit.

For `case-flagship-oki-f2` / `AOI-OKI-04` / `E-FLAGSHIP-OKI-004`, the cache records HH median signed change **−0.2128 dB**, HV **−0.2056 dB**, and **3,148,830** jointly valid pixels between 2026-09-06 and 2026-09-18 UTC. Its recorded mask rule requires valid subswath masks and finite positive power in both observations. The 10 m × 10 m spacing and 314,883,000 m² valid area are arithmetically consistent with that count. Both Scene IDs occur in the local scene catalog. These checks verify the delivered records' internal relationships; they do **not** independently recount the original pixels.

The full source GCOV HDF5 files and source hashes are absent here. External NASA provenance and the original mask/calibration computation remain **BLOCKED for independent verification**. The interface therefore says **NISAR-DERIVED CACHE — PROVENANCE PENDING**. The records are provisional; `cause_not_determined` and `not_burn_severity_or_fire_damage` remain visible. Radar backscatter changes alone cannot confirm peat fire, underground burning, displacement or burn severity.

## Agent and product integration

The existing `GET /api/cases`, `POST /api/radar-fingerprint` and `GET /api/evidence/{id}` routes were retained. Cache hits now report `CACHED_REAL_DATA`. Cached Agent requests use the read-only provider for Fingerprint, Analysis and Evidence, validate their claims against the same EvidenceRecord, bind the selected case/AOI/scene pair, and reject unknown or stale IDs. The Gemini planner sees only allowlisted GIS functions and trusted context; the executor reads science data locally and issues only bounded MapLibre actions. Ranking and multi-region comparison are unavailable in cache mode because no signed georeferenced change raster is present.

The Agent Panel displays the cached HH/HV medians, observation dates, valid-pixel count, Evidence ID, method and limitations. Evidence opens a card and focuses the validated AOI box. Each of the five story frames shows its Evidence ID and source scene pair. AOI switching marks the old story stale. Synthetic Demo remains separate.

## Executed validation

| Gate | Result |
| --- | --- |
| Read-only three-store audit | PASS; 12 Evidence, 12 Fingerprints, 12 Analyses, 108 Claims |
| Six specified Evidence IDs | PASS |
| AOI-OKI-04 HH/HV/API/JSON/Agent comparison | PASS; values match exactly |
| Real Gemini cached investigation | PASS; `gemini-3.1-flash-lite`, 15/15 checks in [evaluation](phase8_gemini_real_evidence_eval.json), 25.08 s on the successful comparison run |
| Invalid ID, cross-AOI and changed scene pair | PASS in Python tests |
| Five-frame story and AOI stale handling | PASS in Python tests |
| Python suite | 99 passed, 6 skipped (full HDF5 cases absent) |
| Frontend tests / TypeScript / Vite build | 9 passed / PASS / PASS |
| Backend HTTP | 200 for Fingerprint, Evidence and real Agent; exact value and provenance comparison PASS |
| Chrome Playwright | 5 passed, including real Gemini cached-evidence browser flow |
| Secret and B JSON integrity audit | PASS; 343 files scanned with zero exact-key matches, B JSON hashes unchanged |
| Source HDF5 pixel recalculation | BLOCKED; source files absent |
| Real within-AOI spatial ranking | BLOCKED; signed change raster and valid mask absent |

The initial real-model comparison reported 14/15 because the evaluation script compared a one-element ID list to a four-element source list. The condition was corrected and the full Gemini/HTTP comparison rerun; it then passed 15/15. No science data was edited.

## Start

Run `D:\SAR2Action\scripts\start_gemini_backend.ps1` for the backend. Start Vite in `D:\SAR2Action\frontend` with `npm run dev -- --host 127.0.0.1`. If port 8000 is already used, pass `-Port 8010` to the backend script and set `SAR2ACTION_BACKEND_URL=http://127.0.0.1:8010` before starting Vite. Select **NISAR Cached Evidence**, **Real AI Analysis**, the flagship case and **AOI-OKI-04**. The existing Gemma/llama.cpp path remains available without a silent provider switch.
