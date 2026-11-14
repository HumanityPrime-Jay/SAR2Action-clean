# SAR2Action D-Team Engineering Evaluation — 2026-11-12

## Completed and tested in this **standalone** package
- `backend/tests/test_agent.py`: **50 tests passed**, including 10 parameterized science-trap queries, scene QA failures, unknown AOI, unsupported polarizations, invalid bbox, ledger traceability, story staleness, valid map-action allowlist, deterministic evidence IDs and story generation.
- Python backend syntax check via `compileall`: passed.
- Frontend JavaScript syntax via `node --check`: passed.
- FastAPI homepage/health: verified HTTP 200 via curl (local container).
- Full HTTP workflow via FastAPI TestClient: analysis → evidence provenance → five-frame story → current/stale validation.

## Not yet completed / risks
- **Real Hermes Agent not installed or authenticated in this environment.** The container cannot resolve external package repositories; there is no accessible `hermes` binary. Hermes HTTP integration is optional, safe-off and unverified end-to-end.
- **No real NASA NISAR GCOV scenes supplied.** Synthetic test data is always labelled `SYNTHETIC`; science metrics cannot be presented as NASA observations.
- **No access to teammates' actual repository, B's HDF5 pipeline, or C's existing MapLibre UI.** This is a standalone working reference rather than a merged production build.
- Chromium Playwright local page navigation returned `ERR_BLOCKED_BY_ADMINISTRATOR` due to the sandbox environment. Browser screenshot/e2e verification was NOT completed in this environment. Validate on the user's own machine during integration.
- A's independent scientific QA is still required; automatically matching metadata is not enough to prove high quality.
- Hermes default gateway exposes powerful internal tools; sandboxing must be verified before enabling text enhancement. Structured known/unknown answers currently work without an LLM; avoid claiming Hermes is in production.
- Operational state is in process memory only; server restarts clear ledger and story sessions. For judged demo, a simple persisted SQLite store would improve recovery, but is not necessary for the initial vertical slice.

## Scientific trap gate
No endpoint returns a 'burned area', 'fire confirmed', 'smoke forecast', 'PM2.5', 'population exposed', 'centimeter displacement', or 'restoration proven' result from NISAR GCOV intensity alone.

## Performance
The fixture is <=72×56 cells and CPU-only, with an `asyncio.Lock` limiting simultaneous agent investigations to 1 process. Memory fit is safe for the RTX 5070 Ti / 32GB machine without consuming the GPU. Large-area live data must be chunked/pre-cropped by B.

## Definition of done for final competition version
1. NISAR pair is genuinely observed, acquired after mission data is available, scene IDs confirmed and QA approved.
2. Hermes installed and sandboxed, its model smoke test passed, and Agent tool flow is constrained by an independent executor.
3. C's real MapLibre UI renders B's co-registered COG tiles; click-through evidence matches actual AOI geometry.
4. Automated science regression tests remain green and browser demo recording demonstrates complete 90-second story.
