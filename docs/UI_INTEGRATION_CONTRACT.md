# UI Integration Contract

## Backend Endpoints for UI Teammate
- `GET /api/ui/modes`, `GET /api/ui/capabilities`
- `GET /api/indicators`, `GET /api/indicators/{indicator_id}`, `POST /api/indicators/explain`
- `POST /api/gis/analyze`, `POST /api/gis/compare`, `POST /api/agent/map-action`
- `POST /api/farmer/chat`, `POST /api/agent/chat`
- `POST /api/agent/investigate-advanced`, `POST /api/agent/legal-query`, `POST /api/agent/legal-search`, `GET /api/agent/legal-sources`

## Reusable Frontend Components
- `frontend/src/components/ModeSwitcher.tsx` (`FARMER` / `AUTHORITY` accessible toggle)
- `frontend/src/components/IndicatorTooltip.tsx` (`ⓘ` hover + click/tap + ARIA dialog)

## Map Action Schema
```json
{
  "action_type": "SELECT_FIELD",
  "payload": {"field_id": "YL-CAND-03"},
  "execution_mode": "CONTROLLED_FRONTEND_DISPATCH"
}
```
