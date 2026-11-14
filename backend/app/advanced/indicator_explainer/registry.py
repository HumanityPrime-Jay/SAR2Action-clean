"""Smart Indicator Explanation Registry (Section 7, 8, 9).

Defines all 22 required scientific/agricultural indicators and 7 data status
explanations with both FARMER (plain) and AUTHORITY (technical) levels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IndicatorDefinition:
    indicator_id: str
    name_zh_tw: str
    name_en: str
    plain_language_definition: str
    technical_definition: str
    unit: str
    calculation_method: str
    interpretation: str
    limitations: list[str]
    data_requirements: list[str]
    source: str
    related_indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ind(
    indicator_id: str,
    name_zh: str,
    name_en: str,
    plain: str,
    tech: str,
    unit: str,
    calc: str,
    interp: str,
    limits: list[str],
    reqs: list[str],
    source: str,
    related: list[str],
) -> IndicatorDefinition:
    return IndicatorDefinition(
        indicator_id=indicator_id,
        name_zh_tw=name_zh,
        name_en=name_en,
        plain_language_definition=plain,
        technical_definition=tech,
        unit=unit,
        calculation_method=calc,
        interpretation=interp,
        limitations=limits,
        data_requirements=reqs,
        source=source,
        related_indicators=related,
    )


INDICATOR_REGISTRY: dict[str, IndicatorDefinition] = {
    "VH_BACKSCATTER_DB": _ind(
        "VH_BACKSCATTER_DB", "VH 極化後向散射", "VH Backscatter (dB)",
        "衛星雷達垂直發射、水平接收的地表訊號強度，用來觀察作物和地表結構變化。",
        "Sentinel-1 C-band cross-polarized (VH) gamma0 backscatter converted to decibels (10*log10).",
        "dB", "10 * log10(linear_gamma0_vh_median)", "較高數值通常反映體積散射或地表粗糙度/含水量增加。",
        ["受含水量、作物生長與雜訊底限 (NESZ) 影響，單一數值無法直接判別災損。"],
        ["OPERA L2 RTC-S1 VH 影像", "農田邊界多邊形"], "OPERA RTC-S1 / Sentinel-1", ["VH_CHANGE_DB", "VALID_PIXEL_COUNT"],
    ),
    "VH_CHANGE_DB": _ind(
        "VH_CHANGE_DB", "VH 訊號變化量", "VH Backscatter Change (dB)",
        "這個數字表示衛星看到的地表雷達訊號在兩次觀測之間有變化，但不代表農田一定受損。",
        "ΔVH 為兩期經相容性檢查之後向散射統計差異（post - pre），單位 dB。其變化受到地表散射機制、含水量、植被結構及觀測處理條件影響。",
        "dB", "median_vh_db(t2) - median_vh_db(t1)", "正值表示後向散射增強，負值表示減弱；須配合時序與地面調查解讀。",
        ["不可直接將 ΔVH 換算成農損率或減產百分比。", "單一 pre-warning 觀測點無法建立完整事前趨勢。"],
        ["同軌道、同極化、同產品版本兩期以上觀測"], "OPERA RTC-S1", ["VH_BACKSCATTER_DB", "TEMPORAL_BASELINE"],
    ),
    "HH_BACKSCATTER_DB": _ind(
        "HH_BACKSCATTER_DB", "HH 極化後向散射", "HH Backscatter (dB)",
        "NISAR L 波段水平發射與接收的雷達訊號強度，對地表與積水反射較敏感。",
        "NISAR L-band co-polarized (HH) gamma0 backscatter in dB.",
        "dB", "10 * log10(linear_gamma0_hh)", "可用於觀察地表粗糙度與淹水/雙次反彈變化。",
        ["不同 CRID 版本（P05023 與 P05036）尚未通過跨版本輻射一致性驗證，不得直接相減。"],
        ["NISAR L2 GCOV HH 子集"], "NASA NISAR L2 GCOV", ["HV_BACKSCATTER_DB", "CRID_COMPATIBILITY"],
    ),
    "HV_BACKSCATTER_DB": _ind(
        "HV_BACKSCATTER_DB", "HV 極化後向散射", "HV Backscatter (dB)",
        "NISAR L 波段對作物枝葉結構敏感的交叉極化雷達訊號。",
        "NISAR L-band cross-polarized (HV) gamma0 backscatter in dB.",
        "dB", "10 * log10(linear_gamma0_hv)", "主要反映植被體積散射變化。",
        ["受 NISAR CRID 版本差異限制，跨 CRID 差值目前被封鎖。"],
        ["NISAR L2 GCOV HV 子集"], "NASA NISAR L2 GCOV", ["HH_BACKSCATTER_DB", "CRID_COMPATIBILITY"],
    ),
    "VALID_PIXEL_COUNT": _ind(
        "VALID_PIXEL_COUNT", "有效像元數", "Valid Pixel Count",
        "這塊農田裡真正有拍到、而且沒有被遮罩或資料缺損扣掉的衛星格子數量。",
        "Count of unmasked, finite radar pixels intersecting the target polygon.",
        "pixels", "count(pixel in polygon where mask == valid and isfinite(val))", "像元數越多，區塊統計中位數越穩定；少於 8 個像元不可靠。",
        ["30 公尺解析度下，小面積農田易受邊界混合像元影響。"],
        ["有效像元遮罩 (validity mask)"], "OPERA RTC-S1 / NISAR", ["VALID_COVERAGE_RATIO", "SPATIAL_RESOLUTION"],
    ),
    "VALID_COVERAGE_RATIO": _ind(
        "VALID_COVERAGE_RATIO", "有效覆蓋率", "Valid Coverage Ratio",
        "這塊田裡面實際有可用衛星資料的比例，100% 代表整塊田都有有效資料。",
        "Ratio of valid unmasked pixels to total polygon pixels.",
        "ratio (0-1)", "valid_pixel_count / total_polygon_pixels", "需 >= 0.80 才符合最低空間品質要求。",
        ["高覆蓋率僅代表資料完整，不代表因果已確認。"],
        ["農田邊界", "像元遮罩"], "OPERA RTC-S1 QA", ["VALID_PIXEL_COUNT", "SCIENTIFIC_QA_STATUS"],
    ),
    "FIELD_AREA_HA": _ind(
        "FIELD_AREA_HA", "農田面積（公頃）", "Field Area (ha)",
        "這塊農田多邊形在地球表面上的實際面積，1 公頃大約等於 10.3 分地。",
        "Geodesic area of the field polygon computed on WGS84 authalic sphere, converted to hectares.",
        "ha", "geodesic_area_m2 / 10000", "用於農地空間尺度確認與分地換算。",
        ["官方候選農地邊界不代表申請人實際土地所有權或耕作面積。"],
        ["有效 WGS84 多邊形邊界"], "WGS84 Geodesic Engine", ["AOI_AREA_HA", "ESTIMATED_AFFECTED_AREA"],
    ),
    "AOI_AREA_HA": _ind(
        "AOI_AREA_HA", "研究區面積（公頃）", "AOI Area (ha)",
        "目前在地圖上選取的整個觀察範圍總面積。",
        "Geodesic area of the selected Area of Interest (AOI) polygon in hectares.",
        "ha", "geodesic_area_m2(aoi) / 10000", "用於定義空間分析與目錄搜尋範圍。",
        ["行政區界或 AOI 面積不等於實際受災農地面積。"],
        ["AOI GeoJSON"], "WGS84 Geodesic Engine", ["FIELD_AREA_HA"],
    ),
    "TEMPORAL_BASELINE": _ind(
        "TEMPORAL_BASELINE", "時間基線", "Temporal Baseline",
        "災害發生前後兩次或多次衛星拍照相隔的天數與時間關係。",
        "Elapsed days and event-window relation between pre-event, warning-window, and post-event acquisitions.",
        "days", "(t2 - t1) in days relative to warning window", "用來判斷變化是否落在災害警報期間。",
        ["若警報前只有 1 筆觀測，無法建立事前自然波動基線。"],
        ["具 UTC/本地時間戳之觀測序列"], "OPERA / NISAR Metadata", ["ACQUISITION_DATE", "OBSERVATION_COUNT"],
    ),
    "ACQUISITION_DATE": _ind(
        "ACQUISITION_DATE", "觀測日期", "Acquisition Date",
        "衛星飛過台灣上空拍下這筆雷達資料的日期與時間。",
        "Satellite sensor acquisition start timestamp in UTC and Taiwan local time (UTC+8).",
        "ISO-8601 timestamp", "direct metadata extraction", "需與中央氣象署警報時窗精確對齊。",
        ["UTC 日期與台灣時間跨午夜時可能差一天，應以精確時戳比對。"],
        ["CMR / Granule Metadata"], "NASA CMR / OPERA / NISAR", ["TEMPORAL_BASELINE"],
    ),
    "OBSERVATION_COUNT": _ind(
        "OBSERVATION_COUNT", "觀測次數", "Observation Count",
        "這塊田在分析期間內總共有幾筆可用的衛星觀測資料。",
        "Number of QA-passing SAR acquisitions available for the target field and period.",
        "count", "count(qa_passing_observations)", "觀測次數越多越能區分季節變化與突發事件。",
        ["目前 2025 與 2026 各 3 筆僅為有界比較，非多年氣候常模。"],
        ["時間序列紀錄"], "OPERA RTC-S1", ["TEMPORAL_BASELINE", "FIELD_COMPARISON"],
    ),
    "SPATIAL_RESOLUTION": _ind(
        "SPATIAL_RESOLUTION", "空間解析度", "Spatial Resolution",
        "衛星照片每一個小格子代表地面多大（例如 30 公尺代表一格是 30m × 30m）。",
        "Ground sample distance (pixel spacing) of the SAR raster product.",
        "m", "product specification (30 m for OPERA RTC-S1)", "決定可可靠觀測的最小農田尺度。",
        ["邊界混合像元可能包含田埂、道路或鄰近不同作物。"],
        ["產品規格中繼資料"], "OPERA RTC-S1 / NISAR", ["VALID_PIXEL_COUNT"],
    ),
    "PRODUCT_VERSION": _ind(
        "PRODUCT_VERSION", "產品處理版本", "Product / Processing Version",
        "衛星中心處理這份雷達資料時使用的軟體版本編號。",
        "Algorithm/collection version and Composite Release ID (CRID) of the SAR product.",
        "version_id", "metadata tag (e.g., OPERA_L2_RTC-S1_v1.0, P05023/P05036)", "不同版本間需先確認輻射校正一致性才可比較。",
        ["未經驗證跨版本一致性的資料不可直接做差值計算。"],
        ["Granule Metadata"], "NASA ASF / JPL", ["CRID_COMPATIBILITY"],
    ),
    "CRID_COMPATIBILITY": _ind(
        "CRID_COMPATIBILITY", "跨版本相容性 (CRID)", "CRID Compatibility",
        "檢查兩張不同時期的 NISAR 衛星資料是不是用同一套標準處理的，不同標準不能直接相減。",
        "Deterministic radiometric comparability gate checking whether pre/post NISAR scenes share a validated CRID.",
        "boolean / gate", "pre_crid == post_crid or cross_crid_qa_passed", "未通過時僅能各自獨立檢視，禁止產生差分災損圖。",
        ["目前 P05023（provisional）與 P05036（validated）尚未通過跨 CRID 一致性驗證。"],
        ["NISAR science_qa.json"], "SAR2Action Cross-CRID Guard", ["PRODUCT_VERSION", "SCIENTIFIC_QA_STATUS"],
    ),
    "NOISE_FLOOR_STATUS": _ind(
        "NOISE_FLOOR_STATUS", "雜訊底限狀態", "Noise Floor Status",
        "當地面雷達訊號很弱時，數值容易受到儀器本身微弱雜訊的影響。",
        "Assessment of proximity to sensor Noise Equivalent Sigma Zero (NESZ) in low-backscatter VH regimes.",
        "status", "deterministic QA flag inspection", "提醒低於約 -28 dB 的極低散射數值應謹慎解讀。",
        ["VH 極化在平靜水面或裸露濕地容易接近雜訊底限。"],
        ["RASTER_PROCESSING_TAGS"], "OPERA RTC-S1 QA", ["VH_BACKSCATTER_DB", "SCIENTIFIC_QA_STATUS"],
    ),
    "SCIENTIFIC_QA_STATUS": _ind(
        "SCIENTIFIC_QA_STATUS", "科學品質檢核狀態", "Scientific QA Status",
        "這份資料是否已經通過系統的空間、像元數與格式安全檢查。",
        "Composite deterministic QA gate covering valid pixels, coverage ratio, unit verification, and compatibility.",
        "status", "deterministic Python QA evaluation", "只有通過 QA 的資料才能用於科學分析。",
        ["通過資料 QA 不等於完成災損因果確認。"],
        ["空間覆蓋與處理標籤"], "Uncertainty Engine", ["VALID_COVERAGE_RATIO", "CRID_COMPATIBILITY"],
    ),
    "EVIDENCE_STATUS": _ind(
        "EVIDENCE_STATUS", "證據可信度狀態", "Evidence Status",
        "代表這項推論目前是「真的觀測到」、還是「原因尚未確定」或「還缺資料」。",
        "Epistemic classification of a scientific claim or hypothesis (OBSERVED, UNRESOLVED, CONTRADICTED, etc.).",
        "status", "deterministic falsification & ledger guard", "用來區分觀測事實與尚未證實的推測。",
        ["無反證不等於假設成立；未經現場查核不得標記為已確認。"],
        ["Evidence Ledger", "Falsification Guard"], "Experimentation Engine", ["SCIENTIFIC_QA_STATUS"],
    ),
    "FIELD_COMPARISON": _ind(
        "FIELD_COMPARISON", "跨農田比對", "Cross-Field Comparison",
        "把你的農田跟附近其他農田的雷達訊號放在一起看，看是不是大家都一起變化。",
        "Descriptive comparison of VH trajectories across the 5 official Taixi farmland candidates.",
        "dB / count", "per-field descriptive difference comparison", "協助區分區域性事件與單一農田管理差異。",
        ["目前僅有 5 塊候選農田，樣本數有限且無作物標籤，不構成正式因果推斷。"],
        ["field_comparison.json"], "Spatial Controls", ["VH_CHANGE_DB", "OBSERVATION_COUNT"],
    ),
    "ESTIMATED_AFFECTED_AREA": _ind(
        "ESTIMATED_AFFECTED_AREA", "衛星推估受影響面積", "Estimated Affected Area",
        "目前僅有整塊田的摘要統計，還沒有辦法用衛星直接算出精確受災面積。",
        "Satellite-derived affected area; strictly NOT_ESTIMABLE without validated pixel-level classification and ground truth.",
        "ha / status", "NOT_ESTIMABLE when only field-level medians exist", "不可用 ΔVH 直接換算受災面積。",
        ["未經地面驗證之像元分類不得產出面積數字。"],
        ["經地面驗證之像元級分類遮罩"], "Damage Assessment Service", ["FIELD_AREA_HA", "FARMER_REPORTED_DAMAGE_AREA"],
    ),
    "FARMER_REPORTED_DAMAGE_AREA": _ind(
        "FARMER_REPORTED_DAMAGE_AREA", "農民自報受災面積", "Farmer-Reported Damage Area",
        "這是你自己在地圖上圈選或回報的受災範圍大小，會標記為農民自報資料供公所參考。",
        "Geodesic intersection area between farmer-drawn damage polygon and field boundary, labeled FARMER_REPORTED.",
        "ha", "geodesic_intersection(field_poly, farmer_damage_poly)", "可協助整理申請資料，但最終仍以公所現場勘查核定為準。",
        ["農民自報面積不等同於政府核定面積 (GOVERNMENT_VERIFIED)。"],
        ["農田邊界", "農民圈選多邊形"], "FarmerFieldService", ["FIELD_AREA_HA", "ESTIMATED_AFFECTED_AREA"],
    ),
    "POTENTIAL_RELIEF_AMOUNT": _ind(
        "POTENTIAL_RELIEF_AMOUNT", "可能救助試算金額", "Potential Relief Amount",
        "依據公告標準與面積粗估的參考金額，實際能領多少還是要等公所勘查核定。",
        "Deterministic potential cash relief estimate when crop, official announcement, verified appendix rate, and eligible area are present.",
        "NTD", "eligible_area * verified_appendix_rate", "僅為 POTENTIAL_RELIEF_ESTIMATE，絕非核定金額。",
        ["若附表額度未經人工核對或公告未驗證，則無法進行試算。"],
        ["官方公告", "核定附表額度", "適用面積"], "ReliefAmountEstimator", ["APPLICATION_DEADLINE", "FIELD_AREA_HA"],
    ),
    "APPLICATION_DEADLINE": _ind(
        "APPLICATION_DEADLINE", "救助申請期限", "Application Deadline",
        "依《農業天然災害救助辦法》第 12 條，通常是在政府正式公告救助地區的隔天起 10 個工作日內申請。",
        "Statutory application deadline: 10 working days from the day following official central authority announcement (subject to extensions).",
        "date / working days", "official_announcement_date + 10 working days (if announced)", "必須以官方正式公告日期為準，不能只從颱風日推算。",
        ["無正式公告日期時回傳 DEADLINE_UNKNOWN。"],
        ["農業部正式救助公告日期", "展延公告（如有）"], "Legal Rule Engine (M0090019-ARTICLE-12)", ["POTENTIAL_RELIEF_AMOUNT"],
    ),
}

DATA_STATUS_EXPLANATIONS: dict[str, dict[str, str]] = {
    "OBSERVED": {
        "name_zh_tw": "已觀測資料",
        "reason": "數值直接來自經過驗證的真實衛星影像或官方紀錄。",
        "next_step": "可搭配時間軸、其他農田與品質指標一起解讀，但仍須確認原因。",
    },
    "SUPPORTED": {
        "name_zh_tw": "有條件支持",
        "reason": "具備通過品質檢核且具有區辨能力的直接證據支持該假設。",
        "next_step": "仍應確認是否還有未執行的地面驗證或法規要件。",
    },
    "UNRESOLVED": {
        "name_zh_tw": "原因尚未確定",
        "reason": "目前有觀測資料，但還不足以確定造成變化的單一原因。",
        "next_step": "需補充作物紀錄、降雨/土壤水分或現場勘查資料。",
    },
    "NOT_EVALUATED": {
        "name_zh_tw": "尚未評估",
        "reason": "缺少進行該項品質或統計檢核所需的輸入資料。",
        "next_step": "請先選取有效農田或載入對應的衛星觀測資料。",
    },
    "INSUFFICIENT_DATA": {
        "name_zh_tw": "資料不足",
        "reason": "現有樣本或外部佐證不足，無法產生可靠的統計或因果結論。",
        "next_step": "請補充缺漏的觀測、作物或地面調查資料。",
    },
    "NOT_COMPATIBLE": {
        "name_zh_tw": "資料條件不相容",
        "reason": "這兩份資料的處理條件（如 NISAR CRID 版本）尚未確認可以直接比較，因此暫時不能計算可靠的差值。",
        "next_step": "請獨立檢視各期影像，或等待相同 CRID 重新處理之產品。",
    },
    "NOT_ESTIMABLE": {
        "name_zh_tw": "目前無法估算",
        "reason": "缺乏經驗證的像元分類或官方計算參數，依科學規範不得憑空推算數字。",
        "next_step": "可由農民手動圈選回報範圍，或等待公所現場勘查結果。",
    },
}
