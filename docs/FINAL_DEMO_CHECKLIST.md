# Final release demo checklist

Run from `D:\SAR2Action` on Windows. Use the two entrances separately; they share the same backend and WebGIS, but have different data modes and source labels.

## Before the rehearsal

1. Confirm the three B-team cache files are present under `data\cache` and run `venv\Scripts\python.exe scripts\validate_science_cache.py`. The expected status is `SCHEMA_AND_INTERNAL_PROVENANCE_VALID`. This checks the delivered cache, not its source HDF5.
2. Confirm the local credential file stays outside any deployment package. The backend launcher reads it into the backend process only. Never paste its contents into a prompt, command argument, report or browser.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\accept_release.ps1`. Inspect `docs\RELEASE_ACCEPTANCE_RESULTS.json`. A failed or unrun gate is not a pass. The script runs Python, frontend, TypeScript/build, HTTP, Chrome, real Gemini, claim and security checks.
4. Check `docs\nisar_source_reproducibility.json`. If absent, keep **NISAR-DERIVED CACHE — PROVENANCE PENDING**. The source report was absent in this release-freeze audit.

## Demo A: NISAR cached evidence

Launch `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_release_demo.ps1 -Demo A`, or open `http://127.0.0.1:5173/?demo=A` after the services are healthy. This entry selects the flagship case, AOI-OKI-04, **NISAR Cached Evidence** and **Real AI Analysis**. Confirm the status says Gemini online, then ask the prefilled HH/HV question. The presenter should inspect `E-FLAGSHIP-OKI-004`, its observation dates, scene pair, pixelwise change definition, valid-pixel count, p10–p90 distributions, QA rule and limitations. Focus the map, open the Radar Fingerprint, generate the five-scene story, then switch AOI and show that the old story is stale.

Expected cached values: HH −0.2128 dB, HV −0.2056 dB, 3,148,830 recorded common valid pixels. They are medians of valid pixelwise T1-minus-T0 dB differences. Say **observed backscatter difference**. Do not claim source-verified pixels, statistically significant disturbance, fire, recovery, subsidence or live HDF5 computation. If Gemini returns a clear HTTP 503/504 tool-selection error, show the error; do not relabel deterministic output as real AI. Retry once after checking `/api/agent/status`; if the endpoint remains unavailable, end the real AI portion honestly.

## Demo B: synthetic spatial ranking

Launch `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_release_demo.ps1 -Demo B`, or open `http://127.0.0.1:5173/?demo=B`. This entry selects **Synthetic Demo** and deterministic execution. Confirm **SIMULATED DATA — NOT NASA OBSERVATIONS** stays visible. Ask the prefilled ranking question, compare the top regions, focus the map, inspect a synthetic Evidence Card, open the fingerprint and generate its five-scene story. Switch AOI and confirm old results disappear or become stale. Never combine Demo B's ranking with Demo A's NISAR evidence in one scientific claim.

## Release decision

The deterministic and cached UI paths can be rehearsed. The complete **real AI** rehearsal should be accepted only after the full acceptance script passes, including both real Chrome flows and the five-question Gemini evaluation. Recent HTTP 503/504 responses make that gate unstable. The source-provenance gate remains pending regardless of model availability.
