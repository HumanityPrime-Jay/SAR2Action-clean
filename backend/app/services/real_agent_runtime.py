"""Bounded real-model planner with an allowlisted local GIS tool executor.

The model chooses functions. Trusted application context supplies case/AOI and
registered evidence IDs; the model never computes measurements or map geometry.
"""
from __future__ import annotations

import re
import os
import threading
import time
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException

from backend.app.services.spatial_ranking import SpatialDataUnavailable

if TYPE_CHECKING:
    from backend.app.services.agent_orchestrator import AgentOrchestrator, InvestigateRequest


EMPTY = {'type': 'object', 'properties': {}, 'additionalProperties': False}
EVIDENCE = {'type': 'object', 'properties': {'evidence_id': {'type': 'string', 'maxLength': 150}},
            'additionalProperties': False}
COMPARE = EMPTY  # The executor binds the first two registered Evidence IDs.
STORY = {'type': 'object', 'properties': {
    'evidence_id': {'type': 'string', 'maxLength': 150},
    'locale': {'type': 'string', 'enum': ['en', 'zh-TW']},
    'audience': {'type': 'string', 'enum': ['public', 'scientific']}},
    'additionalProperties': False}
CONTEXT = {'type': 'object', 'properties': {
    'case_id': {'type': 'string', 'maxLength': 120},
    'aoi_bbox_wgs84': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 4, 'maxItems': 4}},
    'additionalProperties': False}

FIRST_TOOLS = {
    'rank_change_regions': {'description': 'Find the largest contiguous radar change regions in the current AOI.', 'parameters': CONTEXT},
    'analyze_aoi': {'description': 'Analyze radar change in the currently selected AOI.', 'parameters': CONTEXT},
    'get_radar_fingerprint': {'description': 'Explain the measured Radar Fingerprint for the current AOI.', 'parameters': CONTEXT},
    'search_scene': {'description': 'List available scene metadata for the selected case.', 'parameters': CONTEXT},
    'validate_scene_pair': {'description': 'Check whether the selected NISAR scene pair is comparable.', 'parameters': CONTEXT},
}
NEXT_TOOLS = {
    'compare_regions': {'description': 'Compare the first two ranked regions. Supply no arguments; the executor binds their registered Evidence IDs.', 'parameters': COMPARE},
    'inspect_evidence': {'description': 'Inspect a registered Evidence ID and its source and method.', 'parameters': EVIDENCE},
    'generate_story': {'description': 'Generate a five-scene evidence story for a registered region.', 'parameters': STORY},
    'control_map': {'description': 'Focus MapLibre on the highest ranked registered region.', 'parameters': EMPTY},
}


def redact_credentials(value: str) -> str:
    secret = os.getenv('GEMINI_API_KEY', '')
    if secret:
        value = value.replace(secret, '[REDACTED]')
    return re.sub(r'AIza[A-Za-z0-9_\-\.]{20,}', '[REDACTED]', value)


