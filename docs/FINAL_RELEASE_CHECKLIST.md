# SAR2Action final release verification — 2026-11-14 (Taiwan time)

## Decision

**Local demo: PASS. Public repository release: HOLD.** `/studio` was exercised against running Vite and Uvicorn servers with real committed science files and a deterministic V3 HTTP response. The full repository is not yet safe to publish: tracked historical files contain local Windows paths, the repository has no root `LICENSE`, and the exact redistribution terms and attribution for every bundled science asset have not been signed off. A credential pattern scan is not a license review.

## Version and dependency freeze

- Checkout: `main`, commit `ce84378` (`V0.1`, observed during this verification). A separate `feat/final-science-studio` worktree remains at `229b3d0`. The V0.1 commit appeared during this verification and committed the V3 implementation, science exports, and Studio snapshot; no commit, merge, or push was made by this verification.
- At final check, the local checkout still has release-verification edits to `frontend/src/studio/InvestigationStudio.tsx`, `frontend/src/studio/adapter.ts`, and `frontend/vite.config.ts`, plus untracked `frontend/e2e/release-smoke.spec.ts` and these two release documents. Preserve these edits for review before treating a commit as the deployed version. The recorded science files were not modified.
- Frontend contract: `frontend/src/studio/{InvestigationStudio.tsx,adapter.ts,contracts.ts,time.ts,studio.css}` and `frontend/scripts/sync_studio_assets.py`. Vite publishes seven checked snapshots under `frontend/public/studio/`.
- Backend contract: `backend/app/main.py`, `backend/app/schemas/investigation_v3.py`, `backend/app/services/{investigation_v3.py,agriculture_vh_evidence.py}`. LIVE mode uses the deterministic V3 API. Recorded mode uses the completed saved Gemini response and trace, labeled historical.
- OPERA source: `data/exports/yunlin_vh_2025_2026/source_manifest.json`, `scene_inventory.csv`, `fields.geojson`, `vh_timeseries.{csv,json}`, `agent_evidence.json`, `vh_statistics.json`, `scientific_qa.json`. The source manifest reports 33 searched scenes in 2025 and 20 in 2026, with three selected/downloaded scenes each year. Five official farmland candidates yield 30 field-scene observations, not five confirmed rice paddies.
- NISAR/CHAMPI source: `data/exports/typhoon_champi/science_manifest.json`, `science_qa.json`, `scene_inventory.json`, `evidence.json`, `agent_trace.json`, `demo_response.json`, `official_loss_record.json`. The science manifest SHA-256 checks are enforced by V3 for the raster-derived products. The recorded response and trace are linked by `investigation_id`.
- The Studio asset sync rejects non-observed VH status, non-candidate fields, mismatched recorded IDs, missing registered Evidence IDs, and local Windows paths in its seven published files. The seven published files had zero detected private-path matches at this check.

## Bounded verification matrix

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend TypeScript and production build | PASS | `npm run build`; Vite warns about a 1.03 MB JS chunk, which did not block the demo. |
| Frontend unit/contract tests | PASS | `npm test -- --reporter=dot`: 18/18, including observed VH parsing and UTC-to-Taiwan calendar rollover. |
| V3 deterministic science, temporal/cross-CRID guards, trace and response integrity | PASS | `pytest tests/agent/test_investigation_v3.py -k 'not api_serves_case' -q`: 7/7. |
| Agricultural VH processing tests | PASS | `pytest tests/agriculture_vh/test_pipeline.py -q --basetemp .pytest-release-20261114-2307`: 7/7. The first attempt had 2 setup errors because sandbox default TEMP could not create directories; rerun passed. |
| Real local browser `/studio` and V3 API | PASS | `frontend/e2e/release-smoke.spec.ts`: 1/1 against actual Vite/Uvicorn. Five fields, 3+3 dates each, MapLibre canvas, Taiwan time, independent NISAR scenes, cross-CRID warning, six story steps, live V3 response, five read-only Evidence Challenge checks, graph, unresolved hypotheses and JSON download. |
| Existing Studio browser regressions | PASS after fix | `frontend/e2e/investigation-studio.spec.ts`: 3/3. First attempt had 1 pass then Vite exited on Windows `EBUSY` while watching Playwright `.crdownload` output; `frontend/vite.config.ts` now ignores test artifact directories. Rerun passed and Vite remained running. |
| Direct running V3 HTTP plus provenance | PASS | HTTP 200; 72 trace events validated by `validate_tool_trace`, 37 Evidence IDs all in the two source ledgers, six selected-field VH rows, five field comparisons, five hypotheses `UNRESOLVED`, validated typhoon delta disallowed. |
| V3 `TestClient` endpoint test | **INCOMPLETE** | `test_api_serves_case_and_registered_evidence` stalled twice after test entry; each run was stopped after a bounded wait. It is not counted as passing. Actual Uvicorn HTTP and browser paths passed. |
| Entire backend test suite | **NOT RUN** | Deliberately bounded to the release-critical cases. |

