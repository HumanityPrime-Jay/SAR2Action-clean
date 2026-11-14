# Final known limitations

## Scientific source and interpretation

- **Provenance pending:** B team's `evidence_store.json`, `fingerprint_store.json` and `analysis_store.json` pass internal consistency checks. No source-machine HDF5 reproducibility report, original-product SHA-256 pair or processing commit has been delivered to this workspace. Do not upgrade the cache to **Verified Source**.
- **No independent pixel recount:** The recorded 3,148,830 valid pixels and HH/HV medians have not been independently recalculated from source HDF5 on this computer. The B-team [read-only verification request](SCIENCE_REPRODUCIBILITY_REQUEST.md) remains open.
- **No significant-disturbance claim:** AOI-OKI-04 has pixelwise change distributions but no registered stable control region or significance assessment. The signed medians near −0.2 dB do not establish region-wide disturbance. Two observation dates cannot pinpoint when a change occurred.
- **No causal confirmation:** Backscatter differences alone cannot confirm peat fire, underground combustion, forest recovery, subsidence, displacement or burn severity. The source product is provisional, and its RFI comparison metadata is marked unreliable in the cache.
- **No real within-AOI ranking:** A signed georeferenced change raster and matching valid-pixel mask have not been handed off. Ranked subregions in Demo B are explicitly synthetic.

## Model, product and release

- **Gemini availability varies:** `gemini-3.1-flash-lite` performed valid Function Calling, but the release-freeze run also observed HTTP 503 and 504 from its generate endpoint. The model listing/status endpoint can be online while an inference request fails. The backend uses three bounded attempts and shows the safe HTTP failure without deterministic substitution. `gemini-2.5-flash` and `gemini-2.5-flash-lite` appeared in model listing but returned HTTP 404 for the tested Function Calling request; they were not adopted.
- **Gemini is a planner:** The model selects allowlisted GIS functions. Evidence values and final scientific wording are produced by trusted backend logic; the system does not use unrestricted model-generated scientific numbers.
- **Release gate is sensitive to external service:** A full Chrome run can fail when Gemini inference is unavailable even though deterministic, cache and HTTP tests pass. The acceptance script records every gate and exits nonzero on any failure.
- **Frontend bundle size:** Vite reports a JavaScript chunk larger than 500 kB. This is a build warning, not a failed build. The broader WebGIS leaves unused space on wide desktop layouts; no main-interface redesign was included in this freeze.
- **Security audit scope:** Exact-key scanning covers project source, scripts, reports, frontend bundle and generated Playwright artifacts. It cannot prove absence of all encoded forms or files outside the scanned workspace. This directory has no Git repository, so Git history was not audited. No deployment package was produced; packaging must exclude `GERMINI API.txt`.
