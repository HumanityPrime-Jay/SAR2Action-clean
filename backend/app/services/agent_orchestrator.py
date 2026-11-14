"""Single, deterministic investigator over the existing NISAR science service.

The model is deliberately outside this execution path. Only typed science-service
calls can create claims; UI actions are assembled from registered layer IDs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.api import RadarFingerprintRequest, ValidatePairRequest
from backend.app.services.science_service import ScienceService
from backend.app.services.spatial_ranking import SpatialRankingService, SpatialRequest
from backend.app.services.model_provider import ModelProvider
from backend.app.services.gemini_provider import GeminiModelProvider
from backend.app.services.claim_validator import validate_science_claim


class InvestigateRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=120)
    aoi_bbox_wgs84: list[float] = Field(min_length=4, max_length=4)
    aoi_id: str | None = None
    requested_polarizations: list[Literal['HH', 'HV', 'VV', 'VH']] | None = None
    query: str = Field(min_length=1, max_length=1200)
    session_id: str = Field(default='default', pattern=r'^[A-Za-z0-9_-]{1,72}$')
    intent: Literal['investigate', 'rank', 'auto'] = 'investigate'
    data_mode: Literal['live', 'cache', 'fixture'] = 'live'
    agent_mode: Literal['deterministic', 'real'] = 'deterministic'

    @model_validator(mode='after')
    def valid_bbox(self):
        w, s, e, n = self.aoi_bbox_wgs84
        if not all(-180 <= x <= 180 for x in (w, e)) or not all(-90 <= x <= 90 for x in (s, n)) or w >= e or s >= n:
            raise ValueError('Invalid WGS84 AOI bounding box')
        return self


class StoryRequest(BaseModel):
    session_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,72}$')
    evidence_id: str = Field(min_length=4, max_length=150)
    locale: Literal['en', 'zh-TW'] = 'en'
    audience: Literal['public', 'scientific'] = 'public'


class AgentOrchestrator:
    def __init__(self, science: ScienceService):
        self.science = science
        self.spatial = SpatialRankingService(science)
        self.model = (GeminiModelProvider() if os.getenv('SAR2ACTION_LLM_PROVIDER', '').lower() == 'gemini'
                      else ModelProvider())
        self._lock = threading.Lock()
        self.sessions: dict[str, dict] = {}
        self.stories: dict[str, dict] = {}
        self.operations: dict[str, list[dict]] = {}
        self.cancel_events: dict[str, threading.Event] = {}

    def cancel(self, session_id: str) -> None:
        self.cancel_events.setdefault(session_id, threading.Event()).set()

    def _trace(self, session_id: str, trace: list[dict]) -> None:
        self.operations[session_id] = [item.copy() for item in trace]

    @staticmethod
    def _signature(case_id: str, bbox: list[float], evidence_id: str, aoi_id: str | None, polarizations: list[str] | None) -> str:
        blob = json.dumps([case_id, bbox, evidence_id, aoi_id, polarizations], sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:20]

    def investigate(self, req: InvestigateRequest) -> dict:
        if req.data_mode == 'cache':
            from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
            source = ScienceEvidenceProvider('cache').status()
            if source['status'] == 'blocked':
                return {'status': 'blocked', 'reason': 'NISAR cached evidence failed the read-only handoff audit.',
                        'agent_mode': req.agent_mode, 'mode': 'cache', 'source_status': source,
                        'claims': [], 'evidence_ids': [], 'map_actions': [], 'trace': [],
                        'data_notice': 'NISAR-DERIVED CACHE — PROVENANCE PENDING'}
            if req.agent_mode == 'real':
                from backend.app.services.real_agent_runtime import RealAgentRuntime
                return RealAgentRuntime(self).run(req)
            return self._cached(req)
        if req.agent_mode == 'real':
            from backend.app.services.real_agent_runtime import RealAgentRuntime
            return RealAgentRuntime(self).run(req)
        self._trace(req.session_id, [{'tool': 'classify_intent', 'status': 'running'}])
        intent, source = self.model.classify_intent(req.query) if req.intent == 'auto' else (req.intent, 'explicit')
        self._trace(req.session_id, [{'tool': 'classify_intent', 'status': 'complete', 'source': source}])
        if intent == 'rank':
            if self.model.configured:
                accepted = self.model.propose_rank_tool(req.query, req.case_id, req.aoi_bbox_wgs84,
                                                       (req.requested_polarizations or ['HV'])[0], req.data_mode)
                source = 'model_tool_call' if accepted else source
            result = self._rank(req)
            result['intent_source'] = source
            return result
        if req.data_mode == 'fixture':
            result = self._rank(req)
            wants_story = bool(re.search(r'story|故事', req.query, re.I))
            wants_compare = bool(re.search(r'compare|比較', req.query, re.I))
            wants_fingerprint = bool(re.search(r'fingerprint|指紋', req.query, re.I))
            result['intent'] = 'story' if wants_story else 'compare' if wants_compare else 'investigate'
            result['intent_source'] = source
            result['narrative'] = ('Synthetic AOI investigation: three contiguous radar-change regions were '
                                   'measured and ranked. Select a region to inspect its evidence. '
                                   'The physical cause is unknown.')
            if wants_fingerprint:
                result['narrative'] = ('The selected Radar Fingerprint summarizes a two-date, pairwise synthetic '
                                       'backscatter difference. Its measured values and source are in the linked '
                                       'Evidence Card. It does not identify a physical cause or a longer time trend.')
            if wants_compare and len(result['evidence_ids']) >= 2:
                result['comparison'] = self.spatial.compare_change_regions(*result['evidence_ids'][:2])
                result['trace'].append({'tool': 'compare_change_regions', 'status': 'complete'})
                self._trace(req.session_id, result['trace'])
            if wants_story:
                locale = 'zh-TW' if re.search(r'[\u3400-\u9fff]', req.query) else 'en'
                result['story'] = self.build_story(StoryRequest(
                    session_id=req.session_id, evidence_id=result['evidence_ids'][0], locale=locale))
                result['trace'].append({'tool': 'build_story', 'status': 'complete'})
                self._trace(req.session_id, result['trace'])
            return result
        trace = [{'tool': 'classify_intent', 'status': 'complete', 'source': source}]
        def step(tool: str, fn):
            trace.append({'tool': tool, 'status': 'running'})
            self._trace(req.session_id, trace)
            try:
                result = fn()
                trace[-1]['status'] = 'complete'
                self._trace(req.session_id, trace)
                return result
            except Exception:
                trace[-1]['status'] = 'failed'
                self._trace(req.session_id, trace)
                raise

        with self._lock:
            case = step('list_nisar_observations', lambda: self.science.get_case(req.case_id))
            pair = step('validate_scene_pair', lambda: self.science.validate_pair(ValidatePairRequest(
                case_id=req.case_id, scene_t0_id=case.default_t0_scene_id,
                scene_t1_id=case.default_t1_scene_id, aoi_bbox_wgs84=req.aoi_bbox_wgs84)))
            if not pair.result.compatible:
                return {'status': 'blocked', 'reason': 'scene_pair_incompatible', 'trace': trace, 'claims': [], 'map_actions': []}
            fp = step('get_radar_fingerprint', lambda: self.science.compute_radar_fingerprint(RadarFingerprintRequest(
                case_id=req.case_id, aoi_id=req.aoi_id, aoi_bbox_wgs84=req.aoi_bbox_wgs84,
                requested_polarizations=req.requested_polarizations)))
            evidence = step('inspect_provenance', lambda: self.science.get_evidence(fp.evidence_id))
            claims = []
            for claim in fp.claims:
                claims.append(validate_science_claim(claim, evidence))
            layer = 'delta_hv' if 'delta_hv' in fp.layers else 'delta_hh' if 'delta_hh' in fp.layers else next(iter(fp.layers), None)
            actions = [{'type': 'map.focus_bbox', 'payload': {'bbox': fp.aoi_bbox_wgs84}},
                       {'type': 'map.highlight_aoi', 'payload': {'bbox': fp.aoi_bbox_wgs84}},
                       {'type': 'fingerprint.open', 'payload': {'evidence_id': evidence.evidence_id}}]
            if layer:
                actions.append({'type': 'map.set_layer', 'payload': {'layer_id': layer}})
            trace.append({'tool': 'dispatch_map_actions', 'status': 'complete'})
            self._trace(req.session_id, trace)
            signature = self._signature(req.case_id, req.aoi_bbox_wgs84, evidence.evidence_id,
                                        req.aoi_id, req.requested_polarizations)
            previous = self.sessions.get(req.session_id)
            if previous and previous['signature'] != signature:
                for story in self.stories.values():
                    if story['session_id'] == req.session_id:
                        story['status'] = 'stale'
            self.sessions[req.session_id] = {'signature': signature, 'case_id': req.case_id,
                                              'bbox': req.aoi_bbox_wgs84, 'evidence_id': evidence.evidence_id,
                                              'trace': trace}
            narrative = ' '.join(c['statement'] for c in claims[:2]) if claims else 'No quantitative claim is available for this AOI.'
            return {'status': 'completed', 'run_id': 'run-' + signature, 'mode': 'NISAR_DERIVED',
                    'intent_source': source,
                    'intent': 'story' if re.search(r'story|故事', req.query, re.I) else 'investigate',
                    'narrative': narrative, 'claims': claims, 'evidence_ids': [evidence.evidence_id],
                    'unknowns': fp.epistemic_panel.what_we_do_not_know,
                    'trace': trace, 'map_actions': actions,
                    'fingerprint': {'evidence_id': evidence.evidence_id, 'quality_status': fp.quality_status,
                                    'available_polarizations': fp.available_polarizations},
                    'data_notice': 'NISAR-derived analysis; cause is not established by radar change alone.'}

    def _rank(self, req: InvestigateRequest) -> dict:
        trace = [{'tool': 'classify_intent', 'status': 'complete'},
                 {'tool': 'analyze_spatial_changes', 'status': 'running'}]
        self._trace(req.session_id, trace)
        try:
            request = SpatialRequest(case_id=req.case_id, aoi_bbox_wgs84=req.aoi_bbox_wgs84,
                                     polarization=(req.requested_polarizations or ['HV'])[0], mode=req.data_mode)
            analysis = self.spatial.analyze_spatial_changes(request)
            trace[-1]['status'] = 'complete'
            self._trace(req.session_id, trace)
            trace.append({'tool': 'rank_change_regions', 'status': 'running'})
            self._trace(req.session_id, trace)
            ranked = self.spatial.rank_change_regions(analysis, request)
            trace[-1]['status'] = 'complete'
            self._trace(req.session_id, trace)
        except Exception:
            trace[-1]['status'] = 'failed'
            self._trace(req.session_id, trace)
            raise
        regions = ranked['regions']
        if not regions:
            return {'status': 'blocked', 'reason': 'No contiguous change region passes the size, quality and magnitude gates.',
                    'trace': trace, 'claims': [], 'map_actions': [], 'ranked_regions': [],
                    'data_notice': ranked['data_notice']}
        top = regions[0]
        actions = [self.spatial.focus_change_region(top),
                   {'type': 'map.highlight_aoi', 'payload': {'bbox': top['bbox_wgs84'], 'crs': 'EPSG:4326'}},
                   {'type': 'fingerprint.open', 'payload': {'evidence_id': top['evidence_ids'][0]}}]
        trace.append({'tool': 'focus_change_region', 'status': 'complete'})
        self._trace(req.session_id, trace)
        claims = [{'statement': f"Region {region['rank']}: median absolute {region['polarization']} backscatter change {region['median_abs_change_db']:.3f} dB across {region['pixel_count']} contiguous pixels.",
                   'evidence_id': region['evidence_ids'][0], 'unit': 'dB', 'metric_value': region['median_abs_change_db'],
                   'epistemic_status': 'OBSERVED'} for region in regions]
        for claim in claims:
            item = self.spatial.evidence.get(claim['evidence_id'])
            if not item or item['measurements']['median_abs_change_db'] != claim['metric_value'] or item['polarization'] != request.polarization:
                raise ValueError('Spatial claim-to-evidence validation failed')
        signature = self._signature(req.case_id, req.aoi_bbox_wgs84, top['evidence_ids'][0], req.aoi_id, req.requested_polarizations)
        with self._lock:
            previous = self.sessions.get(req.session_id)
            if previous and previous['signature'] != signature:
                for story in self.stories.values():
                    if story['session_id'] == req.session_id:
                        story['status'] = 'stale'
            self.sessions[req.session_id] = {'signature': signature, 'case_id': req.case_id,
                                             'bbox': req.aoi_bbox_wgs84, 'evidence_id': top['evidence_ids'][0],
                                             'evidence_ids': [region['evidence_ids'][0] for region in regions],
                                             'trace': trace, 'mode': req.data_mode}
        return {'status': 'completed', 'run_id': 'run-' + signature, 'mode': req.data_mode,
                'intent': 'rank', 'narrative': 'Ranked contiguous radar-change regions by measured magnitude, valid coverage and area. Physical cause remains unknown.',
                'claims': claims, 'evidence_ids': [region['evidence_ids'][0] for region in regions],
                'ranked_regions': regions, 'unknowns': ['GCOV intensity change alone cannot prove wildfire, peat combustion, displacement or recovery.'],
                'trace': trace, 'map_actions': actions, 'data_notice': ranked['data_notice'],
                'fingerprint': {'evidence_id': top['evidence_ids'][0], 'available_polarizations': [request.polarization],
                                'note': 'Only pairwise dB difference exists; no invented time series.'}}

    def _cached(self, req: InvestigateRequest) -> dict:
        from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
        provider = ScienceEvidenceProvider('cache')
        request = RadarFingerprintRequest(case_id=req.case_id, aoi_id=req.aoi_id,
                                          aoi_bbox_wgs84=req.aoi_bbox_wgs84,
                                          requested_polarizations=req.requested_polarizations)
        fingerprint = provider.get_fingerprint(request)
        evidence = provider.get_evidence(fingerprint.evidence_id)
        analysis = provider.get_analysis(request, evidence.evidence_id)
        case = self.science.get_case(req.case_id)
        if evidence.scene_ids != [case.default_t0_scene_id, case.default_t1_scene_id]:
            raise ValueError('Cached Evidence scene pair does not match selected case')
        if (analysis.evidence_id != fingerprint.evidence_id
                or analysis.scene_t0_id != evidence.scene_ids[0]
                or analysis.scene_t1_id != evidence.scene_ids[1]
                or fingerprint.valid_pixel_count != evidence.valid_pixel_count):
            raise ValueError('Cached fingerprint and analysis provenance mismatch')
        fp_claims = {claim.claim_id: (claim.metric_name, claim.metric_value, claim.unit)
                     for claim in fingerprint.claims}
        an_claims = {claim.claim_id: (claim.metric_name, claim.metric_value, claim.unit)
                     for claim in analysis.claims}
        if fp_claims != an_claims:
            raise ValueError('Cached fingerprint and analysis claims differ')
        claims = [validate_science_claim(claim, evidence) for claim in fingerprint.claims]
        for claim in claims:
            if claim['metric_name'] in ('median_delta_hh_db', 'median_delta_hv_db'):
                pol = claim['polarization']
                claim['source_statement'] = claim['statement']
                claim['statement'] = (f"Median of valid pixelwise {pol} T1-minus-T0 backscatter differences: "
                                      f"{claim['metric_value']:.4f} dB across {claim['valid_pixel_count']:,} "
                                      f"pixels in {evidence.roi_id}. This is not a significance test.")
        bbox = fingerprint.aoi_bbox_wgs84
        actions = [{'type': 'map.focus_bbox', 'payload': {'bbox': bbox, 'crs': 'EPSG:4326'}},
                   {'type': 'fingerprint.open', 'payload': {'evidence_id': evidence.evidence_id}},
                   {'type': 'evidence.open', 'payload': {'evidence_id': evidence.evidence_id}}]
        signature = self._signature(req.case_id, bbox, evidence.evidence_id, fingerprint.roi_id,
                                    req.requested_polarizations)
        with self._lock:
            previous = self.sessions.get(req.session_id)
            if previous and previous['signature'] != signature:
                for story in self.stories.values():
                    if story['session_id'] == req.session_id:
                        story['status'] = 'stale'
            self.sessions[req.session_id] = {'signature': signature, 'case_id': req.case_id,
                                             'bbox': bbox, 'evidence_id': evidence.evidence_id,
                                             'evidence_ids': [evidence.evidence_id], 'mode': 'cache'}
        hh = fingerprint.hh_detail.delta_median_db
        hv = fingerprint.hv_detail.delta_median_db
        per_pol = evidence.summary_statistics.get('per_polarization', {})
        measured = []
        if hh is not None:
            measured.append(f'HH median signed change {hh:.4f} dB')
        if hv is not None:
            measured.append(f'HV median signed change {hv:.4f} dB')
        narrative = (f"{fingerprint.roi_id}: " + '; '.join(measured) + f". Source: {evidence.evidence_id}. "
                     'These are medians of per-pixel T1 minus T0 backscatter differences. '
                     'The signed median alone does not establish a significant region-wide disturbance. '
                     'The cache includes change distributions, but no designated stable control area or '
                     'significance assessment; spatial patterns need source-raster review. '
                     'Radar backscatter change alone cannot confirm peat fire, ground displacement, '
                     'underground combustion, ecological recovery, or physical cause.')
        return {'status': 'completed', 'run_id': 'run-' + signature, 'mode': 'cache',
                'intent': 'investigate', 'narrative': narrative, 'claims': claims,
                'evidence_ids': [evidence.evidence_id], 'unknowns': fingerprint.epistemic_panel.what_we_do_not_know,
                'evidence_limitations': evidence.limitations,
                'trace': [{'tool': 'get_radar_fingerprint', 'status': 'complete', 'evidence_ids': [evidence.evidence_id]},
                          {'tool': 'validate_evidence', 'status': 'complete', 'evidence_ids': [evidence.evidence_id]}],
                'map_actions': actions, 'data_notice': 'NISAR-DERIVED CACHE — PROVENANCE PENDING; not live HDF5 computation.',
                'fingerprint_details': {'evidence_id': evidence.evidence_id, 'roi_id': fingerprint.roi_id,
                                        'aoi_bbox_wgs84': bbox,
                                        'hh_delta_median_db': hh, 'hv_delta_median_db': hv,
                                        't0_acquisition_utc': fingerprint.t0_acquisition_utc,
                                        't1_acquisition_utc': fingerprint.t1_acquisition_utc,
                                        'valid_pixel_count': evidence.valid_pixel_count,
                                        'quality_status': evidence.quality_status.value,
                                        'scene_ids': evidence.scene_ids,
                                        'method': evidence.algorithm_version,
                                        'measurement_definition': 'median of valid pixelwise (T1 dB - T0 dB)',
                                        'significance_status': 'NOT_ASSESSED',
                                        'stable_control_status': 'NOT_DESIGNATED',
                                        'mask_rule': evidence.summary_statistics.get('mask_rule'),
                                        'distribution': {pol: {
                                            'p10_delta_db': per_pol.get(pol, {}).get('p10_delta_db'),
                                            'p90_delta_db': per_pol.get(pol, {}).get('p90_delta_db'),
                                            'median_abs_change_db': per_pol.get(pol, {}).get('median_abs_change_db'),
                                            'positive_change_fraction': per_pol.get(pol, {}).get('positive_change_fraction'),
                                            'negative_change_fraction': per_pol.get(pol, {}).get('negative_change_fraction'),
                                        } for pol in ('HH', 'HV')}}}

    def build_story(self, req: StoryRequest) -> dict:
        session = self.sessions.get(req.session_id)
        if not session or req.evidence_id not in session.get('evidence_ids', [session['evidence_id']]):
            raise ValueError('Evidence is not current for this session')
        spatial_evidence = self.spatial.evidence.get(req.evidence_id)
        if session.get('mode') == 'cache':
            from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
            evidence = ScienceEvidenceProvider('cache').get_evidence(req.evidence_id)
        else:
            evidence = spatial_evidence if spatial_evidence else self.science.get_evidence(req.evidence_id)
        source_ids = evidence['scene_ids'] if spatial_evidence else evidence.scene_ids
        mode = ('cache' if session.get('mode') == 'cache' else
                'fixture' if spatial_evidence and evidence['data_kind'] == 'synthetic' else 'NISAR_DERIVED')
        titles = ['The Region', 'The Change', 'The Evidence', 'What We Know', 'Why It Matters'] if req.locale == 'en' else ['研究區域', '雷達變化', '證據', '已知與未知', '研究意義']
        captions = [
            'The selected region is bounded by the AOI shown on the map.',
            'Compare the two cached radar observations and available change layer. A median difference alone does not establish significant disturbance.',
            'Inspect the Radar Fingerprint and trace every measured claim to its source.',
            'An observed backscatter difference is documented; the physical cause and statistical significance remain unconfirmed.',
            'Review source rasters, a stable control area and independent ground evidence before interpretation.',
        ] if req.locale == 'en' else [
            '地圖顯示本次分析的選取區域。', '比較兩次快取觀測的雷達後向散射差異；中位數差異本身不能證明顯著擾動。',
            '查看雷達指紋與來源證據。', '已記錄雷達訊號差異；物理成因與統計顯著性仍未確認。',
            '需要來源 raster、穩定對照區與獨立地面資料才能進一步解釋。']
        if req.audience == 'scientific':
            method = evidence['method'] if spatial_evidence else evidence.algorithm_version
            captions[2] += f' Method: {method}; evidence: {req.evidence_id}.'
        layers = ['t0_hh', 'delta_hv', 'delta_hv', 'validity_mask', 't1_hh']
        sid = 'story-' + hashlib.sha256((session['signature'] + req.evidence_id).encode()).hexdigest()[:20]
        map_bbox = evidence['bbox_wgs84'] if spatial_evidence else session['bbox']
        frames = [{'title': title, 'narrative': captions[i], 'map_state': {'bbox': map_bbox, 'layer_id': layers[i]},
                   'evidence_ids': [req.evidence_id], 'visualization': 'map' if i != 2 else 'fingerprint',
                   'source': source_ids,
                   'scientific_limitations': evidence['limitations'] if spatial_evidence else list(getattr(evidence, 'limitations', []))}
                  for i, title in enumerate(titles)]
        story = {'story_id': sid, 'session_id': req.session_id, 'status': 'current',
                 'source_signature': session['signature'],
                 'mode': mode, 'locale': req.locale, 'audience': req.audience,
                 'evidence_ids': [req.evidence_id], 'frames': frames,
                 'data_notice': ('SIMULATED DATA — NOT NASA OBSERVATIONS' if mode == 'fixture' else
                                 'NISAR-DERIVED CACHE — PROVENANCE PENDING' if mode == 'cache' else 'NISAR-derived data')}
        self.stories[sid] = story
        return story

    def get_story(self, story_id: str) -> dict | None:
        story = self.stories.get(story_id)
        if not story:
            return None
        session = self.sessions.get(story['session_id'])
        if not session or story['source_signature'] != session['signature']:
            story['status'] = 'stale'
        for evidence_id in story['evidence_ids']:
            if evidence_id.startswith(('SYN-SP-', 'NISAR-SP-')):
                if evidence_id not in self.spatial.evidence:
                    story['status'] = 'stale'
            else:
                try:
                    self.science.get_evidence(evidence_id)
                except Exception:
                    story['status'] = 'stale'
        return story
