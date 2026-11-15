# Planetary Change Stories (`EarthStoryService`)

## Purpose
Synthesizes real satellite observations, Reality Lens states, competing hypotheses, and evidence gaps into a 7-chapter interactive scientific narrative.

## Features
- **7-Chapter Synchronized Playback**: Each chapter specifies `lens_mode`, `camera` (`lon`, `lat`, `zoom`), `region_id`, `evidence_ids`, `scientific_status`, and `key_takeaways`.
- **Persistence & Portability**: Stories can be generated on demand, persisted, exported as JSON or standalone HTML, and re-imported via `POST /api/earth/stories/import` with schema validation.

## API
- `POST /api/earth/stories/generate`
- `GET /api/earth/stories/{story_id}`
- `POST /api/earth/stories/import`
