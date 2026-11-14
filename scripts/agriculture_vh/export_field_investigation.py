"""Materialize a deterministic, source-linked V3 investigation for the UI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.app.schemas.investigation_v3 import InvestigationV3Request
from backend.app.services.investigation_v3 import InvestigationV3Service, CASE, ROOT
from .common import OUTPUT, now_utc, write_json


def _sync_case_evidence() -> dict:
    path = CASE / 'evidence.json'
    ledger = json.loads(path.read_text(encoding='utf-8'))
    existing = {r['evidence_id']: r for r in ledger['records']}
    observations = json.loads((OUTPUT / 'agent_evidence.json').read_text(encoding='utf-8'))
    inventory = json.loads((OUTPUT / 'scene_inventory.json').read_text(encoding='utf-8'))
    scenes = {x['granule_id']: x for x in inventory}
    for row in observations['records']:
        scene = scenes[row['source_scene_id']]
        existing[row['evidence_id']] = {
            **row, 'kind': 'REAL_OPERA_RTC_S1_VH_FIELD_OBSERVATION',
            'source_url': scene['vh_url'], 'rice_crop_verified': False,
            'crop_damage_status': 'UNKNOWN'}
    ledger['records'] = list(existing.values())
    write_json(path, ledger)
    manifest_path = CASE / 'manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        relative = str(path.relative_to(ROOT)).replace('\\', '/')
        for item in manifest.get('output_files', []):
            if item['path'] == relative:
                item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                item['size_bytes'] = path.stat().st_size
        write_json(manifest_path, manifest)
    return ledger


def run(field_id: str = 'YL-CAND-01') -> dict:
    response = InvestigationV3Service().investigate(
        InvestigationV3Request(field_id=field_id, agent_mode='deterministic'))
    ledger = _sync_case_evidence()
    indexed = {r['evidence_id']: r for r in ledger['records']}
    if not set(response.evidence_ids) <= set(indexed):
        raise ValueError('Investigation references unresolved Evidence IDs')
    trace = response.tool_trace
    executed = [x['tool'] for x in trace if x['kind'] == 'tool_result' and x['status'] == 'complete']
    tests_done = [x for x in response.hypothesis_tests if x['status'] not in ('NOT_TESTABLE', 'NOT_TESTED')]
    tests_missing = [x for x in response.hypothesis_tests if x['status'] in ('NOT_TESTABLE', 'NOT_TESTED')]
    comparison = response.field_comparison
    selected = next(f for f in comparison['fields'] if f['field_id'] == field_id)
    citations = {id: {'kind': indexed[id].get('kind'),
                      'source_url': indexed[id].get('source_url'),
                      'source_scene_id': indexed[id].get('source_scene_id', indexed[id].get('scene_id'))}
                 for id in response.evidence_ids}
    result = {'schema_version': 'taixi-field-investigation-v1',
              'generated_at_utc': now_utc(), 'agent_mode': 'deterministic',
              'status': 'OBSERVED_SCIENTIFIC_INVESTIGATION_DAMAGE_UNKNOWN',
              'selected_field': field_id, 'observed_vh_time_series': selected['observations'],
              'comparison_2025_vs_2026': selected['matched_date_pairs'],
              'pre_warning_change': selected['2026_pre_warning_change'],
              'pre_warning_status': selected['2026_pre_warning_status'],
              'pre_to_warning_window_change': selected['2026_pre_to_warning_window'],
              'pre_to_post_warning_change': selected['2026_pre_to_post_warning'],
              'five_field_comparison': comparison['fields'],
              'cross_field_pattern': comparison['cross_field_pattern'],
              'event_reference': comparison['event_reference'],
              'competing_hypotheses': response.hypotheses,
              'supporting_evidence': [citations[id] | {'evidence_id': id}
                                      for id in selected['evidence_ids']],
              'contradicting_evidence': [citations[id] | {'evidence_id': id}
                                         for h in response.hypotheses
                                         for id in h['contradicting_evidence_ids']],
              'unresolved_questions': response.missing_evidence + comparison['scientific_limits'],
              'recommended_scientific_tests': [
                  'Obtain geolocated crop type, harvest, and field damage observations.',
                  'Acquire more same-orbit pre-warning and post-warning VH observations.',
                  'Quantify the local VH noise-floor margin and incidence-angle sensitivity.',
                  'Review field-specific rainfall and waterlogging evidence.',
                  'Reprocess NISAR scenes to one comparable CRID before a radiometric difference.'],
              'executed_tool_names': executed, 'executed_scientific_tests': tests_done,
              'not_executed_or_not_testable': tests_missing,
              'tool_execution_trace': trace, 'evidence_references': citations,
              'nisar': {'pre_crid': 'P05023', 'post_crid': 'P05036',
                        'verified_cross_crid_delta': False,
                        'direct_sentinel_nisar_subtraction_allowed': False},
              'parcel_damage_status': 'UNKNOWN', 'county_loss_is_parcel_loss': False,
              'api_response': response.model_dump()}
    write_json(OUTPUT / 'field_investigation.json', result)
    return result


if __name__ == '__main__':
    report = run()
    print(json.dumps({'status': report['status'], 'selected_field': report['selected_field'],
                      'executed_tools': report['executed_tool_names'],
                      'evidence_count': len(report['evidence_references'])}, indent=2))
