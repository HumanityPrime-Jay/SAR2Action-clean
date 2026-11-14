# SAR2Action — AI Earth Investigator (D team runnable package)

A standalone, working vertical slice to merge into the team's production repository. **This is not yet a validated NISAR analysis system**, because real competition datasets and the A/B science pipeline are not included. The default demo uses explicitly labelled synthetic data.

## Included
- Responsive high-fidelity dark dashboard with radar reveal slider, AOI canvas selection, before/after/difference/quality layers, data QC display.
- Agentic GIS run: scene list → pair QA → change computation → evidence creation → radar fingerprint → provenance lookup → typed map commands.
- Claim-to-pixel evidence IDs; interactive modal with timestamps, granules, AOI, method and limitations.
- Unknown-aware science communication, 5-frame evidence story, evidence-click return navigation, JSON export and stale flagging.
- 50 automated backend/science/trap tests, JavaScript syntax validation, deterministic synthetic fallback.
- Optional HTTP adapter to the official Hermes Agent gateway; **disabled until tool permission isolation is verified**.
- A one-command on-ramp for B-supplied real NISAR-derived geo-referenced GeoTIFF pairs.

## Quick start (Windows PowerShell)
```powershell
cd SAR2Action_Agent_MVP
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
.\run_demo.ps1
```
Go to `http://127.0.0.1:8765` in a local browser. This demo does not call NASA or any outside service; all apparent radar samples are synthetic.

## Linux / WSL
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
./run_demo.sh
```

## Tests
```bash
export PYTHONPATH="$PWD/backend"
./scripts/test_all.sh
python scripts/smoke_api.py
```
On Windows, set `$env:PYTHONPATH = "$PWD\backend"`, then run `python -m pytest backend/tests -q` and `node --check frontend/app.js`.

## Connect real NISAR tomorrow
1. Ask A/B for at least two real GCOV scenes, quality-masked and aligned, with actual granule IDs, timestamps, polarizations, orbit/look, CRID, product maturity and source HDF5 paths.
2. Use B's pipeline to produce AOI-cropped EPSG:4326 GeoTIFFs with identical grids for ONE polarization. Do not pass uncalibrated dB values or phase-derived displacement.
3. `python scripts/ingest_nisar_geotiff_pair.py --help` shows all mandatory metadata and output options. Output `data/live/manifest.json` and `radar_pair.npz`.
4. Start with `SAR2ACTION_LIVE_MANIFEST=/absolute/path/to/data/live/manifest.json` (PowerShell: `$env:SAR2ACTION_LIVE_MANIFEST=...`). If file/QA is invalid the app refuses to start rather than loading test data silently.
5. Verify pair QA, AOI masked coverage, evidence ID, timestamp, scenes and science statements. Replace the data only after A signs off.
6. If B already has a FastAPI analysis engine, adapt `/api/agent/investigate` and the typed tool registry to call B's read-only endpoints rather than duplicate B's heavy raster processing. Keep the current contracts.

## Hermes Agent connection (official, optional)
**Hermes Agent is an agent framework, NOT Hermes 2 Pro weights, and no verified `Hermes Agent 2` release exists.** At last checked 2026-11-12, stable release `v0.23.1` (see official GitHub Releases).

The Windows install is on your **own machine**, not bundled with this project:
```powershell
# Review the official installer and its contents before execution.
irm https://hermes-agent.nousresearch.com/install.ps1 -OutFile install-hermes.ps1
notepad install-hermes.ps1
.\install-hermes.ps1
hermes setup
hermes model
hermes doctor
```
Then configure `~/.hermes/.env` or its native Windows equivalent:
```
API_SERVER_ENABLED=true
API_SERVER_KEY=<your-local-random-secret>
```
Start `hermes gateway`. Verify `http://127.0.0.1:8642/v1/models` with the bearer key.

**Do not enable Hermes inside SAR2Action until you can demonstrate that its terminal, file, browser, web, skills and other built-in tools are disabled for that dedicated API profile**. The Hermes API server normally exposes Hermes' full toolset; a prompt saying “don't use tools” is NOT an enforced sandbox. The backend includes a guarded, default-off `HermesNarrator` that may rewrite deterministic text, but its output is not accepted by default because textual hallucination checks are not complete. Use the deterministic evidence narrator for the judged demo unless sandbox and provenance tests pass.

## Constraints
- Browser receives no Hermes key.
- No NISAR raster or provenance values created by the LLM.
- No one-click claim that wildfire, smoldering peat, smoke or population impacts have been confirmed.
- No unbounded GPU context; all default fixture calculations are NumPy/CPU and use small in-memory rasters.
- This package uses a schematic grid instead of a real base map. C team should replace it with their MapLibre view and keep the typed event bridge.

## Official references
- Hermes: https://github.com/NousResearch/hermes-agent
- API: https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
- Windows install: https://hermes-agent.nousresearch.com/docs/getting-started/installation
- NASA rules: https://github.com/nasa/spaceapps/discussions/1827
