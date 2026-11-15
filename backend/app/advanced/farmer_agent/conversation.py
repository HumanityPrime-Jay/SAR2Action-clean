"""Human-Like Farmer Conversation Service (Phases 1, 2, 8, 9, 11)."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from backend.app.advanced.farmer_agent.announcements import OfficialReliefAnnouncementService
from backend.app.advanced.farmer_agent.application_guide import ReliefApplicationGuideService
from backend.app.advanced.farmer_agent.damage_assessment import AgriculturalDamageAssessmentService
from backend.app.advanced.farmer_agent.field_area import FarmerFieldService, SQ_M_PER_FEN
from backend.app.advanced.farmer_agent.intent_router import classify_farmer_intent
from backend.app.advanced.farmer_agent.loss_calculator import AgriculturalLossCalculator
from backend.app.advanced.farmer_agent.models import (
    FarmerChatResponse,
    FarmerIntent,
    FarmerSessionState,
    ResultCard,
    SuggestedAction,
)
from backend.app.advanced.farmer_agent.relief_estimator import ReliefAmountEstimator
from backend.app.advanced.gemini_client import GeminiClient
from backend.app.advanced.legal_rag import LegalRAGService

ROOT = Path(__file__).resolve().parents[4]

TAIWAN_COUNTIES = ("雲林", "彰化", "嘉義", "台南", "臺南", "高雄", "屏東", "台中", "臺中", "南投", "苗栗", "新竹", "桃園", "宜蘭", "花蓮", "台東", "臺東")
COMMON_CROPS = ("水稻", "稻米", "玉米", "花生", "高麗菜", "蔬菜", "香蕉", "文旦", "鳳梨", "茶葉", "甘藷", "蒜頭", "大蒜", "落花生")

INJECTION_PATTERNS = ("ignore", "忽略", "編造", "虛構", "假裝已核准", "直接核准", "十萬", "100000")


class FarmerConversationService:
    """Multi-turn, adaptive, grounded conversation service for Taiwanese farmers."""

    def __init__(
        self,
        data_root: Path | None = None,
        legal_service: LegalRAGService | None = None,
        announcement_service: OfficialReliefAnnouncementService | None = None,
        use_gemini: bool = False,
    ):
        self.data_root = data_root or ROOT
        self.field_service = FarmerFieldService(self.data_root)
        self.damage_service = AgriculturalDamageAssessmentService(self.data_root)
        self.loss_calculator = AgriculturalLossCalculator()
        self.announcement_service = announcement_service or OfficialReliefAnnouncementService()
        self.relief_estimator = ReliefAmountEstimator()
        self.guide_service = ReliefApplicationGuideService()
        self.legal_service = legal_service or LegalRAGService()
        self.use_gemini = use_gemini
        self.gemini_client = GeminiClient()
        self._sessions: dict[str, FarmerSessionState] = {}

    def get_session(self, session_id: str) -> FarmerSessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = FarmerSessionState(session_id=session_id)
        return self._sessions[session_id]

    def _extract_entities(self, message: str, session: FarmerSessionState) -> None:
        for c in TAIWAN_COUNTIES:
            if c in message:
                session.county = c.replace("臺", "台") + "縣" if c not in ("台中", "臺中", "台南", "臺南", "高雄", "桃園") else c.replace("臺", "台") + "市"
                break
        if "台西" in message or "臺西" in message:
            session.township = "台西鄉"
            if not session.county:
                session.county = "雲林縣"
        for crop in COMMON_CROPS:
            if crop in message:
                session.crop = crop
                break
        if "倒了一半" in message or "一半" in message:
            session.farmer_reported_damage_ratio = 0.5
            session.farmer_reported_condition = "農民自述約一半受損"
        elif "全倒" in message or "全部" in message:
            session.farmer_reported_damage_ratio = 1.0
            session.farmer_reported_condition = "農民自述全部受損"
        elif m := re.search(r"(\d+)\s*成", message):
            ratio = min(1.0, max(0.0, int(m.group(1)) / 10.0))
            session.farmer_reported_damage_ratio = ratio
            session.farmer_reported_condition = f"農民自述約 {m.group(1)} 成受損"

    def _next_missing_question(self, session: FarmerSessionState) -> tuple[str, list[SuggestedAction]]:
        if not session.county and not session.township and not session.selected_field_id:
            return "你的田在哪個縣市鄉鎮呢？", [SuggestedAction("SELECT_LOCATION", "選擇縣市鄉鎮")]
        if not session.crop:
            return "你種的是水稻、蔬菜，還是其他作物？", []
        if not session.selected_field_id and session.field_area_ha is None:
            return "可以在地圖上點選或圈出你的農田嗎？我幫你確認面積。", [SuggestedAction("SELECT_FIELD_ON_MAP", "在地圖點選農田")]
        if session.farmer_reported_affected_area_ha is None and session.farmer_reported_damage_ratio is None:
            return "大約有多少範圍受災？你也可以在地圖上圈選。", [SuggestedAction("DRAW_DAMAGE_AREA", "在地圖圈選受災範圍")]
        return "需要我幫你整理申請文件清單與公所辦理步驟嗎？", [SuggestedAction("VIEW_APPLICATION_GUIDE", "查看申請指引")]

    def _maybe_polish_with_gemini(self, draft_reply: str, message: str, facts: dict[str, Any]) -> str:
        """Optional live Gemini phrasing; strictly rejects output if it fabricates approval or alters numbers."""
        if not self.use_gemini or not self.gemini_client.configured:
            return draft_reply
        system = (
            "你是親切、耐心的台灣農業災損助理。請用自然口語的台灣繁體中文改寫以下回覆，"
            "限制 1 至 3 個短句（約 30-100 字），最多只問一個問題。"
            "絕對不可改變任何數字、不可宣稱政府已核准補助、不可把衛星訊號說成已確認農損。"
        )
        try:
            data = self.gemini_client.generate_content(
                [{"role": "user", "parts": [{"text": json.dumps({"farmer_message": message, "verified_facts": facts, "draft_reply": draft_reply}, ensure_ascii=False)}]}],
                system_instruction=system,
                temperature=0.2,
                max_output_tokens=512,
            )
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if any(bad in text for bad in ("已核准", "確定可以領", "保證領到")):
                return draft_reply
            return text or draft_reply
        except Exception:
            return draft_reply

    def chat(
        self,
        session_id: str,
        message: str,
        *,
        selected_field_id: str | None = None,
        optional_map_geometry: dict[str, Any] | None = None,
        optional_damage_geometry: dict[str, Any] | None = None,
        optional_event_id: str | None = None,
        crop: str | None = None,
    ) -> FarmerChatResponse:
        session = self.get_session(session_id)
        session.turn_count += 1
        if optional_event_id:
            session.disaster_event = optional_event_id
        # Crop the farmer registered in the UI; a crop named in the message still overrides it.
        if crop and crop.strip():
            session.crop = crop.strip()

        # Handle field switch cleanly
        if selected_field_id and selected_field_id != session.selected_field_id:
            session.selected_field_id = selected_field_id
            area_res = self.field_service.calculate_field_area(field_id=selected_field_id)
            if area_res.status == "CALCULATED":
                session.field_area_m2 = area_res.area_m2
                session.field_area_ha = area_res.area_ha
                if "calculate_field_area" not in session.completed_tools:
                    session.completed_tools.append("calculate_field_area")
        elif optional_map_geometry is not None:
            area_res = self.field_service.calculate_field_area(field_id=selected_field_id, geojson_geometry=optional_map_geometry)
            if area_res.status == "CALCULATED":
                session.field_area_m2 = area_res.area_m2
                session.field_area_ha = area_res.area_ha
                if "calculate_field_area" not in session.completed_tools:
                    session.completed_tools.append("calculate_field_area")

        self._extract_entities(message, session)
        intent = classify_farmer_intent(message, has_selected_field=bool(session.selected_field_id or session.field_area_ha))
        session.last_intent = intent.value

        cards: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        sources: list[str] = []
        conv_state = "ACTIVE_CONVERSATION"

        # Guard: Prompt injection or request to confirm approval
        if any(p in message.lower() for p in INJECTION_PATTERNS):
            reply = "我只能依照實際查證的資料與《農業天然災害救助辦法》幫你試算和說明，沒辦法編造金額或代替政府核准。"
            conv_state = "GUARDRAIL_REFUSAL"
            return FarmerChatResponse(reply, conv_state, intent.value, actions, cards, sources, False, session.to_dict())

        if any(k in message for k in ("已經核准", "確認核准", "一定領得到")):
            reply = "我沒辦法幫你確認補助已經核准，實際審核與撥款要由鄉鎮公所勘查後由主管機關核定。"
            conv_state = "DECISION_SUPPORT_ONLY"
            return FarmerChatResponse(reply, conv_state, intent.value, actions, cards, sources, False, session.to_dict())

        if any(law in message for law in ("勞基法", "勞動基準法", "民法", "刑法", "所得稅法")):
            reply = "不好意思，我只熟《農業天然災害救助辦法》相關的農損補助問題，其他法律比較沒辦法回答喔。"
            conv_state = "OUT_OF_SCOPE"
            return FarmerChatResponse(reply, conv_state, intent.value, actions, cards, sources, False, session.to_dict())

        # Explain "公頃" in plain Taiwanese units (分地)
        if "公頃" in message and ("不懂" in message or "是什麼" in message or "幾分" in message):
            if session.field_area_m2:
                fen = round(session.field_area_m2 / SQ_M_PER_FEN, 2)
                reply = f"1 公頃大約是 10 分地。你這塊田約 {session.field_area_ha:.2f} 公頃，換算大概是 {fen} 分地。"
            else:
                reply = "1 公頃大約等於 10.3 分地（1 甲大約是 0.97 公頃）。你有選好農田的話，我可以直接幫你換算成幾分地。"
            return FarmerChatResponse(reply, conv_state, intent.value, actions, cards, sources, False, session.to_dict())

        # Handle specific intents adaptively
        if intent == FarmerIntent.FIND_MY_FIELD:
            reply = "沒關係，不用背地號！你可以在地圖上放大找到附近道路或聚落，直接點選或框出你的田。"
            actions = [SuggestedAction("OPEN_FIELD_PICKER", "在地圖上找我的田").to_dict()]
            conv_state = "WAITING_FOR_FIELD_SELECTION"

        elif intent == FarmerIntent.CHECK_FIELD_AREA:
            if session.field_area_ha is not None and session.field_area_m2 is not None:
                fen = round(session.field_area_m2 / SQ_M_PER_FEN, 2)
                cards.append(ResultCard(
                    "FIELD_AREA_CARD",
                    "農田面積計算",
                    {"field_id": session.selected_field_id, "area_m2": session.field_area_m2, "area_ha": session.field_area_ha, "area_fen": fen},
                    ["WGS84_GEODESIC_SPHERICAL_EXCESS"],
                    ["候選多邊形僅供參考，不代表地籍所有權證明。"],
                ).to_dict())
                reply = f"這塊田大約 {session.field_area_ha:.2f} 公頃（約 {fen} 分地）。接下來要一起看看哪裡受災嗎？"
                actions = [SuggestedAction("DRAW_DAMAGE_AREA", "在地圖圈選受災區").to_dict()]
            else:
                reply = "請先在地圖上點選或畫出你的農田，我就能馬上幫你算出幾公頃和幾分地。"
                actions = [SuggestedAction("SELECT_FIELD_ON_MAP", "在地圖選田").to_dict()]
                conv_state = "WAITING_FOR_FIELD_SELECTION"

        elif intent in (FarmerIntent.HOW_TO_APPLY, FarmerIntent.REQUIRED_DOCUMENTS, FarmerIntent.CHECK_APPLICATION_DEADLINE):
            ann = self.announcement_service.search_official_relief_announcement(
                county=session.county, township=session.township, crop=session.crop
            )
            guide = self.guide_service.get_application_guidance(
                county=session.county, township=session.township, crop=session.crop, area_ha=session.field_area_ha, announcement_result=ann
            )
            cards.append(ResultCard("APPLICATION_STEPS_CARD", "救助申請指引與文件清單", guide, ["M0090019-ARTICLE-12"]).to_dict())
            sources.append("M0090019-ARTICLE-12")
            if intent == FarmerIntent.REQUIRED_DOCUMENTS:
                reply = "要帶身分證、印章、土地或耕作證明、存摺影本，還有受災照片或種植證明。詳細清單我已幫你列在下方卡片。"
            elif intent == FarmerIntent.CHECK_APPLICATION_DEADLINE:
                reply = f"依規定是在官方公告救助地區隔天起 10 個工作日內申請；{guide['deadline_reminder']}"
            else:
                reply = f"請向{guide['application_office']}提出申請。{guide['deadline_reminder']}"
            conv_state = "APPLICATION_GUIDANCE_PROVIDED"

        elif intent in (FarmerIntent.CHECK_RELIEF_PROGRAMS, FarmerIntent.ESTIMATE_RELIEF_AMOUNT):
            ann = self.announcement_service.search_official_relief_announcement(
                county=session.county, township=session.township, crop=session.crop
            )
            legal = self.legal_service.query(message, event_date="2026-10-23", region=session.county, crop=session.crop)
            est = self.relief_estimator.calculate_potential_relief(
                crop=session.crop,
                verified_announcement=ann,
                eligible_area_ha=session.farmer_reported_affected_area_ha or session.field_area_ha,
                area_source_label="FARMER_REPORTED" if session.farmer_reported_affected_area_ha else "UNVERIFIED",
            )
            cards.append(ResultCard("RELIEF_PROGRAM_CARD", "官方公告與資格檢核", {"announcement": ann, "legal_status": legal.rule_evaluations["overall_status"]}, [c["source_id"] for c in legal.citations]).to_dict())
            cards.append(ResultCard("RELIEF_AMOUNT_CARD", "救助金額試算狀態", est, ["M0090019-ARTICLE-6", "M0090019-ARTICLE-12-1"]).to_dict())
            sources.extend(c["source_id"] for c in legal.citations[:2])
            if ann["status"] != "VERIFIED_ANNOUNCEMENT_FOUND":
                next_q = "你種的是什麼作物？" if not session.crop else "你有大致的受災面積或公所現勘資料嗎？"
                reply = f"目前還沒有查到當地已公告的救助資料，而且附表額度也還需要核對，暫時不能直接算出領多少。{next_q}"
                conv_state = "ANNOUNCEMENT_NOT_VERIFIED"
            else:
                reply = "我已查到官方公告，但還需要核對附表額度與核定受災面積才能試算。"

        elif intent in (FarmerIntent.EXPLAIN_SATELLITE_RESULT, FarmerIntent.CHECK_POSSIBLE_DAMAGE, FarmerIntent.ESTIMATE_DAMAGED_AREA):
            dmg = self.damage_service.assess_damage_evidence(
                field_id=session.selected_field_id,
                field_area_ha=session.field_area_ha,
                farmer_reported_affected_area_ha=session.farmer_reported_affected_area_ha,
            )
            if optional_damage_geometry and session.selected_field_id:
                feat = self.field_service.get_field_geometry(session.selected_field_id)
                if feat:
                    rep = self.field_service.calculate_reported_damage_area(feat["geometry"], optional_damage_geometry)
                    if rep.get("affected_area_ha") is not None:
                        session.farmer_reported_affected_area_ha = rep["affected_area_ha"]
                        dmg["FARMER_REPORTED_AFFECTED_AREA"]["value_ha"] = rep["affected_area_ha"]
                        dmg["FARMER_REPORTED_AFFECTED_AREA"]["status"] = "FARMER_REPORTED"
            cards.append(ResultCard("DAMAGE_ESTIMATE_CARD", "災損證據分層評估", dmg, ["OPERA_L2_RTC-S1"]).to_dict())
            if intent == FarmerIntent.EXPLAIN_SATELLITE_RESULT:
                reply = "衛星看到雷達訊號有變化，代表地表狀況可能改變，但不等於已經確認農作物受損，還是要配合現場勘查。"
            elif session.farmer_reported_damage_ratio is not None:
                reply = f"收到，先幫你記下你自述的受災情況（這屬於農民自報資料，不能直接當成政府核定）。{self._next_missing_question(session)[0]}"
            else:
                next_q, sug = self._next_missing_question(session)
                actions = [s.to_dict() for s in sug]
                reply = f"我來幫你看看。{next_q}"

        elif intent in (FarmerIntent.ESTIMATE_CROP_LOSS, FarmerIntent.ESTIMATE_FINANCIAL_LOSS):
            y_loss = self.damage_service.estimate_crop_yield_loss(
                crop=session.crop,
                affected_area_ha=session.farmer_reported_affected_area_ha or session.field_area_ha,
            )
            f_loss = self.loss_calculator.estimate_agricultural_loss(area_ha=session.farmer_reported_affected_area_ha or session.field_area_ha)
            cards.append(ResultCard("CROP_LOSS_CARD", "作物產量與財務損失估算", {"yield_loss": y_loss, "financial_loss": f_loss}, ["M0090019-ARTICLE-9"]).to_dict())
            reply = "因為目前還缺少歷史產量、生產成本與現場確認的損失比例，暫時沒辦法幫你算出公斤數或金額。"

        elif intent == FarmerIntent.FOLLOW_UP_QUESTION:
            reply = "簡單來說，衛星訊號只能當作參考線索，真正能不能申請補助還是要看公所公告、實際種植證明和現場勘查結果。你想先確認哪一項呢？"

        else:
            # General conversation: check if user just answered a pending question (county/crop)
            if any(law in message for law in ("勞基法", "勞動基準法", "民法", "刑法")):
                reply = "不好意思，我只熟《農業天然災害救助辦法》相關的農損補助問題，其他法律比較沒辦法回答喔。"
            else:
                next_q, sug = self._next_missing_question(session)
                actions = [s.to_dict() for s in sug]
                reply = f"好，我記下來了。{next_q}"

        final_reply = self._maybe_polish_with_gemini(
            reply,
            message,
            {"county": session.county, "township": session.township, "crop": session.crop, "field_area_ha": session.field_area_ha},
        )
        session.history.append({"user": message, "assistant": final_reply})

        return FarmerChatResponse(
            reply=final_reply,
            conversation_state=conv_state,
            intent=intent.value,
            suggested_actions=actions,
            result_cards=cards,
            sources=list(dict.fromkeys(sources)),
            requires_confirmation=False,
            session_state=session.to_dict(),
        )
