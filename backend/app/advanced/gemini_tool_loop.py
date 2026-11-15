"""Real Gemini Function Calling Execution Loop (P1).

Implements:
USER -> GEMINI -> FUNCTION CALL -> PYTHON TOOL EXECUTION -> VERIFIED TOOL RESULT -> GEMINI FINAL RESPONSE

Supports all 7 verified deterministic tools without allowing Gemini to fabricate numbers.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from backend.app.advanced.dual_mode.gis_workspace import AuthorityGISService
from backend.app.advanced.farmer_agent.announcements import OfficialReliefAnnouncementService
from backend.app.advanced.farmer_agent.field_area import FarmerFieldService
from backend.app.advanced.farmer_agent.relief_estimator import ReliefAmountEstimator
from backend.app.advanced.gemini_client import GeminiClient
from backend.app.advanced.indicator_explainer import explain_current_indicator
from backend.app.advanced.legal_rag import LegalRAGService


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "calculate_field_area",
        "description": "計算農田幾何面積（平方公尺、公頃、分地）。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "field_id": {"type": "STRING", "description": "農田代號，例如 YL-CAND-03"},
            },
            "required": ["field_id"],
        },
    },
    {
        "name": "get_field_vh_observation",
        "description": "查詢指定農田的真實 Sentinel-1 VH 雷達觀測變化（dB）、品質檢查與科學限制。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "field_id": {"type": "STRING", "description": "農田代號，例如 YL-CAND-03"},
            },
            "required": ["field_id"],
        },
    },
    {
        "name": "compare_yunlin_fields",
        "description": "比較雲林台西五塊候選農田（YL-CAND-01 至 YL-CAND-05）在颱風警報期間的 VH 變化與空間對照分析。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_field_id": {"type": "STRING", "description": "基準農田代號，預設 YL-CAND-01"},
            },
        },
    },
    {
        "name": "search_legal_articles",
        "description": "查詢《農業天然災害救助辦法》（2026-06-29 M0090019）條文與合法引用。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "法律問題或關鍵字"},
                "event_date": {"type": "STRING", "description": "災害日期 YYYY-MM-DD（選填）"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_official_relief_announcement",
        "description": "查詢官方天然災害救助公告（未查證時回傳 ANNOUNCEMENT_NOT_VERIFIED）。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "county": {"type": "STRING", "description": "縣市名稱，例如 雲林縣"},
                "township": {"type": "STRING", "description": "鄉鎮市區，例如 台西鄉"},
                "crop": {"type": "STRING", "description": "作物名稱，例如 水稻"},
            },
        },
    },
    {
        "name": "explain_indicator",
        "description": "解釋 SAR2Action 科學或法規指標（如 VH_CHANGE_DB、VALID_PIXELS、CROP_DAMAGE_CONFIRMED）。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "indicator_id": {"type": "STRING", "description": "指標代碼，例如 VH_CHANGE_DB"},
                "mode": {"type": "STRING", "description": "FARMER 或 AUTHORITY"},
                "actual_value": {"type": "STRING", "description": "實際數值（選填）"},
            },
            "required": ["indicator_id"],
        },
    },
    {
        "name": "estimate_farmer_relief",
        "description": "依已驗證官方附表額度、官方公告與面積條件試算農民潛在現金救助（缺少條件時安全拒答）。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "crop": {"type": "STRING", "description": "作物名稱，例如 水稻"},
                "county": {"type": "STRING", "description": "縣市，例如 雲林縣"},
                "township": {"type": "STRING", "description": "鄉鎮，例如 台西鄉"},
                "area_ha": {"type": "NUMBER", "description": "面積（公頃）"},
                "loss_rate_pct": {"type": "NUMBER", "description": "損失率百分比（0-100，選填）"},
            },
            "required": ["crop"],
        },
    },
]


class GeminiToolOrchestrator:
    """Executes real Gemini Function Calling turns backed by deterministic Python tools."""

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.client = gemini_client or GeminiClient()
        self.field_service = FarmerFieldService()
        self.gis_service = AuthorityGISService()
        self.legal_service = LegalRAGService()
        self.announcement_service = OfficialReliefAnnouncementService()
        self.relief_estimator = ReliefAmountEstimator()

        self.registry: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "calculate_field_area": self._tool_calculate_field_area,
            "get_field_vh_observation": self._tool_get_field_vh,
            "compare_yunlin_fields": self._tool_compare_yunlin_fields,
            "search_legal_articles": self._tool_search_legal,
            "search_official_relief_announcement": self._tool_search_announcement,
            "explain_indicator": self._tool_explain_indicator,
            "estimate_farmer_relief": self._tool_estimate_relief,
        }

    def _tool_calculate_field_area(self, args: dict[str, Any]) -> dict[str, Any]:
        field_id = str(args.get("field_id") or "YL-CAND-03")
        return self.field_service.calculate_field_area(field_id=field_id).to_dict()

    def _tool_get_field_vh(self, args: dict[str, Any]) -> dict[str, Any]:
        field_id = str(args.get("field_id") or "YL-CAND-03")
        return self.gis_service.compare_observations(field_id=field_id)

    def _tool_compare_yunlin_fields(self, args: dict[str, Any]) -> dict[str, Any]:
        target_id = str(args.get("target_field_id") or "YL-CAND-01")
        ordered = [target_id] + [f for f in ("YL-CAND-01", "YL-CAND-02", "YL-CAND-03", "YL-CAND-04", "YL-CAND-05") if f != target_id]
        raw = self.gis_service.analyze_gis(field_ids=ordered)
        summaries = []
        for fs in raw.get("field_statistics", []):
            qa = fs.get("sar_quality", {})
            vh = fs.get("vh_analysis", {})
            summaries.append({
                "field_id": fs.get("field_id"),
                "qa_passed": qa.get("qa_passed"),
                "valid_pixels": qa.get("valid_pixels"),
                "polygon_area_m2": qa.get("polygon_area_m2"),
                "median_change_db": vh.get("median_change_db"),
                "pre_median_db": vh.get("pre_median_db"),
                "warning_median_db": vh.get("warning_median_db"),
                "post_median_db": vh.get("post_median_db"),
                "evidence_ids": vh.get("evidence_ids", []),
            })
        cf = raw.get("cross_field_analysis", {})
        return {
            "status": raw.get("status"),
            "aoi_id": raw.get("aoi_id"),
            "field_summaries": summaries,
            "matched_fields": [m.get("field_id") for m in cf.get("matched_fields", [])],
            "excluded_fields": [{"field_id": e.get("field_id"), "reasons": e.get("exclusion_reasons")} for e in cf.get("excluded_fields", [])],
            "scientific_limitations": cf.get("scientific_limitations", [])[:4],
        }

    def _tool_search_legal(self, args: dict[str, Any]) -> dict[str, Any]:
        q = str(args.get("query") or "")
        event_date = args.get("event_date")
        res = self.legal_service.query(q, event_date=event_date)
        return {
            "status": res.status,
            "answer": res.answer,
            "citations": [{"article": c["article"], "source_id": c["source_id"], "text": c.get("exact_source_text", "")[:220]} for c in res.citations[:3]],
            "law_version": res.applicable_law_version,
        }

    def _tool_search_announcement(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.announcement_service.search_official_relief_announcement(
            county=args.get("county"),
            township=args.get("township"),
            crop=args.get("crop"),
        )

    def _tool_explain_indicator(self, args: dict[str, Any]) -> dict[str, Any]:
        ind_id = str(args.get("indicator_id") or "VH_CHANGE_DB")
        mode = str(args.get("mode") or "FARMER")
        val = args.get("actual_value")
        return explain_current_indicator(ind_id, value=val, mode=mode)

    def _tool_estimate_relief(self, args: dict[str, Any]) -> dict[str, Any]:
        crop = str(args.get("crop") or "")
        ann = self.announcement_service.search_official_relief_announcement(
            county=args.get("county"),
            township=args.get("township"),
            crop=crop or None,
        )
        rate_hit = self.relief_estimator.lookup_verified_appendix_rate(crop) if crop else {"verified": False}
        rec = rate_hit.get("record") or {}
        rate_val = float(rec["amount_ntd"]) if rate_hit.get("verified") and rec.get("amount_ntd") is not None else None
        unit = rec.get("unit") if rate_hit.get("verified") else None
        est = self.relief_estimator.calculate_potential_relief(
            crop=crop or None,
            verified_announcement=ann,
            verified_appendix_rate_ntd_per_unit=rate_val,
            statutory_unit=unit,
            eligible_area_ha=args.get("area_ha"),
            area_source_label="FARMER_REPORTED" if args.get("area_ha") else "UNVERIFIED",
            loss_rate_pct=args.get("loss_rate_pct"),
        )
        est["appendix_lookup_status"] = rate_hit.get("status")
        if rate_val is not None:
            est["verified_appendix_rate_ntd_per_unit"] = rate_val
            est["statutory_unit"] = unit
        return est

    def run_tool_loop(
        self,
        user_prompt: str,
        *,
        mode: str = "FARMER",
        max_steps: int = 3,
        history_contents: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run USER -> GEMINI -> FUNCTION CALL -> PYTHON TOOL -> VERIFIED RESULT -> GEMINI FINAL RESPONSE."""
        if not self.client.configured:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        if mode.upper() == "FARMER":
            system_instruction = (
                "你是親切、耐心的台灣農業災損助理。你必須優先呼叫工具取得真實數據、法條與公告，"
                "絕對不可編造數字、面積、補助金額或公告。回覆限制 1 至 3 個短句、口語台灣繁體中文，每輪最多問一個問題。"
            )
        else:
            system_instruction = (
                "你是 SAR2Action 農業遙測與法規決策支援專家（AUTHORITY 模式）。"
                "必須呼叫工具取得真實 GIS、VH 統計、Evidence IDs 與法規條文，不可編造數值或未核定結論，"
                "並保留科學限制與 DECISION_SUPPORT_ONLY 原則。"
            )

        contents: list[dict[str, Any]] = list(history_contents or [])
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        tool_trace: list[dict[str, Any]] = []
        final_text = ""

        for _ in range(max_steps):
            resp = self.client.generate_content(
                contents,
                system_instruction=system_instruction,
                tools=TOOL_DECLARATIONS,
                temperature=0.1,
                max_output_tokens=600,
            )
            candidates = resp.get("candidates") or []
            if not candidates:
                break
            model_content = candidates[0].get("content") or {}
            parts = model_content.get("parts") or []
            contents.append({"role": "model", "parts": parts})

            fn_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not fn_calls:
                texts = [p.get("text", "") for p in parts if "text" in p]
                final_text = "\n".join(t for t in texts if t).strip()
                break

            fn_response_parts: list[dict[str, Any]] = []
            for call in fn_calls:
                name = str(call.get("name", ""))
                args = call.get("args") or {}
                fn = self.registry.get(name)
                if fn is None:
                    result = {"error": f"Unknown or disallowed tool: {name}"}
                else:
                    result = fn(args)
                tool_trace.append({"tool_name": name, "args": args, "result": result})
                fn_response_parts.append({
                    "functionResponse": {
                        "name": name,
                        "response": {"result": result},
                    }
                })
            contents.append({"role": "user", "parts": fn_response_parts})

        if not final_text and tool_trace:
            # Force a grounded final synthesis turn without tools if max_steps ended on tool output
            resp = self.client.generate_content(
                contents,
                system_instruction=system_instruction,
                tools=None,
                temperature=0.1,
                max_output_tokens=600,
            )
            parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            final_text = "\n".join(p.get("text", "") for p in parts if "text" in p).strip()

        return {
            "model": self.client.model,
            "mode": mode.upper(),
            "final_response": final_text,
            "tool_calls_executed": len(tool_trace),
            "tool_trace": tool_trace,
        }
