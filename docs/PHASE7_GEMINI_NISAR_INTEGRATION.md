# Phase 7 — Gemini agent and NISAR evidence handoff

Validated on Windows, 2026-11-12. **Gemini tool calling is operational on explicitly synthetic test data. B-team NISAR cache integration remains blocked because the handoff files are absent.** This report distinguishes model execution from scientific data verification.

## Runtime and security

- Official `google-genai` SDK 3.2.0 is installed in `D:\SAR2Action\venv`. The configured provider is `gemini`, model `gemini-3.1-flash-lite`. A live model-list request succeeded. A live call to the listed `gemini-2.5-flash` returned 404 for this account; the current Flash Lite model completed a schema-valid function call.
- `scripts/start_gemini_backend.ps1` reads the exact `GERMINI API.txt` path in PowerShell, accepts a raw one-line token or `GEMINI_API_KEY=...`, and passes it only through the backend child process environment. It never writes an `.env` or permanent Windows setting. The key file is ignored by `.gitignore`.
- `GeminiModelProvider` sends only allowlisted function declarations, disables SDK automatic function execution, bounds response tokens, times out requests, and retries 429/5xx at most twice with backoff. The existing real-agent runtime limits planning and tool calls, validates JSON Schema, binds trusted AOI and evidence IDs, and executes only local restricted GIS functions. Gemini receives no shell, code execution, file access, HDF5, entire evidence store or secret.
- Model/provider errors are reduced to safe status and exception class. The trace redacts a process credential if it appears in a user query. The key is never placed in a tool argument. Existing `llamacpp`/OpenAI-compatible provider remains the default when Gemini is not selected; there is no silent provider switch.
- No `.git` directory exists in this checkout. The current key is absent from scanned source, docs, tests and built frontend files, but Git tracking/history cannot be audited here. See `phase7_security_validation.json`.

## Real tool trace

One real Gemini run with an explicit Synthetic Demo AOI completed:

`user_request → check_observations (synthetic) → model_tool_selection → rank_change_regions → model_tool_selection → compare_regions → model_tool_selection → inspect_evidence → validate_evidence → explain_findings → final_response`.

The run returned three synthetic evidence IDs in 4.4 seconds. A separate HTTP run returned 200, `completed`, provider `gemini`, and three evidence IDs. Browser E2E confirmed the map, evidence card, fingerprint panel and five-scene story with synthetic labeling. These are **not NISAR observations**.

## B-team handoff status

The newly supplied `docs/Agent 測試指南 (SAR2Action).docx` was read. It describes `D:\NASA\SAR2Action\data\cache`, but `D:\NASA\SAR2Action` is absent. The primary `D:\SAR2Action\data\cache` has none of `evidence_store.json`, `fingerprint_store.json`, or `analysis_store.json`; no full GCOV HDF5 is present. Thus AOI-OKI-04 HH/HV values and `E-FLAGSHIP-OKI-004` cannot be verified or presented. We did not fabricate them.

`ScienceEvidenceProvider` now has distinct read-only cache, configurable Science API (`SAR2ACTION_SCIENCE_API_URL`), existing live service and isolated synthetic source modes. Typed responses are checked against case/AOI/evidence links, and a cache without provenance is labeled `UNVERIFIED NISAR-DERIVED CACHE`. The cached agent route is deliberately blocked until source and QA review is complete. Its UI option reports missing data and never substitutes synthetic evidence. See `SCIENCE_PROVIDER_HANDOFF.md` and `phase7_science_data_validation.json` for the minimal B-team delivery.

After the user's location clarification, the exact `D:\NASA\SAR2Action\data\cache` path was checked again and remains absent. `D:\SAR2Action\data\cache` exists but is empty. The currently running 8000 backend returned 404 for `E-FLAGSHIP-OKI-004` and 422 for the AOI-OKI-04 fingerprint request. A repeatable read-only three-store validator is now available as `python -m scripts.validate_science_cache`; its current report lists all three files as missing.

AOI-level fingerprint statistics alone cannot rank within-AOI subregions. Formal ranking still requires the signed georeferenced change raster and valid mask under `SPATIAL_RANKING_CONTRACT.md`.

## Verification

| Test | Observed result |
| --- | --- |
| Python unit/API tests | 93 passed, 6 skipped (skips require absent real HDF5) |
| Frontend tests | 9 passed |
| TypeScript | passed |
| Vite build | passed; bundle-size warning |
| HTTP with real Gemini | status 200 online; investigate 200 completed; cache request 200 blocked |
| PowerShell launcher | started on 127.0.0.1:8011, `/api/health` and `/api/agent/status` returned 200, then stopped |
| Chrome E2E, isolated 8010/5174 | 3 passed, including real Gemini tool calling |
| Real Gemini benchmark | 9/10 task completion (90%); p50 8.05 s, p95 15.82 s; 0 unauthorized tool successes. The first run was 8/10 before fixes. The remaining fabrication-request case safely blocked without selecting the expected analysis tool. This fixture benchmark is independent of mock/Gemma results. |
| Exact secret scan | passed over 132 source/docs/tests/scripts/frontend build files and three HTTP responses; no matching key bytes |

The sandbox blocks even a minimal Windows `asyncio.run`; Python TestClient and browser E2E were run with localhost permission. Existing services on 8000/5173 were left running and untouched.

## Start on Windows

Use an unused port if another service owns 8000:

```powershell
cd D:\SAR2Action
.\scripts\start_gemini_backend.ps1 -Port 8000
```

In another PowerShell window:

```powershell
cd D:\SAR2Action\frontend
npm run dev -- --host 127.0.0.1
```

If the backend uses port 8010, set `$env:SAR2ACTION_BACKEND_URL='http://127.0.0.1:8010'` before starting Vite on a free port. The default Vite proxy still targets 8000. Select **Synthetic Demo** and **Real AI Analysis** for the current complete competition flow. Select **NISAR Cached Evidence** only after B supplies and A/B verifies the handoff; today it explicitly blocks.

## Remaining limits

- Cached NISAR evidence, AOI-OKI-04, HH/HV verification, real NISAR story and real subregion ranking: **BLOCKED** by absent B-team files and provenance.
- Full response and trace credential scanning should be repeated when the production process and repository are available. This checkout has no Git history to inspect.
- The configured Gemini model can change availability or pricing. Model-list health does not itself prove function calling; the separate live function-call and E2E tests above do.
