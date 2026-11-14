import os
import json
import hashlib
from types import SimpleNamespace as NS

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest, StoryRequest
from backend.app.services.model_provider import ModelProvider
from backend.app.services.spatial_ranking import SpatialDataUnavailable, SpatialRankingService, SpatialRequest


def fixture_request(**changes):
    data = {'case_id': 'fixture-case', 'aoi_bbox_wgs84': [100.0, 0.0, 100.2, 0.2],
            'mode': 'fixture', 'polarization': 'HV'}
    data.update(changes)
    return SpatialRequest(**data)


def test_fixture_returns_three_contiguous_regions_with_provenance():
    service = SpatialRankingService()
    result = service.run(fixture_request())
    assert result['mode'] == 'fixture' and len(result['regions']) == 3
    assert 'NOT NASA OBSERVATIONS' in result['data_notice']
    for region in result['regions']:
        assert region['crs'] == 'EPSG:4326'
        assert region['pixel_count'] >= 6
        assert region['area_km2_approx'] > 0
        assert region['geometry']['type'] == 'Polygon'
        assert region['quality_status'] == 'SIMULATED'
        assert 0 < region['valid_pixel_percentage'] <= 100
        evidence = service.evidence[region['evidence_ids'][0]]
        assert evidence['measurements']['median_abs_change_db'] == region['median_abs_change_db']
        assert evidence['data_kind'] == 'synthetic'
    assert len({region['region_id'] for region in result['regions']}) == 3


def test_valid_coverage_gate_rejects_sparse_region():
    service = SpatialRankingService()
    request = fixture_request(min_valid_fraction=0.9)
    analysis = service.analyze_spatial_changes(request)
    analysis['valid'][::2, ::2] = False
    ranked = service.rank_change_regions(analysis, request)
    assert all(region['valid_pixel_percentage'] >= 90 for region in ranked['regions'])


def test_single_extreme_pixel_is_not_ranked():
    service = SpatialRankingService()
    result = service.run(fixture_request(threshold_db=20.0))
    assert result['regions'] == []


def test_minimum_area_and_no_valid_regions():
    service = SpatialRankingService()
    assert not service.run(fixture_request(min_area_km2=1000))['regions']
    assert not service.run(fixture_request(threshold_db=29))['regions']


def test_ranking_is_deterministic_and_evidence_changes_with_measurement():
    service = SpatialRankingService()
    request = fixture_request()
    first = service.run(request)
    second = service.run(request)
    assert first['regions'] == second['regions']
    analysis = service.analyze_spatial_changes(request)
    analysis['delta'] *= 1.1
    changed = service.rank_change_regions(analysis, request)
    assert first['regions'][0]['evidence_ids'] != changed['regions'][0]['evidence_ids']


def test_live_mode_never_falls_back_to_fixture(monkeypatch):
    monkeypatch.delenv('SAR2ACTION_SPATIAL_MANIFEST', raising=False)
    with pytest.raises(SpatialDataUnavailable, match='no synthetic fallback'):
        SpatialRankingService().run(fixture_request(mode='live'))


def test_live_bad_manifest_fails_with_explicit_data_error(tmp_path, monkeypatch):
    path = tmp_path/'invalid-manifest.json'
    path.write_text('{invalid', encoding='utf-8')
    monkeypatch.setenv('SAR2ACTION_SPATIAL_MANIFEST', str(path))
    with pytest.raises(SpatialDataUnavailable, match='unreadable JSON'):
        SpatialRankingService().run(fixture_request(mode='live'))


