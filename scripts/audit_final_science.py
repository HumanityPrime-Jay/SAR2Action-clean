"""Deterministic claim and story audit for the delivered science cache."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.schemas.api import DeterministicClaim
from backend.app.schemas.evidence import EvidenceRecord
from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest, StoryRequest
from backend.app.services.claim_validator import validate_science_claim
from backend.app.services.science_service import ScienceService
from scripts.validate_science_cache import audit as audit_cache

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cache = ROOT / 'data/cache'
    evidence = {item['evidence_id']: EvidenceRecord.model_validate(item) for item in
                json.loads((cache / 'evidence_store.json').read_text(encoding='utf-8'))['records']}
    analyses = json.loads((cache / 'analysis_store.json').read_text(encoding='utf-8'))['analyses']
    fingerprints = json.loads((cache / 'fingerprint_store.json').read_text(encoding='utf-8'))['fingerprints']
    claim_results = []
    for source, collection in (('analysis', analyses), ('fingerprint', fingerprints)):
      for analysis in collection.values():
        for raw in analysis['claims']:
            item = {'claim_id': raw['claim_id'], 'evidence_id': raw['evidence_id'],
                    'metric_name': raw['metric_name'], 'source': source, 'status': 'FAIL'}
            try:
                checked = validate_science_claim(DeterministicClaim.model_validate(raw), evidence[raw['evidence_id']])
                if checked['case_id'] != analysis['case_id'] or checked['aoi_bbox_wgs84'] != analysis['aoi_bbox_wgs84']:
                    raise ValueError('case_or_aoi_mismatch')
                if re.search(r'confirmed (fire|disturbance|subsidence|recovery)|proves? (fire|disturbance|subsidence|recovery)',
                             checked['statement'], re.I):
                    raise ValueError('unsupported_causal_strength')
                item['status'] = 'PASS'
            except (ValueError, KeyError) as exc:
                item['reason'] = str(exc)
            claim_results.append(item)
    agent = AgentOrchestrator(ScienceService())
    result = agent.investigate(InvestigateRequest(case_id='case-flagship-oki-f2',
        aoi_id='AOI-OKI-04', aoi_bbox_wgs84=[105.08, -2.92, 105.24, -2.76],
        query='Explain observed HH/HV differences and their scientific limits',
        data_mode='cache', session_id='final-claim-audit'))
    story = agent.build_story(StoryRequest(session_id='final-claim-audit',
                                            evidence_id='E-FLAGSHIP-OKI-004', audience='scientific'))
    text = ' '.join([result['narrative']] + [x['narrative'] for x in story['frames']])
    fp = result['fingerprint_details']
    checks = {
        'cache_internal_integrity': audit_cache(cache)['status'] == 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID',
        'all_108_claims_valid': len(claim_results) == 108 and all(x['status'] == 'PASS' for x in claim_results),
        'median_definition_explicit': 'medians of per-pixel T1 minus T0' in result['narrative'],
        'not_difference_of_medians': all('Median of valid pixelwise' in c['statement'] for c in result['claims'] if c['metric_name'].startswith('median_delta_')),
        'distribution_available': all(fp['distribution'][pol]['p10_delta_db'] is not None and fp['distribution'][pol]['p90_delta_db'] is not None for pol in ('HH','HV')),
        'significance_unassessed': fp['significance_status'] == 'NOT_ASSESSED',
        'stable_control_absent': fp['stable_control_status'] == 'NOT_DESIGNATED',
        'no_confirmed_causal_claim': not re.search(r'confirmed (significant disturbance|peat fire|subsidence|recovery)|proves? (peat fire|subsidence|recovery)', text, re.I),
        'story_five_frames_same_evidence': len(story['frames']) == 5 and all(frame['evidence_ids'] == ['E-FLAGSHIP-OKI-004'] for frame in story['frames']),
        'provenance_pending': 'PROVENANCE PENDING' in result['data_notice'] and 'PROVENANCE PENDING' in story['data_notice'],
        'no_real_spatial_ranking': not result.get('ranked_regions'),
    }
    output = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'scope': 'cache plus trusted agent and story text',
              'source_hdf5_independently_verified': False, 'aoi_id': 'AOI-OKI-04',
              'evidence_id': 'E-FLAGSHIP-OKI-004', 'measurement_definition': 'median of valid pixelwise T1 dB minus T0 dB',
              'hh_median_delta_db': fp['hh_delta_median_db'], 'hv_median_delta_db': fp['hv_delta_median_db'],
              'valid_pixel_count_recorded': fp['valid_pixel_count'], 'checks': checks,
              'claim_results': claim_results, 'story_frames': [{'title': frame['title'], 'narrative': frame['narrative'],
                               'evidence_ids': frame['evidence_ids']} for frame in story['frames']],
              'limitations': ['No independent source HDF5 verification', 'No stable control or significance test',
                              'No source georeferenced change raster for real subregion ranking']}
    (ROOT / 'docs/FINAL_SCIENTIFIC_CLAIM_AUDIT.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"FINAL_CLAIM_AUDIT {output['status']} claims {sum(x['status']=='PASS' for x in claim_results)}/{len(claim_results)}")
    return 0 if output['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
