# SAR2Action Phase 6 — real data integration readiness

Validated on Windows, 2026-11-12. **Formal live NISAR analysis is BLOCKED.** The workspace has NISAR catalog metadata and QA sidecars, but no signed georeferenced change GeoTIFF, full GCOV pixel files, matching live manifest or completed source provenance. The working real-model demo uses explicitly marked synthetic pixels. It is not a NASA observation result.

## B-team handoff audit

The machine-readable [data audit](phase6_nisar_data_validation.json) inventories the workspace and lists every required manifest field. The catalog contains **630 scene metadata records** and **50 catalog-screened pairs**; these are candidates, not pixel-level pair QA. There are **61 small `QA_STATS.h5` sidecars**, **0 full GCOV scene HDF5 files**, **8 mask GeoTIFFs** and **0 signed change GeoTIFFs**. `SAR2ACTION_SPATIAL_MANIFEST` is unset. Existing masks cannot be paired scientifically with a change raster that is absent. [The strict validator](phase6_nisar_data_validation.json) reports the missing manifest; no synthetic file was accepted as live input.

Minimum B-team delivery for one formal live case:

1. A signed, georeferenced, single-band **dB change GeoTIFF** for a compatible T0/T1 GCOV pair and stated polarization.
2. Its **pixel-aligned jointly valid mask GeoTIFF**, with explicit NoData and invalid-pixel policy.
3. An absolute-path-configured JSON manifest following [the spatial ranking contract](SPATIAL_RANKING_CONTRACT.md), including scene IDs and versions, UTC dates, polarization, processing method/version, pixel resolution, linear-power versus dB source declaration, conversion formula, output `dB` unit and SHA-256 hashes.
4. A registered **parent Evidence ID** matching those files, scene pair, dates, polarization and quality decision.
5. Source GCOV pixel files or auditable source-pixel extracts plus processing records, so independent reviewers can verify the dB conversion, mask and random pixels.

## Integration and scientific gates

The live adapter now calls scene-pair compatibility QA for the manifest pair and selected AOI before reading the raster. It checks parent Evidence scene IDs, polarization, quality, acquisition times and CRID when available. It checks GeoTIFF hashes, EPSG:4326, north-up transform, pixel alignment, declared resolution, AOI coverage, explicit NoData and finite valid values. Valid pixels use both the mask value and its GDAL validity mask; a nonzero NoData sentinel is excluded. The adapter reads an already signed dB raster and **does not apply `log10` again**. If source power was linear, B must document `10*log10(P)` before differencing; if source was already dB, the manifest declares `conversion_formula: none`. Source-unit declarations cannot prove correct processing without source-pixel review.

Derived Evidence IDs now include the change and mask hashes, parent Evidence, scene IDs/versions, selected AOI, polarization, method and measured component. Cross-AOI, cross-source and cross-version region comparisons are rejected. Evidence records expose scene IDs, UTC dates, quality, method, parent ID, source hashes and the metric unit. MapLibre receives only verified EPSG:4326 bounding boxes. The UI shows those provenance fields and clearly displays when the B-team live handoff is missing.

The **contract test** uses small generated temporary rasters, not NISAR observations. It checks signed direction and magnitude (3.0 dB), a 49-pixel connected region, WGS84 bounds, geodesic area, a nonzero mask NoData sentinel reducing that region to 48 pixels, source-hash-driven Evidence ID changes, compatible/incompatible pair QA, a mock-model live-tool route, MapLibre focus action, current Evidence and five-scene Story linkage. Existing tests also cover isolated extreme pixels, sparse coverage and minimum region area. These verify software behavior; they do **not** validate the science of absent B-team observations.

The following real-data scientific checks remain **BLOCKED**: random source-pixel spot checks, HH/HV source-channel mapping, actual change direction and magnitude, actual NoData exclusion, real area/geometry comparison, B-team provenance, real Radar Fingerprint values, and Story claims against real scene pixels. No wildfire, displacement or recovery conclusion is inferred from backscatter change alone.

## Executed verification

| Check | Result |
| --- | --- |
| Full Python pytest | **PASS: 85 passed, 6 skipped**, 10 warnings; the six skips include unavailable real-scene cases |
| Frontend unit tests | **PASS: 9 passed** |
| TypeScript and Vite production build | **PASS**; pre-existing large-bundle warning |
| Chrome E2E | **PASS: 3 passed**, including real LLM tool calling and MapLibre action on **synthetic** data |
| Existing Q1–Q5 HTTP regression | **PASS: 5/5**, synthetic data |
| Fresh real-model tool trace | **PASS: rank → compare → inspect Evidence**, three evidence-bound observed findings; [trace](phase6_real_agent_trace.json) is explicitly synthetic |
| Live-mode missing-data HTTP | **PASS: deterministic HTTP 422; real agent `blocked` with no claims or evidence**; [probe](phase6_live_refusal.json) |
| Contract and scene-pair tests | **PASS on temporary test rasters**; no NASA input |
| Formal real NISAR raster, agent, map, fingerprint and Story validation | **BLOCKED: source files and manifest missing** |

The [demo readiness checklist](phase6_demo_readiness.json) checked the running backend, frontend, model, synthetic Evidence API, Story Builder and Chrome MapLibre flow. It reports **Synthetic Demo READY** and **Live Competition Demo BLOCKED**. This distinction is also visible in the UI. The Phase 5 [17-question real-model benchmark](phase5_agent_benchmark.json) remains unchanged as historical evidence; Phase 6 executed a fresh real-model tool trace and Chrome flow rather than counting the Phase 5 benchmark as a new result.

## Start and repeat

From `D:\SAR2Action`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_phase4_demo.ps1
.\venv\Scripts\python.exe scripts\audit_phase6_data.py
.\venv\Scripts\python.exe scripts\verify_phase6_demo.py
```

Open `http://127.0.0.1:5173`, choose an AOI, select **Synthetic Demo** and **Real AI Analysis**, then ask for the top three changes, comparison and Evidence. The same path shows Radar Fingerprint, limitations and a five-scene Story. Live NISAR remains unavailable until the handoff above passes validation and independent source-pixel checks. The local llama.cpp model is operational; Hermes is optional and remains blocked by its actual 4,096-token server context.

**Competition status:** the synthetic demonstration is repeatable and clearly labeled. A formal real NISAR competition demonstration **cannot yet be claimed**. The next gate is B-team delivery of the minimum files and A/B approval of comparability, calibration, masking and interpretation.
