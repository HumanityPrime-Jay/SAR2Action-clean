# Smart Indicator Explanation System

## Registry (`backend/app/advanced/indicator_explainer/registry.py`)
Defines **22 required indicators** (`VH_BACKSCATTER_DB`, `VH_CHANGE_DB`, `HH_BACKSCATTER_DB`, `HV_BACKSCATTER_DB`, `VALID_PIXEL_COUNT`, `VALID_COVERAGE_RATIO`, `FIELD_AREA_HA`, `AOI_AREA_HA`, `TEMPORAL_BASELINE`, `ACQUISITION_DATE`, `OBSERVATION_COUNT`, `SPATIAL_RESOLUTION`, `PRODUCT_VERSION`, `CRID_COMPATIBILITY`, `NOISE_FLOOR_STATUS`, `SCIENTIFIC_QA_STATUS`, `EVIDENCE_STATUS`, `FIELD_COMPARISON`, `ESTIMATED_AFFECTED_AREA`, `FARMER_REPORTED_DAMAGE_AREA`, `POTENTIAL_RELIEF_AMOUNT`, `APPLICATION_DEADLINE`) and **7 data status codes** (`OBSERVED`, `SUPPORTED`, `UNRESOLVED`, `NOT_EVALUATED`, `INSUFFICIENT_DATA`, `NOT_COMPATIBLE`, `NOT_ESTIMABLE`).

## Context-Aware & Accessible Help
- `POST /api/indicators/explain` binds the current field, value, acquisition date, source, and QA status without allowing LLMs to alter observed numbers.
- `ESTIMATED_AFFECTED_AREA` returns `NOT_ESTIMABLE` unless validated pixel classification exists.
- Frontend component `frontend/src/components/IndicatorTooltip.tsx` provides `ⓘ` with hover (desktop), click/tap (mobile/desktop), and keyboard/ARIA support.
