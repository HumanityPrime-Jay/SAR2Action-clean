"""Route-handler integration without local sockets (restricted Windows sandbox)."""

from backend.app.main import (agent_status, build_agent_story, compare_spatial_regions,
                              get_agent_story, investigate_with_agent, rank_spatial_regions,
                              spatial_evidence, CompareRegionsRequest)
from backend.app.services.agent_orchestrator import InvestigateRequest, StoryRequest
from backend.app.services.spatial_ranking import SpatialRequest
from fastapi import HTTPException
import pytest


def test_spatial_api_handler_flow():
    request = SpatialRequest(case_id='case-flagship-oki-f2', aoi_bbox_wgs84=[105.28, -3.28, 105.48, -3.08], mode='fixture')
    ranked = rank_spatial_regions(request)
    assert len(ranked['regions']) == 3
    first, second = ranked['regions'][:2]
    evidence = spatial_evidence(first['evidence_ids'][0])
    assert evidence['data_kind'] == 'synthetic'
    comparison = compare_spatial_regions(CompareRegionsRequest(
        first_evidence_id=first['evidence_ids'][0], second_evidence_id=second['evidence_ids'][0]))
    assert comparison['unit'] == 'dB'


def test_agent_api_handler_to_story_and_status():
    status = agent_status()
    assert status['agent']['status'] == 'offline' and status['demo_available']
    result = investigate_with_agent(InvestigateRequest(
        case_id='case-flagship-oki-f2', aoi_bbox_wgs84=[105.28, -3.28, 105.48, -3.08],
        query='top three change regions', intent='auto', data_mode='fixture', session_id='api-direct'))
    assert result['status'] == 'completed' and result['mode'] == 'fixture'
    story = build_agent_story(StoryRequest(session_id='api-direct', evidence_id=result['evidence_ids'][0]))
    assert len(story['frames']) == 5
    assert get_agent_story(story['story_id'])['status'] == 'current'


def test_live_investigation_without_manifest_returns_explicit_422(monkeypatch):
    monkeypatch.delenv('SAR2ACTION_SPATIAL_MANIFEST', raising=False)
    with pytest.raises(HTTPException) as caught:
        investigate_with_agent(InvestigateRequest(
            case_id='case-flagship-oki-f2', aoi_bbox_wgs84=[105.28, -3.28, 105.48, -3.08],
            query='Rank real NISAR changes', intent='rank', data_mode='live',
            agent_mode='deterministic', session_id='missing-live-direct'))
    assert caught.value.status_code == 422
    assert caught.value.detail['error_code'] == 'LIVE_SPATIAL_DATA_UNAVAILABLE'
    assert 'no synthetic fallback' in caught.value.detail['message']
