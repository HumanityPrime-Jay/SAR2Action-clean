# SAR2Action D ↔ A/B/C contracts, v1

## Contract boundary
- A owns scientific interpretation and validates scene-pair comparability. No model is allowed to label burned area from GCOV differences alone.
- B owns NISAR HDF5/GCOV processing; this standalone package consumes only **pre-geocoded, co-registered, quality-masked** NISAR-derived 2-D intensity arrays (dB).
- C owns MapLibre. D publishes a **typed action payload**; UI can adapt its dispatcher without permitting arbitrary JS from LLMs.
- D owns task orchestration, provenance links and five-frame evidence stories.

## Required endpoints (FastAPI, same origin)
| Method & path | Purpose |
|---|---|
| GET `/api/scenes` | Scene metadata with `simulated` flag and dataset bbox. |
| POST `/api/pair/validate` | `scene_before`, `scene_after` → compatibility, overlap, reasons. |
| POST `/api/change/compute` | Pair + `polarization` + `bbox` → change stats, dB. |
| GET `/api/grid` | Preview-size 2D difference array with null for invalid. |
| POST `/api/agent/investigate` | Controlled flow with tool trace, facts and allowlisted map actions. |
| GET `/api/evidence/{id}` | Provenance, method version, QA, source granules, limitations. |
| POST `/api/story/build` | Evidence IDs → five evidence-bound frames. |
| GET `/api/story/{id}/validate` | Status current/stale. |
| GET `/api/operations/{session}` | Per-session tool trace. |

### Investigation request
```json
{
  "scene_before":"<real_scene_id>",
  "scene_after":"<real_scene_id>",
  "polarization":"HV",
  "bbox":{"west":101.3,"south":-0.2,"east":102.1,"north":0.4},
  "query":"Explain the evidence in this area",
  "locale":"zh-TW","audience":"general","session_id":"session-01",
  "intent":"investigate"
}
```

### Response contracts
Agent output includes `status`, `mode: fixture|live`, `observed_facts[{text,evidence_ids,quantitative}]`, `unknowns`, `possible_interpretations`, `evidence_refs`, `steps`, `map_actions`, `narrative`, `fingerprint` and optional `story`. Quantitative claims carry valid `evidence_ids` created by the deterministic evidence ledger. All commands use only these types:

```
map.focus_bbox       {"bbox":{...}}
map.highlight_aoi    {"bbox":{...}}
map.set_layer        {"layer_id":"difference"}
fingerprint.open     {"evidence_id":"..."}
evidence.open        {"evidence_id":"..."}
story.open           {"story_id":"..."}
```

For C's existing MapLibre app, implement these commands in its state store or reducers. NEVER evaluate a command as JS, accept an arbitrary layer, or navigate to an LLM-produced URL.

## Live data handoff (tomorrow's B integration)
`SAR2ACTION_LIVE_MANIFEST=/absolute/path/to/manifest.json` enables **live-only** mode. If invalid, startup fails; it does not silently load synthetic fixtures. Manifest schema:

```json
{
  "schema_version":"1",
  "data_kind":"nisar",
  "bbox":{"west":101.0,"south":-0.2,"east":101.8,"north":0.6},
  "pixel_spacing_m":null,
  "raster_npz":"radar_pair.npz",
  "scenes":[
    {"scene_id":"REAL_ID_0","acquired_at":"2026-08-19T02:00:00Z","polarizations":["HV"],"orbit_track":"<VERIFIED>","look_direction":"right","grid_id":"<SAME_GRID_ID>","product_maturity":"PROVISIONAL","crid":"<VERIFIED>","source_granule":"<ACTUAL_ASF_GRANULE>","simulated":false},
    {"scene_id":"REAL_ID_1","acquired_at":"2026-09-20T02:00:00Z","polarizations":["HV"],"orbit_track":"<VERIFIED>","look_direction":"right","grid_id":"<SAME_GRID_ID>","product_maturity":"PROVISIONAL","crid":"<VERIFIED>","source_granule":"<ACTUAL_ASF_GRANULE>","simulated":false}
  ]
}
```

**The manifest above is schema documentation only, NOT real observations.** Do not use the example scene IDs, dates, coordinates or metadata in the demo. The matching `.npz` must contain: `REAL_ID_0__HV`, `REAL_ID_1__HV`, `REAL_ID_0__valid`, `REAL_ID_1__valid` arrays on exactly the same grid. Each polarization is a calibrated backscatter **dB** array. Missing pixels must be false in `__valid`, not given fictitious zero values.

Preferred handoff: B supplies cropped/co-registered GeoTIFFs, actual ASF granule IDs and QA-approved metadata. Then run `scripts/ingest_nisar_geotiff_pair.py --help` and start the server with `SAR2ACTION_LIVE_MANIFEST` pointing to the generated manifest. The import tool explicitly rejects geographic/grid mismatch instead of silently distorting measurements.

### Science and security assumptions
- GCOV covariance diagonal is **power**; convert to dB via `10·log10(power)` before comparing.
- Pair QA validates orbit track, look direction, common polarization, grid ID, maturity, CRID and >=30% valid overlap. A must review scientific appropriateness beyond these automatic checks.
- Preview grid in frontend is not full-resolution; numerical statistics in API are computed over the full cropped AOI matrix.
- Only NISAR is allowed as analytical source. Generic UI canvas background is **schematic**, not external imagery.
- No public fire-attribution, smoke, population, health or centimeter-displacement claims.
- All data in `fixture` mode is explicitly simulated; no NASA measurement is bundled.
