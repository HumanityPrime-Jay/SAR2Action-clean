"""Scientific gates for the real Taixi CHAMPI case."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.app.schemas.investigation_v3 import InvestigationV3Request, InvestigationV3Response
from backend.app.services.investigation_v3 import InvestigationV3Service, validate_tool_trace

from backend.app.services.investigation_v3 import DATA_ROOT

RAW_AVAILABLE = (DATA_ROOT / 'exports/typhoon_champi/PRE_HHHH.tif').is_file() and (DATA_ROOT / 'raw/opera_yunlin_vh/download_manifest.json').is_file()
SKIP_RAW = pytest.mark.skipif(not RAW_AVAILABLE, reason='Requires excluded real NISAR/OPERA source assets via SAR2ACTION_DATA_ROOT')


@SKIP_RAW
def test_real_post_event_and_cross_crid_are_kept_separate():
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    nisar = [x for x in result.observation_timeline if x['mission'] == 'NISAR']
    assert [x['relation_to_event'] for x in nisar] == ['PRE_EVENT', 'POST_EVENT']
    assert datetime.fromisoformat(nisar[1]['acquisition_start_utc'].replace('Z', '+00:00')) > datetime.fromisoformat('2026-10-24T23:59:59+08:00')
    assert [x['crid'] for x in nisar] == ['P05023', 'P05036']
    assert all(x['valid_pixels'] > 0 for x in nisar)
    assert result.qa['verified_typhoon_delta_allowed'] is False
    assert all(x['kind'] == 'SENTINEL1_OPERA_DESCRIPTIVE_PRE_POST'
               and x['causal_damage_status'] == 'UNKNOWN' for x in result.observed_changes)


@SKIP_RAW
def test_loss_scope_and_hypotheses_do_not_claim_parcel_damage():
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    assert result.official_loss_context['yunlin_county_ntd'] == 157743000
    assert result.official_loss_context['parcel_loss_ntd'] is None
    assert all(h['status'] == 'UNRESOLVED' for h in result.hypotheses)
    assert all(h['test_status'] in ('NOT_TESTED', 'INCONCLUSIVE') for h in result.hypotheses)
    assert {x['test_id']: x['status'] for x in result.hypothesis_tests}['official_loss_to_parcel_attribution'] == 'FAIL'


@SKIP_RAW
def test_sentinel_metadata_is_not_misrepresented_as_pixels():
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    s1 = [x for x in result.observation_timeline if x['mission'] == 'Sentinel-1']
    assert len(s1) == 2 and all(x['raster_available'] is False and x['valid_pixels'] is None for x in s1)
    assert [x['relation_to_event'] for x in s1] == ['PRE_EVENT', 'POST_EVENT']


@SKIP_RAW
def test_real_vh_series_keeps_dates_units_and_evidence():
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    rows = result.vh_timeseries['observations']
    assert len(rows) == 6
    assert {r['year'] for r in rows} == {2025, 2026}
    assert {r['platform'] for r in rows} == {'Sentinel-1C'}
    assert {str(r['relative_orbit']) for r in rows} == {'105'}
    assert len({r['burst_id'] for r in rows}) == 1
    assert all(r['valid_pixel_count'] >= 8 and r['valid_coverage_ratio'] >= 0.8 for r in rows)
    assert all(-50 < r['vh_median_db'] < 1 and r['evidence_id'] in result.evidence_ids for r in rows)
    assert {x['relation_to_event'] for x in result.observation_timeline
            if x['mission'] == 'Sentinel-1/OPERA'} == {'HISTORICAL_REFERENCE', 'PRE_EVENT', 'EVENT_WINDOW', 'POST_EVENT'}
    assert next(x for x in result.hypothesis_tests
                if x['test_id'] == 'vh_unique_event_signature_falsification')['status'] == 'FAIL_UNIQUENESS_CLAIM'


@SKIP_RAW
def test_wrong_aoi_and_missing_evidence_links_are_rejected():
    with pytest.raises(ValidationError):
        InvestigationV3Request(aoi_id='TW-01')
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    broken = result.model_dump()
    broken['observation_timeline'][0]['evidence_id'] = 'E-FAKE'
    with pytest.raises(ValidationError):
        InvestigationV3Response.model_validate(broken)
    broken = result.model_dump()
    broken['observed_changes'][0]['source_evidence_ids'] = ['E-FAKE']
    with pytest.raises(ValidationError):
        InvestigationV3Response.model_validate(broken)


@SKIP_RAW
def test_fabricated_tool_result_is_rejected():
    result = InvestigationV3Service().investigate(InvestigationV3Request())
    trace = [dict(x) for x in result.tool_trace]
    trace.insert(1, {'step': 2, 'timestamp_utc': '2026-11-14T00:00:00+00:00',
                     'kind': 'tool_result', 'tool': 'invented_tool', 'status': 'complete',
                     'source_references': ['fake']})
    for index, item in enumerate(trace, 1):
        item['step'] = index
    with pytest.raises(ValueError):
        validate_tool_trace(trace)


class FakeModel:
    model = 'fake-model'

    def choose_gis_tools(self, question, available, context):
        name = next(iter(available))
        if name == 'propose_scientific_hypotheses':
            return ([{'name': name, 'arguments': {'hypothesis_ids': ['storm_disturbance', 'observation_processing']}, 'error': None}], '')
        return ([{'name': 'inspect_nisar_observations', 'arguments': {}, 'error': None}], '')


@SKIP_RAW
def test_model_tool_selection_is_executed_but_does_not_confirm_damage():
    result = InvestigationV3Service(FakeModel()).investigate(InvestigationV3Request(agent_mode='gemini'))
    assert any(x['kind'] == 'tool_call' and x['tool'] == 'inspect_nisar_observations' and x['status'] == 'executed'
               for x in result.tool_trace)
    assert any(x['hypothesis_id'] == 'storm_disturbance' and x['proposed_by_gemini'] and x['status'] == 'UNRESOLVED'
               for x in result.hypotheses)


@SKIP_RAW
def test_api_serves_case_and_registered_evidence():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client:
        response = client.post('/api/agent/investigate-v3', json={'agent_mode': 'deterministic'})
        assert response.status_code == 200
        report = response.json()
        assert report['case_id'] == 'CHAMPI-YUNLIN-TAIXI'
        assert len(report['field_comparison']['fields']) == 5
        assert report['temporal_changes']['2026_pre_warning_status'] == 'ONE_OBSERVATION_ONLY'
        assert report['official_loss_context']['parcel_loss_ntd'] is None
        evidence = client.get('/api/agent/champi/evidence/E-CHAMPI-NISAR-TAIXI-POST')
        assert evidence.status_code == 200
        assert evidence.json()['valid_pixels'] == report['observation_statistics']['POST']['valid_pixels']
        vh_id = report['vh_timeseries']['observations'][0]['evidence_id']
        vh_evidence = client.get('/api/agent/champi/evidence/' + vh_id)
        assert vh_evidence.status_code == 200
        assert vh_evidence.json()['source_scene_id'] == report['vh_timeseries']['observations'][0]['source_scene_id']
        comparison = client.post('/api/agent/agriculture-vh/tool',
                                 json={'tool': 'compare_five_fields', 'field_id': 'YL-CAND-01'})
        assert comparison.status_code == 200
        assert comparison.json()['cross_field_pattern']['pre_to_warning_increase_count'] == 4
        other_evidence_id = report['field_comparison']['fields'][-1]['evidence_ids'][-1]
        assert client.get('/api/agent/champi/evidence/' + other_evidence_id).status_code == 200


def test_missing_science_assets_fails_closed(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.services import investigation_v3 as v3_mod

    monkeypatch.setattr(v3_mod, 'DATA_ROOT', tmp_path)
    monkeypatch.setattr(v3_mod, 'CASE', tmp_path / 'exports/typhoon_champi')
    with pytest.raises(ValueError, match='Required science asset unavailable'):
        InvestigationV3Service().investigate(InvestigationV3Request())
    with TestClient(app) as client:
        response = client.post('/api/agent/investigate-v3', json={'agent_mode': 'deterministic'})
        assert response.status_code == 422
        assert 'Required science asset unavailable' in response.json()['detail']
