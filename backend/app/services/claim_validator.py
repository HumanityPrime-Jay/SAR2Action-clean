# Ported from SAR2Action-clean-main.zip::backend/app/services/claim_validator.py
"""Validate science-service and TW-05 observed claims against persisted Evidence ledgers."""
from __future__ import annotations

import math


def validate_science_claim(claim, evidence) -> dict:
    if (
        claim.evidence_id != evidence.evidence_id
        or claim.scene_ids != evidence.scene_ids
        or claim.valid_pixel_count != evidence.valid_pixel_count
        or claim.roi_id != evidence.roi_id
        or claim.algorithm_version != evidence.algorithm_version
    ):
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


def validate_tw05_observed_fact(fact: dict, evidence_ledger: dict[str, dict]) -> dict:
    """Ensure every TW-05 observed fact matches a registered Evidence record and exact verified value."""
    evidence_ids = fact.get('evidence_ids') or []
    if not evidence_ids:
        raise ValueError('TW-05 observed fact lacks Evidence ID citation')
    metric_name = str(fact.get('metric_name') or '').strip()
    if not metric_name:
        raise ValueError('TW-05 observed fact lacks metric_name')

    matched_expected = None
    found_metric = False
    for eid in evidence_ids:
        record = evidence_ledger.get(eid)
        if record is None:
            raise ValueError(f'TW-05 observed fact cites unregistered Evidence ID: {eid}')
        verified_metrics = record.get('verified_metrics') or {}
        if metric_name in verified_metrics:
            found_metric = True
            matched_expected = verified_metrics[metric_name]
            break

    if not found_metric:
        raise ValueError(f'TW-05 observed fact metric `{metric_name}` not registered in cited Evidence ledger')

    metric_value = fact.get('metric_value')
    if metric_value is not None:
        if not isinstance(metric_value, (int, float)) or not math.isfinite(float(metric_value)):
            raise ValueError(f'TW-05 observed fact numeric value for `{metric_name}` is non-finite')
        if matched_expected is None or not isinstance(matched_expected, (int, float)):
            raise ValueError(f'TW-05 observed fact `{metric_name}` disagrees with non-numeric ledger entry')
        if not math.isclose(float(matched_expected), float(metric_value), rel_tol=0.0, abs_tol=1e-6):
            raise ValueError(
                f'TW-05 observed fact `{metric_name}` ({metric_value}) does not match verified Evidence ({matched_expected})'
            )

    validated = dict(fact)
    validated['epistemic_status'] = 'OBSERVED'
    return validated
