from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest
from backend.app.services.scientific_reasoner import assess_scientific_evidence
from backend.app.services.model_provider import ModelProvider
from backend.app.services.real_agent_runtime import NEXT_TOOLS

import httpx
import pytest


def request(**changes):
    data = dict(case_id='fixture-case', aoi_bbox_wgs84=[100, 0, 100.2, 0.2],
                query='Rank regions, compare them and inspect evidence',
                data_mode='fixture', agent_mode='real', session_id='real-mock')
    data.update(changes)
    return InvestigateRequest(**data)


class FakeModel:
    configured = True
    model = 'mock-model'
    provider = 'openai_compatible'

    def choose_gis_tools(self, query, available, context):
        if not context['ranking_complete']:
            return [{'name': 'rank_change_regions', 'arguments': {}, 'error': None}], ''
        if 'compare_regions' in available:
            return [{'name': 'compare_regions', 'arguments': {}, 'error': None},
                    {'name': 'inspect_evidence', 'arguments': {}, 'error': None}], ''
        return [], ''


def test_mock_model_selects_safe_tools_and_evidence():
    agent = AgentOrchestrator(object())
    agent.model = FakeModel()
    result = agent.investigate(request())
    assert result['status'] == 'completed' and result['agent_mode'] == 'real'
    assert result['comparison']['evidence_ids'] == result['evidence_ids'][:2]
    assert result['inspected_evidence_id'] in agent.spatial.evidence
    assert result['unauthorized_tool_calls'] == 0
    assert {'rank_change_regions', 'compare_regions', 'inspect_evidence'}.issubset(
        {event['tool'] for event in result['trace'] if event['status'] == 'complete'})


def test_real_mode_does_not_fallback_when_model_unavailable():
    agent = AgentOrchestrator(object())
    agent.model = type('Offline', (), {'configured': False})()
    result = agent.investigate(request())
    assert result['status'] == 'blocked' and result['claims'] == []
    assert not agent.spatial.evidence


def test_model_cannot_change_trusted_aoi_or_execute_unknown_tool():
    agent = AgentOrchestrator(object())
    class Malicious(FakeModel):
        def choose_gis_tools(self, query, available, context):
            if not context['ranking_complete']:
                return [{'name': 'shell', 'arguments': None, 'error': 'unauthorized_tool'},
                        {'name': 'rank_change_regions', 'arguments': {'case_id': 'other'}, 'error': None},
                        {'name': 'rank_change_regions', 'arguments': {}, 'error': None}], ''
            return [], ''
    agent.model = Malicious()
    result = agent.investigate(request(session_id='malicious-mock'))
    assert result['status'] == 'completed'
    assert result['unauthorized_tool_calls'] == 1
    assert any(event['tool'] == 'shell' and event['status'] == 'rejected' for event in result['trace'])
    assert any(event['tool'] == 'rank_change_regions' and event['status'] == 'rejected' for event in result['trace'])
    assert len(result['ranked_regions']) == 3


def test_cancellation_after_model_call_prevents_science_execution():
    agent = AgentOrchestrator(object())
    class Cancelling(FakeModel):
        def choose_gis_tools(self, query, available, context):
            agent.cancel('cancel-mock')
            return [{'name': 'rank_change_regions', 'arguments': {}, 'error': None}], ''
    agent.model = Cancelling()
    result = agent.investigate(request(session_id='cancel-mock'))
    assert result['status'] == 'cancelled'
    assert not agent.spatial.evidence


def test_process_credential_is_redacted_before_model_and_trace(monkeypatch):
    secret = 'test-key-process-only-1234567890'
    monkeypatch.setenv('GEMINI_API_KEY', secret)
    agent = AgentOrchestrator(object())
    seen = []
    class Capture(FakeModel):
        def choose_gis_tools(self, query, available, context):
            seen.append(query)
            return super().choose_gis_tools(query, available, context)
    agent.model = Capture()
    result = agent.investigate(request(query='Rank regions. token=' + secret, session_id='secret-redaction'))
    assert result['status'] == 'completed'
    assert all(secret not in query for query in seen)
    assert secret not in str(result['trace'])


