# Local deployment

Use Python 3.12+ and Node.js. From the repository root create and activate `.venv`, run `python -m pip install -e '.[dev]'`, then `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`. From `frontend/`, run `npm ci` and `npm run dev`. Check `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:5173`.

Use `SAR2ACTION_LLM_PROVIDER=mock` for the synthetic demo. For Gemini, provide `GEMINI_API_KEY` only in the backend process environment and set `SAR2ACTION_LLM_PROVIDER=gemini`. Cached evidence requires authorized local JSON in `data/cache/`; live analysis requires authorized NISAR products. Neither cache nor raw products are part of the repository. Do not expose this development server directly to untrusted networks: the FastAPI app currently allows permissive CORS and has no production authentication.

