# Codex — SAR2Action D-team integration, EXECUTE NOW (explicit project-owner decision)

> User has explicitly authorized implementation now. **Competition eligibility warning:** NASA Space Apps organizers state that project work before the official Nov 14 start may cause disqualification. The professor's approval does not change organizer rules; have the team lead document their decision. Do not represent this as organizer-cleared development.

You are the principal engineer in the user's **actual local SAR2Action repository**. The attached `SAR2Action_Agent_MVP/` is a **working isolated vertical slice** built from the agreed plan, NOT yet integrated into teammates' repository, and contains synthetic test data rather than NASA data. You must implement, run and test rather than describe. Timebox: **one working day**. Do not modify other teammates' feature branches without a clean interface contract.

## Read first
1. `docs/README_AGENT.md`
2. `docs/AGENT_CONTRACTS.md`
3. `docs/AGENT_EVAL.md`
4. The original SAR2Action NASA 2026 consolidated plan, if available in the repository.

## One large implementation batch
1. Inspect `git status`, app architecture and existing B/C APIs. Record initial state and an integration branch. Preserve uncommitted work. Map the current React + TypeScript + MapLibre architecture, then **port** the working `frontend/app.js` interactions into C's existing UI (do not overwrite C's design), reusing: selection AOI, pair QA, layer state, Radar Reveal, fingerprint/evidence modal, story timeline. The provided pure JS demo is behavioral reference, not required production UI.
2. Reuse `backend/app/models.py`, `data.py`, `agent.py`, `main.py` as backend adapters. Preserve B's existing heavy NISAR HDF5/COG process; replace `RadarDataService` only behind a stable interface. All claims must flow from B's deterministic outputs; no fake confidence, dates, burn area or centimeter displacement.
3. Set up official NousResearch Hermes Agent on user's Windows PC (CLI native, not a guessed `Hermes Agent 2` package). Use official current stable installer and verify `hermes doctor`, `hermes model`, `hermes gateway`, HTTP `/v1/models`, a short chat smoke test. Configure a **dedicated constrained profile** disabling Hermes' terminal/file/web/browser/skills and other built-in toolsets; verify permissions by attempting denied actions. Keep all credentials out of git and the frontend. If sandbox cannot be proven safe, leave Hermes bridge disabled and explain; D's constrained deterministic tool runner must remain working.
4. Extend the safe Agent Orchestrator to use the Hermes model for *bounded intent parsing* and narration only where supported; an explicit command allowlist and deterministic API tool executor remain authoritative. Do NOT accept raw model JS, remote URLs, arbitrary shell commands or invented evidence IDs. Add timeout/retry/cancel, request ID, concurrency 1, trace and stale-response handling.
5. Integrate the mandatory P0 flow: select AOI → valid NISAR scene pair → quality check → compute Δγ⁰ dB → fingerprint → evidence claim chip click → map focus and provenance → five-frame story → export. Verify everything in a browser. If B data isn't ready, use the supplied synthetic test mode with permanent DEMO labels; do not present it as NASA data.
6. Run existing backend tests, TypeScript/build/lint and one browser interaction test in the real repo. Fix failures. Create a 90-second recorded-ready demo sequence and a README with exact start commands.
7. Prepare tomorrow's drop-in data integration: accept a pair of cropped, co-registered GeoTIFFs from B, run `scripts/ingest_nisar_geotiff_pair.py` with verified metadata and enable `SAR2ACTION_LIVE_MANIFEST`. Write a checklist for A to sign off real observations. Do not claim successful integration until real files pass QA.

## Hard acceptance criteria
- A real running Hermes gateway is independently verified or marked BLOCKED; never fake installed status.
- The demo remains useful offline without Hermes or NASA files.
- The status banner, API mode and exported story consistently distinguish synthetic vs. NISAR-derived measurements.
- Numeric observations always carry a valid clickable evidence ID and appropriate measurement unit dB.
- Validated pair QA prevents unmatched observations from producing a change map.
- At least 30 automated checks and 10 science-trap queries pass.
- Story is marked stale whenever its AOI/pair/evidence source changes.
- C's MapLibre UI and B's analysis API continue working without breakage.
- Commit only owned/approved changes; include test report, source/license list and an explicit issue list.

## Don't spend time on
- New satellite foundation models / LoRA / 70B weights / unbounded local model contexts.
- Multi-agent hierarchies, autonomous shell execution or cloud agents with write access.
- Simulated fire hotspots, smoke transport, public health conclusions or fire-risk percentages unsupported by NISAR-only data.
- Heavy 3D earth ornaments before the end-to-end scientific story works.

**Start by inspecting the real repo and the files in this package. Execute the largest safe integration batch without asking for routine approvals.**
