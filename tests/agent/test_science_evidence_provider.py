import json

import httpx
import pytest

from backend.app.schemas.api import RadarFingerprintRequest
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider, ScienceSourceUnavailable


def test_missing_cache_is_blocked_and_synthetic_stays_isolated(tmp_path):
    provider = ScienceEvidenceProvider('cache', cache_dir=tmp_path)
    assert provider.status()['status'] == 'blocked'
    assert len(provider.status()['missing']) == 3
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_evidence('E-FLAGSHIP-OKI-004')
    with pytest.raises(ScienceSourceUnavailable):
        ScienceEvidenceProvider('synthetic').get_evidence('E-FLAGSHIP-OKI-004')


def test_cache_read_only_and_rejects_unknown_id(tmp_path):
    path = tmp_path / 'evidence_store.json'
    path.write_text(json.dumps({'records': []}), encoding='utf-8')
    provider = ScienceEvidenceProvider('cache', cache_dir=tmp_path)
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_evidence('E-FLAGSHIP-OKI-004')
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_evidence('../secret')
    assert path.read_text(encoding='utf-8') == '{"records": []}'


def test_science_api_contract_and_loopback_guard():
    paths = []
    def handler(request):
        paths.append((request.method, request.url.path))
        if request.url.path == '/api/cases':
            return httpx.Response(200, json={'cases': []})
        return httpx.Response(404)
    provider = ScienceEvidenceProvider('science_api', base_url='http://127.0.0.1:8001',
                                       transport=httpx.MockTransport(handler))
    assert provider.get_cases().cases == []
    assert provider.status()['status'] == 'unverified'
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_fingerprint(RadarFingerprintRequest(case_id='case-a', aoi_bbox_wgs84=[100, 0, 101, 1]))
    with pytest.raises(ScienceSourceUnavailable):
        provider.get_evidence('E-001')
    assert ('POST', '/api/radar-fingerprint') in paths
    assert ('GET', '/api/evidence/E-001') in paths
    with pytest.raises(ValueError):
        ScienceEvidenceProvider('science_api', base_url='http://other-host:8000')
