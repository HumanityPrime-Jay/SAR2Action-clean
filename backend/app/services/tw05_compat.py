"""Compatibility adapter for TW-05 agricultural evidence & statutory relief endpoints."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.investigation_v3 import InvestigationV3Request
from backend.app.services.agriculture_vh_evidence import run_tool as run_vh_tool
from backend.app.services.gemini_provider import GeminiModelProvider
from backend.app.services.investigation_v3 import ALL_TOOLS, InvestigationV3Service

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get('SAR2ACTION_DATA_ROOT') or (ROOT / 'data')).resolve()

# Statutory rates under 《農業天然災害救助辦法》附表二 (Schedule II).
# No verified parcel-level disaster announcement is assumed.
STATUTORY_ITEMS: list[dict[str, Any]] = [
    {
        'item_id': 'grains_3_peanut_sweetpotato',
        'display_name': '雜糧三（落花生、甘藷等）',
        'statutory_category': '附表二 · 雜糧三',
        'rate_twd_per_ha': 36000,
        'unit': 'TWD/ha',
        'announced_in_yunlin_11510': False,
        'statutory_conditions': '須經主管機關公告救助地區及品項，並經現場勘查核認損害率達 20% 以上。',
    },
    {
        'item_id': 'garlic',
        'display_name': '大蒜（蔥蒜類）',
        'statutory_category': '附表二 · 蔬菜一／蔥蒜類',
        'rate_twd_per_ha': 40000,
        'unit': 'TWD/ha',
        'announced_in_yunlin_11510': False,
        'statutory_conditions': '須經主管機關公告救助地區及品項，並經現場勘查核認損害率達 20% 以上。',
    },
    {
        'item_id': 'paddy_rice',
        'display_name': '稻米',
        'statutory_category': '附表二 · 稻米',
        'rate_twd_per_ha': 20000,
        'unit': 'TWD/ha',
        'announced_in_yunlin_11510': False,
        'statutory_conditions': '須經主管機關公告救助地區及品項，並經現場勘查核認損害率達 20% 以上。',
    },
    {
        'item_id': 'vegetables_general',
        'display_name': '短期葉菜類／一般蔬菜',
        'statutory_category': '附表二 · 蔬菜',
        'rate_twd_per_ha': 29000,
        'unit': 'TWD/ha',
        'announced_in_yunlin_11510': False,
        'statutory_conditions': '須經主管機關公告救助地區及品項，並經現場勘查核認損害率達 20% 以上。',
    },
]
STATUTORY_BY_ID = {item['item_id']: item for item in STATUTORY_ITEMS}

PARCEL_TO_FIELD = {
    74: 'YL-CAND-03',
    174: 'YL-CAND-01',
    4183: 'YL-CAND-04',
}


class Tw05InvestigateRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    case_id: str = 'TW-05-YUNLIN-AGRO'
    aoi_id: str = 'TW-01-YUNLIN-5KM'
    parcel_feature_id: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=1200)
    agent_mode: Literal['gemini', 'deterministic', 'real'] = 'deterministic'
    session_id: str | None = None


class TwAgroReliefEstimateRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    parcel_feature_id: int | None = None
    crop_item_id: str = Field(min_length=1)
    assumed_approved_area_ha: float | None = None
    assumed_loss_threshold: Literal[
        'unverified',
        'below_20_percent',
        'meets_20_percent',
        'article_12_simplified_exception',
    ] = 'unverified'
    allow_cross_aoi_boundary_area: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_recorded_investigation() -> dict[str, Any]:
    candidates = [
        DATA_ROOT / 'exports/yunlin_vh_2025_2026/field_investigation.json',
        ROOT / 'data/exports/yunlin_vh_2025_2026/field_investigation.json',
        ROOT / 'frontend/public/studio/field_investigation.json',
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding='utf-8'))
    return {}


def build_agent_status_extras() -> dict[str, Any]:
    api_key = bool(os.environ.get('GEMINI_API_KEY'))
    model_name = os.environ.get('SAR2ACTION_GEMINI_MODEL', 'gemini-3.1-flash-lite')
    return {
        'gemini': {
            'status': 'configured' if api_key else 'unconfigured',
            'provider': 'google-genai',
            'model': model_name,
            'api_key_configured': api_key,
            'live_function_calling_verified': False,
            'reason': None if api_key else 'GEMINI_API_KEY is not set; deterministic pipeline active.',
        },
        'tw05_agent_available': True,
        'tw05_tools': list(ALL_TOOLS.keys()),
    }


def investigate_tw05(req: Tw05InvestigateRequest) -> dict[str, Any]:
    """Execute bounded deterministic or Gemini-grounded investigation for a Yunlin parcel."""
    t0 = time.perf_counter()
    field_id = PARCEL_TO_FIELD.get(req.parcel_feature_id, 'YL-CAND-03')
    parcel_eid = f'E-TW01-PARCEL-{req.parcel_feature_id}'

    if req.agent_mode == 'gemini' and not os.environ.get('GEMINI_API_KEY'):
        return {
            'investigation_id': str(uuid4()),
            'status': 'blocked',
            'execution_mode': 'BLOCKED_NO_MODEL_CONFIGURED',
            'agent_mode': req.agent_mode,
            'model_provider': 'google-genai',
            'model_name': os.environ.get('SAR2ACTION_GEMINI_MODEL', 'gemini-3.1-flash-lite'),
            'case_id': req.case_id,
            'aoi_id': req.aoi_id,
            'locked_parcel_feature_id': req.parcel_feature_id,
            'question': req.question,
            'observed_facts': [],
            'inferences': [],
            'unknowns': ['GEMINI_API_KEY is not configured in the backend environment.'],
            'evidence_ids': [parcel_eid],
            'evidence_records': [],
            'tool_trace': [],
            'scientific_limitations': ['Live Gemini mode requires GEMINI_API_KEY; deterministic mode remains available.'],
            'error': {
                'error_code': 'NO_GEMINI_KEY',
                'message': 'GEMINI_API_KEY is not configured; live Gemini tool calling is blocked.',
                'rejected_tool_count': 0,
                'unauthorized_tool_calls': 0,
            },
            'epistemic_guardrails': {
                'crop_type_label': 'UNVERIFIED',
                'actual_damage_rate': 'UNKNOWN',
                'confirmed_typhoon_damage': False,
                'official_relief_eligibility': 'ANNOUNCEMENT_NOT_VERIFIED',
                'optical_insufficient_parcel_flag': req.parcel_feature_id == 174,
            },
            'parcel_summary': {'parcel_feature_id': req.parcel_feature_id, 'mapped_field_id': field_id},
        }

    # Run deterministic science tools (either live V3 if data root provisioned, or recorded/VH tool fallback)
    ts_data = run_vh_tool('get_field_vh_timeseries', field_id)
    changes_data = run_vh_tool('calculate_temporal_changes', field_id)
    hyp_data = run_vh_tool('evaluate_field_hypotheses', field_id)

    v3_used = False
    try:
        v3_resp = InvestigationV3Service().investigate(
            InvestigationV3Request(
                field_id=field_id,
                question=req.question,
                agent_mode='gemini' if req.agent_mode in {'gemini', 'real'} else 'deterministic',
            )
        )
        v3_used = True
        v3_eids = list(v3_resp.evidence_ids)
        v3_limitations = list(v3_resp.scientific_limitations)
    except Exception:
        recorded = _load_recorded_investigation()
        v3_eids = list(recorded.get('evidence_ids', []))[:8]
        v3_limitations = list(recorded.get('scientific_limitations', [])) or [
            'Parcel-level crop type and typhoon damage rate are not confirmed from SAR backscatter alone.',
            'Optical Sentinel-2 parcel QA raster is not provisioned in this checkout (DATA_NOT_AVAILABLE).',
        ]

    obs_list = ts_data.get('observations', [])
    vh_delta = (changes_data.get('2026_pre_to_warning_window') or {}).get('median_difference_db')
    vh_delta_str = f'{vh_delta:+.3f} dB' if isinstance(vh_delta, (int, float)) else 'UNAVAILABLE'

    evidence_ids = [parcel_eid] + [eid for eid in v3_eids if eid != parcel_eid][:6]
    observed_facts = [
        {
            'fact_id': f'FACT-{req.parcel_feature_id}-VH-SERIES',
            'sensor_or_source': 'Sentinel-1C OPERA RTC-S1 VH',
            'metric_name': 'Observed VH pre-warning to warning-window median change',
            'metric_value': vh_delta if isinstance(vh_delta, (int, float)) else None,
            'verified_value_str': vh_delta_str,
            'unit': 'dB',
            'statement': f'Mapped reference field {field_id} has {len(obs_list)} QA-passing OPERA VH observations; observed change is descriptive only, not confirmed crop damage.',
            'epistemic_status': 'OBSERVED',
            'evidence_ids': evidence_ids[:2],
        },
        {
            'fact_id': f'FACT-{req.parcel_feature_id}-OPTICAL',
            'sensor_or_source': 'Sentinel-2 Optical QA',
            'metric_name': 'Optical parcel raster availability',
            'metric_value': None,
            'verified_value_str': 'DATA_NOT_AVAILABLE',
            'unit': 'status',
            'statement': 'Parcel-level Sentinel-2 optical raster is not provisioned; Blue Marble basemap is never substituted.',
            'epistemic_status': 'OBSERVED',
            'evidence_ids': [parcel_eid],
        },
    ]

    inferences = [
        {
            'inference_id': f'INF-{req.parcel_feature_id}-HYPOTHESES',
            'statement': 'Observed VH shifts remain consistent with multiple competing causes (surface moisture, harvesting, field preparation, storm disturbance, or geometry/processing).',
            'status': 'UNRESOLVED',
            'supporting_evidence_ids': evidence_ids[:2],
            'contradicting_evidence_ids': [],
            'proposed_by_gemini': req.agent_mode == 'gemini' and v3_used,
            'reason': hyp_data.get('status', 'Multiple competing hypotheses remain open without ground truth.'),
        }
    ]

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    tool_trace = [
        {
            'step': 1,
            'timestamp_utc': _now(),
            'kind': 'tool_call',
            'tool': 'get_field_vh_timeseries',
            'status': 'complete',
            'validated_arguments': {'field_id': field_id, 'parcel_feature_id': req.parcel_feature_id},
            'source_references': ['data/exports/yunlin_vh_2025_2026/vh_timeseries.json'],
            'evidence_ids': evidence_ids[:2],
            'duration_ms': elapsed_ms,
            'detail': {'observation_count': len(obs_list)},
        },
        {
            'step': 2,
            'timestamp_utc': _now(),
            'kind': 'tool_result',
            'tool': 'calculate_temporal_changes',
            'status': 'complete',
            'validated_arguments': {'field_id': field_id},
            'source_references': ['data/exports/yunlin_vh_2025_2026/field_comparison.json'],
            'evidence_ids': evidence_ids[:2],
            'duration_ms': elapsed_ms,
            'detail': {'median_difference_db': vh_delta},
        },
        {
            'step': 3,
            'timestamp_utc': _now(),
            'kind': 'validation',
            'tool': 'evaluate_field_hypotheses',
            'status': 'complete',
            'validated_arguments': {'field_id': field_id},
            'source_references': ['data/exports/yunlin_vh_2025_2026/scientific_qa.json'],
            'evidence_ids': [parcel_eid],
            'duration_ms': elapsed_ms,
            'detail': {'crop_damage_status': 'UNKNOWN'},
        },
    ]

    execution_mode = (
        'GEMINI_FUNCTION_CALLING_LIVE'
        if req.agent_mode == 'gemini' and os.environ.get('GEMINI_API_KEY') and v3_used
        else 'DETERMINISTIC_TOOL_PIPELINE'
    )

    return {
        'investigation_id': str(uuid4()),
        'status': 'completed',
        'execution_mode': execution_mode,
        'agent_mode': req.agent_mode,
        'model_provider': 'google-genai' if execution_mode == 'GEMINI_FUNCTION_CALLING_LIVE' else 'deterministic',
        'model_name': os.environ.get('SAR2ACTION_GEMINI_MODEL', 'gemini-3.1-flash-lite')
        if execution_mode == 'GEMINI_FUNCTION_CALLING_LIVE'
        else 'sar2action-deterministic-v3',
        'case_id': req.case_id,
        'aoi_id': req.aoi_id,
        'locked_parcel_feature_id': req.parcel_feature_id,
        'question': req.question,
        'observed_facts': observed_facts,
        'inferences': inferences,
        'unknowns': [
            'Parcel-level crop type is unverified.',
            'Actual crop damage rate and official relief eligibility require on-site inspection and official disaster announcement.',
        ],
        'evidence_ids': evidence_ids,
        'evidence_records': [
            {
                'evidence_id': parcel_eid,
                'source_module': 'tw05_compat',
                'sensor_or_authority': 'Sentinel-1C OPERA RTC-S1 VH + Scientific QA',
                'acquisition_window': '2025-10 to 2026-11',
                'summary': f'Parcel #{req.parcel_feature_id} mapped to {field_id} ({vh_delta_str} descriptive VH change).',
                'provenance_status': 'OBSERVED_DESCRIPTIVE_ONLY',
                'verified_metrics': {'vh_median_diff_db': vh_delta, 'observations': len(obs_list)},
                'limitations': v3_limitations[:2],
            }
        ],
        'tool_trace': tool_trace,
        'scientific_limitations': v3_limitations,
        'error': None,
        'epistemic_guardrails': {
            'crop_type_label': 'UNVERIFIED',
            'actual_damage_rate': 'UNKNOWN',
            'confirmed_typhoon_damage': False,
            'official_relief_eligibility': 'ANNOUNCEMENT_NOT_VERIFIED',
            'optical_insufficient_parcel_flag': req.parcel_feature_id == 174,
        },
        'parcel_summary': {
            'parcel_feature_id': req.parcel_feature_id,
            'mapped_field_id': field_id,
            'v3_live_verified': v3_used,
        },
    }


def get_relief_catalog() -> dict[str, Any]:
    """Return statutory relief schedule under 《農業天然災害救助辦法》."""
    return {
        'schedule_version_id': 'MOA-RELIEF-REGULATIONS-SCHED-II',
        'regulation_title': '農業天然災害救助辦法（附表二）',
        'announcement_status': 'ANNOUNCEMENT_NOT_VERIFIED',
        'min_application_area_ha': 0.01,
        'statutory_loss_threshold_fraction': 0.2,
        'items': STATUTORY_ITEMS,
    }


def estimate_relief(req: TwAgroReliefEstimateRequest) -> dict[str, Any]:
    """Compute conditional statutory relief estimate or fail closed when requirements are missing."""
    disclaimer = (
        'CONDITIONAL ESTIMATE / NOT OFFICIAL: 僅依使用者假設條件與《農業天然災害救助辦法》附表二試算，'
        '實際救助資格與金額須以主管機關公告及現場勘查核定為準。'
    )
    unconfirmed = ['ANNOUNCEMENT_NOT_VERIFIED', 'CROP_TYPE_UNVERIFIED', 'ON_SITE_INSPECTION_REQUIRED']

    item = STATUTORY_BY_ID.get(req.crop_item_id)
    if item is None:
        return {
            'calculation_allowed': False,
            'result_status': 'BLOCKED_UNKNOWN_CROP',
            'result_label': '未知作物品項',
            'blocked_reason': 'CANNOT_ESTIMATE_MISSING_REQUIREMENTS: unknown crop_item_id',
            'conditional_reference_amount_twd': None,
            'formula_display': None,
            'confirmed_facts': {'parcel_feature_id': req.parcel_feature_id},
            'user_assumptions': {'crop_item_id': req.crop_item_id},
            'unconfirmed_eligibility': unconfirmed,
            'non_approval_disclaimer': disclaimer,
        }

    if req.assumed_loss_threshold in {'unverified', 'below_20_percent'}:
        reason = (
            'CANNOT_ESTIMATE_MISSING_REQUIREMENTS: 損害率尚未驗證，禁止以雷達變化替代農損率。'
            if req.assumed_loss_threshold == 'unverified'
            else '損害率未達法定 20% 救助門檻，依規定不予救助。'
        )
        return {
            'calculation_allowed': False,
            'result_status': 'BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD',
            'result_label': '未達門檻或未驗證',
            'blocked_reason': reason,
            'conditional_reference_amount_twd': None,
            'formula_display': None,
            'confirmed_facts': {'parcel_feature_id': req.parcel_feature_id, 'rate_twd_per_ha': item['rate_twd_per_ha']},
            'user_assumptions': {
                'crop_item_id': req.crop_item_id,
                'assumed_loss_threshold': req.assumed_loss_threshold,
            },
            'unconfirmed_eligibility': unconfirmed,
            'non_approval_disclaimer': disclaimer,
        }

    area = req.assumed_approved_area_ha
    if area is None or area <= 0:
        return {
            'calculation_allowed': False,
            'result_status': 'BLOCKED_INVALID_AREA',
            'result_label': '無效面積',
            'blocked_reason': 'CANNOT_ESTIMATE_MISSING_REQUIREMENTS: assumed_approved_area_ha must be > 0',
            'conditional_reference_amount_twd': None,
            'formula_display': None,
            'confirmed_facts': {'parcel_feature_id': req.parcel_feature_id},
            'user_assumptions': {'crop_item_id': req.crop_item_id},
            'unconfirmed_eligibility': unconfirmed,
            'non_approval_disclaimer': disclaimer,
        }

    if area < 0.01:
        return {
            'calculation_allowed': False,
            'result_status': 'BLOCKED_BELOW_MIN_AREA_001_HA',
            'result_label': '未達最小申請面積 0.01 公頃',
            'blocked_reason': '低於法定最小申請面積 0.01 公頃。',
            'conditional_reference_amount_twd': None,
            'formula_display': None,
            'confirmed_facts': {'parcel_feature_id': req.parcel_feature_id},
            'user_assumptions': {'assumed_approved_area_ha': area},
            'unconfirmed_eligibility': unconfirmed,
            'non_approval_disclaimer': disclaimer,
        }

    rate = int(item['rate_twd_per_ha'])
    amount = round(area * rate)
    return {
        'calculation_allowed': True,
        'result_status': 'CONDITIONAL_REFERENCE_ESTIMATE',
        'result_label': '條件式參考試算（非核定金額）',
        'blocked_reason': None,
        'conditional_reference_amount_twd': amount,
        'formula_display': f'{area:.6f} 公頃 × NT$ {rate:,}/公頃',
        'confirmed_facts': {
            'parcel_feature_id': req.parcel_feature_id,
            'statutory_schedule': '農業天然災害救助辦法附表二',
            'rate_twd_per_ha': rate,
        },
        'user_assumptions': {
            'crop_item_id': req.crop_item_id,
            'assumed_approved_area_ha': area,
            'assumed_loss_threshold': req.assumed_loss_threshold,
            'allow_cross_aoi_boundary_area': req.allow_cross_aoi_boundary_area,
        },
        'unconfirmed_eligibility': unconfirmed,
        'non_approval_disclaimer': disclaimer,
    }


def get_parcel_optical(parcel_feature_id: int) -> dict[str, Any]:
    """Return structured optical availability status without fabricating imagery."""
    return {
        'parcel_feature_id': parcel_feature_id,
        'status': 'DATA_NOT_AVAILABLE',
        'source': None,
        'reason': (
            'No verified parcel-level Sentinel-2 optical observation raster is provisioned; '
            'general basemaps (e.g., Blue Marble) are not substituted.'
        ),
        'optical_insufficient_parcel_flag': parcel_feature_id == 174,
    }
