# Earth Change Intelligence Platform — World-Class Visual & Interaction Acceptance Test Report

## 1. Backend Regression & Earth Intelligence API Tests (`pytest`)
Command:
```powershell
$env:SAR2ACTION_DATA_ROOT='D:\NASA\data'
D:\SAR2Action-clean\.venv\Scripts\python.exe -m pytest -ra --tb=short
```
Result:
- **216 passed, 17 skipped, 18 warnings in 49.46s** (0 failures)
- Includes `tests/earth_intelligence/test_earth_intelligence.py` (**8 passed**) and `tests/advanced/legal_rag/test_legal_rag_benchmark.py`.
- Verified `EvidenceGapNavigator.search_catalog()` returns `FOUND` / `NO_RESULT` / `CMR_UNAVAILABLE` cleanly against live NASA CMR scenes (`download_permitted=false`).
- Skips are strictly conditional environment skips when private B-team evidence caches, private scene manifests, or local Gate A.2 HDF5 scene pairs are absent.

## 2. Frontend TypeScript Build & Unit Tests (`tsc -b && vite build` + `vitest run`)
Commands:
```powershell
npm.cmd run build
npm.cmd test
```
Result:
- **Build**: `tsc -b && vite build` passed (`58 modules transformed`, built in `548ms`).
- **Vitest**: **6 test files passed (6), 35 tests passed (35)** in `3.13s`:
  - `src/data/champi.test.ts` (2 tests)
  - `src/studio/adapter.test.ts` (11 tests)
  - `src/__tests__/AgentPanel.test.tsx` (2 tests)
  - `src/__tests__/AssistScreen.test.tsx` (3 tests)
  - `src/__tests__/EarthIntelligence.test.tsx` (1 test covering all 8 modules & navigation)
  - `src/__tests__/App.test.tsx` (16 tests)

## 3. End-to-End Browser Verification (`Playwright` — Journeys 1–8 + Multi-Viewport)
Command:
```powershell
$env:SAR2ACTION_PYTHON='D:\SAR2Action-clean\.venv\Scripts\python.exe'
$env:SAR2ACTION_GIS_E2E='1'
$env:SAR2ACTION_DATA_ROOT='D:\NASA\data'
$env:SAR2ACTION_E2E_REAL_API='1'
npx.cmd playwright test e2e/earth-intelligence.spec.ts e2e/gis-b2.spec.ts e2e/investigation-studio.spec.ts e2e/final-rc-integration.spec.ts --reporter=list
```
Result:
- **8 passed, 1 skipped** in `29.1s` (0 failures):
  - `e2e/earth-intelligence.spec.ts` (Journeys 1–8 + Responsive Viewports `1920×1080`, `1440×900`, `1366×768`, `768×1024`, `390×844`, `375×812` against live FastAPI backend): **PASSED** (`22.2s`)
  - `e2e/gis-b2.spec.ts` (2 tests): **PASSED** (`10.0s`, `5.9s`)
  - `e2e/final-rc-integration.spec.ts` (1 test): **PASSED** (`15.1s`)
  - `e2e/investigation-studio.spec.ts` (4 passed, 1 skipped optional live Gemini studio test): **PASSED** (`10.5s`, `4.2s`, `2.0s`, `2.1s`)

## 4. Observed Browser Performance Metrics (`PERF_METRICS_JSON`)
Measured in live Chromium during `e2e/earth-intelligence.spec.ts`:
- `domContentLoadedMs`: **228 ms**
- `loadEventMs`: **228 ms**
- `fcpMs` (First Contentful Paint): **816 ms**
- `usedJSHeapMB` (after completing all 8 journeys + 6 viewport resizes): **49.1 MB**

## 5. Captured Final Acceptance Screenshots (`docs/earth-intelligence-screenshots/final/`)
1. `01-global-earth-desktop.png` (`1920×1080` Mission Control — Full-Bleed MapLibre Canvas + Left/Right/Bottom Docks)
2. `02-earth-memory-animation.png` (Video-Editor Time Dock with Pre/Event/Post Keyframe & `NO_OBSERVATION` Gap Track)
3. `03-reality-lens.png` (4-Mode Epistemic Switcher: `OBSERVED` / `HYPOTHESES` / `UNKNOWN` / `NEXT_EVIDENCE`)
4. `04-hypothesis-arena.png` (Competing Hypotheses + Experiment Execution Stepper + Evidence Balance Bar)
5. `05-fingerprint-comparison.png` (SVG Temporal Signature + 8-Metric Feature Matrix + Role-Aware `ⓘ` Tooltips + Field Comparison)
6. `06-evidence-gap.png` (4-Quadrant Epistemic Matrix + Live NASA CMR Catalog Search with `APPROVAL REQUIRED` Gate)
7. `07-guided-discovery.png` (Validated AI Map Actions + Bilingual Explanation + Follow-Up Prompts)
8. `08-planetary-story.png` (7-Chapter Documentary Player with `Play / Pause / Restart / Exit Story` + Visual Evidence Artifact)
9. `09-mobile-view.png` (`390×844` Map-First Responsive Layout + 3-Drawer Bottom Sheet Switcher)
10. `10-full-product-overview.png` (`1920×1080` Full Product Overview)
