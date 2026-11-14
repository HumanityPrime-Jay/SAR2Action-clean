from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.investigation import (
    HypothesisStatus, InvestigationRequest, ObservationMetadata,
)
from backend.app.services.scientific_investigator import compatible_for_direct_difference
from backend.app.services.scientific_investigator import ScientificInvestigator
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider, ScienceSourceUnavailable


BBOX = [105.08, -2.92, 105.24, -2.76]
CACHE = Path(__file__).resolve().parents[2] / 'data' / 'cache'


def request(**changes):
    data = dict(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04',
                aoi_bbox_wgs84=BBOX, question='Could this confirm a peatland wildfire?')
    data.update(changes)
    return data


def metadata(mission='NASA–ISRO NISAR'):
    return ObservationMetadata(mission=mission, sensor='L-band SAR', frequency_band='L',
                               polarization=['HH', 'HV'], product_type='NISAR_L2_GCOV',
                               radiometric_convention='gamma0', source_reference='test-scene',
                               scientific_limitations=[])


def test_cross_mission_difference_fails_closed():
    assert compatible_for_direct_difference(metadata(), metadata('CSA RADARSAT'))[0] is False
    assert compatible_for_direct_difference(metadata(), metadata())[0] is True
    assert compatible_for_direct_difference(metadata().model_copy(update={'radiometric_convention': None}), metadata())[0] is False


def test_request_rejects_invalid_aoi_and_non_cache_mode():
    with pytest.raises(ValueError):
        InvestigationRequest(**request(aoi_bbox_wgs84=[105.24, -2.92, 105.08, -2.76]))
    with pytest.raises(ValueError):
        InvestigationRequest(**request(data_mode='fixture'))


def test_missing_private_cache_does_not_fall_back_to_synthetic(tmp_path):
    investigator = ScientificInvestigator(provider=ScienceEvidenceProvider('cache', cache_dir=tmp_path))
    with pytest.raises(ScienceSourceUnavailable, match='cache is missing'):
        investigator.investigate(InvestigationRequest(**request()))


@pytest.mark.skipif(not (CACHE / 'evidence_store.json').is_file(),
                    reason='Private B-team cache unavailable; no synthetic substitution')
def test_oki04_falsification_and_read_only_graph():
    client = TestClient(app)
    response = client.post('/api/agent/scientific-investigation', json=request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['evidence_ids'] == ['E-FLAGSHIP-OKI-004']
    assert result['validation_status'] == 'INTERNALLY_CONSISTENT_SOURCE_UNVERIFIED'
    assert len(result['tool_trace']) <= 4
    assert all(item['status'] == HypothesisStatus.UNRESOLVED for item in result['hypotheses'])
    observed = ' '.join(item['statement'] for item in result['observation_summary'])
    assert '-0.2128 dB' in observed and '-0.2056 dB' in observed and '3,148,830' in observed
    assert not result['supporting_evidence'] and not result['contradicting_evidence']
    assert all(item['evidence_ids'] == result['evidence_ids'] for item in result['observation_summary'])
    graph = client.get(f"/api/agent/scientific-investigation/{result['investigation_id']}/evidence-graph")
    assert graph.status_code == 200
    assert {node['node_type'] for node in graph.json()['nodes']} == {
        'claim', 'evidence', 'analysis', 'aoi', 'scene_pair', 'observation_metadata', 'provenance'}
    assert client.get('/api/agent/scientific-investigation/nonexistent/evidence-graph').status_code == 404
    assert client.post('/api/agent/scientific-investigation',
                       json=request(aoi_id='AOI-OKI-02')).status_code == 422
    displacement = client.post('/api/agent/scientific-investigation',
                               json=request(question='Does GCOV show surface displacement?'))
    assert displacement.status_code == 200
    assert any(h['hypothesis_id'] == 'displacement' and h['status'] == 'UNRESOLVED'
               for h in displacement.json()['hypotheses'])
