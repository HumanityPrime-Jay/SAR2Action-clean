# SAR2Action release candidate — final freeze

Validated on Windows in `D:\SAR2Action`, 2026-11-13. **Release decision: ready for a supervised competition rehearsal, with provenance pending and an intermittent Gemini endpoint risk.** The final [acceptance run](RELEASE_ACCEPTANCE_RESULTS.json) passed every executable gate. The B-team source HDF5 reproducibility report has **not** been delivered to this workspace; the NISAR cache remains **NISAR-DERIVED CACHE — PROVENANCE PENDING**.

## Frozen demonstration paths

- **Demo A — NISAR cached evidence:** `http://127.0.0.1:5173/?demo=A` preselects the flagship case, AOI-OKI-04, NISAR Cached Evidence and real Gemini. Its Radar Fingerprint, Evidence Card, map focus and five-scene Story use `E-FLAGSHIP-OKI-004` and the delivered B-team cache. The recorded HH/HV signed pixelwise median changes are −0.2128/−0.2056 dB over 3,148,830 recorded valid pixels. They do not establish a significant disturbance or peat fire.
- **Demo B — synthetic spatial ranking:** `http://127.0.0.1:5173/?demo=B` preselects Synthetic Demo and deterministic execution. Ranked regions, comparison, map focus, Evidence and Story remain explicitly labeled **SIMULATED DATA — NOT NASA OBSERVATIONS**. No synthetic value enters Demo A's NISAR cache.

Both URLs are linked in the Agent panel. The [launcher](../scripts/start_release_demo.ps1) accepts `-Demo A` or `-Demo B`, checks loopback health in order, and opens the selected URL. It starts the existing backend and Vite if needed; no second science API or model orchestration stack was added. The [acceptance script](../scripts/accept_release.ps1) runs all gates and records [machine-readable results](RELEASE_ACCEPTANCE_RESULTS.json), continuing after any failure and exiting nonzero if a gate fails. The Gemini key loader is backend-process-only.

## Executed final acceptance

| Gate | Observed result |
| --- | --- |
| Three-file B cache and scientific claim audit | PASS; 12 Evidence, 12 Fingerprints, 12 Analyses; 108/108 cross-file Claims |
| Python `pytest -q` | 99 passed, 6 skipped; skipped cases require absent source HDF5 |
| Frontend Vitest | 9 passed |
| TypeScript and Vite build | PASS; large JavaScript chunk warning remains |
| Loopback HTTP E2E | 11/11 PASS, including exact HH/HV, pixel count, Scene Pair, AOI, Evidence and stale Story checks |
| Chrome Playwright | **7/7 PASS** on the final complete run, including both release entrances and two real-model browser flows |
| Real Gemini scientific evaluation | **5/5 PASS**, including a malicious request that did not execute Shell or return a fabricated value |
| Exact-key leakage scan | PASS; 0 matches in 149 files at the acceptance gate; 0 matches in 151 files after final reports |
| B-team source-machine HDF5 report | **NOT DELIVERED**; source verification not run here |

The final Gemini evaluation used `gemini-3.1-flash-lite` through the existing Google GenAI SDK. Its real Function Calling selected allowlisted GIS tools; the Safe Tool Executor bound trusted case/AOI and Evidence IDs, and the backend generated evidence-bounded scientific wording. The real-mode failure path visibly reports an error without converting to deterministic output. The final [evaluation](FINAL_GEMINI_SCIENCE_EVAL.json) records per-question tools, checks and latency. The [scientific claim audit](FINAL_SCIENTIFIC_CLAIM_AUDIT.json) and [HTTP report](FINAL_HTTP_E2E.json) provide the numerical cross-checks. The three B JSON SHA-256 hashes still match the Phase 8 baseline; no B-team scientific value was modified.

## Failures retained and release risk

Earlier freeze attempts were **5/7** and **6/7** in Chrome because Gemini tool selection failed while its model-listing status still appeared online. An isolated diagnostic observed HTTP **503**; the later browser error showed HTTP **504**. The existing three-attempt retry remains bounded, with a longer 2/4-second backoff for transient 429/5xx responses. Safe error messages now include only exception class and HTTP status, never request text or credentials. A later complete run passed 7/7 and the separate five-question evaluation passed 5/5. These facts are both retained in [failure history](RELEASE_FAILURE_HISTORY.json). `gemini-2.5-flash` and `gemini-2.5-flash-lite` were listed under the present credential but returned HTTP 404 for the tested Function Calling request, so the release model was not changed. A live model status badge does not guarantee successful inference.

## Provenance, security and rehearsal call

No `nisar_source_reproducibility.json` or equivalent source-machine report was found in the project docs or data cache. Therefore **Verified Source** is blocked. A source HDF5 pixel recount, a stable control/significance assessment, and a real signed georeferenced change raster with valid mask are still needed for stronger scientific claims and real within-AOI ranking. The [source request](SCIENCE_REPRODUCIBILITY_REQUEST.md) supplies a read-only script for B team to run where the HDF5 files reside; D team did not recreate source observations from cache JSON.

The key scan covered backend/scripts/docs, frontend source and build, Playwright outputs and generated reports; the exact credential was absent. The local `GERMINI API.txt` is excluded by `.gitignore` and must not be packaged. No deployment package was produced, and this workspace has no Git repository, so Git history was not audited.

**Rehearsal is suitable with a presenter-controlled fallback:** demonstrate Demo A while Gemini inference responds; if it returns 503/504, show the explicit error and continue with clearly labeled cached deterministic inspection or Demo B. Never describe that fallback as real AI. Keep the cache provenance label pending throughout. Follow the [demo checklist](FINAL_DEMO_CHECKLIST.md) and [known limitations](FINAL_KNOWN_LIMITATIONS.md). A claim of source-verified NASA pixels, confirmed significant disturbance or live HDF5 computation is not release-ready.
