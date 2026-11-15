"""HTTP contract tests for PR #4 GIS and TW-05 compatibility routes."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_gis_transform_point_and_measure_real_field():
    pt = client.post(
        '/api/gis/transform-point',
        json={'x': 120.19, 'y': 23.70, 'from_crs': 'EPSG:4326', 'to_crs': 'EPSG:3826'},
    )
    assert pt.status_code == 200
    body = pt.json()
    assert 160000 < body['x'] < 175000
    assert 2620000 < body['y'] < 2630000

    fields = json.loads(Path('frontend/public/studio/fields.geojson').read_text(encoding='utf-8'))
    yl01 = next(f for f in fields['features'] if f['properties']['field_id'] == 'YL-CAND-01')
    measured = client.post(
        '/api/gis/measure',
        json={
            'case_id': 'CHAMPI-YUNLIN-TAIXI',
            'geometry': yl01['geometry'],
            'input_crs': 'EPSG:4326',
            'geometry_source': 'USER_DRAWN',
        },
    )
    assert measured.status_code == 200
    m = measured.json()
    assert m['area_m2'] == 125089.43
    assert m['area_crs'] == 'EPSG:3826'
    assert m['measurement_status'] == 'MEASURED_NOT_OFFICIAL'


def test_tw05_investigate_deterministic_and_fail_closed_gemini(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    det = client.post(
        '/api/agent/tw05/investigate',
        json={'parcel_feature_id': 74, 'question': '請檢查雷達變化', 'agent_mode': 'deterministic'},
    )
    assert det.status_code == 200
    d = det.json()
    assert d['status'] == 'completed'
    assert d['execution_mode'] == 'DETERMINISTIC_TOOL_PIPELINE'
    assert 'E-TW01-PARCEL-74' in d['evidence_ids']
    assert d['epistemic_guardrails']['confirmed_typhoon_damage'] is False

    gem = client.post(
        '/api/agent/tw05/investigate',
        json={'parcel_feature_id': 74, 'question': '請檢查雷達變化', 'agent_mode': 'gemini'},
    )
    assert gem.status_code == 200
    assert gem.json()['execution_mode'] == 'BLOCKED_NO_MODEL_CONFIGURED'


def test_tw_agro_relief_catalog_estimate_and_optical():
    cat = client.get('/api/tw-agro/relief-catalog')
    assert cat.status_code == 200
    assert cat.json()['announcement_status'] == 'ANNOUNCEMENT_NOT_VERIFIED'

    est = client.post(
        '/api/tw-agro/relief-estimate',
        json={
            'parcel_feature_id': 4183,
            'crop_item_id': 'grains_3_peanut_sweetpotato',
            'assumed_approved_area_ha': 0.453978,
            'assumed_loss_threshold': 'meets_20_percent',
        },
    )
    assert est.status_code == 200
    assert est.json()['conditional_reference_amount_twd'] == 16343

    blocked = client.post(
        '/api/tw-agro/relief-estimate',
        json={
            'parcel_feature_id': 4183,
            'crop_item_id': 'grains_3_peanut_sweetpotato',
            'assumed_approved_area_ha': 0.453978,
            'assumed_loss_threshold': 'unverified',
        },
    )
    assert blocked.status_code == 200
    assert blocked.json()['calculation_allowed'] is False

    opt = client.get('/api/tw-agro/parcels/174/optical')
    assert opt.status_code == 200
    assert opt.json()['status'] == 'DATA_NOT_AVAILABLE'
    assert opt.json()['optical_insufficient_parcel_flag'] is True
