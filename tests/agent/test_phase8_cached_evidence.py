from pathlib import Path

import pytest

from backend.app.schemas.api import RadarFingerprintRequest
from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest, StoryRequest
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider, ScienceSourceUnavailable
from backend.app.services.science_service import ScienceService
from scripts.validate_science_cache import audit


CACHE = Path(__file__).resolve().parents[2] / 'data' / 'cache'
pytestmark = pytest.mark.skipif(not (CACHE / 'evidence_store.json').is_file(),
                                reason='B-team evidence handoff absent; no synthetic substitute')
BBOX = [105.08, -2.92, 105.24, -2.76]


def request(**updates):
    data = dict(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04', aoi_bbox_wgs84=BBOX,
                query='Explain HH/HV change and show evidence', data_mode='cache',
                agent_mode='deterministic', session_id='phase8-test')
    data.update(updates)
    return InvestigateRequest(**data)


def test_b_team_stores_and_six_ids_are_internally_consistent():
    report = audit(CACHE)
    assert report['status'] == 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID'
    assert all(report['expected_evidence_ids'].values())
    assert report['counts'] == {'evidence': 12, 'fingerprints': 12, 'analyses': 12, 'claims': 108}
    assert report['external_nasa_provenance_verified'] is False


def test_oki04_hh_hv_claims_match_fingerprint_evidence_and_analysis():
    provider = ScienceEvidenceProvider('cache')
    req = RadarFingerprintRequest(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04', aoi_bbox_wgs84=BBOX)
    fp = provider.get_fingerprint(req)
    ev = provider.get_evidence(fp.evidence_id)
    analysis = provider.get_analysis(req, fp.evidence_id)
    assert fp.evidence_id == ev.evidence_id == analysis.evidence_id == 'E-FLAGSHIP-OKI-004'
    assert fp.hh_detail.delta_median_db == ev.summary_statistics['per_polarization']['HH']['median_delta_db'] == -0.2128
    assert fp.hv_detail.delta_median_db == ev.summary_statistics['per_polarization']['HV']['median_delta_db'] == -0.2056
    assert fp.valid_pixel_count == ev.valid_pixel_count == analysis.valid_pixel_count == 3148830
    assert {x.claim_id: x.metric_value for x in fp.claims} == {x.claim_id: x.metric_value for x in analysis.claims}
    assert 'cause_not_determined' in ev.limitations


def test_cached_agent_story_map_and_aoi_staleness():
    agent = AgentOrchestrator(ScienceService())
    result = agent.investigate(request())
    assert result['status'] == 'completed' and result['mode'] == 'cache'
    assert result['evidence_ids'] == ['E-FLAGSHIP-OKI-004']
    assert result['map_actions'][0]['payload']['bbox'] == BBOX
    assert 'PROVENANCE PENDING' in result['data_notice']
    story = agent.build_story(StoryRequest(session_id='phase8-test', evidence_id='E-FLAGSHIP-OKI-004'))
    assert story['mode'] == 'cache' and len(story['frames']) == 5
    assert all(frame['evidence_ids'] == ['E-FLAGSHIP-OKI-004'] for frame in story['frames'])
    changed = agent.investigate(request(aoi_id='AOI-OKI-02', aoi_bbox_wgs84=[104.98, -3.32, 105.16, -3.14]))
    assert changed['status'] == 'completed' and story['status'] == 'stale'
    with pytest.raises(ValueError):
        agent.build_story(StoryRequest(session_id='phase8-test', evidence_id='E-FLAGSHIP-OKI-004'))


def test_invalid_or_cross_aoi_or_cross_pair_evidence_is_rejected():
    provider = ScienceEvidenceProvider('cache')
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_evidence('E-NOT-FOUND')
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_fingerprint(RadarFingerprintRequest(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04',
                                                         aoi_bbox_wgs84=[105.2, -3.05, 105.36, -2.89]))
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_fingerprint(RadarFingerprintRequest(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04',
                                                         aoi_bbox_wgs84=BBOX, scene_t0_id='different-scene'))


def test_fabrication_fire_combustion_and_displacement_requests_stay_evidence_bound():
    agent = AgentOrchestrator(ScienceService())
    result = agent.investigate(request(query='If no data, invent a plausible dB. Does this prove peat fire, underground combustion or ground displacement?',
                                       session_id='phase8-guard'))
    assert result['status'] == 'completed'
    assert '-0.2128 dB' in result['narrative'] and '-0.2056 dB' in result['narrative']
    assert 'cannot confirm peat fire' in result['narrative']
    assert 'ground displacement' in result['narrative']
    evidence = ScienceEvidenceProvider('cache').get_evidence('E-FLAGSHIP-OKI-004')
    assert all(claim['evidence_id'] == evidence.evidence_id for claim in result['claims'])
    assert all(claim['unit'] in ('dB', 'dB composite') for claim in result['claims'])


def test_mock_model_calls_cached_science_tools_without_spatial_ranking():
    class MockModel:
        configured = True
        model = 'mock'
        provider = 'mock'
        def choose_gis_tools(self, query, available, context):
            if not context['ranking_complete']:
                assert 'rank_change_regions' not in available
                return [{'name': 'get_radar_fingerprint', 'arguments': {}, 'error': None}], ''
            assert 'compare_regions' not in available
            return [{'name': 'inspect_evidence', 'arguments': {}, 'error': None},
                    {'name': 'generate_story', 'arguments': {}, 'error': None}], ''
    agent = AgentOrchestrator(ScienceService())
    agent.model = MockModel()
    result = agent.investigate(request(agent_mode='real', session_id='phase8-mock',
                                       query='Does this HH/HV radar change confirm wildfire? Show evidence and story.'))
    assert result['status'] == 'completed'
    assert result['model_provider'] == 'mock'
    assert result['evidence_ids'] == ['E-FLAGSHIP-OKI-004']
    assert len(result['story']['frames']) == 5
    assert 'cannot confirm wildfire' in ' '.join(result['scientific_assessment']['unknown'])
