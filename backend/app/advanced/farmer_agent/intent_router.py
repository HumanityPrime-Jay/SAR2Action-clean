"""Farmer Intent Router supporting colloquial & incomplete Traditional Chinese."""
from __future__ import annotations

from backend.app.advanced.farmer_agent.models import FarmerIntent


def classify_farmer_intent(message: str, *, has_selected_field: bool = False) -> FarmerIntent:
    m = message.strip().lower()

    if any(k in m for k in ("多少錢", "領多少", "補助多少", "多少補助", "試算", "補貼多少", "能領", "金額")):
        return FarmerIntent.ESTIMATE_RELIEF_AMOUNT
    if any(k in m for k in ("截止", "期限", "什麼時候前", "來得及", "幾天內")):
        return FarmerIntent.CHECK_APPLICATION_DEADLINE
    if any(k in m for k in ("帶什麼", "文件", "證件", "準備什麼", "資料")):
        return FarmerIntent.REQUIRED_DOCUMENTS
    if any(k in m for k in ("去哪", "哪裡辦", "怎麼申請", "如何申請", "公所", "流程")):
        return FarmerIntent.HOW_TO_APPLY
    if any(k in m for k in ("有沒有補助", "救助方案", "公告", "符合補助", "申請資格", "核准")):
        return FarmerIntent.CHECK_RELIEF_PROGRAMS
    if any(k in m for k in ("賠多少", "虧多少", "損失金額", "收入損失", "成本")):
        return FarmerIntent.ESTIMATE_FINANCIAL_LOSS
    if any(k in m for k in ("產量", "收成", "公斤", "少收")):
        return FarmerIntent.ESTIMATE_CROP_LOSS
    if any(k in m for k in ("倒了一半", "淹了", "幾分", "受災面積", "壞了多少", "圈選")):
        return FarmerIntent.ESTIMATE_DAMAGED_AREA
    if any(k in m for k in ("面積", "多大", "幾公頃", "幾分地")):
        return FarmerIntent.CHECK_FIELD_AREA
    if any(k in m for k in ("vh", "db", "衛星", "雷達", "這張圖", "7.553", "為什麼顯示")):
        return FarmerIntent.EXPLAIN_SATELLITE_RESULT
    if any(k in m for k in ("找不到田", "我的田在哪", "地號", "附近", "台西", "雲林")):
        if not has_selected_field and any(k in m for k in ("找不到", "在哪", "地號", "附近")):
            return FarmerIntent.FIND_MY_FIELD
    if any(k in m for k in ("被颱風", "吹壞", "受災", "災損", "泡水", "倒伏", "影響")):
        return FarmerIntent.CHECK_POSSIBLE_DAMAGE
    if any(k in m for k in ("詳細", "為什麼", "怎麼算", "再說明", "解釋")):
        return FarmerIntent.FOLLOW_UP_QUESTION
    return FarmerIntent.GENERAL_CONVERSATION
