"""Phase 3C Item 8: Live Backend + Frontend End-to-End Browser QA & Screenshot Capture.

Launches:
- FastAPI Backend on http://127.0.0.1:8000
- Vite React Frontend on http://127.0.0.1:5173
- Headless Google Chrome via Playwright (`1680 x 1150`)

Verifies all 16 required UI QA items end-to-end, asserts zero page/console errors,
and saves representative screenshots to `docs/demo/screenshots/`.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = ROOT / "docs" / "demo" / "screenshots"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PYTHON_EXE = r"C:\Users\user\.venvs\sar2action\Scripts\python.exe"


def wait_for_http(url: str, timeout_s: float = 30.0) -> None:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}")


def main() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    backend_proc = subprocess.Popen(
        [
            PYTHON_EXE,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    frontend_proc = subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
        ],
        cwd=str(ROOT / "frontend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    qa_results: dict[str, Any] = {"items": {}, "console_errors": [], "page_errors": []}

    try:
        print("Waiting for FastAPI (127.0.0.1:8000) and Vite (127.0.0.1:5173)...")
        wait_for_http("http://127.0.0.1:8000/api/health", timeout_s=30.0)
        wait_for_http("http://127.0.0.1:5173", timeout_s=30.0)
        print("Both servers online. Launching Chrome via Playwright...")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
            )
            context = browser.new_context(viewport={"width": 1680, "height": 1180})
            page = context.new_page()

            page.on(
                "console",
                lambda msg: qa_results["console_errors"].append(msg.text)
                if msg.type == "error"
                else None,
            )
            page.on("pageerror", lambda exc: qa_results["page_errors"].append(str(exc)))
            qa_results["failed_responses"] = []
            page.on(
                "response",
                lambda resp: qa_results["failed_responses"].append(
                    {"status": resp.status, "url": resp.url}
                )
                if resp.status >= 400
                else None,
            )

            # 1. Flagship case load
            page.goto("http://127.0.0.1:5173", wait_until="networkidle")
            page.wait_for_selector('[data-testid="radar-fingerprint-panel"]', timeout=15000)
            page.wait_for_timeout(500)

            assert page.locator('[data-testid="badge-provisional"]').inner_text() == "PROVISIONAL"
            assert (
                page.locator('[data-testid="badge-cause-not-determined"]').inner_text()
                == "CAUSE NOT DETERMINED"
            )
            non_attr = page.locator('[data-testid="non-attribution-statement"]').inner_text()
            assert "NISAR observed radar backscatter change between 6 Sep and 18 Sep 2026." in non_attr
            assert "The radar observation alone does not prove that wildfire caused every observed change." in non_attr

            p1 = SCREENSHOTS_DIR / "01_flagship_case_default_load.png"
            page.screenshot(path=str(p1), full_page=True)
            qa_results["items"]["01_flagship_case_load"] = {"status": "PASS", "screenshot": p1.name}
            print("[PASS] 1. Flagship case load ->", p1.name)

            # 2. Engineering case switch (Riau T047_F087)
            page.select_option('[data-testid="case-select"]', "case-engineering-riau-t047")
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-PHASE2A-ENG-001')"
            )
            page.wait_for_timeout(500)
            p2 = SCREENSHOTS_DIR / "02_engineering_case_riau_switch.png"
            page.screenshot(path=str(p2), full_page=True)
            qa_results["items"]["02_engineering_case_switch"] = {"status": "PASS", "screenshot": p2.name}
            print("[PASS] 2. Engineering case switch ->", p2.name)

            # Switch back to Flagship case and select Predefined External-Context AOI (AOI-OKI-04)
            page.select_option('[data-testid="case-select"]', "case-flagship-oki-f2")
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-FLAGSHIP-OKI-001')"
            )
            page.click('[data-testid="preset-aoi-AOI-OKI-04"]')
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-FLAGSHIP-OKI-004')"
            )
            page.wait_for_timeout(500)
            assert (
                page.locator('[data-testid="fingerprint-selection-method"]').inner_text()
                == "PREDEFINED_EXTERNAL_CONTEXT"
            )
            p3 = SCREENSHOTS_DIR / "03_flagship_aoi_oki_04_predefined_external_context.png"
            page.screenshot(path=str(p3), full_page=True)
            qa_results["items"]["03_predefined_external_context_aoi_oki_04"] = {
                "status": "PASS",
                "screenshot": p3.name,
            }
            print("[PASS] 2b. Predefined external-context AOI-OKI-04 ->", p3.name)

            # 3. T0 layer
            page.click('[data-testid="layer-btn-t0_hh"]')
            page.wait_for_timeout(400)
            assert "T0 HH Backscatter" in page.locator('[data-testid="scientific-legend-card"]').inner_text()
            p4 = SCREENSHOTS_DIR / "04_layer_t0_hh.png"
            page.screenshot(path=str(p4), full_page=True)
            qa_results["items"]["03_t0_layer"] = {"status": "PASS", "screenshot": p4.name}
            print("[PASS] 3. T0 layer ->", p4.name)

            # 4. T1 layer
            page.click('[data-testid="layer-btn-t1_hh"]')
            page.wait_for_timeout(400)
            assert "T1 HH Backscatter" in page.locator('[data-testid="scientific-legend-card"]').inner_text()
            p5 = SCREENSHOTS_DIR / "05_layer_t1_hh.png"
            page.screenshot(path=str(p5), full_page=True)
            qa_results["items"]["04_t1_layer"] = {"status": "PASS", "screenshot": p5.name}
            print("[PASS] 4. T1 layer ->", p5.name)

            # 5. T0 / T1 swipe
            page.click('[data-testid="layer-btn-swipe_hv"]')
            page.wait_for_selector('[data-testid="swipe-stage"]')
            page.wait_for_timeout(400)
            p6 = SCREENSHOTS_DIR / "06_layer_swipe_t0_t1_hv.png"
            page.screenshot(path=str(p6), full_page=True)
            qa_results["items"]["05_t0_t1_swipe"] = {"status": "PASS", "screenshot": p6.name}
            print("[PASS] 5. T0 / T1 swipe ->", p6.name)

            # 6. Delta_HH
            page.click('[data-testid="layer-btn-delta_hh"]')
            page.wait_for_timeout(400)
            assert "Signed ΔHH" in page.locator('[data-testid="scientific-legend-card"]').inner_text()
            p7 = SCREENSHOTS_DIR / "07_layer_delta_hh.png"
            page.screenshot(path=str(p7), full_page=True)
            qa_results["items"]["06_delta_hh"] = {"status": "PASS", "screenshot": p7.name}
            print("[PASS] 6. Delta_HH ->", p7.name)

            # 7. Delta_HV
            page.click('[data-testid="layer-btn-delta_hv"]')
            page.wait_for_timeout(400)
            assert "Signed ΔHV" in page.locator('[data-testid="scientific-legend-card"]').inner_text()
            p8 = SCREENSHOTS_DIR / "08_layer_delta_hv.png"
            page.screenshot(path=str(p8), full_page=True)
            qa_results["items"]["07_delta_hv"] = {"status": "PASS", "screenshot": p8.name}
            print("[PASS] 7. Delta_HV ->", p8.name)

            # 8. Combined Radar Change (with dB composite unit and disclaimer)
            page.click('[data-testid="layer-btn-combined_change"]')
            page.wait_for_timeout(400)
            legend_text = page.locator('[data-testid="scientific-legend-card"]').inner_text()
            assert "dB composite" in legend_text
            disclaimer_text = page.locator('[data-testid="combined-metric-disclaimer"]').inner_text()
            assert "Custom visualization metric" in disclaimer_text
            p9 = SCREENSHOTS_DIR / "09_layer_combined_radar_change_db_composite.png"
            page.screenshot(path=str(p9), full_page=True)
            qa_results["items"]["08_combined_radar_change"] = {"status": "PASS", "screenshot": p9.name}
            print("[PASS] 8. Combined Radar Change (dB composite) ->", p9.name)

            # 9. Valid / Invalid Mask
            page.click('[data-testid="layer-btn-validity_mask"]')
            page.wait_for_timeout(400)
            assert "Validity Mask" in page.locator('[data-testid="scientific-legend-card"]').inner_text()
            p10 = SCREENSHOTS_DIR / "10_layer_validity_mask.png"
            page.screenshot(path=str(p10), full_page=True)
            qa_results["items"]["09_validity_mask"] = {"status": "PASS", "screenshot": p10.name}
            print("[PASS] 9. Valid / Invalid Mask ->", p10.name)

            # 10. Custom AOI drawing on map canvas (2-click corner selection)
            page.click('[data-testid="layer-btn-delta_hv"]')
            page.click('[data-testid="btn-draw-aoi"]')
            stage = page.locator('[data-testid="map-viewport"]')
            box = stage.bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + box["width"] * 0.42, box["y"] + box["height"] * 0.42)
            page.wait_for_timeout(200)
            page.mouse.click(box["x"] + box["width"] * 0.56, box["y"] + box["height"] * 0.56)
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-AOI-')",
                timeout=60000,
            )
            page.wait_for_timeout(500)
            assert (
                page.locator('[data-testid="fingerprint-selection-method"]').inner_text()
                == "EXPLORATORY_POST_HOC_RADAR_CHANGE"
            )
            p11 = SCREENSHOTS_DIR / "11_custom_aoi_drawn_live_analysis.png"
            page.screenshot(path=str(p11), full_page=True)
            qa_results["items"]["10_custom_aoi_drawing"] = {"status": "PASS", "screenshot": p11.name}
            print("[PASS] 10. Custom AOI drawing ->", p11.name)

            # Return to AOI-OKI-04 to verify 11, 12, 13 cleanly
            page.click('[data-testid="preset-aoi-AOI-OKI-04"]')
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-FLAGSHIP-OKI-004')"
            )
            page.wait_for_timeout(400)

            # 11. Radar Fingerprint panel
            fp_text = page.locator('[data-testid="radar-fingerprint-panel"]').inner_text()
            assert "E-FLAGSHIP-OKI-004" in fp_text
            assert "3,148,830" in fp_text
            assert "dB composite" in fp_text
            qa_results["items"]["11_radar_fingerprint_panel"] = {"status": "PASS"}
            print("[PASS] 11. Radar Fingerprint panel verified")

            # 12. What We Observed / What May Explain It / What We Do Not Know
            ep_text = page.locator('[data-testid="epistemic-summary-panel"]').inner_text()
            assert "WHAT WE OBSERVED" in ep_text
            assert "WHAT MAY EXPLAIN IT" in ep_text
            assert "WHAT WE DO NOT KNOW" in ep_text
            qa_results["items"]["12_epistemic_panel"] = {"status": "PASS"}
            print("[PASS] 12. What We Observed / What May Explain It / What We Do Not Know verified")

            # 13. Clicking a claim -> inspecting EvidenceRecord
            page.click('[data-testid="claim-btn-E-FLAGSHIP-OKI-004-CLAIM-COMBINED"]')
            page.wait_for_timeout(400)
            inspector_text = page.locator('[data-testid="evidence-inspector-drawer"]').inner_text()
            assert "E-FLAGSHIP-OKI-004" in inspector_text
            assert "PREDEFINED_EXTERNAL_CONTEXT" in inspector_text
            assert "cause_not_determined" in inspector_text
            p12 = SCREENSHOTS_DIR / "12_claim_to_evidence_inspector_aoi_oki_04.png"
            page.screenshot(path=str(p12), full_page=True)
            qa_results["items"]["13_claim_click_evidence_inspector"] = {
                "status": "PASS",
                "screenshot": p12.name,
            }
            print("[PASS] 13. Claim click -> EvidenceRecord inspector ->", p12.name)

            # 14. Outside-coverage AOI error state
            page.click('[data-testid="btn-test-outside-aoi"]')
            page.wait_for_selector('[data-testid="science-error-banner"]')
            page.wait_for_timeout(400)
            err_text = page.locator('[data-testid="science-error-banner"]').inner_text()
            assert "AOI_OUTSIDE_COVERAGE" in err_text
            assert "INSUFFICIENT_EVIDENCE" in err_text
            assert page.locator('[data-testid="radar-fingerprint-panel"]').count() == 0, (
                "Stale fingerprint from previous AOI still displayed after refusal"
            )
            p13 = SCREENSHOTS_DIR / "13_outside_coverage_gate_refusal.png"
            page.screenshot(path=str(p13), full_page=True)
            qa_results["items"]["14_outside_coverage_error_state"] = {
                "status": "PASS",
                "screenshot": p13.name,
            }
            print("[PASS] 14. Outside-coverage AOI error state ->", p13.name)

            # 15. Missing polarization state (HH Only -> HV Unavailable)
            page.click('[data-testid="preset-aoi-AOI-OKI-01"]')
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"fingerprint-evidence-id\"]')?.textContent?.includes('E-FLAGSHIP-OKI-001')"
            )
            page.click('[data-testid="pol-mode-hh-only"]')
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"pol-status-hv\"]')?.textContent === 'Unavailable'"
            )
            page.wait_for_timeout(400)
            assert page.locator('[data-testid="pol-status-hv"]').inner_text() == "Unavailable"
            p14 = SCREENSHOTS_DIR / "14_missing_hv_polarization_unavailable.png"
            page.screenshot(path=str(p14), full_page=True)
            qa_results["items"]["15_missing_polarization_state"] = {
                "status": "PASS",
                "screenshot": p14.name,
            }
            print("[PASS] 15. Missing polarization state ->", p14.name)

            # 16. Console errors check
            # Expected: exactly one HTTP 422 from the deliberate outside-coverage science-gate refusal.
            # Any other failed response or JS error is an unexpected defect.
            unexpected_failed = [
                r
                for r in qa_results["failed_responses"]
                if not (r["status"] == 422 and r["url"].endswith("/api/radar-fingerprint"))
            ]
            expected_422 = len(qa_results["failed_responses"]) - len(unexpected_failed)
            print("Failed responses:", qa_results["failed_responses"])
            unexpected_console = [
                e
                for e in qa_results["console_errors"]
                if "status of 422" not in e
            ]
            assert not unexpected_failed, f"Unexpected failed responses: {unexpected_failed}"
            assert not unexpected_console, f"Unexpected console errors: {unexpected_console}"
            assert len(qa_results["page_errors"]) == 0, f"Page errors: {qa_results['page_errors']}"
            qa_results["items"]["16_zero_console_errors"] = {
                "status": "PASS",
                "unexpected_console_error_count": 0,
                "expected_422_science_gate_refusals": expected_422,
                "page_error_count": 0,
            }
            print("[PASS] 16. No unexpected console/page errors (only expected 422 gate refusal).")

            browser.close()

        summary_file = SCREENSHOTS_DIR / "ui_qa_verification_summary.json"
        summary_file.write_text(json.dumps(qa_results, indent=2), encoding="utf-8")
        print(f"Saved UI QA summary to {summary_file}")

    finally:
        backend_proc.terminate()
        frontend_proc.terminate()


if __name__ == "__main__":
    main()
