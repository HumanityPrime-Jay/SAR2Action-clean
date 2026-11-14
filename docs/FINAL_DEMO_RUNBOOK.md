# SAR2Action Investigation Studio — final demo runbook

## Start the local demo

Run from the repository root with an existing environment containing the backend requirements. Verification used Python 3.12.10. A Gemini key is **not required** for Recorded mode or LIVE deterministic V3. No Earthdata or Earth Engine login, satellite download, or science recomputation is needed.

Terminal 1:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

- Frontend: `http://127.0.0.1:5173/studio`
- Backend: `http://127.0.0.1:8000`
- Health: `GET /api/health`; API schema: `GET /openapi.json`
- Investigation: `POST /api/agent/investigate-v3`
- Read-only VH checks: `POST /api/agent/agriculture-vh/tool`
- Evidence lookup: `GET /api/agent/champi/evidence/{evidence_id}`
- Vite proxies `/api` to `http://127.0.0.1:8000` by default. Set `SAR2ACTION_BACKEND_URL` only if the backend uses another URL. `GEMINI_API_KEY` and optional `SAR2ACTION_GEMINI_MODEL` are needed only for a separately authorized live Gemini investigation; `/studio` LIVE uses `agent_mode=deterministic`.

## Six-step scenario

1. **The disaster:** Open `/studio`. Explain that the Ministry of Agriculture loss record is county-wide context; it is not parcel damage evidence.
2. **The observations:** Select each of `YL-CAND-01` through `YL-CAND-05` on the map or picker. All five are agricultural candidates, not verified rice paddies. Show each field's 2025 and 2026 VH points (three actual acquisitions per year), pixel counts, platform, orbit and Evidence ID. The plot uses Taiwan calendar dates; source CSV/JSON preserve UTC.
3. **The question:** Read the prefilled scientific question. In default Recorded mode, the saved Gemini response is scoped to `YL-CAND-01` and clearly labeled historical. Switch to LIVE, select a field and press **Investigate with live API** for a new deterministic V3 investigation ID.
4. **The investigation:** Open the completed tool trace. LIVE trace comes from the newly returned V3 response; Recorded trace has 44 saved events. Show scientific QA and the explicit cross-CRID refusal.
5. **The evidence:** Open the Evidence Graph and select an Evidence ID. Use **Rerun scientific checks** for observation timing, seasonal comparison, cross-field comparison, cross-CRID compatibility and missing ground truth. Four checks call the VH read-only tool API; cross-CRID reruns deterministic V3. The visible output includes the actual status, execution type, Evidence IDs and raw result. Per-hypothesis challenge buttons remain disabled as `NOT AVAILABLE` for a dedicated per-hypothesis test; no hypothesis status is edited.
6. **The action:** Read observed facts, alternative explanations and missing ground evidence. Export **dossier JSON**. Verify its investigation ID matches the displayed LIVE result or the scoped Recorded result.

## Evidence map

| Purpose | Source path |
| --- | --- |
| Official field boundaries and status | `data/exports/yunlin_vh_2025_2026/fields.geojson` |
| Six OPERA scenes and 30 field-scene observations | `data/exports/yunlin_vh_2025_2026/scene_inventory.csv`, `vh_timeseries.csv`, `vh_timeseries.json` |
| OPERA Evidence and provenance | `data/exports/yunlin_vh_2025_2026/agent_evidence.json`, `source_manifest.json`, `scientific_qa.json` |
| NISAR QA and source checksums | `data/exports/typhoon_champi/science_qa.json`, `science_manifest.json`, `scene_inventory.json` |
| NISAR/official Evidence, recorded response and trace | `data/exports/typhoon_champi/evidence.json`, `official_loss_record.json`, `demo_response.json`, `agent_trace.json` |
| Published browser snapshot | `frontend/public/studio/` (seven files copied by `frontend/scripts/sync_studio_assets.py`) |

## What to say about the result

The 2025 and 2026 Sentinel-1C VH observations show descriptive differences for the same candidate fields. The October 2026 event is temporally bracketed, but there is only one 2026 pre-warning observation, no verified rice crop records or field damage ground truth, and no validated normal seasonal baseline. Harvesting, land preparation and moisture can also change VH. The NISAR pre/post scenes have different CRIDs; a validated radiometric delta is blocked. **Do not state confirmed typhoon crop damage, parcel loss percentage or insurance compensation.**

## Verification and handoff

The bounded local browser smoke in `frontend/e2e/release-smoke.spec.ts` and three existing Studio browser regressions passed against running servers. Frontend build and 18 unit tests, seven deterministic V3 tests, and seven agricultural VH tests passed. The V3 FastAPI `TestClient` test stalled and was stopped; direct running HTTP passed. Vite ignores Playwright output directories to avoid a Windows file-watcher `EBUSY` crash during testing. See `docs/FINAL_RELEASE_CHECKLIST.md` for the complete matrix, remaining publication blockers and Git state. Do not push until the public-file path and licensing review is complete.