def test_live_manifest_contract_with_stubbed_parent_evidence(tmp_path, monkeypatch):
    transform = from_bounds(100, 0, 100.2, 0.2, 20, 20)
    delta = np.zeros((20, 20), dtype='float32')
    delta[3:10, 4:11] = 3.0
    valid = np.ones((20, 20), dtype='uint8')
    for name, array in [('delta.tif', delta), ('valid.tif', valid)]:
        with rasterio.open(tmp_path/name, 'w', driver='GTiff', height=20, width=20, count=1,
                           dtype=array.dtype, crs='EPSG:4326', transform=transform,
                           nodata=-9999 if name == 'delta.tif' else 0) as output:
            output.write(array, 1)
    manifest = {'schema_version': '1', 'data_kind': 'nisar', 'case_id': 'verified-case',
                'polarization': 'HV', 'scene_ids': ['T0', 'T1'],
                'observation_times': ['2026-09-01T00:00:00Z', '2026-09-13T00:00:00Z'],
                'parent_evidence_id': 'E-PARENT', 'change_geotiff': 'delta.tif',
                'valid_mask_geotiff': 'valid.tif',
                'method': 'TEST dB difference v1', 'scene_versions': ['001', '001'],
                'pixel_resolution_deg': [0.01, 0.01], 'source_backscatter_unit': 'linear_power',
                'change_unit': 'dB', 'conversion_formula': '10*log10(P)',
                'change_sha256': hashlib.sha256((tmp_path/'delta.tif').read_bytes()).hexdigest(),
                'valid_mask_sha256': hashlib.sha256((tmp_path/'valid.tif').read_bytes()).hexdigest()}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setenv('SAR2ACTION_SPATIAL_MANIFEST', str(path))
    parent = NS(scene_ids=['T0', 'T1'], polarizations=['HV'], quality_status='COMPARABLE',
                valid_pixel_count=400, processing_metadata={
                    't0_acquisition_utc': '2026-09-01T00:00:00Z',
                    't1_acquisition_utc': '2026-09-13T00:00:00Z'}, limitations=['cause_not_determined'])
    science = NS(get_evidence=lambda _: parent,
                 validate_pair=lambda _: NS(result=NS(compatible=True)),
                 get_case=lambda _: NS(default_t0_scene_id='T0', default_t1_scene_id='T1'))
    service = SpatialRankingService(science)
    request = SpatialRequest(case_id='verified-case', aoi_bbox_wgs84=[100, 0, 100.2, 0.2], mode='live')
    ranked = service.run(request)
    assert ranked['mode'] == 'live' and ranked['regions'][0]['pixel_count'] == 49
    assert ranked['regions'][0]['evidence_ids'][0].startswith('NISAR-SP-')
    assert ranked['regions'][0]['median_signed_change_db'] == 3.0
    assert ranked['regions'][0]['median_abs_change_db'] == 3.0
    assert ranked['regions'][0]['bbox_wgs84'] == pytest.approx([100.04, 0.10, 100.11, 0.17])
    assert 60 < ranked['regions'][0]['area_km2_approx'] < 62
    assert service.evidence[ranked['regions'][0]['evidence_ids'][0]]['change_sha256'] == manifest['change_sha256']
    class TestOnlyModel:
        configured = True
        model = 'mock-live-contract'
        provider = 'openai_compatible'
        def choose_gis_tools(self, query, available, context):
            if not context['ranking_complete']:
                return [{'name': 'rank_change_regions', 'arguments': {}, 'error': None}], ''
            if 'inspect_evidence' in available:
                return [{'name': 'inspect_evidence', 'arguments': {}, 'error': None}], ''
            return [], ''
    agent = AgentOrchestrator(science)
    agent.model = TestOnlyModel()
    investigation = agent.investigate(InvestigateRequest(
        case_id='verified-case', aoi_bbox_wgs84=[100, 0, 100.2, 0.2],
        query='Rank and inspect this test raster', session_id='live-contract-test',
        data_mode='live', agent_mode='real'))
    assert investigation['status'] == 'completed'
    assert investigation['scientific_assessment']['data_kind'] == 'nisar'
    assert investigation['map_actions'][0]['type'] == 'map.focus_bbox'
    assert agent.spatial.evidence[investigation['evidence_ids'][0]]['change_sha256'] == manifest['change_sha256']
    story = agent.build_story(StoryRequest(session_id='live-contract-test',
                                          evidence_id=investigation['evidence_ids'][0]))
    assert len(story['frames']) == 5
    assert all(investigation['evidence_ids'][0] in frame['evidence_ids'] for frame in story['frames'])
    # Changing an unrelated source pixel still changes the provenance-bound
    # Evidence ID, even when the ranked component's measurements are identical.
    delta[0, 0] = 1.0
    with rasterio.open(tmp_path/'delta.tif', 'r+') as output:
        output.write(delta, 1)
    manifest['change_sha256'] = hashlib.sha256((tmp_path/'delta.tif').read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest), encoding='utf-8')
    changed_source = service.run(request)
    assert changed_source['regions'][0]['evidence_ids'][0] != ranked['regions'][0]['evidence_ids'][0]
    # A nonzero mask NoData sentinel must never become a valid source pixel.
    valid[3, 4] = 255
    with rasterio.open(tmp_path/'valid.tif', 'w', driver='GTiff', height=20, width=20, count=1,
                       dtype='uint8', crs='EPSG:4326', transform=transform, nodata=255) as output:
        output.write(valid, 1)
    manifest['valid_mask_sha256'] = hashlib.sha256((tmp_path/'valid.tif').read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest), encoding='utf-8')
    masked = service.run(request)
    assert masked['regions'][0]['pixel_count'] == 48
    manifest['observation_times'][0] = '2026-09-02T00:00:00Z'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(SpatialDataUnavailable, match='timestamps'):
        service.run(request)
    manifest['observation_times'][0] = '2026-09-01T00:00:00Z'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    service.science = NS(get_evidence=lambda _: parent,
                         validate_pair=lambda _: NS(result=NS(compatible=False)))
    with pytest.raises(SpatialDataUnavailable, match='incompatible'):
        service.run(request)


