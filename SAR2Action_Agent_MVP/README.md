# SAR2Action — Agentic Earth Change Intelligence

**Working standalone D-team vertical slice** · NISAR-only science · Evidence-grounded GIS interaction · Synthetic dataset until A/B provide NASA observations.

[Quick start](docs/README_AGENT.md) · [Contracts](docs/AGENT_CONTRACTS.md) · [Codex integration task](docs/CODEX_INTEGRATE_NOW.md) · [Engineering report](docs/AGENT_EVAL.md) · [Demo script](docs/DEMO_SCRIPT_AGENT.md)

**Windows**: `pip install -r backend/requirements.txt` then `./run_demo.ps1`, visit `http://127.0.0.1:8765`.

**Linux/WSL**: `pip install -r backend/requirements.txt` then `./run_demo.sh`.

**Test**: `PYTHONPATH=backend python -m pytest backend/tests -q`.

**Data**: default SYNTHETIC. Use `scripts/ingest_nisar_geotiff_pair.py` with real B-validated NISAR-derived data to create a manifest, then set `SAR2ACTION_LIVE_MANIFEST`.

**Hermes**: adapter present but intentionally disabled until official Hermes gateway is actually installed and its potentially powerful tools are independently restricted. No API keys are shipped.
