"""Twelve independent scientific assertions over the locked TW-01 catalog case."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import investigation_v2 as service_module


client = TestClient(app)
TW03_AVAILABLE = all((service_module.TW03_PATH / name).is_file() for name in
                     ('TW03_statistics.json', 'TW03_evidence.json', 'TW03_manifest.json'))
TW03_REASON = 'Requires excluded real TW-03 QA artifacts; catalog-only guards remain tested'


@pytest.fixture(scope='module')
def result():
    response = client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'TW-01',
        'question': 'Did Typhoon Chambi damage farmland in Yunlin, Taiwan?'})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('scenario,check', [
    ('nisar_pre_event', lambda r: r['qa']['nisar_pre_event'] and all(
        x['relation_to_event'] == 'PRE_EVENT' for x in r['observation_timeline'] if x['mission'] == 'NISAR')),
    ('sentinel_spans_event', lambda r: r['qa']['sentinel_spans_event'] and {
        x['relation_to_event'] for x in r['observation_timeline'] if x['mission'] == 'Sentinel-1'} == {'PRE_EVENT', 'POST_EVENT'}),
    ('cross_sensor_subtraction_rejected', lambda r: r['cross_sensor_direct_subtraction_allowed'] is False),
    ('harvest_not_damage', lambda r: next(x for x in r['hypotheses'] if x['hypothesis_id'] == 'harvesting')['status'] == 'UNRESOLVED'),
    ('field_preparation_not_damage', lambda r: next(x for x in r['hypotheses'] if x['hypothesis_id'] == 'field_preparation')['status'] == 'UNRESOLVED'),
    ('moisture_not_damage', lambda r: next(x for x in r['hypotheses'] if x['hypothesis_id'] == 'moisture')['status'] == 'UNRESOLVED'),
    ('storm_not_confirmed_damage', lambda r: next(x for x in r['hypotheses'] if x['hypothesis_id'] == 'storm_disturbance')['status'] == 'UNRESOLVED'),
    ('no_db_to_crop_loss_rate', lambda r: all(not x['damage_claim_supported'] for x in r['observed_changes'])
     and any('crop-loss rate' in x for x in r['expert_report']['UNKNOWN'])),
    ('no_db_to_monetary_loss', lambda r: any('monetary loss' in x for x in r['expert_report']['UNKNOWN'])),
    ('observation_gap_not_no_damage', lambda r: any('not established' in x for x in r['expert_report']['UNKNOWN'])),
    ('evidence_ids_registered', lambda r: all(client.get('/api/agent/tw01/evidence/' + eid).status_code == 200
                                             for eid in r['evidence_ids'])),
    ('source_provenance_not_upgraded', lambda r: r['qa']['crid_validated'] is False
     and 'PROVISIONAL_CRID_NOT_VALIDATED' in r['provenance_status']),
], ids=lambda item: item if isinstance(item, str) else None)
def test_scientific_guard_scenarios(result, scenario, check):
    if scenario == 'source_provenance_not_upgraded' and not TW03_AVAILABLE:
        pytest.skip(TW03_REASON)
    assert check(result), scenario


def test_wrong_aoi_and_fake_evidence_rejected():
    assert client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'AOI-OKI-04', 'question': 'Use wrong AOI'}).status_code == 422
    assert client.get('/api/agent/tw01/evidence/E-FAKE-999').status_code == 404
    assert client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'TW-01', 'aoi_bbox_wgs84': [120.0, 23.5, 120.1, 23.6],
        'question': 'Assert caller supplied AOI coverage'}).status_code == 422


@pytest.mark.skipif(not TW03_AVAILABLE, reason=TW03_REASON)
def test_gemini_proposal_cannot_assign_damage_status(monkeypatch):
    class MockModel:
        configured = True
        def choose_gis_tools(self, question, available, context):
            assert list(available) == ['propose_scientific_hypotheses']
            assert context['raster_data_available'] is True
            assert context['tw03_pre_event_change']['valid_pixels'] == 62556
            assert context['tw03_pre_event_change']['damage_claim_supported'] is False
            return ([{'name': 'propose_scientific_hypotheses',
                      'arguments': {'hypothesis_ids': ['storm_disturbance', 'harvesting']}, 'error': None}], '')
    monkeypatch.setattr(app_module_investigation_v2(), 'model', MockModel())
    response = client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'TW-01', 'question': 'Confirm storm damage', 'agent_mode': 'gemini'})
    assert response.status_code == 200
    hypotheses = response.json()['hypotheses']
    assert len(hypotheses) == 6
    assert all(item['status'] == 'UNRESOLVED' and not item['supporting_evidence_ids'] for item in hypotheses)
    assert sum(item['proposed_by_gemini'] for item in hypotheses) == 2


def app_module_investigation_v2():
    from backend.app.main import investigation_v2
    return investigation_v2


def test_invalid_model_tool_is_not_silently_replaced(monkeypatch):
    class BadModel:
        configured = True
        def choose_gis_tools(self, question, available, context):
            return ([{'name': 'shell', 'arguments': {}, 'error': 'unauthorized_tool'}], '')
    monkeypatch.setattr(app_module_investigation_v2(), 'model', BadModel())
    response = client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'TW-01', 'question': 'Run a shell', 'agent_mode': 'gemini'})
    assert response.status_code == 422


def test_catalog_provenance_tampering_fails_closed(monkeypatch, tmp_path):
    catalog = service_module.load_catalog()
    catalog['nisar'][0]['scene_id'] = 'FAKE'
    fake = tmp_path / 'catalog.json'
    fake.write_text(__import__('json').dumps(catalog), encoding='utf-8')
    monkeypatch.setattr(service_module, 'CATALOG_PATH', fake)
    response = client.post('/api/agent/investigate-v2', json={
        'case_id': 'TW-01', 'aoi_id': 'TW-01', 'question': 'Use fake source'})
    assert response.status_code == 422


@pytest.mark.skipif(not TW03_AVAILABLE, reason=TW03_REASON)
def test_real_tw03_provisional_change_integrity(result):
    import numpy as np
    import rasterio
    from pathlib import Path

    assert result['data_mode'] == 'TW03_PROVISIONAL_OBSERVED'
    assert result['qa']['aoi_coverage'] is True
    assert result['qa']['valid_pixels'] == 62556
    assert len(result['observed_changes']) == 2
    assert {x['evidence_id'] for x in result['observed_changes']} <= set(result['evidence_ids'])
    assert all(x['type'] == 'REAL_NISAR_PRE_EVENT_CHANGE' and not x['damage_claim_supported']
               for x in result['observed_changes'])
    root = service_module.DATA_ROOT.parent
    with rasterio.open(root / 'data/processed/tw03/TW03_delta_HH_HV_db.tif') as image:
        hh = image.read(1)
        hv = image.read(2)
        assert image.crs.to_epsg() == 32651
        assert int(np.isfinite(hh).sum()) == int(np.isfinite(hv).sum()) == result['qa']['valid_pixels']
        assert np.isclose(np.nanmedian(hh), result['observed_changes'][0]['delta_db']['median'], atol=1e-5)
        assert np.isclose(np.nanmedian(hv), result['observed_changes'][1]['delta_db']['median'], atol=1e-5)
        row, column = np.argwhere(np.isfinite(hh) & np.isfinite(hv))[0]
        for band, variable in ((hh, 'HHHH'), (hv, 'HVHV')):
            with rasterio.open(root / f'data/processed/tw03/T0_{variable}.tif') as first, \
                    rasterio.open(root / f'data/processed/tw03/T1_{variable}.tif') as second:
                expected = 10 * np.log10(second.read(1)[row, column]) - 10 * np.log10(first.read(1)[row, column])
                assert np.isclose(band[row, column], expected, atol=1e-5)
