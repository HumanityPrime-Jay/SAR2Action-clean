"""Context-Aware Smart Indicator Explainer (Sections 7, 9, 10)."""
from __future__ import annotations

from typing import Any

from backend.app.advanced.indicator_explainer.registry import (
    DATA_STATUS_EXPLANATIONS,
    INDICATOR_REGISTRY,
)


def list_all_indicators() -> list[dict[str, Any]]:
    return [INDICATOR_REGISTRY[k].to_dict() for k in sorted(INDICATOR_REGISTRY)]


def get_indicator(indicator_id: str) -> dict[str, Any] | None:
    item = INDICATOR_REGISTRY.get(indicator_id.upper())
    return item.to_dict() if item else None


def explain_current_indicator(
    indicator_id: str,
    *,
    mode: str = "FARMER",
    field_id: str | None = None,
    value: Any = None,
    acquisition_date: str | None = None,
    data_source: str | None = None,
    qa_status: str | None = None,
) -> dict[str, Any]:
    """Generate a deterministic, context-aware explanation without altering observed numbers."""
    key = indicator_id.upper()
    defn = INDICATOR_REGISTRY.get(key)
    if defn is None:
        return {
            "status": "UNKNOWN_INDICATOR",
            "indicator_id": indicator_id,
            "mode": mode.upper(),
            "explanation": f"系統尚未收錄指標 '{indicator_id}' 的定義，無法提供科學解釋。",
        }

    upper_mode = mode.upper()
    is_farmer = upper_mode == "FARMER"

    # Enforce NOT_ESTIMABLE rule for ESTIMATED_AFFECTED_AREA if value is missing/unverified
    effective_value = value
    if key == "ESTIMATED_AFFECTED_AREA" and (value is None or qa_status in ("NOT_ESTIMABLE", "NOT_COMPATIBLE")):
        effective_value = "NOT_ESTIMABLE"

    if effective_value is None:
        value_text = "目前尚無數值（MISSING_VALUE）" if is_farmer else "MISSING_VALUE (no verified measurement provided)"
    elif effective_value == "NOT_ESTIMABLE":
        value_text = "目前無法估算（NOT_ESTIMABLE）" if is_farmer else "NOT_ESTIMABLE (lacks validated pixel classification)"
    else:
        value_text = f"{effective_value} {defn.unit}".strip()

    field_label = field_id or "目前選取區域"
    if is_farmer:
        if key == "VH_CHANGE_DB" and isinstance(effective_value, (int, float)):
            sign = "+" if effective_value > 0 else ""
            ctx_sentence = (
                f"{field_label} 在兩次指定觀測之間，VH 雷達訊號中位數變化為 {sign}{effective_value:.3f} dB。"
                "這表示雷達後向散射出現變化，尚不能直接判定農作物損失。"
            )
        else:
            ctx_sentence = f"{field_label} 的「{defn.name_zh_tw}」目前為 {value_text}。{defn.plain_language_definition}"
    else:
        ctx_sentence = (
            f"[{field_label}] {defn.name_en} ({key}) = {value_text}"
            f"{f' | Date: {acquisition_date}' if acquisition_date else ''}"
            f"{f' | Source: {data_source}' if data_source else ''}"
            f"{f' | QA: {qa_status}' if qa_status else ''}. "
            f"{defn.technical_definition}"
        )

    return {
        "status": "EXPLAINED",
        "indicator_id": key,
        "name_zh_tw": defn.name_zh_tw,
        "name_en": defn.name_en,
        "mode": upper_mode,
        "value": effective_value,
        "unit": defn.unit,
        "explanation": ctx_sentence,
        "what_is_this": defn.plain_language_definition if is_farmer else defn.technical_definition,
        "how_calculated": defn.calculation_method,
        "how_to_read": defn.interpretation,
        "source": data_source or defn.source,
        "limitations": defn.limitations,
        "data_status_detail": DATA_STATUS_EXPLANATIONS.get(str(qa_status).upper()) if qa_status else None,
        "aria_label": f"{defn.name_zh_tw}：{ctx_sentence}",
    }


def explain_current_layer(layer_id: str, *, mode: str = "FARMER", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = metadata or {}
    is_farmer = mode.upper() == "FARMER"
    return {
        "layer_id": layer_id,
        "mode": mode.upper(),
        "explanation": (
            f"圖層 {layer_id} 顯示衛星雷達觀測到的地表訊號分布，僅供觀察變化位置，不能直接代表農作物受災。"
            if is_farmer
            else f"Layer {layer_id} ({meta.get('sensor', 'SAR')} / {meta.get('processing_version', 'verified')}) displays calibrated radar backscatter or masks; verify CRID compatibility before differencing."
        ),
        "metadata": meta,
    }


def explain_scientific_result(result_summary: dict[str, Any], *, mode: str = "FARMER") -> dict[str, Any]:
    is_farmer = mode.upper() == "FARMER"
    field_id = result_summary.get("field_id", "目標農田")
    delta = result_summary.get("median_change_db")
    delta_str = f"{delta:+.3f} dB" if isinstance(delta, (int, float)) else "未計算"
    return {
        "mode": mode.upper(),
        "explanation": (
            f"衛星發現 {field_id} 的訊號有變化（{delta_str}），不過還不能確定是不是颱風造成的損失。我可以幫你看看接下來需要確認什麼。"
            if is_farmer
            else f"{field_id} 於警報前至警報期間的 VH 中位數差異為 {delta_str}；地塊級農損歸因未經驗證（UNRESOLVED / DECISION_SUPPORT_ONLY）。"
        ),
    }


def explain_data_limitation(status_code: str, *, mode: str = "FARMER") -> dict[str, Any]:
    info = DATA_STATUS_EXPLANATIONS.get(status_code.upper())
    if not info:
        return {"status_code": status_code, "mode": mode.upper(), "explanation": f"資料狀態：{status_code}。"}
    return {
        "status_code": status_code.upper(),
        "mode": mode.upper(),
        **info,
    }
