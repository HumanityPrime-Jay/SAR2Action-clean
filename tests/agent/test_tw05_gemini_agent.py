"""Phase A integration & safety suite for TW-05 Bounded Gemini Agent backend.

Exercises real `google.genai.types` declarations, `GeminiModelProvider`,
`RealAgentRuntime.run_tw05`, `Tw05AgentToolAdapter`, `claim_validator`,
and FastAPI route handlers over verified TW-01, TW-03, TW-08A, and TW-07.2 data
(without local sockets per Windows sandbox guidance).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import (
    agent_orchestrator,
    agent_status,
    app,
    get_tw05_evidence_endpoint,
    investigate_tw05_endpoint,
    science_service,
    taiwan_agro_service,
)
from backend.app.schemas.taiwan_agro import TwAgroReliefEstimateRequest
from backend.app.schemas.tw05_agent import (
    Tw05InvestigationRequest,
    Tw05InvestigationResponse,
)
from backend.app.services.agent_orchestrator import AgentOrchestrator
from backend.app.services.claim_validator import validate_tw05_observed_fact
from backend.app.services.gemini_provider import GeminiModelProvider
from backend.app.services.real_agent_runtime import redact_credentials
from backend.app.services.tw05_agent_adapter import TW05_SYSTEM_INSTRUCTION, TW05_TOOLS


class ScriptedGeminiModels:
    """Fake google.genai `client.models` recording real `GenerateContentConfig` payloads."""

    def __init__(self, script_fn):
        self.script_fn = script_fn
        self.configs = []
        self.contents = []

    def generate_content(self, *, model, contents, config):
        self.configs.append(config)
        self.contents.append(contents)
        calls = self.script_fn(len(self.configs), contents, config)
        return SimpleNamespace(function_calls=calls)


class FailingGeminiModels:
    def generate_content(self, *, model, contents, config):
        err = RuntimeError('simulated upstream 500')
        setattr(err, 'code', 500)
        raise err


def _make_provider(monkeypatch, script_fn) -> tuple[GeminiModelProvider, ScriptedGeminiModels]:
    monkeypatch.setenv('GEMINI_API_KEY', 'AIzaSyFakeProcessKeyForUnitTestsOnly123456')
    models = ScriptedGeminiModels(script_fn)
    provider = GeminiModelProvider(client=SimpleNamespace(models=models))
    return provider, models


def test_gemini_tw05_tool_declarations_and_argument_guards(monkeypatch):
    def script(round_idx, contents, config):
        return [
            SimpleNamespace(
                name='query_tw01_s1_parcel_changes',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 74},
            ),
            SimpleNamespace(
                name='query_tw07_statutory_relief',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'crop_item_id': 'rice_hacked', 'damage_rate': 0.5},
            ),
            SimpleNamespace(name='shell', args={'command': 'cat /etc/passwd'}),
        ]

    provider, models = _make_provider(monkeypatch, script)
    calls, _ = provider.choose_gis_tools(
        'Check parcel #74 and estimate relief with AIzaSyLeakedSecretValue99999999999',
        TW05_TOOLS,
        {'case_id': 'TW-05-YUNLIN-AGRO', 'locked_parcel_feature_id': 74},
        system_instruction=TW05_SYSTEM_INSTRUCTION,
    )
    cfg = models.configs[0]
    assert cfg.automatic_function_calling.disable is True
    assert str(cfg.tool_config.function_calling_config.mode).endswith('ANY')
    declared_names = [fd.name for fd in cfg.tools[0].function_declarations]
    assert set(declared_names) == set(TW05_TOOLS.keys())

    assert calls[0]['error'] is None
    assert calls[1]['error'] == 'invalid_arguments'  # extra relief params forbidden by schema
    assert calls[2]['error'] == 'unauthorized_tool'
    assert 'AIzaSy' not in redact_credentials('token=AIzaSyLeakedSecretValue99999999999')
    assert 'AIzaSyFakeProcessKeyForUnitTestsOnly123456' not in redact_credentials(
        'key=AIzaSyFakeProcessKeyForUnitTestsOnly123456'
    )


def test_gemini_multi_round_parcel_74_verified_real_data(monkeypatch):
    def script(round_idx, contents, config):
        if round_idx == 1:
            return [
                SimpleNamespace(
                    name='query_tw01_s1_parcel_changes',
                    args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 74},
                ),
                SimpleNamespace(
                    name='query_tw03_nisar_evidence',
                    args={'case_id': 'TW-05-YUNLIN-AGRO'},
                ),
            ]
        return [
            SimpleNamespace(
                name='query_tw08_s2_optical_qa',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 74},
            ),
            SimpleNamespace(
                name='query_tw07_statutory_relief',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 74},
            ),
        ]

    provider, models = _make_provider(monkeypatch, script)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', provider)

    secret = 'AIzaSyFakeProcessKeyForUnitTestsOnly123456'
    resp: Tw05InvestigationResponse = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            case_id='TW-05-YUNLIN-AGRO',
            aoi_id='TW-01-YUNLIN-5KM',
            parcel_feature_id=74,
            question=f'請整合四個模組檢查坵塊 #74（key={secret}）',
            agent_mode='gemini',
            session_id='tw05-p74-test',
        )
    )
    assert resp.status == 'completed'
    assert resp.execution_mode == 'GEMINI_FUNCTION_CALLING_MOCK'
    assert resp.model_provider == 'gemini'
    assert resp.locked_parcel_feature_id == 74
    assert len(models.configs) == 2

    overview = taiwan_agro_service.get_overview()
    opt74 = taiwan_agro_service.get_parcel_optical_metrics(74)
    cand74 = next(c for c in overview.parcel_screening_summary.candidates if c.parcel_feature_id == 74)
    facts = {f.fact_id: f for f in resp.observed_facts}

    assert facts['tw01_s1_vv_aoi_median'].metric_value == pytest.approx(
        overview.s1_tw01.polarization_stats['VV'].delta_db.median, abs=1e-6
    )
    assert facts['tw01_s1_vh_aoi_median'].metric_value == pytest.approx(
        overview.s1_tw01.polarization_stats['VH'].delta_db.median, abs=1e-6
    )
    assert facts['tw03_nisar_hh_median'].metric_value == pytest.approx(
        overview.nisar_tw03.polarization_stats['HH'].delta_db.median, abs=1e-6
    )
    assert facts['tw03_nisar_hv_median'].metric_value == pytest.approx(
        overview.nisar_tw03.polarization_stats['HV'].delta_db.median, abs=1e-6
    )
    assert facts['tw01_parcel_74_s1_vv'].metric_value == pytest.approx(cand74.median_delta_vv_db, abs=1e-6)
    assert facts['tw01_parcel_74_s1_vh'].metric_value == pytest.approx(cand74.median_delta_vh_db, abs=1e-6)
    assert facts['tw08_parcel_74_delta_ndvi'].metric_value == pytest.approx(
        opt74.delta_ndvi_20261011_20261105, abs=1e-6
    )

    assert resp.epistemic_guardrails.crop_type_label == 'UNKNOWN'
    assert resp.epistemic_guardrails.actual_damage_rate == 'UNKNOWN'
    assert resp.epistemic_guardrails.confirmed_typhoon_damage is False
    assert resp.epistemic_guardrails.official_relief_eligibility == 'UNKNOWN'
    assert resp.epistemic_guardrails.cross_sensor_direct_subtraction_allowed is False
    assert resp.epistemic_guardrails.optical_insufficient_parcel_flag is False
    assert resp.relief_assessment is not None
    assert resp.relief_assessment['result_status'] == 'BLOCKED_NO_USER_ASSUMPTIONS'
    assert resp.relief_assessment['conditional_reference_amount_twd'] is None

    serialized = json.dumps(resp.model_dump(mode='json'), ensure_ascii=False)
    assert secret not in serialized
    assert len(resp.evidence_ids) >= 4
    ev = get_tw05_evidence_endpoint(resp.evidence_ids[0])
    assert ev.evidence_id == resp.evidence_ids[0]


def test_parcel_174_preserves_insufficient_optical_evidence_without_fabrication(monkeypatch):
    def script(round_idx, contents, config):
        return [
            SimpleNamespace(
                name='query_tw01_s1_parcel_changes',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 174},
            ),
            SimpleNamespace(
                name='query_tw08_s2_optical_qa',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 174},
            ),
        ]

    provider, _ = _make_provider(monkeypatch, script)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', provider)

    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=174,
            question='Inspect parcel #174 Sentinel-2 quality status.',
            agent_mode='gemini',
            session_id='tw05-p174-insufficient',
        )
    )
    assert resp.status == 'completed'
    assert resp.epistemic_guardrails.optical_insufficient_parcel_flag is True
    facts = {f.fact_id: f for f in resp.observed_facts}
    assert 'tw08_parcel_174_delta_ndvi' not in facts
    assert 'tw08_parcel_174_insufficient' in facts
    assert facts['tw08_parcel_174_insufficient'].verified_value_str == 'INSUFFICIENT OPTICAL EVIDENCE'
    assert any('INSUFFICIENT OPTICAL EVIDENCE' in item for item in resp.unknowns)


def test_parcel_4183_with_caller_relief_assumptions_computes_exact_16343_ntd(monkeypatch):
    def script(round_idx, contents, config):
        return [
            SimpleNamespace(
                name='query_tw01_s1_parcel_changes',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 4183},
            ),
            SimpleNamespace(
                name='query_tw07_statutory_relief',
                args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 4183},
            ),
        ]

    provider, _ = _make_provider(monkeypatch, script)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', provider)

    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=4183,
            question='Use caller relief assumptions to inspect #4183.',
            agent_mode='gemini',
            session_id='tw05-p4183-relief',
            user_relief_assumptions=TwAgroReliefEstimateRequest(
                parcel_feature_id=4183,
                crop_item_id='grains_3_peanut_sweetpotato',
                assumed_approved_area_ha=0.453978,
                assumed_loss_threshold='meets_20_percent',
            ),
        )
    )
    assert resp.status == 'completed'
    assert resp.relief_assessment is not None
    assert resp.relief_assessment['calculation_allowed'] is True
    assert resp.relief_assessment['conditional_reference_amount_twd'] == 16343
    assert resp.epistemic_guardrails.official_relief_eligibility == 'UNKNOWN'
    assert any(
        f.fact_id == 'tw07_conditional_reference_amount' and f.metric_value == 16343.0
        for f in resp.observed_facts
    )


def test_cross_aoi_and_cross_parcel_isolation_enforced(monkeypatch):
    # 1. Cross-AOI schema locks reject OKI / non-Yunlin cases & unknown parcel
    with pytest.raises(ValidationError, match='Cross-AOI case_id'):
        Tw05InvestigationRequest(case_id='AOI-OKI-04', question='Switch to OKI')
    with pytest.raises(ValidationError, match='Cross-AOI aoi_id'):
        Tw05InvestigationRequest(aoi_id='OKI-F2', question='Switch to OKI')
    with pytest.raises(HTTPException) as exc404:
        investigate_tw05_endpoint(
            Tw05InvestigationRequest(
                parcel_feature_id=10009160,
                question='Inspect OKI parcel',
                agent_mode='deterministic',
                session_id='tw05-foreign-pid',
            )
        )
    assert exc404.value.status_code == 404
    assert exc404.value.detail['error_code'] == 'PARCEL_NOT_FOUND'

    # 2. Model escaping parcel lock (#74 -> #174) or AOI lock is rejected and traced
    def escaping_script(round_idx, contents, config):
        if round_idx == 1:
            return [
                SimpleNamespace(name='query_tw01_s1_parcel_changes', args={'case_id': 'AOI-OKI-04'}),
                SimpleNamespace(
                    name='query_tw01_s1_parcel_changes',
                    args={'case_id': 'TW-05-YUNLIN-AGRO', 'parcel_feature_id': 174},
                ),
                SimpleNamespace(name='shell', args={'cmd': 'dir'}),
            ]
        if round_idx == 2:
            return [
                SimpleNamespace(
                    name='query_tw03_nisar_evidence',
                    args={'case_id': 'TW-05-YUNLIN-AGRO'},
                ),
            ]
        return []

    provider, _ = _make_provider(monkeypatch, escaping_script)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', provider)

    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=74,
            question='Try escaping to #174',
            agent_mode='gemini',
            session_id='tw05-escape-guard',
        )
    )
    assert resp.status == 'completed'
    rejected_steps = [step for step in resp.tool_trace if step.status == 'rejected']
    assert len(rejected_steps) == 3
    assert resp.error is not None
    assert resp.error.error_code == 'PARTIAL_TOOL_REJECTIONS'
    assert resp.error.unauthorized_tool_calls == 1
    assert '174' not in json.dumps([f.model_dump(mode='json') for f in resp.observed_facts], ensure_ascii=False)
    assert '174' not in json.dumps([e.model_dump(mode='json') for e in resp.evidence_records], ensure_ascii=False)


def test_evidence_and_numeric_tampering_rejected():
    ledger = {
        'E-TW03-NISAR': {
            'evidence_id': 'E-TW03-NISAR',
            'verified_metrics': {'nisar_hv_median_delta_db': -0.1541},
        }
    }
    valid_fact = {
        'fact_id': 'f1',
        'sensor_or_source': 'NISAR',
        'metric_name': 'nisar_hv_median_delta_db',
        'metric_value': -0.1541,
        'verified_value_str': '-0.1541 dB',
        'unit': 'dB',
        'statement': 'NISAR HV median -0.1541 dB',
        'evidence_ids': ['E-TW03-NISAR'],
    }
    checked = validate_tw05_observed_fact(valid_fact, ledger)
    assert checked['epistemic_status'] == 'OBSERVED'

    forged_id = {**valid_fact, 'evidence_ids': ['E-FAKE']}
    with pytest.raises(ValueError, match='unregistered Evidence ID'):
        validate_tw05_observed_fact(forged_id, ledger)

    tampered_num = {**valid_fact, 'metric_value': -9.9999}
    with pytest.raises(ValueError, match='does not match verified Evidence'):
        validate_tw05_observed_fact(tampered_num, ledger)

    with pytest.raises(ValidationError, match='crop_type_label'):
        Tw05InvestigationResponse(
            investigation_id='x',
            status='completed',
            execution_mode='GEMINI_FUNCTION_CALLING_MOCK',
            agent_mode='gemini',
            model_provider='gemini',
            case_id='TW-05-YUNLIN-AGRO',
            aoi_id='TW-01-YUNLIN-5KM',
            aoi_bbox_wgs84=[120.1, 23.6, 120.3, 23.8],
            question='q',
            epistemic_guardrails={'crop_type_label': 'Rice'},
            data_mode='TW05_VERIFIED_REAL_DATA',
            provenance_status='TEST',
        )


def test_fail_closed_when_gemini_missing_or_errors(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', GeminiModelProvider())

    status = agent_status()
    assert status['gemini']['status'] == 'offline'

    blocked_missing = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            question='Should fail closed without deterministic fallback',
            agent_mode='gemini',
            session_id='tw05-missing-key',
        )
    )
    assert blocked_missing.status == 'blocked'
    assert blocked_missing.execution_mode == 'BLOCKED_NO_MODEL_CONFIGURED'
    assert blocked_missing.observed_facts == []
    assert blocked_missing.evidence_ids == []

    # Execution failure also fails closed
    monkeypatch.setenv('GEMINI_API_KEY', 'AIzaSyFakeProcessKeyForUnitTestsOnly123456')
    failing_provider = GeminiModelProvider(client=SimpleNamespace(models=FailingGeminiModels()))
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', failing_provider)
    blocked_err = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            question='Trigger simulated upstream error',
            agent_mode='gemini',
            session_id='tw05-upstream-err',
        )
    )
    assert blocked_err.status == 'blocked'
    assert blocked_err.execution_mode == 'BLOCKED_MODEL_EXECUTION_FAILED'
    assert blocked_err.observed_facts == []
    assert blocked_err.error is not None
    assert blocked_err.error.error_code == 'GEMINI_EXECUTION_ERROR'


def test_explicit_deterministic_mode_executes_four_allowlisted_tools():
    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=74,
            question='Deterministic read-only verification',
            agent_mode='deterministic',
            session_id='tw05-deterministic-p74',
        )
    )
    assert resp.status == 'completed'
    assert resp.execution_mode == 'DETERMINISTIC_TOOL_PIPELINE'
    assert resp.model_provider == 'deterministic_adapter'
    assert resp.model_name is None
    executed_tools = {s.tool for s in resp.tool_trace if s.kind == 'tool_result' and s.status == 'complete'}
    assert executed_tools == set(TW05_TOOLS.keys())


def test_phase_a5_default_route_surface_and_no_legacy_side_effects(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', GeminiModelProvider())

    tw05_routes = {r.path for r in app.routes if hasattr(r, 'path') and r.path.startswith('/api/agent/tw05')}
    assert tw05_routes == {
        '/api/agent/tw05/investigate',
        '/api/agent/tw05/evidence/{evidence_id}',
    }
    assert '/api/agent/status' in {r.path for r in app.routes if hasattr(r, 'path')}

    status = agent_status()
    assert status['gemini']['api_key_configured'] is False
    assert status['gemini']['live_function_calling_verified'] is False

    sid = 'tw05-no-legacy-side-effects'
    agent_orchestrator.operations.pop(sid, None)
    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=74,
            question='Inspect parcel #74 without touching legacy operations',
            agent_mode='deterministic',
            session_id=sid,
        )
    )
    assert resp.status == 'completed'
    assert sid not in agent_orchestrator.operations


def test_phase_a5_evidence_allowlist_stateless_lookup_and_preflight_parcel_lock(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', GeminiModelProvider())

    # 1. Cross-case and traversal evidence IDs rejected with HTTP 422
    for bad_id in ('E-FLAGSHIP-OKI-001', '../secret', 'E-PHASE2A-ENG-001', 'invalid-id'):
        with pytest.raises(HTTPException) as exc422:
            get_tw05_evidence_endpoint(bad_id)
        assert exc422.value.status_code == 422
        assert exc422.value.detail['error_code'] == 'INVALID_OR_CROSS_CASE_EVIDENCE_ID'

    # 2. Well-formed nonexistent TW-05 evidence ID -> HTTP 404
    with pytest.raises(HTTPException) as exc404_ev:
        get_tw05_evidence_endpoint('E-TW01-DOESNOTEXIST')
    assert exc404_ev.value.status_code == 404
    assert exc404_ev.value.detail['error_code'] == 'TW05_EVIDENCE_NOT_FOUND'

    # 3. Stateless resolution on a fresh orchestrator with empty tw05_evidence_index
    fresh_orch = AgentOrchestrator(science_service, taiwan_agro_service)
    assert fresh_orch.tw05_evidence_index == {}
    ev_p74 = fresh_orch.get_tw05_evidence('E-TW01-PARCEL-74')
    assert ev_p74 is not None and ev_p74.evidence_id == 'E-TW01-PARCEL-74'
    ev_opt74 = get_tw05_evidence_endpoint('E-TW08A-PARCEL-74')
    assert ev_opt74.evidence_id == 'E-TW08A-PARCEL-74'

    # 4. Preflight parcel lock rejects foreign parcel even when Gemini is offline
    with pytest.raises(HTTPException) as exc404_pid:
        investigate_tw05_endpoint(
            Tw05InvestigationRequest(
                parcel_feature_id=10009160,
                question='Query foreign parcel when offline',
                agent_mode='gemini',
                session_id='tw05-offline-foreign-pid',
            )
        )
    assert exc404_pid.value.status_code == 404
    assert exc404_pid.value.detail['error_code'] == 'PARCEL_NOT_FOUND'


def test_phase_a5_local_filesystem_path_and_secret_redaction(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(agent_orchestrator, 'gemini_model', GeminiModelProvider())

    resp = investigate_tw05_endpoint(
        Tw05InvestigationRequest(
            parcel_feature_id=74,
            question=r'Check D:\SecretDir\credentials.json and /Users/dev/.env token=AIzaSyLeakTestSecret123456789012',
            agent_mode='gemini',
            session_id='tw05-redact-paths',
        )
    )
    dumped = json.dumps(resp.model_dump(mode='json'), ensure_ascii=False)
    assert 'D:\\SecretDir' not in dumped
    assert 'C:\\' not in dumped
    assert '/Users/dev/' not in dumped
    assert 'AIzaSy' not in dumped
    assert '[LOCAL_PATH_REDACTED]' in resp.question
    assert '[REDACTED]' in resp.question
