"""Validate a science-service claim against its persisted EvidenceRecord."""
from __future__ import annotations

import math


def validate_science_claim(claim, evidence) -> dict:
    if (claim.evidence_id != evidence.evidence_id or claim.scene_ids != evidence.scene_ids
            or claim.valid_pixel_count != evidence.valid_pixel_count
            or claim.roi_id != evidence.roi_id or claim.algorithm_version != evidence.algorithm_version):
        raise ValueError('Claim provenance validation failed')
    if claim.unit not in ('dB', 'dB composite') or not math.isfinite(claim.metric_value):
        raise ValueError('Claim unit or value validation failed')
    if claim.metric_name == 'median_combined_radar_change_db':
        expected = evidence.combined_change_db.stats.median if evidence.combined_change_db else None
        if claim.unit != 'dB composite':
            raise ValueError('Combined change unit mismatch')
    else:
        pol = claim.polarization.value if hasattr(claim.polarization, 'value') else claim.polarization
        data = evidence.summary_statistics.get('per_polarization', {}).get(pol, {})
        metric = f'median_delta_{pol.lower()}_db' if pol else None
        magnitude = f'median_abs_change_{pol.lower()}_db' if pol else None
        if claim.metric_name == metric:
            expected = data.get('median_delta_db')
        elif claim.metric_name == magnitude:
            expected = data.get('median_abs_change_db')
        else:
            raise ValueError('Unsupported claim metric')
        if claim.unit != 'dB':
            raise ValueError('Polarization metric unit mismatch')
    if expected is None or not math.isclose(float(expected), claim.metric_value, rel_tol=0, abs_tol=1e-6):
        raise ValueError('Claim measurement not supported by evidence')
    result = claim.model_dump(mode='json')
    result['epistemic_status'] = 'OBSERVED'
    return result
