"""CHAMPI investigation over verified source records and real NISAR subsets."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from shapely.geometry import shape

from backend.app.schemas.investigation_v3 import InvestigationV3Request, InvestigationV3Response
from backend.app.services.gemini_provider import GeminiModelProvider
from backend.app.services.agriculture_vh_evidence import active_output, run_tool as run_vh_tool
from scripts.agriculture_vh.compare_years import EVENT_START, EVENT_END

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get('SAR2ACTION_DATA_ROOT') or (ROOT / 'data')).resolve()
CASE = DATA_ROOT / 'exports/typhoon_champi'
HYPOTHESES = {
    'harvesting': 'Harvesting may alter field radar return.',
    'field_preparation': 'Field preparation may alter roughness or cover.',
    'moisture': 'Moisture may alter radar return.',
    'storm_disturbance': 'Typhoon-related disturbance may alter vegetation or surface conditions.',
    'observation_processing': 'Different processing versions or geometry may affect comparison.',
}
TOOLS = {
    'inspect_nisar_observations': 'Read verified pre/post NISAR subset QA and acquisition metadata.',
    'inspect_official_loss_scope': 'Read the official Ministry of Agriculture regional loss record.',
    'test_cross_crid_compatibility': 'Apply deterministic NISAR processing compatibility gate.',
}
VH_TOOLS = {
    'get_field_vh_timeseries': 'Retrieve real OPERA VH observations for the selected Taixi farmland candidate.',
    'check_event_temporal_alignment': 'Check actual OPERA acquisitions before, during, and after CHAMPI.',
    'compare_seasonal_backscatter': 'Compare observed 2025 and 2026 VH signals on matched acquisition geometry.',
    'evaluate_field_hypotheses': 'Evaluate alternative causes without assigning crop-damage status.',
    'find_missing_observations': 'Identify observation and field-evidence gaps.',
}
FIELD_TOOLS = {
    'calculate_temporal_changes': 'Compute selected-field observed VH differences with warning-window timing.',
    'compare_five_fields': 'Compare five re-extracted official farmland candidates and their spatial pattern.',
}
ALL_TOOLS = {**TOOLS, **VH_TOOLS, **FIELD_TOOLS}


def validate_tool_trace(trace: list[dict]) -> None:
    """Require recorded results to follow recorded calls; forbid unregistered tools."""
    called: set[str] = set()
    for step, item in enumerate(trace, 1):
        if item.get('step') != step or not item.get('timestamp_utc'):
            raise ValueError('Tool trace has a missing or forged sequence/timestamp')
        if item.get('kind') == 'tool_call' and item.get('tool') in ALL_TOOLS:
            called.add(item['tool'])
        if item.get('kind') == 'tool_result':
            if item.get('tool') not in ALL_TOOLS or item['tool'] not in called:
                raise ValueError('Tool trace contains a result without an executed allowlisted call')
            if not item.get('source_references') or item.get('status') != 'complete':
                raise ValueError('Tool result lacks verified source references')
    if not set(TOOLS) <= called:
        raise ValueError('Required scientific tools were not executed')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(name: str) -> dict:
    path = CASE / name
    if not path.is_file():
        path = ROOT / 'data/exports/typhoon_champi' / name
    return json.loads(path.read_text(encoding='utf-8'))


def get_champi_evidence(evidence_id: str) -> dict | None:
    ledger = _load('evidence.json')
    if ledger.get('case_id') != 'CHAMPI-YUNLIN-TAIXI':
        raise ValueError('CHAMPI evidence ledger has wrong case')
    records = ledger.get('records', [])
    if len({x.get('evidence_id') for x in records}) != len(records):
        raise ValueError('CHAMPI evidence ledger has duplicate IDs')
    return next((x for x in records if x.get('evidence_id') == evidence_id), None)


def _verify_science(qa: dict, manifest: dict, inventory: dict) -> None:
    if manifest.get('status') != 'REAL_PRE_POST_SCENES_QA_PASSED_CROSS_CRID_DELTA_BLOCKED':
        raise ValueError('Real pre/post science manifest is not QA passed')
    for item in manifest['inputs'] + manifest['outputs']:
        path = DATA_ROOT / Path(item['path']).relative_to('data')
        if not path.is_file():
            raise ValueError(f'Required science asset unavailable: {item["path"]}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Science asset integrity mismatch')
    scenes = {s['scene_id']: s for s in inventory['scenes']}
    for label, observed in qa['observations'].items():
        source = scenes.get(observed['scene_id'])
        if source is None or source['acquisition_start_utc'] != observed['acquisition_start_utc']:
            raise ValueError('Science observation cannot be reconciled to CMR inventory')
        if observed['valid_pixels'] <= 0 or observed['event_relation'] != ('PRE_EVENT' if label == 'PRE' else 'POST_EVENT'):
            raise ValueError('No genuine pre/post valid NISAR pixels')


def _model_proposals(model: GeminiModelProvider, question: str, context: dict,
                     available: dict[str, str]) -> tuple[list[str], list[str]]:
    spec = {name: {'description': description, 'parameters': {
        'type': 'object', 'properties': {}, 'additionalProperties': False}}
        for name, description in available.items()}
    calls, _ = model.choose_gis_tools(question, spec, context)
    selected = [c['name'] for c in calls if c.get('error') is None and c.get('name') in available]
    if not selected:
        raise ValueError('Gemini did not select a valid investigation tool')
    hypothesis_spec = {'propose_scientific_hypotheses': {'description':
        'Select plausible hypotheses, without declaring confirmed damage or assigning probabilities.',
        'parameters': {'type': 'object', 'properties': {'hypothesis_ids': {
            'type': 'array', 'items': {'type': 'string', 'enum': list(HYPOTHESES)},
            'minItems': 1, 'maxItems': len(HYPOTHESES), 'uniqueItems': True}},
            'required': ['hypothesis_ids'], 'additionalProperties': False}}}
    proposal, _ = model.choose_gis_tools(question, hypothesis_spec, context)
    valid_proposals = [item for item in proposal if item.get('error') is None
                       and item.get('name') == 'propose_scientific_hypotheses']
    if not valid_proposals:
        raise ValueError('Gemini did not return a valid hypothesis proposal')
    ids = valid_proposals[0]['arguments']['hypothesis_ids']
    if not ids or not set(ids) <= set(HYPOTHESES):
        raise ValueError('Gemini hypothesis IDs are invalid')
    return selected, ids


class InvestigationV3Service:
    def __init__(self, model: GeminiModelProvider | None = None):
        self.model = model

    def investigate(self, request: InvestigationV3Request) -> InvestigationV3Response:
        inventory = _load('scene_inventory.json')
        qa = _load('science_qa.json')
        manifest = _load('science_manifest.json')
        loss = _load('official_loss_record.json')
        boundary = _load('boundary_provenance.json')
        aoi = next(f for f in _load('candidate_aois.geojson')['features']
                   if f['properties']['aoi_id'] == request.aoi_id)
        sentinel = json.loads((ROOT / 'docs/TW03_EVIDENCE_CATALOG.json').read_text(encoding='utf-8'))['sentinel1']
        if len(sentinel) != 2 or any(shape(s['footprint_wgs84']).covers(shape(aoi['geometry'])) is False
                                     for s in sentinel):
            raise ValueError('Supplementary Sentinel-1 footprints do not cover Taixi')
        _verify_science(qa, manifest, inventory)
        if qa['case_id'] != request.case_id or qa['aoi_id'] != request.aoi_id:
            raise ValueError('Case/AOI mismatch')
        if loss['yunlin_county_ntd'] != 157743000 or not loss['source_verified_in_page']:
            raise ValueError('Official loss record cannot be verified')
        if qa['comparability']['qa_decision'] != 'SEPARATE_OBSERVATIONS_ONLY':
            raise ValueError('Cross-CRID result must be kept separate')
        try:
            vh_base = active_output()
        except RuntimeError:
            vh_base = None
        vh_possible = vh_base is not None
        active_tools = {**TOOLS, **(VH_TOOLS if vh_possible else {}),
                        **(FIELD_TOOLS if vh_base is not None and vh_base.name != 'gee_fallback' else {})}
        trace = []

        def event(kind: str, tool: str, status: str, sources: list[str] | None = None, **detail):
            trace.append({'step': len(trace) + 1, 'timestamp_utc': _now(), 'kind': kind,
                          'tool': tool, 'status': status, 'source_references': sources or [], **detail})

        event('plan', 'bounded_champi_planner', 'complete',
              ['scene_inventory.json', 'science_qa.json', 'official_loss_record.json'],
              steps=list(active_tools), limit=len(active_tools), question=request.question)
        selected, proposed = [], []
        if request.agent_mode == 'gemini':
            model = self.model or GeminiModelProvider()
            context = {'case_id': request.case_id, 'aoi_id': request.aoi_id,
                       'available_tools': list(active_tools), 'field_id': request.field_id,
                       'pre_scene': qa['observations']['PRE']['scene_id'],
                       'post_scene': qa['observations']['POST']['scene_id'],
                       'cross_crid_delta_verified': False,
                       'official_loss_scope': 'Yunlin County, not parcel'}
            selected, proposed = _model_proposals(model, request.question, context, active_tools)
            event('tool_call', 'GeminiModelProvider.choose_gis_tools', 'complete', [],
                  selected_tools=selected, model=model.model)
            event('hypothesis', 'GeminiModelProvider.choose_gis_tools', 'complete', [],
                  proposed_ids=proposed, model=model.model)
        executed = []
        vh_results = {}
        for name in [*selected, *active_tools]:
            if name in executed:
                continue
            executed.append(name)
            event('tool_call', name, 'executed')
            if name == 'inspect_nisar_observations':
                result = {'pre_valid_pixels': qa['observations']['PRE']['valid_pixels'],
                          'post_valid_pixels': qa['observations']['POST']['valid_pixels'],
                          'evidence_ids': ['E-CHAMPI-NISAR-TAIXI-PRE', 'E-CHAMPI-NISAR-TAIXI-POST']}
                refs = ['science_qa.json', 'scene_inventory.json']
            elif name == 'inspect_official_loss_scope':
                result = {'scope': 'Yunlin County', 'loss_ntd': loss['yunlin_county_ntd'],
                          'parcel_ground_truth': False, 'evidence_ids': ['E-CHAMPI-MOA-20261106']}
                refs = [loss['source_url']]
            elif name == 'test_cross_crid_compatibility':
                result = {'crid_match': qa['comparability']['crid_match'],
                          'verified_delta_allowed': qa['comparability']['verified_typhoon_delta_allowed'],
                          'evidence_ids': ['E-CHAMPI-NISAR-TAIXI-PRE', 'E-CHAMPI-NISAR-TAIXI-POST',
                                           'E-CHAMPI-ASF-CROSS-CRID']}
                refs = [qa['comparability']['release_notes_url']]
            else:
                result = run_vh_tool(name, request.field_id)
                vh_results[name] = result
                refs = ['data/' + str((vh_base / file).relative_to(DATA_ROOT)).replace('\\', '/')
                        for file in ('agent_evidence.json', 'source_manifest.json')]
                if name in FIELD_TOOLS:
                    refs.append('data/' + str((vh_base / 'field_comparison.json').relative_to(DATA_ROOT)).replace('\\', '/'))
            event('tool_result', name, 'complete', refs, result=result)
        vh_series = vh_results.get('get_field_vh_timeseries', {})
        vh_observed = vh_series.get('status') == 'OBSERVED' and bool(vh_series.get('observations'))
        vh_rows = vh_series.get('observations', []) if vh_observed else []
        vh_compare = vh_results.get('compare_seasonal_backscatter') if vh_observed else None
        field_compare = vh_results.get('compare_five_fields') if vh_observed else None
        temporal_changes = vh_results.get('calculate_temporal_changes') if vh_observed else None
        if field_compare and field_compare.get('status') != 'OBSERVED_DESCRIPTIVE_ONLY':
            field_compare = None
        if temporal_changes and temporal_changes.get('status') != 'OBSERVED_DESCRIPTIVE_ONLY':
            temporal_changes = None
        vh_mean_definition = (json.loads((vh_base / 'vh_timeseries.json')
                                   .read_text(encoding='utf-8'))['mean_definition'] if vh_observed else None)
        vh_is_gee = vh_observed and vh_base.name == 'gee_fallback'
        ids = ['E-CHAMPI-MOA-20261106', 'E-CHAMPI-NLSC-TAIXI',
               'E-CHAMPI-NISAR-TAIXI-PRE', 'E-CHAMPI-NISAR-TAIXI-POST',
               'E-CHAMPI-ASF-CROSS-CRID', 'E-CHAMPI-S1-TAIXI-PRE', 'E-CHAMPI-S1-TAIXI-POST']
        if vh_observed:
            ids.extend(field_compare['evidence_ids'] if field_compare else
                       [row['evidence_id'] for row in vh_rows])
        for evidence_id in ids:
            event('evidence', 'register_source_evidence', 'verified', [], evidence_id=evidence_id)
        timeline = [{
            'mission': 'NISAR', 'acquisition_start_utc': obs['acquisition_start_utc'],
            'relation_to_event': obs['event_relation'], 'product_maturity': obs['product_maturity'],
            'crid': obs['crid'], 'valid_pixels': obs['valid_pixels'],
            'evidence_id': 'E-CHAMPI-NISAR-TAIXI-' + label,
        } for label, obs in qa['observations'].items()]
        for label, source in zip(('PRE', 'POST'), sentinel):
            timeline.append({'mission': 'Sentinel-1',
                             'acquisition_start_utc': source['acquisition_start_utc'],
                             'relation_to_event': label + '_EVENT',
                             'product_maturity': 'CATALOG_METADATA_ONLY', 'crid': None,
                             'valid_pixels': None, 'raster_available': False,
                             'evidence_id': 'E-CHAMPI-S1-TAIXI-' + label})
        if vh_observed:
            event_start = datetime.fromisoformat(EVENT_START)
            event_end = datetime.fromisoformat(EVENT_END)
            for row in vh_rows:
                acquisition = datetime.fromisoformat(row['acquisition_datetime'])
                relation = ('HISTORICAL_REFERENCE' if row['year'] == 2025 else
                            'PRE_EVENT' if acquisition < event_start else
                            'POST_EVENT' if acquisition > event_end else 'EVENT_WINDOW')
                timeline.append({'mission': 'Sentinel-1/GEE' if vh_is_gee else 'Sentinel-1/OPERA',
                                 'acquisition_start_utc': row['acquisition_datetime'],
                                 'relation_to_event': relation, 'product_maturity': 'EE_GRD_DB' if vh_is_gee else 'RTC-S1_V1.0',
                                 'crid': None, 'valid_pixels': row['valid_pixel_count'],
                                 'raster_available': True, 'field_id': request.field_id,
                                 'evidence_id': row['evidence_id']})
        tests = [
            {'test_id': 'genuine_post_event_observation', 'status': 'PASS',
             'result': 'October 28 NISAR acquisition follows the October 23–24 event window.',
             'evidence_ids': ['E-CHAMPI-NISAR-TAIXI-POST']},
            {'test_id': 'cross_crid_radiometric_compatibility', 'status': 'FAIL',
             'result': 'P05023 provisional and P05036 validated are not independently established as radiometrically equivalent.',
             'evidence_ids': ['E-CHAMPI-NISAR-TAIXI-PRE', 'E-CHAMPI-NISAR-TAIXI-POST', 'E-CHAMPI-ASF-CROSS-CRID']},
            {'test_id': 'official_loss_to_parcel_attribution', 'status': 'FAIL',
             'result': 'The Ministry reports county-level losses, with no parcel-level labels.',
             'evidence_ids': ['E-CHAMPI-MOA-20261106']},
        ]
        vh_changes = []
        if vh_observed:
            years = {year: sorted((r for r in vh_rows if r['year'] == year),
                                  key=lambda r: r['acquisition_datetime']) for year in (2025, 2026)}
            if not all(len(years[y]) >= 2 for y in years):
                raise ValueError('Observed VH series lacks two dates per year')
            current_pre = [r for r in years[2026] if datetime.fromisoformat(r['acquisition_datetime']) < datetime.fromisoformat(EVENT_START)]
            current_post = [r for r in years[2026] if datetime.fromisoformat(r['acquisition_datetime']) > datetime.fromisoformat(EVENT_END)]
            if not current_pre or not current_post:
                raise ValueError('Observed VH series does not bracket the event')
            pre, post = current_pre[-1], current_post[0]
            vh_changes.append({'kind': 'SENTINEL1_GEE_DESCRIPTIVE_PRE_POST' if vh_is_gee else
                                       'SENTINEL1_OPERA_DESCRIPTIVE_PRE_POST',
                               'field_id': request.field_id, 'polarization': 'VH',
                               'pre_date': pre['acquisition_datetime'], 'post_date': post['acquisition_datetime'],
                               'pre_median_db': pre['vh_median_db'], 'post_median_db': post['vh_median_db'],
                               'median_difference_db': round(post['vh_median_db'] - pre['vh_median_db'], 5),
                               'source_evidence_ids': [pre['evidence_id'], post['evidence_id']],
                               'causal_damage_status': 'UNKNOWN'})
            tests.append({'test_id': 'vh_event_bracketing', 'status': 'PASS',
                          'result': 'Real Sentinel-1 VH acquisitions bracket the event on one platform/orbit/processing convention.',
                          'evidence_ids': [pre['evidence_id'], post['evidence_id']]})
            if all(len(years[y]) >= 3 for y in years):
                peaks = {y: years[y][1]['vh_median_db'] > years[y][0]['vh_median_db']
                         and years[y][1]['vh_median_db'] > years[y][2]['vh_median_db']
                         for y in (2025, 2026)}
                tests.append({'test_id': 'vh_unique_event_signature_falsification',
                              'status': 'FAIL_UNIQUENESS_CLAIM' if all(peaks.values()) else 'INCONCLUSIVE',
                              'result': ('A mid-season VH peak followed by decline also occurs in the 2025 same-orbit series; '
                                         'this challenges uniqueness, not whether the typhoon had an effect.')
                              if all(peaks.values()) else 'The small seasonal sample cannot test uniqueness.',
                              'evidence_ids': [r['evidence_id'] for y in (2025, 2026) for r in years[y]]})
            if field_compare:
                pattern = field_compare['cross_field_pattern']
                tests.append({'test_id': 'vh_five_field_common_change', 'status': 'DESCRIPTIVE_MIXED',
                              'result': (f"{pattern['pre_to_warning_increase_count']}/5 fields increased from the "
                                         'pre-warning observation to the warning-window observation; this is '
                                         'a shared temporal signal, not proof of a common cause.'),
                              'evidence_ids': field_compare['evidence_ids']})
                tests.append({'test_id': 'vh_strict_pre_warning_change', 'status': 'NOT_TESTABLE',
                              'result': 'Only one 2026 acquisition precedes the land warning in each field.',
                              'evidence_ids': [r['evidence_id'] for r in years[2026]
                                               if datetime.fromisoformat(r['acquisition_datetime']) <
                                               datetime.fromisoformat(EVENT_START)]})
        for test in tests:
            event('test', test['test_id'], test['status'], test['evidence_ids'], result=test['result'])
        hypotheses = []
        for key, statement in HYPOTHESES.items():
            test_status = 'INCONCLUSIVE' if key == 'observation_processing' or (vh_observed and key == 'storm_disturbance') else 'NOT_TESTED'
            contradicting = ([r['evidence_id'] for r in years[2025]] if key == 'storm_disturbance' and
                             vh_observed and len(years[2025]) == 3 else [])
            hypotheses.append({'hypothesis_id': key, 'statement': statement,
                               'status': 'UNRESOLVED', 'test_status': test_status,
                               'falsification_check': (
                                   'Cross-CRID compatibility check executed; mismatch leaves processing as a plausible confound.'
                                   if key == 'observation_processing' else
                                   'A matched 2025 VH pattern was checked; a recurring peak/decline challenges uniqueness but cannot rule out storm effects.'
                                   if key == 'storm_disturbance' and vh_observed else
                                   'Crop records or independent field observations are required to test this cause.'),
                               'supporting_evidence_ids': [], 'contradicting_evidence_ids': contradicting,
                               'proposed_by_gemini': key in proposed})
            event('hypothesis', key, test_status, [], proposed_by_gemini=key in proposed)
        event('validation', 'deterministic_evidence_guard', 'complete', ids,
              confirmed_parcel_damage=False, verified_radiometric_delta=False)
        recommendation = ('Prioritize field verification in Taixi only as an administrative screening area; '
                          'obtain geolocated crop and damage observations, and reprocessed same-CRID NISAR scenes before radiometric attribution.')
        if vh_observed:
            recommendation = ('Inspect the five official farmland candidates with crop/harvest records and field survey; '
                              'use the observed Sentinel-1 VH series for prioritization only, and wait for same-CRID NISAR reprocessing before NISAR delta claims.')
        event('final_recommendation', 'evidence_to_action_planner', 'complete', ids,
              recommendation=recommendation)
        validate_tool_trace(trace)
        result = InvestigationV3Response(
            case_id=request.case_id, aoi_id=request.aoi_id, investigation_id=str(uuid4()),
            question=request.question, data_mode=('REAL_NISAR_SEPARATE_AND_GEE_VH_OBSERVED' if vh_is_gee else
                                                    'REAL_NISAR_SEPARATE_AND_OPERA_VH_OBSERVED') if vh_observed else 'REAL_PRE_POST_SEPARATE_CROSS_CRID',
            observation_timeline=timeline,
            observation_statistics={label: {'HH_gamma0_db': obs['gamma0_db']['HH'],
                                            'HV_gamma0_db': obs['gamma0_db']['HV'],
                                            'valid_pixels': obs['valid_pixels'],
                                            'valid_fraction': obs['valid_fraction_of_township_pixels']}
                                    for label, obs in qa['observations'].items()},
            vh_timeseries={'field_id': request.field_id, 'status': 'OBSERVED',
                           'mean_definition': vh_mean_definition,
                           'observations': vh_rows} if vh_observed else None,
            vh_comparison=vh_compare,
            field_comparison=field_compare,
            temporal_changes=temporal_changes,
            available_sensors=[
                {'mission': 'NISAR', 'band': 'L', 'polarizations': ['HH', 'HV'],
                 'source': 'real Harmony AOI subsets'},
                {'mission': 'Sentinel-1', 'band': 'C', 'polarizations': ['VV', 'VH'],
                 'source': ('real Earth Engine S1 GRD VH field pixels plus Copernicus catalog metadata' if vh_is_gee else
                            'real NASA OPERA RTC-S1 VH field pixels plus Copernicus catalog metadata')
                 if vh_observed else 'verified Copernicus catalog footprints only; raster unavailable'}],
            observed_changes=vh_changes, hypotheses=hypotheses, hypothesis_tests=tests, evidence_ids=ids,
            scientific_limitations=[
                'P05023 provisional and P05036 validated data have not passed cross-CRID radiometric equivalence QA.',
                'Township boundaries are administrative; the OPERA candidate polygons are official farmland boundaries, not verified rice crop labels.'
                if vh_observed else 'Township boundaries are administrative, not agricultural field polygons.',
                'County agricultural losses do not identify Taixi or individual parcel damage.',
                'Three Sentinel-1 dates per year are a bounded comparison, not a calibrated seasonal baseline.'
                if vh_observed else 'Sentinel-1 pre/post catalog metadata are available but no calibrated Taixi pixels were downloaded.',
                'The October 22 UTC OPERA observation is October 23 05:51 Taiwan, inside the land-warning window; only one 2026 acquisition precedes that warning.'
                if vh_observed else 'Event timing cannot be inferred from catalog metadata alone.',
                'OPERA noise correction is tagged, but the field-level VH noise-floor margin has not been independently quantified.'
                if field_compare else 'Field-level noise-floor margin is not available.',
                'Separate pre/post radar values cannot isolate typhoon effects from farming, moisture, or processing.'],
            missing_evidence=['Geolocated field crop/damage survey', 'Comparable same-CRID reprocessed pre-event GCOV',
                              'Verified crop and harvest records', 'Independent field control observations'],
            recommended_next_action=recommendation,
            provenance_status=('REAL_NISAR_SUBSETS_QA_PASSED; REAL_' + ('GEE' if vh_is_gee else 'OPERA') + '_VH_OBSERVED; '
                               'CROSS_CRID_NISAR_COMPARISON_BLOCKED; CROP_DAMAGE_UNKNOWN') if vh_observed else
                              'REAL_NISAR_SUBSETS_QA_PASSED; CROSS_CRID_COMPARISON_BLOCKED; REGIONAL_LOSS_ONLY',
            tool_trace=trace, qa=qa['comparability'],
            official_loss_context={'taiwan_total_ntd': loss['taiwan_total_ntd'],
                                   'yunlin_county_ntd': loss['yunlin_county_ntd'],
                                   'parcel_loss_ntd': None, 'source_url': loss['source_url'],
                                   'evidence_id': ids[0]},
            expert_report={'observed': ('Real pre/post NISAR HH/HV and 2025/2026 matched-geometry Sentinel-1 VH observations exist over Taixi.'
                                        if vh_observed else 'Real pre- and post-event NISAR HH/HV gamma0 pixels exist over Taixi.'),
                           'possible_interpretation': 'Agriculture, moisture, storm disturbance, and processing all remain possible.',
                           'unknown': 'VH change is descriptive; no confirmed crop damage, NISAR cross-CRID delta, or parcel loss can be stated.',
                           'recommended_next_evidence': recommendation})
        return result