def test_scientific_reasoner_marks_fire_cause_unknown_and_rejects_forged_value():
    agent = AgentOrchestrator(object())
    agent.model = FakeModel()
    req = request(query='Did a wildfire happen here?', session_id='science-mock')
    result = agent.investigate(req)
    assert result['status'] == 'completed'
    assessment = result['scientific_assessment']
    assert assessment['observed'] and assessment['observed'][0]['evidence_ids'][0] in result['evidence_ids']
    assert any('cannot confirm wildfire' in text for text in assessment['unknown'])
    assert assessment['data_kind'] == 'synthetic'
    result['claims'][0]['metric_value'] += 1
    with pytest.raises(ValueError, match='numeric claim'):
        assess_scientific_evidence(req, result, agent.spatial, agent.sessions[req.session_id])


def test_story_optional_argument_repair_never_repairs_evidence_id(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8086/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'mock')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'openai_compatible')
    def answer(arguments):
        return httpx.MockTransport(lambda request: httpx.Response(200, json={'choices': [{'message': {
            'tool_calls': [{'function': {'name': 'generate_story', 'arguments': arguments}}]}}]}))
    model = ModelProvider(transport=answer('{"audience":"science","extra":"ignore"}'))
    calls, _ = model.choose_gis_tools('Create a scientific story', {'generate_story': NEXT_TOOLS['generate_story']}, {})
    assert calls[0]['repaired'] and calls[0]['arguments'] == {'audience': 'scientific'}
    model.transport = answer('{"evidence_id":77,"audience":"scientific"}')
    calls, _ = model.choose_gis_tools('Create a scientific story', {'generate_story': NEXT_TOOLS['generate_story']}, {})
    assert calls[0]['error'] == 'invalid_arguments' and calls[0]['arguments'] is None


def test_inspect_evidence_repairs_extra_fields_only_for_registered_ids(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8086/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'mock')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'openai_compatible')
    def response(args):
        return httpx.MockTransport(lambda _: httpx.Response(200, json={'choices': [{'message': {
            'tool_calls': [{'function': {'name': 'inspect_evidence', 'arguments': args}}]}}]}))
    model = ModelProvider(transport=response('{"evidence_id":"SYN-CURRENT","reason":"show proof"}'))
    context = {'evidence_ids': ['SYN-CURRENT']}
    calls, _ = model.choose_gis_tools('Show proof', {'inspect_evidence': NEXT_TOOLS['inspect_evidence']}, context)
    assert calls[0]['repaired'] and calls[0]['arguments'] == {'evidence_id': 'SYN-CURRENT'}
    model.transport = response('{"evidence_id":"SYN-STALE","reason":"show proof"}')
    calls, _ = model.choose_gis_tools('Show proof', {'inspect_evidence': NEXT_TOOLS['inspect_evidence']}, context)
    assert calls[0]['error'] == 'invalid_arguments' and calls[0]['arguments'] is None


def test_one_model_timeout_retries_without_unauthorized_execution():
    agent = AgentOrchestrator(object())
    class Flaky(FakeModel):
        attempts = 0
        def choose_gis_tools(self, query, available, context):
            self.attempts += 1
            if self.attempts == 1:
                raise httpx.ReadTimeout('transient local model delay')
            return super().choose_gis_tools(query, available, context)
    agent.model = Flaky()
    result = agent.investigate(request(session_id='timeout-mock'))
    assert result['status'] == 'completed'
    assert any(event['tool'] == 'model_retry' for event in result['trace'])
    assert agent.model.attempts <= 3


def test_optional_followup_timeout_preserves_valid_evidence():
    agent = AgentOrchestrator(object())
    class LateTimeout(FakeModel):
        attempts = 0
        def choose_gis_tools(self, query, available, context):
            self.attempts += 1
            if self.attempts == 3:
                raise httpx.ReadTimeout('late optional selection')
            return super().choose_gis_tools(query, available, context)
    agent.model = LateTimeout()
    result = agent.investigate(request(session_id='late-timeout'))
    assert result['status'] == 'completed' and result['scientific_assessment']['observed']
    assert any(event['tool'] == 'model_retry' and event['status'] == 'skipped' for event in result['trace'])


@pytest.mark.parametrize('question', [
    'Does this radar change prove the ground moved?',
    'Can we conclude the ecosystem recovered?',
])
def test_causal_paraphrases_remain_unknown(question):
    agent = AgentOrchestrator(object())
    agent.model = FakeModel()
    result = agent.investigate(request(query=question, session_id='causal-paraphrase'))
    assert result['status'] == 'completed'
    assert any('cannot confirm' in item for item in result['scientific_assessment']['unknown'])
