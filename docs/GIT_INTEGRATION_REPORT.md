# Git Integration Report

Status: isolated integration tested; private draft pull request opened. The pull request is not merged.

## Git sources and strategy

- Original local `main`: `7f6b677a154f886a663711795a7afab79bd10b9b` (V0.3), clean at inspection. Backup `backup/local-main-v03` and private `origin/upload/local-v03` retain it.
- Private `origin/main`: `5c64d771b5b02fd88c2e1521e24f663156718354`, with previous `568465d`. Backup `backup/remote-main` retains it.
- Product `feat/final-science-studio`: `75b97f0eebe44ff24612ed5baef72e60402913b3`.
- `main` and `origin/main` have no merge base. `origin/main...main` has two remote and three local commits.
- Integration branch: `integration/sar2action-v03` in a dedicated local worktree, created from `origin/main`.
- Strategy B, selective file integration. Strategy A, `merge --allow-unrelated-histories`, would publish local historical Hermes state, a tracked virtual environment, ZIP files, and machine paths. It was not attempted. Neither source branch was reset or rewritten.
- Remote competition README, publication/security reports, and safe history remain the base. No direct update to remote `main`.

## Imported file groups

| Source commit | Imported files |
| --- | --- |
| Local V0.3 `7f6b677` | Agent V2/V3 and agriculture VH backend schemas/services/endpoints, bounded science scripts, focused tests, TW-03 catalog, selected CHAMPI and five-field derived evidence/QA JSON, GeoJSON, and PNG, plus V0.3 demo runbook/checklist. |
| Product `75b97f0` | Investigation Studio components, MapLibre camera and separate NISAR observation layers, five-field views, Evidence Challenge/Graph, dossier export, six-step Story Mode, static reviewed studio snapshots, asset sync/validation, frontend package and browser test. |
| Remote `5c64d77` | Existing README, original app, existing backend, publication docs, safe Git history, and base project metadata. |

The product branch's code and static map previews are present. This does not merge its unrelated Git history. Local V0.3's read-only Evidence Challenge is present in the product Studio. No visual redesign was made. The map uses NASA GIBS Blue Marble/Landsat WELD, attribution in the Studio, and a MapLibre fly-to path; it does **not** use a true globe projection.

## Reconciliation and science safeguards

- Updated MapLibre, Vite, Vitest and React plugin from the product branch's vulnerable versions to the already-used remote-main versions. Adapted two MapLibre imports to the current module API and configured the Vite-bundled worker URL before map creation, per https://maplibre.org/maplibre-gl-js/docs/ . No UI design or scientific numeric values changed.
- Replaced one machine-specific `download_manifest` path in the exported VH source manifest with a repository-relative path. Evidence IDs, source hashes, and VH statistics were not changed.
- Five field candidates remain unverified crop types. VH changes are observations, not confirmed parcel damage. Official county losses are not parcel losses.
- NISAR 2026-10-16 P05023 provisional and 2026-10-28 P05036 validated are shown separately. Cross-CRID radiometric change remains blocked. No Sentinel-1/NISAR cross-sensor subtraction is shown.
- The recorded Gemini trace is labeled recorded; live API actions issue fresh V3 requests. Evidence Challenge is read-only.

## Tests (isolated worktree)

- Frontend build: PASS on Vite 8.3.8 / MapLibre 6.18.0.
- Frontend unit: 20 passed.
- Studio Chrome E2E: 5 passed with an explicit MapLibre load-event assertion, including field selection, NISAR HH/HV/opacity, MapLibre, six story steps, recorded modes, live deterministic API, Evidence ID resolution, and one live Gemini V3 run. Live run did not promote parcel damage.
- Agent V3/five-field backend focused tests: 12 passed after ten SHA-256-matched, Git-ignored NISAR GeoTIFF inputs and the Git-ignored OPERA download manifest were copied into this worktree for testing. The original D: checkout was read only.
- Additional V2/legacy backend batch: not passing in a clean release checkout. TW-03 catalog declares observed pixels while the private `data/processed/tw03` QA artifacts are absent. The batch had 2 failed, 13 setup errors, other tests passing/skipped. These are data-dependent failures, not a pass. V2 must retain its evidence gate; cloning this branch cannot reproduce its real-pixel investigation without those assets.
- Full backend suite: not run for this integration. No claim of full-suite pass.
- npm audit on updated lockfile: 0 known vulnerabilities.

## Publication and security review

- Staging was restricted to explicit code, derived evidence, preview, and test paths. Original `.phase4_hermes`, `venv_hermes`, `node_modules`, ZIP, HDF5, raw GeoTIFF/COG, model weights, credentials, and private source caches are excluded. Git history stays based on safe `origin/main`.
- Every staged blob was scanned for common Google/GitHub/Earthdata token signatures, private keys, credential assignments, and private Windows paths. No credential signature was detected. One machine-path pattern match is the literal defensive rejection string inside `frontend/scripts/sync_studio_assets.py`, not an actual path.
- Old npm lockfile had 1 high and 3 critical advisories; updated lockfile audit is 0. The scanner does not prove absence of all malware. Prior Microsoft Safety Scanner said no infection, but folder coverage could not be independently confirmed; malware scan gate remains **unverified**, not PASS.
- NISAR/OPERA derived images are attributed to NASA/ASF; original raw scenes are excluded. Field geometry is attributed to Taiwan Ministry of Agriculture and township boundary to NLSC in the UI. Source license references: https://nisar-docs.asf.alaska.edu/ , https://data.gov.tw/en/datasets/166618 , https://maps.nlsc.gov.tw/pro/download.jsp , https://data.gov.tw/license . NASA GIBS tiles are requested at runtime, not redistributed in Git: https://nasa-gibs.github.io/gibs-api-docs/access-basics/ .
- Repository is PRIVATE. No software open-source license was added; do not make the repo public without a separate license and redistribution review. The existing `upload/local-v03` remote branch contains historical assets and was not treated as safe to merge or publish further.

## Outstanding items

1. Clean-clone live V3 investigation requires the excluded, hash-verified raw NISAR/OPERA inputs; static Studio snapshots and frontend build work without them. Provide an authorized asset provisioning path before claiming turnkey live science from a clone.
2. Legacy V2/TW-03 real-pixel tests require excluded private QA artifacts; no result was fabricated or weakened.
3. Prior malware scan folder coverage remains unverified.
4. True globe projection is not implemented; current MapLibre camera uses a flat map.
5. Draft pull request: https://github.com/HumanityPrime-Jay/SAR2Action/pull/1 . Do not merge until review limits are resolved.