def test_compare_and_focus_require_registered_evidence():
    service = SpatialRankingService()
    regions = service.run(fixture_request())['regions']
    assert service.focus_change_region(regions[0])['type'] == 'map.focus_bbox'
    difference = service.compare_change_regions(regions[0]['evidence_ids'][0], regions[1]['evidence_ids'][0])
    assert difference['unit'] == 'dB'
    with pytest.raises(SpatialDataUnavailable):
        service.compare_change_regions('SYN-UNKNOWN', regions[1]['evidence_ids'][0])
    other_aoi = service.run(fixture_request(aoi_bbox_wgs84=[100, 0, 100.25, 0.2]))['regions']
    with pytest.raises(SpatialDataUnavailable, match='not comparable'):
        service.compare_change_regions(regions[0]['evidence_ids'][0], other_aoi[1]['evidence_ids'][0])


def test_agent_rank_and_stale_story_without_real_nisar():
    agent = AgentOrchestrator(object())
    request = InvestigateRequest(case_id='fixture-case', aoi_bbox_wgs84=[100, 0, 100.2, 0.2],
                                 query='找出變化最大的三個地方', intent='rank', data_mode='fixture', session_id='spatial-test')
    result = agent.investigate(request)
    assert result['status'] == 'completed' and len(result['ranked_regions']) == 3
    assert result['map_actions'][0]['payload']['crs'] == 'EPSG:4326'
    story = agent.build_story(StoryRequest(session_id='spatial-test', evidence_id=result['evidence_ids'][1],
                                           locale='zh-TW', audience='scientific'))
    assert len(story['frames']) == 5 and story['mode'] == 'fixture'
    assert story['frames'][0]['map_state']['bbox'] == result['ranked_regions'][1]['bbox_wgs84']
    agent.investigate(request.model_copy(update={'aoi_bbox_wgs84': [100, 0, 100.3, 0.2]}))
    assert agent.get_story(story['story_id'])['status'] == 'stale'


def test_story_stales_when_spatial_evidence_disappears():
    agent = AgentOrchestrator(object())
    request = InvestigateRequest(case_id='fixture-case', aoi_bbox_wgs84=[100, 0, 100.2, 0.2],
                                 query='top regions', intent='rank', data_mode='fixture', session_id='missing-evidence')
    result = agent.investigate(request)
    eid = result['evidence_ids'][0]
    story = agent.build_story(StoryRequest(session_id='missing-evidence', evidence_id=eid))
    del agent.spatial.evidence[eid]
    assert agent.get_story(story['story_id'])['status'] == 'stale'


