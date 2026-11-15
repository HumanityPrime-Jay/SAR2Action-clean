# Earth Memory — Acquisition-Based Time Machine (`EarthMemoryService`)

## Purpose
Replaces interpolated animations with an **acquisition-based** temporal inspection engine that strictly distinguishes real satellite passes from unmeasured periods.

## Key Guarantees
- **Real Acquisitions**: Every frame carries `acquisition_time_utc`, `acquisition_time_local` (`Asia/Taipei` CST, e.g. `2026-10-22T21:51:56Z` → `2026-10-23 05:51:56 CST`), `sensor`, `polarization`, `product_version`, and `warning_phase` (`DURING_TYPHOON_WARNING`).
- **Explicit Gaps**: Unobserved windows are emitted as `observation_gaps` with `status: "NO_OBSERVATION"` and dashed SVG indicators rather than interpolated points.
- **Cross-CRID Guardrails**: Comparisons between incompatible processor versions (`P05023` vs `P05036`) emit explicit `cross_sensor_warnings` and `compatible_with_baseline: false`.

## API
- `GET /api/earth/events/{event_id}/timeline?field_id=...`
