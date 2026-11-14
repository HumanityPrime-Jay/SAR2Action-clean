"""TW-01 causal and cross-sensor guards over verified public catalog metadata.

Catalog existence is not pixel evidence. Gemini may nominate hypotheses; only
this deterministic validator assigns scientific status and cites Evidence IDs.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from shapely.geometry import box, shape

from backend.app.schemas.investigation_v2 import (
    HypothesisAssessment, InvestigationV2Request, InvestigationV2Response,
    TimelineObservation,
)
from backend.app.services.gemini_provider import GeminiModelProvider


ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / 'docs' / 'TW03_EVIDENCE_CATALOG.json'
DATA_ROOT = Path(os.environ.get('SAR2ACTION_DATA_ROOT') or (ROOT / 'data')).resolve()
TW03_PATH = DATA_ROOT / 'processed' / 'tw03'
HYPOTHESES = {
    'normal_agriculture': 'Normal agricultural activity changed the radar response.',
    'harvesting': 'Harvesting changed crop structure.',
    'field_preparation': 'Field preparation changed roughness or cover.',
    'moisture': 'Soil or vegetation moisture changed.',
    'storm_disturbance': 'Storm-related disturbance affected the fields.',
    'observation_processing': 'Observation geometry or processing differences affected the signal.',
}


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _covers(footprint: dict | None, bbox: list[float] | None) -> bool | None:
    if footprint is None or bbox is None:
        return None
    return bool(shape(footprint).covers(box(*bbox)))


def load_catalog() -> dict:
    if not CATALOG_PATH.is_file():
        raise ValueError('TW-01 public source catalog is unavailable')
    catalog = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    if (catalog.get('aoi_id') != 'TW-01' or len(catalog.get('nisar', [])) != 2
            or len(catalog.get('sentinel1', [])) != 2
            or catalog.get('event', {}).get('evidence_id') != 'E-TW01-CWA-CHAMPI-202629'):
        raise ValueError('TW-01 public source catalog has invalid scope')
    expected = (
        'NISAR_L2_PR_GCOV_032_061_D_076_2005_DHDH_A_20261004T103752_20261004T103826_P05023_N_F_J_001',
        'NISAR_L2_PR_GCOV_033_061_D_076_2005_DHDH_A_20261016T103752_20261016T103826_P05023_N_F_J_001',
    )
    if tuple(item.get('scene_id') for item in catalog['nisar']) != expected:
        raise ValueError('TW-01 NISAR scene pair does not match the locked case')
    if any(item.get('catalog_status') not in ('EXACT_GRANULE_VERIFIED', 'EXACT_PRODUCT_VERIFIED')
           for item in catalog['nisar'] + catalog['sentinel1']):
        raise ValueError('TW-01 catalog sources are not verified')
    ids = [item['evidence_id'] for item in catalog['nisar'] + catalog['sentinel1']]
    ids.append(catalog['event']['evidence_id'])
    if len(ids) != len(set(ids)):
        raise ValueError('TW-01 duplicate Evidence ID')
    return catalog


def get_catalog_evidence(evidence_id: str) -> dict | None:
    catalog = load_catalog()
    records = catalog['nisar'] + catalog['sentinel1'] + [catalog['event']]
    tw03 = load_tw03(catalog)
    if tw03:
        records += tw03['evidence']['records']
    return next((item for item in records
                 if item['evidence_id'] == evidence_id), None)


def load_tw03(catalog: dict) -> dict | None:
    if catalog.get('tw03_change_status') != 'REAL_PROVISIONAL_SUBSET_QA_PASSED':
        return None
    stats_path = TW03_PATH / 'TW03_statistics.json'
    evidence_path = TW03_PATH / 'TW03_evidence.json'
    manifest_path = TW03_PATH / 'TW03_manifest.json'
    if not any(path.is_file() for path in (stats_path, evidence_path, manifest_path)):
        return None  # Metadata only: no private pixel QA assets in this checkout.
    if not all(path.is_file() for path in (stats_path, evidence_path, manifest_path)):
        raise ValueError('Incomplete TW-03 QA artifacts')
    stats = json.loads(stats_path.read_text(encoding='utf-8'))
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (stats.get('data_mode') != 'TW03_PROVISIONAL_OBSERVED'
            or stats.get('source_scene_ids') != [x['scene_id'] for x in catalog['nisar']]
            or stats.get('qa', {}).get('aoi_bbox_wgs84') != catalog.get('aoi_bbox_wgs84')
            or stats.get('qa', {}).get('common_valid_pixels', 0) <= 0
            or stats.get('qa', {}).get('crid_validated') is not False
            or manifest.get('status') != 'REAL_PROVISIONAL_SUBSET_QA_PASSED'
            or evidence.get('case_id') != 'TW-01'
            or [x.get('evidence_id') for x in evidence.get('records', [])] !=
            ['E-TW01-NISAR-TW03-HH', 'E-TW01-NISAR-TW03-HV']):
        raise ValueError('TW-03 QA artifacts are inconsistent with the locked case')
    for output in manifest['output_files']:
        path = DATA_ROOT / Path(output['path']).relative_to('data')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != output['sha256']:
            raise ValueError('TW-03 QA output integrity mismatch')
    return {'stats': stats, 'evidence': evidence, 'manifest': manifest}


def propose_hypotheses(question: str, catalog: dict, model: GeminiModelProvider,
                       tw03: dict | None = None) -> list[str]:
    if not model.configured:
        raise RuntimeError('Gemini hypothesis proposer is not configured')
    schema = {'type': 'object', 'properties': {
        'hypothesis_ids': {'type': 'array', 'items': {'type': 'string', 'enum': list(HYPOTHESES)},
                           'minItems': 1, 'maxItems': len(HYPOTHESES), 'uniqueItems': True}},
        'required': ['hypothesis_ids'], 'additionalProperties': False}
    context = {'case_id': 'TW-01', 'aoi_id': 'TW-01',
               'nisar_observation_dates': [x['acquisition_start_utc'] for x in catalog['nisar']],
               'sentinel1_observation_dates': [x['acquisition_start_utc'] for x in catalog['sentinel1']],
               'storm_land_warning_start': catalog['event']['land_warning_start_local'],
               'raster_data_available': tw03 is not None,
               'tw03_pre_event_change': None if tw03 is None else {
                   'valid_pixels': tw03['stats']['qa']['common_valid_pixels'],
                   'HH_median_delta_db': tw03['stats']['statistics']['HH']['delta_db']['median'],
                   'HV_median_delta_db': tw03['stats']['statistics']['HV']['delta_db']['median'],
                   'source_maturity': 'PROVISIONAL', 'crid_validated': False,
                   'damage_claim_supported': False},
               'candidate_hypotheses': list(HYPOTHESES)}
    calls, _ = model.choose_gis_tools(question, {
        'propose_scientific_hypotheses': {
            'description': 'Select plausible agricultural and observation hypotheses; do not assign scientific status.',
            'parameters': schema}}, context)
    if len(calls) != 1 or calls[0].get('name') != 'propose_scientific_hypotheses' or calls[0].get('error'):
        raise ValueError('Gemini did not return one valid allowlisted hypothesis proposal')
    proposed = calls[0].get('arguments', {}).get('hypothesis_ids', [])
    if not proposed or not set(proposed) <= set(HYPOTHESES):
        raise ValueError('Gemini hypothesis proposal contains invalid IDs')
    return proposed


class InvestigationV2Service:
    def __init__(self, model: GeminiModelProvider | None = None):
        self.model = model

    def investigate(self, request: InvestigationV2Request) -> InvestigationV2Response:
        catalog = load_catalog()
        tw03 = load_tw03(catalog)
        catalog_bbox = catalog.get('aoi_bbox_wgs84')
        if request.aoi_bbox_wgs84 is not None and (
                catalog.get('aoi_status') not in ('USER_ATTESTED_ORIGINAL', 'ORIGINAL_TW01_VERIFIED')
                or request.aoi_bbox_wgs84 != catalog_bbox):
            raise ValueError('Caller AOI bbox does not match the recorded original TW-01 geometry')
        trace = [{'tool': 'load_verified_public_catalog', 'status': 'complete'}]
        if tw03:
            trace.append({'tool': 'verify_tw03_provisional_subsets', 'status': 'complete',
                          'valid_pixels': tw03['stats']['qa']['common_valid_pixels']})
        event = catalog['event']
        event_start = _time(event['land_warning_start_local'])
        event_end = _time(event['land_warning_end_local'])
        timeline: list[TimelineObservation] = []
        all_sources = [('NISAR', item) for item in catalog['nisar']]
        all_sources += [('Sentinel-1', item) for item in catalog['sentinel1']]
        for mission, item in all_sources:
            acquisition = _time(item['acquisition_start_utc'])
            relation = ('PRE_EVENT' if acquisition < event_start else
                        'POST_EVENT' if acquisition > event_end else 'UNKNOWN')
            timeline.append(TimelineObservation(
                mission=mission, acquisition_start_utc=item['acquisition_start_utc'],
                relation_to_event=relation, evidence_id=item['evidence_id'],
                catalog_verified=True, raster_available=item['raster_status'] != 'NOT_DOWNLOADED',
                tw01_coverage_verified=_covers(item.get('footprint_wgs84'), catalog_bbox)
                if catalog.get('aoi_status') in ('USER_ATTESTED_ORIGINAL', 'ORIGINAL_TW01_VERIFIED') else None))
        trace.append({'tool': 'validate_observation_timeline', 'status': 'complete'})
        nisar_pre_event = all(t.relation_to_event == 'PRE_EVENT' for t in timeline if t.mission == 'NISAR')
        sentinel_spans_event = any(t.relation_to_event == 'PRE_EVENT' for t in timeline if t.mission == 'Sentinel-1') and any(
            t.relation_to_event == 'POST_EVENT' for t in timeline if t.mission == 'Sentinel-1')
        nisar_pol = {p for item in catalog['nisar'] for p in item['polarizations']}
        sentinel_pol = {p for item in catalog['sentinel1'] for p in item['polarizations']}
        if nisar_pol != {'HH', 'HV'} or sentinel_pol != {'VV', 'VH'}:
            raise ValueError('Unexpected NISAR or Sentinel-1 polarization metadata')
        if len({(x['orbit_direction'], x['track'], x['frame']) for x in catalog['nisar']}) != 1:
            raise ValueError('NISAR catalog pair orbit/track/frame mismatch')
        if len({(x['orbit_direction'], x['relative_orbit']) for x in catalog['sentinel1']}) != 1:
            raise ValueError('Sentinel-1 catalog pair orbit mismatch')
        trace.append({'tool': 'validate_sensor_compatibility', 'status': 'complete',
                      'direct_cross_sensor_subtraction': 'rejected'})
        if request.agent_mode == 'gemini':
            proposed = propose_hypotheses(request.question, catalog, self.model or GeminiModelProvider(), tw03)
            trace.append({'tool': 'gemini_propose_hypotheses', 'status': 'complete',
                          'proposed_ids': proposed})
        else:
            proposed = []
            trace.append({'tool': 'required_hypothesis_set', 'status': 'complete',
                          'model_calls': 0})
        hypotheses = [HypothesisAssessment(
            hypothesis_id=key, statement=statement, status='UNRESOLVED',
            supporting_evidence_ids=[], contradicting_evidence_ids=[],
            reason='Catalog metadata and an official storm report do not identify field-level physical cause or damage.',
            proposed_by_gemini=key in proposed)
            for key, statement in HYPOTHESES.items()]
        trace.append({'tool': 'deterministic_evidence_validator', 'status': 'complete',
                      'confirmed_damage': False})
        coverage = [item.tw01_coverage_verified for item in timeline]
        coverage_qa = None if any(x is None for x in coverage) else all(coverage)
        missing = ['Independent source document for the user-attested TW-01 AOI' if catalog.get('aoi_status') == 'USER_ATTESTED_ORIGINAL' else
                   'Original TW-01 5 × 5 km AOI geometry' if catalog.get('aoi_status') != 'ORIGINAL_TW01_VERIFIED' else
                   'Verified TW-01 coverage for every source' if coverage_qa is not True else None,
                   None if tw03 else 'TW-03 NISAR source pixels, mask and number-of-looks QA',
                   'Calibrated Sentinel-1 VV/VH pixel observations and co-registration',
                   'Field survey, crop type and management/harvest records',
                   'Local storm exposure and loss records for TW-01']
        missing = [item for item in missing if item]
        next_action = ('Provide the original TW-01 AOI geometry for exact footprint checks.'
                       if catalog_bbox is None else
                       'Obtain the bounded NISAR Harmony subset and validate mask, looks and aligned gamma0 pixels.'
                       if not tw03 else
                       'Acquire calibrated post-event Sentinel-1 pixels and field/harvest records before assessing damage.')
        evidence_ids = [item['evidence_id'] for _, item in all_sources] + [event['evidence_id']]
        if tw03:
            evidence_ids += [item['evidence_id'] for item in tw03['evidence']['records']]
        digest = hashlib.sha256(json.dumps([request.case_id, request.aoi_id, request.aoi_bbox_wgs84,
                                            request.question, catalog['checked_at_utc']], sort_keys=True).encode()).hexdigest()[:20]
        report = {
            'OBSERVED': [f"NASA CMR confirms NISAR observations on 2026-10-04 and 2026-10-16 [{catalog['nisar'][0]['evidence_id']}, {catalog['nisar'][1]['evidence_id']}].",
                         f"Copernicus catalog confirms regional Sentinel-1 observations on 2026-10-14 and 2026-10-26 [{catalog['sentinel1'][0]['evidence_id']}, {catalog['sentinel1'][1]['evidence_id']}].",
                         f"Taiwan CWA records Typhoon CHAMPI (薔琵), with a land warning beginning 2026-10-22 [{event['evidence_id']}]."],
            'POSSIBLE_INTERPRETATION': ['Agricultural practice, moisture, storm disturbance and processing differences remain competing explanations.'],
            'UNKNOWN': ['Whether Typhoon CHAMPI damaged farmland inside TW-01 is not established.',
                        'No crop-loss rate, monetary loss or causal attribution can be derived from catalog metadata.'],
            'RECOMMENDED_NEXT_EVIDENCE': [next_action],
        }
        if tw03:
            report['OBSERVED'].append(
                f"A real provisional NISAR Harmony subset yields pre-event HH and HV change on {tw03['stats']['qa']['common_valid_pixels']} common valid TW-01 pixels [E-TW01-NISAR-TW03-HH, E-TW01-NISAR-TW03-HV].")
        observed_changes = tw03['evidence']['records'] if tw03 else []
        qa = {
            'aoi_coverage': coverage_qa, 'acquisition_time': True,
            'nisar_orbit_track_frame_match': True, 'nisar_hh_hv_listed': True,
            'sentinel_vv_vh_listed': True, 'product_maturity': 'PROVISIONAL',
            'crid_validated': False, 'crs': None, 'grid_alignment': None,
            'mask_semantics': None, 'number_of_looks': None, 'valid_pixels': None,
            'gamma0_power_qa': None, 'nan_nodata_qa': None,
            'nisar_pre_event': nisar_pre_event, 'sentinel_spans_event': sentinel_spans_event}
        if tw03:
            source_qa = tw03['stats']['qa']
            qa.update(crs=source_qa['crs'], grid_alignment=source_qa['grid_alignment'],
                      mask_semantics=source_qa['mask_semantics'],
                      number_of_looks=source_qa['number_of_looks'],
                      valid_pixels=source_qa['common_valid_pixels'],
                      gamma0_power_qa=source_qa['gamma0_power_qa'],
                      nan_nodata_qa=source_qa['nan_nodata_counts_within_aoi'])
        return InvestigationV2Response(
            case_id='TW-01', aoi_id='TW-01', investigation_id='investigation-tw01-' + digest,
            question=request.question,
            data_mode='TW03_PROVISIONAL_OBSERVED' if tw03 else 'CATALOG_ONLY',
            observation_timeline=timeline,
            available_sensors=[
                {'mission': 'NISAR', 'band': 'L', 'polarizations': ['HH', 'HV'],
                 'source_status': 'REAL_PROVISIONAL_HARMONY_SUBSET_QA_PASSED' if tw03 else 'CATALOG_VERIFIED_RASTER_UNAVAILABLE'},
                {'mission': 'Sentinel-1', 'band': 'C', 'polarizations': ['VV', 'VH'], 'source_status': 'CATALOG_VERIFIED_RASTER_UNAVAILABLE'}],
            observed_changes=observed_changes, hypotheses=hypotheses, evidence_ids=evidence_ids,
            scientific_limitations=[
                'NISAR 10/04 and 10/16 observations precede the official CHAMPI land-warning period and cannot prove later damage.',
                'Sentinel-1 10/14 to 10/26 spans the event in time but catalog metadata alone cannot prove field damage.',
                'NISAR L-band HH/HV and Sentinel-1 C-band VV/VH are not directly subtractable or interchangeable.',
                'P05023 is a filename CRID, not a validated radiometric calibration.',
                'The TW-01 AOI was supplied by the user; an independent source document has not been recovered.',
                'No crop-loss percentage or post-event NISAR change has been verified for TW-01.'],
            missing_evidence=missing, recommended_next_action=next_action,
            provenance_status=tw03['evidence']['provenance_status'] if tw03 else
            'PUBLIC_CATALOG_VERIFIED; TW03_SOURCE_PIXELS_UNAVAILABLE',
            tool_trace=trace, qa=qa,
            cross_sensor_direct_subtraction_allowed=False, expert_report=report)
