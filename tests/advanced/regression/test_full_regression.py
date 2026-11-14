"""Phase L & Dual-Mode Full Regression Suite + Local HTTP Endpoint Verification."""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.advanced.api_router import (
    handle_agent_chat,
    handle_explain_indicator,
    handle_farmer_chat,
    handle_get_indicator,
    handle_gis_analyze,
    handle_gis_compare,
    handle_investigate_advanced,
    handle_legal_query,
    handle_legal_search,
    handle_legal_sources,
    handle_list_indicators,
    handle_map_action,
    handle_ui_capabilities,
    handle_ui_modes,
)
from backend.app.advanced.dual_mode import (
    AuthorityGISService,
    ModeCapabilityRegistry,
    ModeTransitionController,
    UserMode,
    UserModeContext,
)
from backend.app.advanced.evidence_acquisition import (
    AcquisitionController,
    CatalogSearchQuery,
    SatelliteCatalogSearcher,
    UnauthorizedAcquisitionError,
    detect_evidence_gaps,
)
from backend.app.advanced.experimentation import build_v3_context, run_bounded_investigation
from backend.app.advanced.indicator_explainer import (
    INDICATOR_REGISTRY,
    explain_current_indicator,
    explain_data_limitation,
)
from backend.app.advanced.orchestrator import AdvancedOrchestrator, ScientificLegalOrchestrator
from backend.app.advanced.reproducibility import InvestigationRecorder
from backend.app.advanced.spatial_controls import match_spatial_reference_fields
from backend.app.advanced.uncertainty import analyze_robust_vh_change, assess_sar_quality


