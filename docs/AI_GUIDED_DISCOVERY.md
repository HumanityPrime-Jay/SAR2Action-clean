# AI Guided Discovery (`GuidedDiscoveryService` & `AIMapActionValidator`)

## Purpose
Provides context-aware bilingual (`zh` / `en`) natural-language control over the Earth Change Intelligence workspace while preventing hallucinated UI/map commands.

## Security & Scientific Guardrails
- **Backend-Only Gemini**: Uses `GEMINI_API_KEY` solely on the FastAPI backend (`GuidedDiscoveryService`), with a deterministic bilingual fallback when Gemini is unavailable or offline.
- **Allowlisted Map Actions**: `AIMapActionValidator` enforces 19 strict action types (such as `FLY_TO_REGION`, `SWITCH_LENS`, `SELECT_PARCEL`, `SWITCH_EVENT`, `OPEN_TAB`, `PLAY_STORY`, etc.), rejecting any unvalidated or out-of-bounds action.
- **Role-Aware Modes**: Supports `FARMER` (plain-language agricultural/relief clarity) and `AUTHORITY` (technical SAR/legal provenance detail), never fabricating unconfirmed crop damage or confidence percentages.

## API
- `POST /api/earth/guided-discovery`
