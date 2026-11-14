"""Read-only, fail-closed audit of the B-team three-file science cache handoff."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.schemas.api import AnalyzeChangeResponse, RadarFingerprintResponse
from backend.app.schemas.evidence import EvidenceRecord
from backend.app.services.claim_validator import validate_science_claim


EXPECTED_IDS = (
    'E-FLAGSHIP-OKI-001', 'E-FLAGSHIP-OKI-002', 'E-FLAGSHIP-OKI-003',
    'E-FLAGSHIP-OKI-004', 'E-PHASE2A-ENG-001', 'E-PHASE2A-ENG-002',
)
NAMES = ('evidence_store.json', 'fingerprint_store.json', 'analysis_store.json')


def audit(cache_dir: Path) -> dict:
    report = {'cache_dir': str(cache_dir.resolve()), 'status': 'BLOCKED',
              'source_label': 'UNVERIFIED NISAR-DERIVED CACHE',
              'files': {}, 'errors': [], 'expected_evidence_ids': {key: False for key in EXPECTED_IDS},
              'counts': {'evidence': 0, 'fingerprints': 0, 'analyses': 0, 'claims': 0},
              'external_nasa_provenance_verified': False}
    report['source_limitations'] = ['Full GCOV source HDF5 and source hashes are not established by this three-file audit.']
    raw = {}
    for name in NAMES:
        path = cache_dir / name
        if not path.is_file():
            report['files'][name] = {'status': 'MISSING'}
            report['errors'].append(name + ': missing')
            continue
        try:
            content = path.read_bytes()
            raw[name] = json.loads(content)
            if not isinstance(raw[name], dict):
                raise ValueError('root_not_object')
            report['files'][name] = {'status': 'READABLE', 'bytes': len(content),
                                     'sha256': hashlib.sha256(content).hexdigest()}
        except (OSError, ValueError):
            report['files'][name] = {'status': 'INVALID_JSON'}
            report['errors'].append(name + ': invalid JSON object')
    if len(raw) != len(NAMES):
        return report

    evidence = {}
    records = raw['evidence_store.json'].get('records')
    if not isinstance(records, list):
        report['errors'].append('evidence_store.json: records must be an array')
        return report
    for index, item in enumerate(records):
        try:
            record = EvidenceRecord.model_validate(item)
            if record.evidence_id in evidence:
                raise ValueError('duplicate_id')
            summary = record.summary_statistics
            metadata = record.processing_metadata if isinstance(record.processing_metadata, dict) else record.processing_metadata.model_dump()
            if summary.get('valid_pixel_count') != record.valid_pixel_count:
                raise ValueError('valid_pixel_mismatch')
            mask = summary.get('mask_diagnostics', {})
            if mask.get('common_valid_all_channels_pixels') != record.valid_pixel_count:
                raise ValueError('mask_count_mismatch')
            spacing = metadata.get('pixel_spacing_m')
            if spacing and len(spacing) == 2 and summary.get('valid_area_m2') is not None:
                expected_area = record.valid_pixel_count * abs(spacing[0] * spacing[1])
                if not math.isclose(summary['valid_area_m2'], expected_area, rel_tol=0, abs_tol=1):
                    raise ValueError('area_pixel_mismatch')
            if not metadata.get('t0_acquisition_utc') or not metadata.get('t1_acquisition_utc'):
                raise ValueError('observation_date_missing')
            if not record.algorithm_version or 'cause_not_determined' not in record.limitations:
                raise ValueError('method_or_limitation_missing')
            for pol in record.polarizations:
                name = pol.value
                stats = summary.get('per_polarization', {}).get(name, {})
                if name in record.delta_db and not math.isclose(record.delta_db[pol].median,
                                                                 stats.get('median_delta_db', float('nan')),
                                                                 rel_tol=0, abs_tol=1e-6):
                    raise ValueError('polarization_delta_mismatch')
            evidence[record.evidence_id] = record
        except (ValueError, TypeError):
            report['errors'].append(f'evidence record {index}: schema or duplicate ID invalid')
    report['counts']['evidence'] = len(evidence)
    for key in EXPECTED_IDS:
        report['expected_evidence_ids'][key] = key in evidence

    fingerprints = raw['fingerprint_store.json'].get('fingerprints')
    if not isinstance(fingerprints, dict):
        report['errors'].append('fingerprint_store.json: fingerprints must be an object')
        fingerprints = {}
    parsed_fingerprints = {}
    for key, item in fingerprints.items():
        try:
            fp = RadarFingerprintResponse.model_validate(item)
            ev = evidence[fp.evidence_id]
            if (fp.evidence_record.evidence_id != ev.evidence_id or fp.roi_id != ev.roi_id
                    or fp.fingerprint.pair_compatibility.scene_ids != ev.scene_ids
                    or fp.fingerprint.evidence_id != ev.evidence_id
                    or fp.valid_pixel_count != ev.valid_pixel_count):
                raise ValueError('provenance_mismatch')
            metadata = ev.processing_metadata if isinstance(ev.processing_metadata, dict) else ev.processing_metadata.model_dump()
            if fp.t0_acquisition_utc != metadata['t0_acquisition_utc'] or fp.t1_acquisition_utc != metadata['t1_acquisition_utc']:
                raise ValueError('observation_date_mismatch')
            stats = ev.summary_statistics.get('per_polarization', {})
            for pol, detail in (('HH', fp.hh_detail), ('HV', fp.hv_detail)):
                expected = stats.get(pol, {}).get('median_delta_db')
                if detail.delta_median_db != expected:
                    raise ValueError('fingerprint_delta_mismatch')
            for claim in fp.claims:
                validate_science_claim(claim, ev)
            parsed_fingerprints[fp.evidence_id] = fp
            report['counts']['fingerprints'] += 1
            report['counts']['claims'] += len(fp.claims)
        except (ValueError, TypeError, KeyError):
            report['errors'].append(f'fingerprint {key}: schema, source or claim mismatch')

    analyses = raw['analysis_store.json'].get('analyses')
    if not isinstance(analyses, dict):
        report['errors'].append('analysis_store.json: analyses must be an object')
        analyses = {}
    for key, item in analyses.items():
        try:
            analysis = AnalyzeChangeResponse.model_validate(item)
            ev = evidence[analysis.evidence_id]
            if (analysis.evidence_record.evidence_id != ev.evidence_id
                    or analysis.roi_id != ev.roi_id or
                    [analysis.scene_t0_id, analysis.scene_t1_id] != ev.scene_ids
                    or analysis.valid_pixel_count != ev.valid_pixel_count):
                raise ValueError('provenance_mismatch')
            fp = parsed_fingerprints.get(analysis.evidence_id)
            if (fp is None or fp.case_id != analysis.case_id or fp.aoi_bbox_wgs84 != analysis.aoi_bbox_wgs84
                    or fp.t0_acquisition_utc != analysis.t0_acquisition_utc
                    or fp.t1_acquisition_utc != analysis.t1_acquisition_utc):
                raise ValueError('analysis_fingerprint_scope_mismatch')
            fp_claims = {c.claim_id: (c.metric_name, c.metric_value, c.unit) for c in fp.claims}
            an_claims = {c.claim_id: (c.metric_name, c.metric_value, c.unit) for c in analysis.claims}
            if fp_claims != an_claims:
                raise ValueError('analysis_fingerprint_claim_mismatch')
            for claim in analysis.claims:
                validate_science_claim(claim, ev)
            report['counts']['analyses'] += 1
            report['counts']['claims'] += len(analysis.claims)
        except (ValueError, TypeError, KeyError):
            report['errors'].append(f'analysis {key}: schema, source or claim mismatch')
    if not all(report['expected_evidence_ids'].values()):
        report['errors'].append('One or more guide-listed Evidence IDs are absent')
    if not fingerprints or not analyses:
        report['errors'].append('Fingerprint and analysis stores must be nonempty')
    focus = evidence.get('E-FLAGSHIP-OKI-004')
    if focus:
        summary = focus.summary_statistics
        meta = focus.processing_metadata if isinstance(focus.processing_metadata, dict) else focus.processing_metadata.model_dump()
        manifest_path = cache_dir.parent / 'scenes' / 'scene_manifest.json'
        try:
            catalog = json.loads(manifest_path.read_text(encoding='utf-8')).get('scenes', [])
            catalog_matches = {scene: any(scene in json.dumps(item) for item in catalog)
                               for scene in focus.scene_ids}
        except (OSError, ValueError):
            catalog_matches = {scene: False for scene in focus.scene_ids}
        raw_dir = cache_dir.parent / 'raw' / 'scenes'
        report['aoi_oki_04'] = {
            'evidence_id': focus.evidence_id, 'roi_id': focus.roi_id,
            'scene_ids': focus.scene_ids,
            'scene_ids_in_catalog': catalog_matches,
            'full_gcov_hdf5_present': {scene: (raw_dir / (scene + '.h5')).is_file()
                                       for scene in focus.scene_ids},
            'source_hashes_in_evidence': any('sha256' in key.lower() or 'source_hash' in key.lower()
                                             for key in list(focus.model_dump()) + list(meta)),
            'observation_times_utc': [meta.get('t0_acquisition_utc'), meta.get('t1_acquisition_utc')],
            'valid_pixel_count_recorded': focus.valid_pixel_count,
            'mask_rule_recorded': summary.get('mask_rule'),
            'common_valid_all_channels_pixels_recorded': summary.get('mask_diagnostics', {}).get('common_valid_all_channels_pixels'),
            'pixel_spacing_m_recorded': meta.get('pixel_spacing_m'),
            'valid_area_m2_recorded': summary.get('valid_area_m2'),
            'hh_median_delta_db': summary.get('per_polarization', {}).get('HH', {}).get('median_delta_db'),
            'hv_median_delta_db': summary.get('per_polarization', {}).get('HV', {}).get('median_delta_db'),
            'quality_status': focus.quality_status.value, 'method': focus.algorithm_version,
            'limitations': focus.limitations,
            'independent_raw_pixel_recalculation': 'NOT_RUN_SOURCE_HDF5_ABSENT',
        }
    if not report['errors']:
        report['status'] = 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID'
    return report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', type=Path, default=root / 'data' / 'cache')
    parser.add_argument('--output', type=Path, default=root / 'docs' / 'phase7_science_data_validation.json')
    args = parser.parse_args()
    result = audit(args.cache_dir)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(result['status'], 'errors=' + str(len(result['errors'])))


if __name__ == '__main__':
    main()
