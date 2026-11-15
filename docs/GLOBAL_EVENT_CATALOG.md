# Global Event Catalog (`GlobalEventCatalog`)

## Purpose
Provides a structured, provenance-tagged catalog of Earth change events across 8 supported disaster and environmental categories without fabricating unverified measurements.

## Supported Event Types
- `TYPHOON`
- `FLOOD`
- `LANDSLIDE`
- `SUBSIDENCE`
- `COASTAL_CHANGE`
- `AGRICULTURAL_ANOMALY`
- `DROUGHT`
- `THERMAL`

## Provenance Statuses
- `CHANGE_ANALYZED`: Committed local scientific studies with verified parcel geometry and real SAR observations (`CHAMPI-YUNLIN-TAIXI`, `TW-05-YUNLIN-AGRO`).
- `COMPARISON_COMPATIBLE` / `OBSERVATION_AVAILABLE`: Regions with compatible sensor acquisitions ready for delta verification.
- `CATALOG_DISCOVERED`: Global CMR discovery targets whose footprints and metadata are indexed, while parcel-level damage or cross-sensor deltas remain explicitly unverified until ingested.

## API
- `GET /api/earth/events?event_type=...&q=...`
