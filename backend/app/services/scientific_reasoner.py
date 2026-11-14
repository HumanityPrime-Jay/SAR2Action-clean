"""Evidence-bound scientific interpretation of deterministic GIS results.

The model may choose tools, but cannot author measurements or turn radar
change into a confirmed physical cause. This reasoner reads registered records
from the current investigation only.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.agent_orchestrator import InvestigateRequest
    from backend.app.services.spatial_ranking import SpatialRankingService


CAUSE_QUESTION = re.compile(
    r'fire|wildfire|burn|火災|野火|燃燒|displac|subsiden|ground\s+mov|moved|位移|沉降|'
    r'recover|regrow|恢復|復原', re.I)


def assess_scientific_evidence(req: InvestigateRequest, result: dict,
                               spatial: SpatialRankingService, session: dict | None,
                               science=None) -> dict:
    """Reject stale/mismatched claims and return observed/inferred/unknown cards."""
    ids = result.get('evidence_ids') or []
    if not session or session.get('case_id') != req.case_id or session.get('bbox') != req.aoi_bbox_wgs84:
        raise ValueError('Analysis session no longer matches the selected case and AOI')
    if not ids or set(ids) != set(session.get('evidence_ids', [session['evidence_id']])):
        raise ValueError('Evidence IDs are not current for this investigation')
    observed = []
    methods = set()
    pairs = set()
    if not result.get('ranked_regions') and req.data_mode in ('live', 'cache'):
        if science is None:
            raise ValueError('Science Evidence Ledger is unavailable')
        for claim in result.get('claims') or []:
            eid = claim.get('evidence_id')
            if eid not in ids:
                raise ValueError('Scientific claim uses inactive Evidence ID')
            evidence = science.get_evidence(eid)
            if claim.get('scene_ids') != evidence.scene_ids or claim.get('algorithm_version') != evidence.algorithm_version:
                raise ValueError('Scientific evidence scene pair or version mismatch')
            if claim.get('case_id') != req.case_id or claim.get('aoi_bbox_wgs84') != req.aoi_bbox_wgs84 or claim.get('roi_id') != evidence.roi_id:
                raise ValueError('Scientific claim case or AOI mismatch')
            if claim.get('metric_value') is None or not math.isfinite(claim['metric_value']):
                raise ValueError('Scientific numeric claim is invalid')
            from backend.app.schemas.api import DeterministicClaim
            from backend.app.services.claim_validator import validate_science_claim
            validate_science_claim(DeterministicClaim.model_validate(
                {key: value for key, value in claim.items() if key not in ('epistemic_status', 'source_statement')}), evidence)
            pairs.add(tuple(evidence.scene_ids))
            methods.add(evidence.algorithm_version)
            observed.append({'status': 'OBSERVED', 'statement': claim['statement'],
                             'evidence_ids': [eid], 'value': claim['metric_value'], 'unit': claim['unit']})
        if len(methods) != 1 or len(pairs) != 1:
            raise ValueError('Science claims mix scene pairs or analysis versions')
        return _assessment(req, result, observed, methods, pairs)
    for claim in result.get('claims') or []:
        eid = claim.get('evidence_id')
        evidence = spatial.evidence.get(eid)
        if eid not in ids or not evidence:
            raise ValueError('Scientific claim lacks registered spatial evidence')
        if evidence.get('data_kind') != ('synthetic' if req.data_mode == 'fixture' else 'nisar'):
            raise ValueError('Scientific evidence data mode mismatch')
        region = next((region for region in result.get('ranked_regions', [])
                       if eid in region.get('evidence_ids', [])), None)
        if not region or region.get('scene_ids') != evidence.get('scene_ids') or region.get('polarization') != evidence.get('polarization'):
            raise ValueError('Scientific evidence scene pair or polarization mismatch')
        if region.get('bbox_wgs84') != evidence.get('bbox_wgs84'):
            raise ValueError('Scientific evidence geometry mismatch')
        bbox = region['bbox_wgs84']
        aoi = req.aoi_bbox_wgs84
        if not (aoi[0] <= bbox[0] < bbox[2] <= aoi[2] and aoi[1] <= bbox[1] < bbox[3] <= aoi[3]):
            raise ValueError('Scientific evidence lies outside the selected AOI')
        value = claim.get('metric_value')
        measured = evidence.get('measurements', {}).get('median_abs_change_db')
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value != measured or claim.get('unit') != 'dB':
            raise ValueError('Scientific numeric claim differs from deterministic Evidence Ledger')
        methods.add(evidence.get('method'))
        pairs.add(tuple(evidence.get('scene_ids', [])))
        observed.append({'status': 'OBSERVED', 'statement': claim['statement'],
                         'evidence_ids': [eid], 'value': value, 'unit': 'dB'})
    if len(methods) != 1 or len(pairs) != 1:
        raise ValueError('Evidence records mix scene pairs or analysis versions')
    return _assessment(req, result, observed, methods, pairs)


def _assessment(req, result, observed, methods, pairs):
    causal = bool(CAUSE_QUESTION.search(req.query))
    unknown = ['The physical cause of radar backscatter change is not established by these observations.']
    if req.data_mode == 'cache':
        unknown.append('The signed medians alone do not establish significant region-wide disturbance; no stable control or significance test is registered for this AOI.')
    if causal:
        unknown.append('These radar measurements alone cannot confirm wildfire, ground displacement, or ecological recovery.')
    if req.data_mode == 'fixture':
        unknown.append('The current analysis uses synthetic pixels; no NISAR observation supports a real-world conclusion.')
    limitations = list(dict.fromkeys(
        list(result.get('evidence_limitations', [])) +
        [item for region in result.get('ranked_regions', []) for item in region.get('limitations', [])]))
    next_steps = (['Acquire and validate comparable NISAR scene data and a georeferenced change raster.']
                  if req.data_mode == 'fixture' else
                  ['Compare independent optical, thermal or field evidence before assigning a cause.'])
    return {'observed': observed,
            'inferred': [{'status': 'INFERRED',
                          'statement': ('The ranked radar-change pattern' if result.get('ranked_regions')
                                        else 'The observed radar-change signal') +
                                       ' is a candidate for follow-up, not a confirmed event.',
                          'evidence_ids': result['evidence_ids'][:1]}],
            'unknown': unknown, 'next_steps': next_steps, 'limitations': limitations,
            'scene_ids': list(next(iter(pairs))), 'analysis_version': next(iter(methods)),
            'data_kind': ('synthetic' if req.data_mode == 'fixture' else
                          'nisar_cached_provenance_pending' if req.data_mode == 'cache' else 'nisar')}
