"""Bounded OpenAI-compatible model adapter for allowlisted GIS function calls.

Only restricted function schemas are sent to the model. Scientific measurements
and map commands are exclusively created by local services.
"""
from __future__ import annotations

import os
import json
import re
from urllib.parse import urlparse

import httpx
from jsonschema import Draft202012Validator, ValidationError


RANK_TOOL_PARAMETERS = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'case_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
        'aoi_bbox_wgs84': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 4, 'maxItems': 4},
        'polarization': {'type': 'string', 'enum': ['HH', 'HV', 'VV', 'VH']},
        'data_mode': {'type': 'string', 'enum': ['live', 'fixture']},
    },
    'required': ['case_id', 'aoi_bbox_wgs84', 'polarization', 'data_mode'],
}


class ModelProvider:
    def __init__(self, transport=None):
        self.url = os.getenv('SAR2ACTION_MODEL_URL', '').strip()
        self.model = os.getenv('SAR2ACTION_MODEL_NAME', '').strip()
        self.key = os.getenv('SAR2ACTION_MODEL_KEY', '').strip()
        self.provider = os.getenv('SAR2ACTION_MODEL_PROVIDER', '').strip().lower()
        self.transport = transport

    @property
    def configured(self) -> bool:
        if not self.url or not self.model or self.provider not in ('openai_compatible', 'hermes'):
            return False
        parsed = urlparse(self.url)
        if self.provider == 'hermes' and os.getenv('SAR2ACTION_HERMES_SAFE_PROFILE_VERIFIED') != 'true':
            return False
        return parsed.path.endswith('/v1/chat/completions') and (parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')))

    def status(self) -> dict:
        if not self.configured:
            return {'status': 'offline', 'reason': 'No approved model endpoint configured'}
        try:
            base = self.url.split('/v1/chat/completions')[0]
            with httpx.Client(timeout=3, transport=self.transport) as client:
                response = client.get(base + '/v1/models', headers=self._headers())
                response.raise_for_status()
            if not self.propose_rank_tool('Rank these regions', 'status-probe',
                                          [100.0, 0.0, 100.1, 0.1], 'HV', 'fixture'):
                return {'status': 'offline', 'reason': 'Model tool-calling probe failed'}
            return {'status': 'online', 'model': self.model, 'reason': 'Model function-call probe succeeded'}
        except (httpx.HTTPError, ValueError):
            return {'status': 'offline', 'reason': 'Model API health check failed'}

    def _headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        return headers

    def classify_intent(self, query: str) -> tuple[str, str]:
        fallback = 'rank' if re.search(r'最大|前三|前\s*[1-9]|排名|top\s*\d*|largest|rank|regions?', query, re.I) else 'investigate'
        if not self.configured:
            return fallback, 'deterministic_fallback'
        payload = {'model': self.model, 'stream': False, 'temperature': 0, 'max_tokens': 10,
                   'tool_choice': 'none',
                   'messages': [{'role': 'system', 'content': 'Classify the user request. Reply with exactly one token: rank or investigate. Do not provide facts or call tools.'},
                                {'role': 'user', 'content': query[:500]}]}
        for attempt in range(2):
            try:
                with httpx.Client(timeout=5, transport=self.transport) as client:
                    response = client.post(self.url, json=payload, headers=self._headers())
                    response.raise_for_status()
                    content = response.json()['choices'][0]['message']['content'].strip().lower()
                if content in ('rank', 'investigate'):
                    return content, 'model'
                break
            except (httpx.HTTPError, KeyError, ValueError, IndexError, AttributeError):
                if attempt:
                    break
        return fallback, 'deterministic_fallback'

    def propose_rank_tool(self, query: str, case_id: str, bbox: list[float],
                          polarization: str, data_mode: str) -> bool:
        """Accept only a model tool call with arguments equal to trusted UI context.

        The model receives no shell, file, browser or free-form tool. A rejected
        call leaves deterministic routing in control; no model values enter science.
        """
        if not self.configured:
            return False
        tool = {'type': 'function', 'function': {'name': 'rank_change_regions',
                'description': 'Request the local validated spatial ranking service.',
                'parameters': RANK_TOOL_PARAMETERS}}
        payload = {'model': self.model, 'stream': False, 'temperature': 0,
                   'tool_choice': {'type': 'function', 'function': {'name': 'rank_change_regions'}},
                   'tools': [tool],
                   'messages': [
                       {'role': 'system', 'content': 'Use rank_change_regions only with the exact case, AOI, polarization and data mode supplied by the application. Never infer measurements.'},
                       {'role': 'user', 'content': query[:500]},
                       {'role': 'system', 'content': json.dumps({
                           'case_id': case_id, 'aoi_bbox_wgs84': bbox,
                           'polarization': polarization, 'data_mode': data_mode})},
                   ]}
        try:
            with httpx.Client(timeout=8, transport=self.transport) as client:
                response = client.post(self.url, json=payload, headers=self._headers())
                response.raise_for_status()
                calls = response.json()['choices'][0]['message']['tool_calls']
            if len(calls) != 1 or calls[0]['function']['name'] != 'rank_change_regions':
                return False
            args = json.loads(calls[0]['function']['arguments'])
            Draft202012Validator(RANK_TOOL_PARAMETERS).validate(args)
            return args == {'case_id': case_id, 'aoi_bbox_wgs84': bbox,
                            'polarization': polarization, 'data_mode': data_mode}
        except (httpx.HTTPError, ValidationError, KeyError, ValueError, IndexError, TypeError, AttributeError):
            return False

    def choose_gis_tools(self, query: str, available: dict[str, dict], context: dict) -> tuple[list[dict], str]:
        """Ask a real model to select only the given GIS functions.

        Arguments are parsed and schema-checked here; execution stays in the
        local Safe Tool Executor. No model text is treated as scientific data.
        """
        if not self.configured:
            raise RuntimeError('Real model endpoint is not configured')
        tools = [{'type': 'function', 'function': {'name': name,
                  'description': spec['description'], 'parameters': spec['parameters']}}
                 for name, spec in available.items()]
        if context.get('ranking_complete'):
            instruction = ('Ranking is complete, but no comparison, evidence inspection or story tool has run unless '
                           'listed in completed_tools. Re-read the original user request. Call the remaining '
                           'necessary tools now, possibly several together. If the user asked for comparison and '
                           'evidence, call compare_regions and inspect_evidence. If the user asked for a story, '
                           'call generate_story. Do not invent measurements or physical causes.')
        else:
            instruction = ('Choose the first GIS analysis tool for the original user request. '
                           'For largest change areas choose rank_change_regions. For an AOI summary choose '
                           'analyze_aoi. For a Radar Fingerprint choose get_radar_fingerprint. '
                           'Never invent observations, measurements or physical causes.')
        payload = {'model': self.model, 'stream': False, 'temperature': 0, 'max_tokens': 800,
                   'tool_choice': 'auto', 'tools': tools,
                   'messages': [
                       {'role': 'system', 'content': instruction},
                       {'role': 'user', 'content': query[:500]},
                       {'role': 'system', 'content': 'Trusted context: ' + json.dumps(context, ensure_ascii=False)},
                   ]}
        with httpx.Client(timeout=20, transport=self.transport) as client:
            response = client.post(self.url, json=payload, headers=self._headers())
            response.raise_for_status()
            message = response.json()['choices'][0]['message']
        calls = []
        for call in message.get('tool_calls') or []:
            function = call.get('function') or {}
            name = function.get('name')
            if name not in available:
                calls.append({'name': name, 'arguments': None, 'error': 'unauthorized_tool'})
                continue
            arguments = None
            try:
                arguments = json.loads(function.get('arguments') or '{}')
                Draft202012Validator(available[name]['parameters']).validate(arguments)
                calls.append({'name': name, 'arguments': arguments, 'error': None, 'repaired': False})
            except (ValueError, TypeError, ValidationError):
                # One bounded repair is safe only for optional story presentation
                # fields. Never repair case, AOI, coordinates or Evidence IDs.
                repaired = None
                if name == 'inspect_evidence' and isinstance(arguments, dict):
                    eid = arguments.get('evidence_id')
                    registered = context.get('evidence_ids') or []
                    if eid is None:
                        repaired = {}
                    elif isinstance(eid, str) and eid in registered:
                        repaired = {'evidence_id': eid}
                    if repaired is not None:
                        try:
                            Draft202012Validator(available[name]['parameters']).validate(repaired)
                        except ValidationError:
                            repaired = None
                elif name == 'generate_story' and isinstance(arguments, dict):
                    raw = arguments
                    if 'evidence_id' not in raw or isinstance(raw.get('evidence_id'), str):
                        repaired = {key: raw[key] for key in ('evidence_id', 'locale', 'audience')
                                    if key in raw}
                        if repaired.get('locale') not in (None, 'en', 'zh-TW'):
                            repaired.pop('locale')
                        if repaired.get('audience') not in (None, 'public', 'scientific'):
                            repaired.pop('audience')
                        if 'audience' not in repaired and ('scientific' in query.lower() or '科學' in query):
                            repaired['audience'] = 'scientific'
                        try:
                            Draft202012Validator(available[name]['parameters']).validate(repaired)
                        except ValidationError:
                            repaired = None
                calls.append({'name': name, 'arguments': repaired, 'error': None if repaired is not None else 'invalid_arguments',
                              'repaired': repaired is not None})
        return calls, str(message.get('content') or '')[:500]
