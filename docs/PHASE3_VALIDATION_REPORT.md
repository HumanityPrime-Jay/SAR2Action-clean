# SAR2Action Phase 3 validation — 2026-11-12

## Delivered and observed

The root FastAPI and Vite applications were started on `127.0.0.1:8000` and `127.0.0.1:5173`. Both returned HTTP 200. The original loopback/socket error was a Codex sandbox restriction: an approved host-side Python `socketpair` probe succeeded, npm registry DNS worked, and local servers answered requests. It was not an application HTTP defect. See `phase3_environment_diagnostics.json` for host versions, GPU, network, endpoint and service probes. The project Python environment is 3.11.9, Node 24.15.0, npm 11.12.1, FastAPI 0.136.1, Vite 5.4.21, Playwright 1.65.0, and the GPU reports RTX 5070 Ti with 16,303 MiB VRAM. PyTorch CUDA is unavailable in the project venv; no local model was installed or downloaded.

The React investigator now executes the explicit Synthetic Demo path through the root science application, automatically displays three ranked regions, focuses the first region in MapLibre, opens the region fingerprint and evidence, and keeps later region/evidence clicks synchronized. Natural-language comparison and story questions execute their respective tools automatically. The browser tests verify the MapLibre `fitBounds` action was applied, three camera-projected map outlines appeared, comparison worked, five story scenes navigated, and an AOI switch removed old rankings and marked the story stale. The screenshot is `frontend/test-results/agent-spatial-flow-synthet-86ed9-rprint-and-five-scene-story-chrome/agent-spatial-story.png`. The basemap tiles rendered gray in headless Chrome; the georeferenced ranked outlines remained visible. This screenshot depicts **synthetic data**, not NASA observations.

The ranking now filters components below a configurable valid coverage threshold, ignores isolated extreme pixels and NoData, sums WGS84 geodesic cell areas, and returns a GeoJSON bounding rectangle, quality status, observations, method, scene IDs, metrics, Evidence ID and explicit limitations. Different component rectangles can overlap because they are extents; connected pixels remain disjoint. The live manifest stays fail-closed and follows `SPATIAL_RANKING_CONTRACT.md`.

The five story frames contain narrative, map state, visualization, evidence IDs and scientific limitations. English/Traditional Chinese and public/scientific mode remain available. Evidence records contain source scenes, dates, polarization, AOI bounds, method, measurement, unit, quality and Evidence ID. The backend rejects claims without a registered matching evidence record. The UI invalidates old evidence, comparison and story responses when the AOI or mode changes.

## Executed tests

| Check | Observed result |
| --- | --- |
| Full Python suite | 70 passed, 6 skipped, 3 dependency deprecation warnings |
| Skips | Five real HDF5 API tests because the required scene files are absent; one pre-existing optional test |
| React unit tests | 9 passed |
| Production frontend build | Passed |
| Real Chrome Playwright flows | 2 passed, 2.1 s; includes AOI stale protection, MapLibre focus, automatic comparison and story |
| HTTP fixed questions Q1–Q5 | 5/5 completed using explicit synthetic mode; per-question times 62.5, 47.0, 48.5, 29.9, 64.4 ms in the captured run |
| Evaluation rates | Tool success 5/5, end-to-end completion 5/5, evidence validity 5/5 for synthetic HTTP cases |
| Live missing-raster refusal | HTTP 422, no synthetic fallback |

The machine-readable Q1–Q5 result is `phase3_agent_evaluation.json`. Q3 and Q5 checks require automatic comparison and story execution, respectively. Its map-action check verifies the server response. Chrome separately verifies the UI camera action. None of these tests establish scientific validity for real NISAR data.

## Hermes and model tool calling

The official [Hermes releases](https://github.com/NousResearch/hermes-agent/releases) identify v0.23.1 as latest stable as checked on 2026-11-12; the [official Windows installation guide](https://hermes-agent.nousresearch.com/docs/getting-started/installation) supports native Windows. The isolated local environment remains on v0.19.0 to avoid changing a functioning installation solely for version parity. `hermes gateway status` reported **not running**. There is no configured model URL, model name or credential, and no verified restricted Hermes gateway profile. Consequently provider health reports **offline**; neither Hermes inference nor a live model tool call was claimed successful.

The model adapter now has a real OpenAI-compatible function-call request for `rank_change_regions`, bounded to one JSON Schema with `additionalProperties:false`. The returned arguments must pass JSON Schema validation and exactly match the trusted case, AOI, polarization and data mode from the UI. The local typed orchestrator performs the science computation and evidence check; the model receives no shell or file tool. Mocked tests verified a valid call, rejection of a forged case plus shell argument, and routing an accepted call to local science evidence. A representative **mocked, not live**, response is:

```json
{"tool_calls":[{"function":{"name":"rank_change_regions","arguments":"{\"case_id\":\"fixture-case\",\"aoi_bbox_wgs84\":[100.0,0.0,100.2,0.2],\"polarization\":\"HV\",\"data_mode\":\"fixture\"}"}}]}
```

HTTP model calls have an 8-second timeout and fall back to deterministic routing after provider failure or disconnect. Browser cancellation aborts the request and prevents stale UI writes, but the server does not yet interrupt a running raster computation. Agent session/story state is in process memory and will reset on server restart. A real Hermes gateway must be connected through a verified restricted profile before setting `SAR2ACTION_HERMES_SAFE_PROFILE_VERIFIED=true`; terminal, file modification, web, browser and arbitrary skills must remain inaccessible to this agent path.

## Remaining integration work

1. B team supplies an actual aligned signed-dB change GeoTIFF and valid-mask GeoTIFF, their SHA-256 hashes and manifest; A team supplies the matching persisted parent Evidence ID and approves scene-pair QA. The live adapter checks CRS, alignment, NoData, polarization, UTC acquisition dates, scene IDs and checksums before ranking. No HDF5 scene or per-pixel change GeoTIFF is present here, so live science remains unverified.
2. Configure a real OpenAI-compatible endpoint and credential, then verify inference, function calling, gateway reconnect, tool-deny profile and provider health on this host. The mocked tool-call test is only an integration contract test.
3. Add cooperative server-side cancellation for long raster work and durable session/evidence storage before multi-user deployment.
4. Supply a keyed or self-hosted basemap for competition deployment; the current OSM standard tile endpoint is suitable only for low-volume local demonstration.

## Reproduce

From `D:\SAR2Action`, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_phase3_demo.ps1`, then open `http://127.0.0.1:5173`, choose **Synthetic Demo**, and ask “找出這個地區變化最大的三個地方，帶我查看證據。” Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diagnose_phase3_environment.ps1` for diagnostics and `.\venv\Scripts\python.exe scripts\evaluate_phase3_agent.py` for HTTP evaluation. `scripts\run_phase3_demo.ps1 -Stop` stops only processes recorded by that launcher.
