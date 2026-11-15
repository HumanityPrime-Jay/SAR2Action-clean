# Dual-Mode Architecture (`FARMER` / `AUTHORITY`)

## Modes & Separation of Authorization
- `FARMER`: Plain Taiwan Traditional Chinese, 1–3 short sentences, 1 question per turn, structured Result Cards.
- `AUTHORITY`: Technical remote sensing, GIS statistics, tool traces, uncertainty, and legal citations.
- **Security**: Mode switching (`ModeTransitionController`) preserves AOI, loaded layers, shared conversation context, and public analysis results while stripping sensitive keys (`private_*`). Mode preference NEVER elevates backend authorization (`is_authenticated_authority=False` by default).

## API Endpoints
- `GET /api/ui/modes`
- `GET /api/ui/capabilities?mode=FARMER|AUTHORITY`
- `POST /api/agent/chat`
- `POST /api/farmer/chat`
