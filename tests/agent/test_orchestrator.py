from types import SimpleNamespace as NS

import pytest

from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest, StoryRequest


class Claim:
    evidence_id = 'E-VALID'
    unit = 'dB'
    scene_ids = ['T0', 'T1']
    valid_pixel_count = 42
    roi_id = 'ROI-1'
    algorithm_version = 'change-v1'
    metric_name = 'median_delta_hv_db'
    metric_value = 1.2
    polarization = 'HV'
    def model_dump(self, **_):
        return {'evidence_id': self.evidence_id, 'unit': self.unit,
                'statement': 'HV median difference +1.2 dB', 'metric_value': 1.2}


class Science:
    compatible = True
    claim = Claim()
    def get_case(self, _):
        return NS(default_t0_scene_id='T0', default_t1_scene_id='T1')
    def validate_pair(self, _):
        return NS(result=NS(compatible=self.compatible))
    def compute_radar_fingerprint(self, request):
        return NS(evidence_id='E-VALID', claims=[self.claim],
                  aoi_bbox_wgs84=request.aoi_bbox_wgs84,
                  layers={'delta_hv': object()},
                  epistemic_panel=NS(what_we_do_not_know=['Cause unknown']),
                  quality_status='COMPARABLE', available_polarizations=['HV'])
    def get_evidence(self, _):
        return NS(evidence_id='E-VALID', scene_ids=['T0', 'T1'], valid_pixel_count=42,
                  roi_id='ROI-1', algorithm_version='change-v1',
                  summary_statistics={'per_polarization': {'HV': {'median_delta_db': 1.2}}},
                  combined_change_db=None)


def request(**updates):
    data = {'case_id': 'case-1', 'aoi_bbox_wgs84': [100, 0, 101, 1],
            'query': 'Find change', 'session_id': 'test-session'}
    data.update(updates)
    return InvestigateRequest(**data)


def test_completed_flow_has_only_deterministic_claim_and_registered_layer():
    agent = AgentOrchestrator(Science())
    result = agent.investigate(request())
    assert result['status'] == 'completed'
    assert result['claims'][0]['evidence_id'] == result['evidence_ids'][0]
    assert {a['type'] for a in result['map_actions']} == {
        'map.focus_bbox', 'map.highlight_aoi', 'fingerprint.open', 'map.set_layer'}
    assert result['trace'][-1]['status'] == 'complete'


def test_incompatible_pair_blocks_claims():
    science = Science()
    science.compatible = False
    result = AgentOrchestrator(science).investigate(request())
    assert result['status'] == 'blocked' and not result['claims']


def test_forged_claim_evidence_is_rejected():
    science = Science()
    science.claim = Claim()
    science.claim.evidence_id = 'E-FORGED'
    with pytest.raises(ValueError, match='validation failed'):
        AgentOrchestrator(science).investigate(request())


def test_forged_numeric_claim_is_rejected():
    science = Science()
    science.claim = Claim()
    science.claim.metric_value = 99.0
    with pytest.raises(ValueError, match='not supported'):
        AgentOrchestrator(science).investigate(request())


def test_story_has_five_scenes_and_stales_on_aoi_change():
    agent = AgentOrchestrator(Science())
    result = agent.investigate(request())
    story = agent.build_story(StoryRequest(session_id='test-session', evidence_id=result['evidence_ids'][0]))
    assert len(story['frames']) == 5
    agent.investigate(request(aoi_bbox_wgs84=[100.1, 0, 101, 1]))
    assert agent.get_story(story['story_id'])['status'] == 'stale'


def test_story_rejects_unknown_or_inactive_evidence():
    agent = AgentOrchestrator(Science())
    agent.investigate(request())
    with pytest.raises(ValueError):
        agent.build_story(StoryRequest(session_id='test-session', evidence_id='E-FAKE'))


def test_invalid_aoi_rejected():
    with pytest.raises(ValueError):
        request(aoi_bbox_wgs84=[102, 0, 101, 1])