class TestFullRegression(unittest.TestCase):
    def test_uncertainty_and_spatial_controls_real_yl03(self) -> None:
        qa = assess_sar_quality("YL-CAND-03", data_root=ROOT)
        self.assertTrue(qa.qa_passed)
        self.assertEqual(qa.valid_pixels, 48)
        self.assertEqual(assess_sar_quality("YL-CAND-999", data_root=ROOT).status, "NOT_EVALUATED")

        vh = analyze_robust_vh_change("YL-CAND-03", data_root=ROOT)
        self.assertEqual(vh.status, "OBSERVED")
        self.assertAlmostEqual(vh.median_change_db, 7.55336, places=3)
        self.assertFalse(vh.damage_rate_convertible)

        match = match_spatial_reference_fields("YL-CAND-03", data_root=ROOT)
        self.assertEqual(match.status, "MATCHED")
        self.assertFalse(match.causal_inference_completed)

    def test_active_evidence_acquisition_and_reproducibility(self) -> None:
        # Fake catalog transport (kept strictly separate from live network)
        def fake_http(url: str, timeout: float):
            return {
                "feed": {
                    "entry": [
                        {
                            "title": "OPERA_L2_RTC-S1_FAKE_01",
                            "time_start": "2026-10-05T21:51:56Z",
                            "orbit_direction": "DESCENDING",
                            "polarization": "VV+VH",
                            "version": "1.0",
                        }
                    ]
                }
            }

        searcher = SatelliteCatalogSearcher(http_get=fake_http)
        res = searcher.search(CatalogSearchQuery((120.15, 23.65, 120.25, 23.75), "2026-10-01T00:00:00Z", "2026-10-15T00:00:00Z"))
        self.assertEqual(res["status"], "OK")
        self.assertFalse(res["is_live_network"])

        ctrl = AcquisitionController()
        plan = ctrl.execute_action("REQUEST_APPROVAL", scenes=res["scenes"])
        self.assertFalse(plan.approved_for_download)
        with self.assertRaises(UnauthorizedAcquisitionError):
            ctrl.execute_action("DOWNLOAD", scenes=res["scenes"])

        # Reproducibility replay (never pretends to re-run Gemini)
        ctx = build_v3_context("YL-CAND-03", data_root=ROOT)
        inv = run_bounded_investigation(ctx)
        rec_eng = InvestigationRecorder()
        rec = rec_eng.record(ctx, inv)
        replay = rec_eng.replay(rec, ctx, data_root=ROOT)
        self.assertEqual(replay["replay_status"], "VERIFIED_DETERMINISTIC_MATCH")
        self.assertFalse(replay["llm_replay_executed"])

    def test_scientific_legal_orchestrator_real_yl03(self) -> None:
        orch = ScientificLegalOrchestrator(data_root=ROOT)
        resp = orch.analyze("雲林這塊農田 VH 增加 7.553 dB，符不符合天然災害救助？", field_id="YL-CAND-03")
        self.assertEqual(resp.decision_posture, "DECISION_SUPPORT_ONLY")
        self.assertEqual(resp.scientific_evidence["observation_status"], "OBSERVED")
        self.assertFalse(resp.scientific_evidence["crop_damage_confirmed"])
        self.assertEqual(resp.scientific_evidence["source_boundary"], "SCIENTIFIC_EVIDENCE_ONLY")
        self.assertEqual(resp.legal_authority["source_boundary"], "LEGAL_AUTHORITY_M0090019_ONLY")
        self.assertNotIn(resp.legal_authority["rule_evaluations"]["overall_status"], ("ELIGIBLE", "APPROVED"))

    def test_dual_mode_and_indicator_explainer(self) -> None:
        ctrl = ModeTransitionController()
        ctx = UserModeContext(
            mode=UserMode.FARMER,
            selected_aoi="10009160",
            loaded_layers=["Fields", "OPERA_VH"],
            shared_conversation_context=[{"user": "hello"}],
            allowed_analysis_results={"vh": 7.553, "private_applicant_id": "SECRET"},
        )
        auth_ctx = ctrl.switch_mode(ctx, "AUTHORITY")
        self.assertEqual(auth_ctx.mode, UserMode.AUTHORITY)
        self.assertFalse(auth_ctx.is_authenticated_authority)
        self.assertEqual(auth_ctx.selected_aoi, "10009160")
        self.assertEqual(auth_ctx.loaded_layers, ["Fields", "OPERA_VH"])
        self.assertNotIn("private_applicant_id", auth_ctx.allowed_analysis_results)

        cap = ModeCapabilityRegistry().get_capabilities("AUTHORITY", is_authenticated_authority=False)
        self.assertFalse(cap["private_records_accessible"])
        self.assertFalse(cap["official_approval_actions_enabled"])

        # All 22 required indicators must have definition, unit, limitations
        self.assertGreaterEqual(len(INDICATOR_REGISTRY), 22)
        for ind in INDICATOR_REGISTRY.values():
            self.assertTrue(ind.plain_language_definition)
            self.assertTrue(ind.unit)
            self.assertTrue(ind.limitations)

        exp_f = explain_current_indicator("VH_CHANGE_DB", mode="FARMER", field_id="YL-CAND-03", value=7.553)
        exp_a = explain_current_indicator("VH_CHANGE_DB", mode="AUTHORITY", field_id="YL-CAND-03", value=7.553)
        self.assertIn("7.553", exp_f["explanation"])
        self.assertIn("ΔVH", exp_a["explanation"])
        self.assertEqual(explain_current_indicator("ESTIMATED_AFFECTED_AREA", value=None)["value"], "NOT_ESTIMABLE")
        self.assertEqual(explain_current_indicator("NON_EXISTENT")["status"], "UNKNOWN_INDICATOR")
        self.assertIn("處理條件", explain_data_limitation("NOT_COMPATIBLE")["reason"])

    def test_authority_gis_cross_crid_guard_and_map_actions(self) -> None:
        gis = AuthorityGISService(ROOT)
        nisar_cmp = gis.compare_observations(sensor="NISAR", compute_difference=True)
        self.assertEqual(nisar_cmp["status"], "BLOCKED_CROSS_CRID_INCOMPATIBLE")
        self.assertFalse(nisar_cmp["difference_allowed"])

        act = gis.build_map_action("SELECT_FIELD", {"field_id": "YL-CAND-03"})
        self.assertEqual(act["action_type"], "SELECT_FIELD")
        with self.assertRaises(ValueError):
            gis.build_map_action("EXECUTE_RAW_JS", {})

    def test_http_endpoints_over_real_local_server(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                if self.path == "/api/ui/modes":
                    body = handle_ui_modes()
                elif self.path == "/api/indicators":
                    body = handle_list_indicators()
                elif self.path == "/api/agent/legal-sources":
                    body = handle_legal_sources()
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                routes = {
                    "/api/agent/investigate-advanced": handle_investigate_advanced,
                    "/api/agent/legal-query": handle_legal_query,
                    "/api/agent/legal-search": handle_legal_search,
                    "/api/farmer/chat": handle_farmer_chat,
                    "/api/indicators/explain": handle_explain_indicator,
                    "/api/gis/analyze": handle_gis_analyze,
                    "/api/gis/compare": handle_gis_compare,
                    "/api/agent/chat": handle_agent_chat,
                    "/api/agent/map-action": handle_map_action,
                }
                fn = routes.get(self.path)
                if fn is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                raw = json.dumps(fn(payload), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(raw)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for ep in ("/api/ui/modes", "/api/indicators", "/api/agent/legal-sources"):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{ep}", timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
            for ep, payload in (
                ("/api/agent/investigate-advanced", {"question": "Analyze YL-CAND-03 VH and relief", "field_id": "YL-CAND-03"}),
                ("/api/agent/legal-query", {"question": "第12-1條損失率未達20%的規定？", "event_date": "2026-10-23"}),
                ("/api/farmer/chat", {"session_id": "http-test", "message": "我的田被颱風吹壞了"}),
                ("/api/indicators/explain", {"indicator_id": "VH_CHANGE_DB", "mode": "FARMER", "field_id": "YL-CAND-03", "value": 7.553}),
                ("/api/gis/analyze", {"field_ids": ["YL-CAND-03"]}),
                ("/api/gis/compare", {"sensor": "NISAR", "compute_difference": True}),
            ):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}{ep}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self.assertEqual(resp.status, 200)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