class RealAgentRuntime:
    def __init__(self, orchestrator: AgentOrchestrator):
        self.agent = orchestrator

    def run(self, req: InvestigateRequest) -> dict:
        started = time.perf_counter()
        safe_query = redact_credentials(req.query)
        cancel_event = self.agent.cancel_events.setdefault(req.session_id, threading.Event())
        cancel_event.clear()
        events: list[dict] = [{'tool': 'user_request', 'status': 'complete',
                               'request': safe_query, 'case_id': req.case_id,
                               'aoi_bbox_wgs84': req.aoi_bbox_wgs84,
                               'data_mode': req.data_mode}]

        def record(tool: str, status: str, **fields):
            events.append({'tool': tool, 'status': status, **fields})
            self.agent._trace(req.session_id, events)

        def blocked(reason: str) -> dict:
            record('final_response', 'blocked', reason=reason,
                   duration_ms=round((time.perf_counter() - started) * 1000, 1))
            return {'status': 'blocked', 'reason': reason, 'agent_mode': 'real',
                    'mode': req.data_mode, 'claims': [], 'evidence_ids': [], 'map_actions': [],
                    'trace': events, 'data_notice': ('SIMULATED DATA — NOT NASA OBSERVATIONS'
                    if req.data_mode == 'fixture' else 'NISAR-DERIVED CACHE — PROVENANCE PENDING'
                    if req.data_mode == 'cache' else 'LIVE NISAR DATA UNAVAILABLE')}

        def cancelled() -> dict:
            record('final_response', 'cancelled', reason='User cancelled analysis',
                   duration_ms=round((time.perf_counter() - started) * 1000, 1))
            return {'status': 'cancelled', 'reason': 'User cancelled analysis', 'agent_mode': 'real',
                    'mode': req.data_mode, 'claims': [], 'evidence_ids': [], 'map_actions': [],
                    'trace': events, 'data_notice': ('SIMULATED DATA — NOT NASA OBSERVATIONS'
                    if req.data_mode == 'fixture' else 'NISAR-DERIVED CACHE — PROVENANCE PENDING'
                    if req.data_mode == 'cache' else 'LIVE NISAR DATA')}

        if not self.agent.model.configured:
            return blocked('No real model endpoint is configured.')
        if req.data_mode == 'live' and not __import__('os').environ.get('SAR2ACTION_SPATIAL_MANIFEST'):
            return blocked('Live NISAR change raster and manifest are missing; synthetic data was not substituted.')

        # Deterministic observation preflight is a safety gate, not model planning.
        if req.data_mode == 'fixture':
            record('check_observations', 'complete', result_status='synthetic_fixture',
                   evidence_ids=[])
        else:
            try:
                case = self.agent.science.get_case(req.case_id)
                record('search_scene', 'complete', result_status='metadata_available',
                       scene_ids=[case.default_t0_scene_id, case.default_t1_scene_id])
            except Exception as exc:
                return blocked(f'Scene metadata unavailable: {type(exc).__name__}')

        result: dict | None = None
        completed: set[str] = set()
        plan: list[dict] = []
        tool_calls = 0
        unauthorized = 0
        last_error: str | None = None
        max_rounds = 4 if req.data_mode == 'cache' else 3
        for round_index in range(max_rounds):
            if cancel_event.is_set():
                return cancelled()
            if time.perf_counter() - started > 60:
                return blocked('Investigation exceeded the 60-second planning limit.')
            available = ({name: spec for name, spec in FIRST_TOOLS.items()
                          if name not in completed and (req.data_mode != 'cache' or name != 'rank_change_regions')}
                         if result is None else
                         {name: spec for name, spec in NEXT_TOOLS.items()
                          if name not in completed and (req.data_mode != 'cache' or name != 'compare_regions')})
            if not available:
                break
            context = {'case_id': req.case_id, 'aoi_bbox_wgs84': req.aoi_bbox_wgs84,
                       'data_mode': req.data_mode, 'completed_tools': sorted(completed),
                       'ranking_complete': result is not None,
                       'evidence_ids': result.get('evidence_ids', []) if result else [],
                       'previous_tool_error': last_error}
            last_error = None
            call_start = time.perf_counter()
            record('model_tool_selection', 'running', round=round_index + 1)
            try:
                calls, _ = self.agent.model.choose_gis_tools(safe_query, available, context)
            except Exception as exc:
                safe_reason = (str(exc) if isinstance(exc, RuntimeError) and
                               str(exc).startswith('Gemini request failed (') else type(exc).__name__)
                record('model_tool_selection', 'failed', reason=safe_reason,
                       duration_ms=round((time.perf_counter() - call_start) * 1000, 1))
                if isinstance(exc, httpx.TimeoutException) and round_index < 2:
                    last_error = 'Model endpoint timed out; retry the same permitted task once'
                    record('model_retry', 'running', reason='model_timeout', round=round_index + 1)
                    continue
                if isinstance(exc, httpx.TimeoutException) and result is not None:
                    record('model_retry', 'skipped', reason='optional_followup_timeout_after_valid_analysis')
                    break
                return blocked(f'Real model tool selection failed: {safe_reason}. No deterministic substitution was made.')
            record('model_tool_selection', 'complete', round=round_index + 1,
                   selected_intent=[item['name'] for item in calls],
                   duration_ms=round((time.perf_counter() - call_start) * 1000, 1))
            for item in calls[:5]:
                if item['name'] not in {step['tool'] for step in plan}:
                    plan.append({'tool': item['name'], 'status': 'planned'})
            record('investigation_plan', 'complete', steps=[step.copy() for step in plan])
            if cancel_event.is_set():
                return cancelled()
            if not calls:
                if result is None and round_index == 0:
                    record('model_retry', 'running', reason='no_tool_selected')
                    continue
                break
            for call in calls[:5]:
                if cancel_event.is_set():
                    return cancelled()
                if time.perf_counter() - started > 60:
                    return blocked('Investigation exceeded the 60-second planning limit.')
                tool_calls += 1
                if tool_calls > 8:
                    return blocked('Investigation exceeded the eight-call safety limit.')
                name, args = call['name'], call['arguments']
                if call.get('repaired'):
                    record('tool_argument_repair', 'complete', tool_name=name,
                           reason='optional_story_fields_normalized', validated_arguments=args)
                if call['error']:
                    unauthorized += int(call['error'] == 'unauthorized_tool')
                    record(str(name), 'rejected', reason=call['error'])
                    last_error = f'{name}: {call["error"]}; use the advertised JSON Schema exactly'
                    continue
                if name in completed:
                    continue
                tool_start = time.perf_counter()
                try:
                    if name in FIRST_TOOLS:
                        if any(args.get(key) != expected for key, expected in
                               [('case_id', req.case_id), ('aoi_bbox_wgs84', req.aoi_bbox_wgs84)]
                               if key in args):
                            raise ValueError('Model changed trusted case or AOI')
                        validated = {'case_id': req.case_id, 'aoi_bbox_wgs84': req.aoi_bbox_wgs84,
                                     'data_mode': req.data_mode}
                        record(name, 'running', validated_arguments=validated)
                        if name == 'search_scene' and req.data_mode == 'fixture':
                            record(name, 'complete', result_status='synthetic_fixture_no_nisar_scenes')
                        elif name == 'search_scene':
                            case = self.agent.science.get_case(req.case_id)
                            record(name, 'complete', scene_ids=[case.default_t0_scene_id, case.default_t1_scene_id])
                        elif name == 'validate_scene_pair' and req.data_mode == 'fixture':
                            record(name, 'complete', result_status='synthetic_not_nisar_qa')
                        elif name == 'validate_scene_pair' and req.data_mode == 'cache':
                            from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
                            from backend.app.schemas.api import RadarFingerprintRequest
                            fp = ScienceEvidenceProvider('cache').get_fingerprint(RadarFingerprintRequest(
                                case_id=req.case_id, aoi_id=req.aoi_id, aoi_bbox_wgs84=req.aoi_bbox_wgs84))
                            qa = fp.fingerprint.pair_compatibility
                            record(name, 'complete', result_status='compatible' if qa.compatible else 'incompatible',
                                   scene_ids=qa.scene_ids)
                            if not qa.compatible:
                                return blocked('Cached scene pair quality gate refused this AOI.')
                        elif name == 'validate_scene_pair':
                            from backend.app.schemas.api import ValidatePairRequest
                            case = self.agent.science.get_case(req.case_id)
                            qa = self.agent.science.validate_pair(ValidatePairRequest(
                                case_id=req.case_id, scene_t0_id=case.default_t0_scene_id,
                                scene_t1_id=case.default_t1_scene_id,
                                aoi_bbox_wgs84=req.aoi_bbox_wgs84))
                            record(name, 'complete', result_status='compatible' if qa.result.compatible else 'incompatible')
                            if not qa.result.compatible:
                                return blocked('Scene pair quality gate refused this AOI.')
                        else:
                            if req.data_mode == 'cache':
                                result = self.agent._cached(req)
                                if name != 'get_radar_fingerprint':
                                    record('get_radar_fingerprint', 'complete',
                                           evidence_ids=result.get('evidence_ids', []),
                                           result_status='read_only_cache')
                                record('get_cached_analysis', 'complete',
                                       evidence_ids=result.get('evidence_ids', []),
                                       result_status='claims_cross_checked')
                            elif req.data_mode == 'fixture' or name == 'rank_change_regions':
                                result = self.agent._rank(req)
                            else:
                                result = self.agent.investigate(req.model_copy(update={'intent': 'investigate'}))
                            record(name, 'complete', evidence_ids=result.get('evidence_ids', []),
                                   result_status=result['status'],
                                   duration_ms=round((time.perf_counter() - tool_start) * 1000, 1))
                            if result['status'] != 'completed':
                                return blocked(result.get('reason', 'Analysis did not complete.'))
                    elif result is not None:
                        ids = result.get('evidence_ids', [])
                        if name == 'compare_regions':
                            if len(ids) < 2:
                                raise ValueError('At least two registered regions are required')
                            selected = [args.get('first_evidence_id', ids[0]),
                                        args.get('second_evidence_id', ids[1])]
                            if selected != ids[:2]:
                                raise ValueError('Model selected unregistered comparison evidence')
                            record(name, 'running', validated_arguments={'evidence_ids': selected})
                            result['comparison'] = self.agent.spatial.compare_change_regions(*selected)
                            record(name, 'complete', evidence_ids=selected)
                        elif name == 'inspect_evidence':
                            eid = args.get('evidence_id', ids[0])
                            if eid not in ids:
                                raise ValueError('Model selected stale or unknown evidence')
                            record(name, 'running', validated_arguments={'evidence_id': eid})
                            evidence = self.agent.spatial.evidence.get(eid)
                            if evidence is None:
                                if req.data_mode == 'cache':
                                    from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
                                    evidence = ScienceEvidenceProvider('cache').get_evidence(eid)
                                else:
                                    evidence = self.agent.science.get_evidence(eid)
                            result['inspected_evidence_id'] = eid
                            record(name, 'complete', evidence_ids=[eid],
                                   result_status='registered' if evidence else 'missing')
                        elif name == 'generate_story':
                            from backend.app.services.agent_orchestrator import StoryRequest
                            eid = args.get('evidence_id', ids[0])
                            if eid not in ids:
                                raise ValueError('Model selected stale or unknown story evidence')
                            locale = args.get('locale', 'zh-TW' if re.search(r'[\u3400-\u9fff]', req.query) else 'en')
                            audience = args.get('audience', 'public')
                            record(name, 'running', validated_arguments={'evidence_id': eid,
                                                                         'locale': locale, 'audience': audience})
                            result['story'] = self.agent.build_story(StoryRequest(
                                session_id=req.session_id, evidence_id=eid,
                                locale=locale, audience=audience))
                            record(name, 'complete', evidence_ids=[eid],
                                   result_status='five_frames')
                        elif name == 'control_map':
                            bbox = result['ranked_regions'][0]['bbox_wgs84'] if result.get('ranked_regions') else req.aoi_bbox_wgs84
                            record(name, 'running', validated_arguments={'bbox': bbox})
                            result['map_actions'] = [{'type': 'map.focus_bbox',
                                                      'payload': {'bbox': bbox, 'crs': 'EPSG:4326'}}] + [
                                action for action in result['map_actions'] if action['type'] != 'map.focus_bbox']
                            record(name, 'complete', ui_actions=['map.focus_bbox'])
                    completed.add(name)
                    for step in plan:
                        if step['tool'] == name:
                            step['status'] = 'complete'
                except (ValueError, SpatialDataUnavailable, HTTPException) as exc:
                    record(name, 'rejected', reason=type(exc).__name__ if isinstance(exc, HTTPException) else str(exc),
                           duration_ms=round((time.perf_counter() - tool_start) * 1000, 1))
                    last_error = f'{name}: rejected; select only registered evidence and trusted AOI'
            if result is None and round_index == max_rounds - 1:
                return blocked('The model did not select a valid analysis tool within bounded attempts.')
        if result is None:
            return blocked('The model did not select a valid analysis tool.')
        from backend.app.services.scientific_reasoner import CAUSE_QUESTION, assess_scientific_evidence
        try:
            record('validate_evidence', 'running')
            if req.data_mode == 'cache':
                from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
                science = ScienceEvidenceProvider('cache')
            else:
                science = self.agent.science
            assessment = assess_scientific_evidence(req, result, self.agent.spatial,
                                                     self.agent.sessions.get(req.session_id), science)
            record('validate_evidence', 'complete', evidence_ids=result.get('evidence_ids', []),
                   analysis_version=assessment['analysis_version'])
        except ValueError as exc:
            record('validate_evidence', 'rejected', reason=str(exc))
            return blocked('Scientific evidence validation failed: ' + str(exc))
        result['scientific_assessment'] = assessment
        result['investigation_plan'] = plan
        if assessment['unknown'] and CAUSE_QUESTION.search(req.query):
            result['narrative'] += ' ' + ' '.join(assessment['unknown'])
        record('explain_findings', 'complete', evidence_ids=result.get('evidence_ids', []),
               epistemic_categories=['OBSERVED', 'INFERRED', 'UNKNOWN'])
        result['agent_mode'] = 'real'
        result['model_name'] = self.agent.model.model
        result['model_provider'] = self.agent.model.provider
        result['intent_source'] = 'real_model_tool_call'
        result['trace'] = events
        result['unauthorized_tool_calls'] = unauthorized
        record('final_response', 'complete', evidence_ids=result.get('evidence_ids', []),
               ui_actions=[action['type'] for action in result['map_actions']],
               response=result.get('narrative', ''),
               duration_ms=round((time.perf_counter() - started) * 1000, 1))
        return result