def test_model_health_probes_tool_call_and_classifier_remains_bounded(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8642/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'test-model')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'openai_compatible')
    seen = []
    def handle(request):
        seen.append(request)
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': []})
        body = __import__('json').loads(request.content)
        if body['tool_choice'] == 'none':
            assert 'tools' not in body
            return httpx.Response(200, json={'choices': [{'message': {'content': 'rank'}}]})
        assert [tool['function']['name'] for tool in body['tools']] == ['rank_change_regions']
        args = {'case_id': 'status-probe', 'aoi_bbox_wgs84': [100.0, 0.0, 100.1, 0.1],
                'polarization': 'HV', 'data_mode': 'fixture'}
        return httpx.Response(200, json={'choices': [{'message': {'tool_calls': [
            {'function': {'name': 'rank_change_regions', 'arguments': json.dumps(args)}}]}}]})
    provider = ModelProvider(transport=httpx.MockTransport(handle))
    assert provider.status()['status'] == 'online'
    assert provider.classify_intent('Find change')[0] == 'rank'
    assert len(seen) == 3


def test_model_fallback_on_failure(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8642/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'test-model')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'openai_compatible')
    def fail(_):
        return httpx.Response(503)
    provider = ModelProvider(transport=httpx.MockTransport(fail))
    assert provider.status()['status'] == 'offline'
    assert provider.classify_intent('top three regions') == ('rank', 'deterministic_fallback')


def test_model_tool_call_requires_schema_and_exact_trusted_context(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8642/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'test-model')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'openai_compatible')
    bbox = [100.0, 0.0, 100.2, 0.2]
    seen = []
    def valid(request):
        body = json.loads(request.content)
        seen.append(body)
        args = {'case_id': 'fixture-case', 'aoi_bbox_wgs84': bbox,
                'polarization': 'HV', 'data_mode': 'fixture'}
        return httpx.Response(200, json={'choices': [{'message': {'tool_calls': [
            {'function': {'name': 'rank_change_regions', 'arguments': json.dumps(args)}}]}}]})
    provider = ModelProvider(transport=httpx.MockTransport(valid))
    assert provider.propose_rank_tool('rank regions', 'fixture-case', bbox, 'HV', 'fixture')
    assert [tool['function']['name'] for tool in seen[0]['tools']] == ['rank_change_regions']
    def forged(_):
        args = {'case_id': 'other-case', 'aoi_bbox_wgs84': bbox,
                'polarization': 'HV', 'data_mode': 'fixture', 'shell': 'del data'}
        return httpx.Response(200, json={'choices': [{'message': {'tool_calls': [
            {'function': {'name': 'rank_change_regions', 'arguments': json.dumps(args)}}]}}]})
    provider.transport = httpx.MockTransport(forged)
    assert not provider.propose_rank_tool('rank regions', 'fixture-case', bbox, 'HV', 'fixture')


def test_orchestrator_routes_accepted_model_tool_to_local_science():
    agent = AgentOrchestrator(object())
    class Model:
        configured = True
        def classify_intent(self, query):
            return 'rank', 'model'
        def propose_rank_tool(self, query, case_id, bbox, polarization, data_mode):
            assert case_id == 'fixture-case' and bbox == [100, 0, 100.2, 0.2]
            assert polarization == 'HV' and data_mode == 'fixture'
            return True
    agent.model = Model()
    result = agent.investigate(InvestigateRequest(case_id='fixture-case',
        aoi_bbox_wgs84=[100, 0, 100.2, 0.2], query='rank regions',
        intent='auto', data_mode='fixture', session_id='model-tool-test'))
    assert result['intent_source'] == 'model_tool_call'
    assert result['ranked_regions'][0]['evidence_ids'][0] in agent.spatial.evidence


def test_hermes_requires_verified_restricted_profile(monkeypatch):
    monkeypatch.setenv('SAR2ACTION_MODEL_URL', 'http://127.0.0.1:8642/v1/chat/completions')
    monkeypatch.setenv('SAR2ACTION_MODEL_NAME', 'hermes-agent')
    monkeypatch.setenv('SAR2ACTION_MODEL_PROVIDER', 'hermes')
    monkeypatch.delenv('SAR2ACTION_HERMES_SAFE_PROFILE_VERIFIED', raising=False)
    provider = ModelProvider()
    assert provider.status()['status'] == 'offline'
    assert provider.classify_intent('rank these regions')[1] == 'deterministic_fallback'
