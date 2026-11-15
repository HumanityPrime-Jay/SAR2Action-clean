# SAR2Action Frontend Handoff Contract (P9)

> **Integration Status**: `FRONTEND_INTEGRATION_PENDING`
> - Standalone components ready for UI embedding: `frontend/src/components/ModeSwitcher.tsx`, `frontend/src/components/IndicatorTooltip.tsx`
> - Existing `frontend/src/App.tsx` and visual layout remain unmodified.

---

## 1. Mode Switch Contract
- **Endpoint**: `GET /api/advanced/ui/modes`
- **Modes**:
  - `FARMER`: Plain-language Taiwanese Traditional Chinese, max 1–3 short sentences, max 1 follow-up question per turn, structured cards for details.
  - `AUTHORITY`: Full GIS statistics, spatial reference matching, temporal guard, QA flags, Evidence IDs, and `DECISION_SUPPORT_ONLY` legal posture.
- **Capabilities Check**: `GET /api/advanced/ui/capabilities?mode=FARMER|AUTHORITY`

## 2. Farmer Conversation API
- **Endpoints**:
  - `POST /api/advanced/farmer/chat`
  - `POST /api/advanced/agent/chat` (`mode: "FARMER"`)
- **Request**:
```json
{
  "session_id": "string",
  "message": "string",
  "selected_field_id": "YL-CAND-03 | null",
  "optional_map_geometry": "GeoJSON Geometry | null",
  "optional_damage_geometry": "GeoJSON Geometry | null",
  "optional_event_id": "string | null"
}
```
- **Response**:
```json
{
  "reply": "1–3 short sentences in zh-TW",
  "conversation_state": "ACTIVE_CONVERSATION | WAITING_FOR_FIELD_SELECTION | ANNOUNCEMENT_NOT_VERIFIED | APPLICATION_GUIDANCE_PROVIDED | GUARDRAIL_REFUSAL | OUT_OF_SCOPE",
  "intent": "FarmerIntent",
  "suggested_actions": [{ "action_type": "string", "label": "string" }],
  "result_cards": [{ "card_type": "string", "title": "string", "data": {}, "citations": [] }],
  "sources": ["M0090019-ARTICLE-12"],
  "requires_confirmation": false,
  "session_state": {}
}
```

## 3. Authority Analysis API
- **Endpoints**:
  - `POST /api/advanced/agent/chat` (`mode: "AUTHORITY"`)
  - `POST /api/advanced/gis/analyze`
  - `POST /api/advanced/gis/compare`
- **Returns**: `decision_posture: "DECISION_SUPPORT_ONLY"`, `scientific_evidence` (VH delta, SAR quality, spatial controls, experimentation, reproducibility), `legal_authority` (`M0090019` 2026-06-29), `required_follow_up`, `limitations`, and `evidence_ids`.

## 4. Structured Response Cards
| `card_type` | Purpose | Key Data Fields |
| --- | --- | --- |
| `FIELD_AREA_CARD` | Geodesic parcel area | `field_id`, `area_m2`, `area_ha`, `area_fen` |
| `DAMAGE_ESTIMATE_CARD` | Layered damage evidence | `SATELLITE_SUSPECTED_CHANGE`, `FARMER_REPORTED_AFFECTED_AREA`, `GOVERNMENT_VERIFIED_DAMAGE_AREA` |
| `CROP_LOSS_CARD` | Yield & financial loss | `yield_loss`, `financial_loss` (`INSUFFICIENT_DATA` if missing history) |
| `RELIEF_PROGRAM_CARD` | Announcement & legal check | `announcement` (`ANNOUNCEMENT_NOT_VERIFIED` / `VERIFIED_ANNOUNCEMENT_FOUND`), `legal_status` |
| `RELIEF_AMOUNT_CARD` | Relief calculation guard | `status`, `POTENTIAL_RELIEF_ESTIMATE_NTD`, `is_approved_amount: false`, `missing_requirements` |
| `APPLICATION_STEPS_CARD` | Office, deadline & docs | `application_office`, `deadline_reminder`, `required_documents` |

## 5. Map Action Schema (`POST /api/advanced/gis/map-action`)
- `OPEN_FIELD_PICKER`: Pan/zoom to Taixi candidate fields (`YL-CAND-01`..`05`).
- `SELECT_FIELD_ON_MAP`: Bind `selected_field_id` and trigger geodesic area + VH lookup.
- `DRAW_DAMAGE_AREA`: Enable polygon draw tool; submit GeoJSON via `optional_damage_geometry`.
- `COMPARE_FIELDS`: Open side-by-side / cross-field VH comparison panel.

## 6. Indicator Tooltip Contract
- **Endpoints**: `GET /api/advanced/indicators`, `GET /api/advanced/indicators/{indicator_id}`, `POST /api/advanced/indicators/explain`
- **Payload (`mode: "FARMER" | "AUTHORITY"`)**:
  - `indicator_id`, `plain_explanation`, `technical_definition`, `calculation_method`, `unit`, `actual_value`, `scientific_limitations`, `data_source`, `next_steps`.
- Covers **22 indicators** and **7 data status codes**. Numeric values are immutable across modes.

## 7. Session State Contract (`FarmerSessionState`)
`session_id`, `turn_count`, `county`, `township`, `crop`, `disaster_event`, `selected_field_id`, `field_area_m2`, `field_area_ha`, `farmer_reported_affected_area_ha`, `farmer_reported_damage_ratio`, `completed_tools`, `last_intent`, `history`.

## 8. Error & Guardrail Handling
- `ANNOUNCEMENT_NOT_VERIFIED`: Prompt user to check township office / MOA; never guess eligibility.
- `HUMAN_REVIEW_REQUIRED` / `CANNOT_ESTIMATE_MISSING_REQUIREMENTS`: Block relief multiplication until verified rate + announcement + area + loss threshold exist.
- `VERSION_NOT_VERIFIED` / `OUT_OF_SCOPE` / `INSUFFICIENT_LEGAL_BASIS`: Display non-fabrication notice; never invent statutes.
- HTTP `429` / Gemini timeout: Automatic fallback to deterministic grounded response + structured cards.

## 9. Loading States
- `TOOL_EXECUTING`: Show lightweight status indicator (`"正在查詢衛星資料與法規條文..."`) during live Gemini tool-calling turns (typically 1.5–4.5 s).
- `IDLE` / `WAITING_FOR_MAP_INPUT`: Highlight `suggested_actions` buttons directly beneath the latest assistant bubble.
