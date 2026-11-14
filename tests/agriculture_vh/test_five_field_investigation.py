"""Focused scientific checks against existing real OPERA assets."""
from __future__ import annotations

import json
import pytest

from backend.app.schemas.investigation_v3 import InvestigationV3Request
from backend.app.services.investigation_v3 import InvestigationV3Service, get_champi_evidence, validate_tool_trace
from scripts.agriculture_vh.analyze_five_fields import (
    CSV_PATH, FIELDS_PATH, _csv_rows, build_comparison, verify_rasters,
)
from scripts.agriculture_vh.common import OUTPUT, RASTER_DIR


def _report():
    return json.loads((OUTPUT / 'field_comparison.json').read_text(encoding='utf-8'))


@pytest.mark.skipif(not (RASTER_DIR / 'download_manifest.json').is_file(), reason='Requires excluded OPERA source COGs via SAR2ACTION_DATA_ROOT')
def test_all_30_csv_observations_reextract_from_source_cogs():
    rows = _csv_rows()
    fields = json.loads(FIELDS_PATH.read_text(encoding='utf-8'))['features']
    qa = verify_rasters(rows, fields)
    assert qa['reextracted_field_scene_count'] == 30
    assert qa['raster_scene_count'] == 6
    assert all(x['noise_correction_applied_tag'] == 'True' for x in qa['source_scene_qa'])
    assert all(x['local_noise_floor_margin_db'] is None for x in qa['source_scene_qa'])


def test_five_field_differences_are_from_csv_and_warning_times_are_local():
    import hashlib
    rows = _csv_rows()
    features = json.loads(FIELDS_PATH.read_text(encoding='utf-8'))['features']
    result = build_comparison(rows, features, hashlib.sha256(CSV_PATH.read_bytes()).hexdigest())
    assert result['fields'] == _report()['fields']
    assert result['cross_field_pattern']['pre_to_warning_increase_count'] == 4
    assert result['cross_field_pattern']['pre_to_post_increase_count'] == 2
    first = result['fields'][0]
    assert first['2026_pre_warning_change'] is None
    assert first['2026_pre_warning_status'] == 'ONE_OBSERVATION_ONLY'
    middle = first['observations']['2026'][1]
    assert middle['acquisition_utc'].startswith('2026-10-22T21:51:56')
    assert middle['acquisition_taiwan'].startswith('2026-10-23T05:51:56')
    assert middle['warning_relation'] == 'WARNING_WINDOW'
    assert first['2026_pre_to_warning_window']['median_difference_db'] == round(
        first['observations']['2026'][1]['vh_median_db'] -
        first['observations']['2026'][0]['vh_median_db'], 5)


def test_adjacent_fields_show_shared_signal_without_damage_claim():
    result = _report()
    fields = {f['field_id']: f for f in result['fields']}
    assert fields['YL-CAND-03']['distance_to_other_fields_m']['YL-CAND-04'] < 200
    assert fields['YL-CAND-03']['2026_pre_to_warning_window']['direction'] == 'INCREASE'
    assert fields['YL-CAND-04']['2026_pre_to_warning_window']['direction'] == 'INCREASE'
    assert fields['YL-CAND-05']['2026_pre_to_warning_window']['direction'] == 'DECREASE'
    assert result['cross_field_pattern']['shared_response_is_causal_evidence'] is False


@pytest.mark.skipif(not (RASTER_DIR / 'download_manifest.json').is_file(), reason='Requires excluded NISAR/OPERA source assets via SAR2ACTION_DATA_ROOT')
def test_v3_executes_five_field_tools_and_resolves_all_evidence():
    response = InvestigationV3Service().investigate(InvestigationV3Request())
    validate_tool_trace(response.tool_trace)
    executed = {x['tool'] for x in response.tool_trace if x['kind'] == 'tool_result'}
    assert {'calculate_temporal_changes', 'compare_five_fields', 'test_cross_crid_compatibility'} <= executed
    assert len(response.field_comparison['fields']) == 5
    assert response.temporal_changes['2026_pre_warning_change'] is None
    assert all(get_champi_evidence(id) is not None for id in response.evidence_ids)
    assert response.official_loss_context['parcel_loss_ntd'] is None
    assert response.qa['verified_typhoon_delta_allowed'] is False
    assert all(h['status'] == 'UNRESOLVED' for h in response.hypotheses)
