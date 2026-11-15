# Change Fingerprint (`ScientificFingerprintService`)

## Purpose
Computes deterministic multi-temporal backscatter signatures and compatibility-gated similarity metrics without fabricating missing polarizations or spatial statistics.

## Key Guarantees
- **Observed Bands**: Computes `vh_temporal_signature`, `temporal_difference_db`, and `seasonal_reference_db` from real Sentinel-1 IW GRD acquisitions.
- **Missing Evidence Transparency**: Unmeasured polarizations (`hh_hv_signature`) and unavailable metrics are explicitly returned as `"NOT_AVAILABLE"` with `missing_evidence` entries.
- **Compatibility Gating**: `compareFingerprints` and `findSimilar` refuse to compute cross-sensor/cross-CRID distances when `comparable: false`, returning `incompatibility_reasons` and `scientific_caution`.

## API
- `GET /api/earth/fingerprint/{region_id}`
- `POST /api/earth/fingerprint/compare`
- `GET /api/earth/fingerprint/{region_id}/similar`
