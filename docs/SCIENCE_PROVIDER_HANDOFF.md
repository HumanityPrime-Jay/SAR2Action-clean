# Science provider handoff (B → D)

The Phase 7 agent runs from `D:\SAR2Action`. The guide's `D:\NASA\SAR2Action` is not present on this machine. B can hand off a small, read-only evidence package without transferring the full HDF5 collection.

Required inputs:

1. `data/cache/evidence_store.json` with `schema_version` and `records` conforming to `EvidenceRecord`.
2. `data/cache/fingerprint_store.json` with `fingerprints` conforming to `RadarFingerprintResponse`.
3. `data/cache/analysis_store.json` with `analyses` and per-claim source IDs.
4. The Science API source or reachable endpoint supporting `GET /api/cases`, `POST /api/radar-fingerprint`, and `GET /api/evidence/{evidence_id}`. Configure `SAR2ACTION_SCIENCE_API_URL`; use port 8001 if D's backend owns 8000.
5. Evidence schema/version and a checksum for each handed-off file.
6. Scene pair IDs, acquisition UTC times, AOI ID and WGS84 geometry, and polarization mapping.
7. Provenance and QA records: source granule identifiers or authoritative product records, method/version, valid-pixel mask and counts, units, calibration, limitations, and A/B review decision.

The `ScienceEvidenceProvider` reads the JSON files without modifying them and validates typed responses and case/AOI/evidence links. Presence and schema validity alone do not prove NASA provenance. Until the QA and source records are checked, label the source **NISAR CACHED EVIDENCE · PROVENANCE NOT VERIFIED**. It is never called live computation.

After copying the three files into this workspace, run `D:\SAR2Action\venv\Scripts\python.exe -m scripts.validate_science_cache` from `D:\SAR2Action`. For another readable location, pass `--cache-dir <absolute-path>` and set `SAR2ACTION_SCIENCE_CACHE_DIR` to the same path for the backend. The audit is read-only and writes only its validation report to `docs/phase7_science_data_validation.json`; it checks the six guide-listed IDs, typed records, claims, and internal scene/AOI/evidence links. It does not certify external NASA provenance.

AOI-level cache statistics cannot support ranking subregions. B must separately supply the signed georeferenced change raster and valid-pixel mask in `SPATIAL_RANKING_CONTRACT.md` for real spatial ranking. Synthetic ranking remains isolated.
