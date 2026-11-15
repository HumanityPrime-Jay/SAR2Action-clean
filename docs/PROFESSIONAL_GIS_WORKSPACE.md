# Professional GIS Workspace

## Capabilities (`backend/app/advanced/dual_mode/gis_workspace.py`)
- **Geodesic Geometry**: WGS84 spherical-excess area calculation, self-intersection validation, buffer area estimation, and polygon intersection (`FarmerFieldService`).
- **Field & Cross-Field Statistics**: Valid pixel counts, coverage ratios, dB medians/IQR on linear gamma0 scale, and 5-field comparisons (`YL-CAND-01..05`).
- **Scientific Compare Mode & Cross-CRID Guard**: `POST /api/gis/compare` blocks unverified NISAR differencing (`P05023` vs `P05036`) with `BLOCKED_CROSS_CRID_INCOMPATIBLE`.
- **Controlled Map Actions**: `POST /api/agent/map-action` permits only `SHOW_LAYER`, `HIDE_LAYER`, `ZOOM_TO_AOI`, `SELECT_FIELD`, `COMPARE_OBSERVATIONS`, `OPEN_TIMELINE`, `DISPLAY_STATISTICS`.