## Feature and science gates

- MapLibre renders the official candidate polygons on a neutral local background. Field list and chart work when WebGL is unavailable; the actual browser smoke confirmed a canvas.
- The VH chart plots only acquired OPERA RTC-S1 Sentinel-1C VH observations, with one relative orbit (105) and separate 2025/2026 curves. Date labels and month/day alignment use Taiwan time (UTC+8). Raw UTC timestamps remain in source JSON/CSV. Gaps over 24 days stay disconnected.
- NISAR October 16 P05023 and October 28 P05036 are independent observations. Their cross-CRID radiometric equivalence is **not validated**. Sentinel-1 C-band VH is never subtracted from NISAR L-band HV.
- County-level official loss is context, not field-level ground truth. Five fields remain `AGRICULTURAL_FIELD_CANDIDATE`; no crop planting records confirm rice. The 2025 observations do not establish a normal seasonal distribution. Harvest, field preparation, moisture and storm effects remain competing explanations. All V3 hypotheses remain `UNRESOLVED` and causal damage is `UNKNOWN`.
- Read-only Evidence Challenge calls existing deterministic APIs for observation timing, seasonal comparison, cross-field comparison and missing observations, and reruns V3 for its cross-CRID gate. It displays returned Evidence IDs; it does not edit hypothesis status. Hypothesis-specific challenge buttons remain disabled and say test not available because there is no dedicated safe per-hypothesis API.
- Recorded 44-event Gemini trace and LIVE deterministic 72-event response are visibly distinguished. LIVE trace and dossier share the returned investigation ID.

## Publication safety review

- A read-only pattern scan of 320 tracked/untracked text files found zero likely API-key assignments and zero known token formats. This is a bounded scan, not proof that every binary or historical file is safe.
- A second scan of the 17 proposed Studio code, runbook and browser snapshot text files found zero token-pattern and zero absolute local-path matches. This narrow set is reviewable for a demo handoff; it does not clear the rest of the repository.
- The same scan found local Windows paths in 32 files, including tracked `.phase4_hermes/gateway_state.json`, `data/exports/yunlin_vh_2025_2026/source_manifest.json`, and older diagnostics/documents. Do not publish the repository wholesale until those exact files are reviewed and scrubbed or explicitly excluded. The source manifest contains an absolute local download-manifest path; any redaction must preserve scientific provenance and hashes where relevant.
- `.gitignore` excludes credential patterns and raw rasters, but earlier tracked files and bundled archives are unaffected by ignore rules. Review the committed `data/exports/typhoon_champi/nlsc_township_boundaries_source.zip`, `data/exports/tw03/TW03_antigravity_bundle.zip`, PNGs, GeoJSON and all release artifacts individually before publication.
- No root `LICENSE`/`NOTICE` file was found. MapLibre GL JS uses BSD-3-Clause and its copyright notices must be retained ([upstream license](https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt)). ASF identifies OPERA RTC-S1 as the NASA/ASF Level-2 product ([ASF product guide](https://hyp3-docs.asf.alaska.edu/guides/opera_rtc_product_guide/)); confirm the correct collection citation and redistribution wording for the packaged outputs. The farmland dataset is attributed to Taiwan's Ministry of Agriculture ([dataset catalog](https://odportal.tw/dataset/4n4KVarl)); verify the specific source record's license and attribution before distributing its derived polygons. Taiwan's general open-data license does not by itself establish this particular file's terms ([license text](https://data.gov.tw/license)). Also check official loss and NISAR source terms.
- Do not stage all files, push, or label the public submission `RELEASE CANDIDATE` until the path, license, citation and review checks pass. The local demonstration is ready.
