"""Read-only science handoff adapter. Cache provenance is never inferred from a filename."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.app.schemas.api import AnalyzeChangeResponse, CasesListResponse, RadarFingerprintRequest, RadarFingerprintResponse
from backend.app.schemas.evidence import EvidenceRecord
from backend.app.services.science_service import ScienceService


class ScienceSourceUnavailable(ValueError):
    pass


class ScienceEvidenceProvider:
    SOURCES = ('science_api', 'cache', 'live', 'synthetic')

    def __init__(self, source: str | None = None, *, cache_dir: str | Path | None = None,
                 base_url: str | None = None, transport=None, science: ScienceService | None = None):
        self.source = source or os.getenv('SAR2ACTION_SCIENCE_SOURCE', 'live')
        if self.source not in self.SOURCES:
            raise ValueError('Unsupported science source')
        self.cache_dir = Path(cache_dir or os.getenv('SAR2ACTION_SCIENCE_CACHE_DIR',
                                                    str(Path(__file__).resolve().parents[3] / 'data' / 'cache')))
        self.base_url = (base_url or os.getenv('SAR2ACTION_SCIENCE_API_URL', '')).rstrip('/')
        self.transport = transport
        self.science = science
        if self.source == 'science_api':
            parsed = urlparse(self.base_url)
            if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')):
                raise ValueError('Science API must use HTTPS or loopback HTTP')

    def status(self) -> dict:
        if self.source == 'cache':
            required = ('evidence_store.json', 'fingerprint_store.json', 'analysis_store.json')
            missing = [name for name in required if not (self.cache_dir / name).is_file()]
            if missing:
                return {'source': 'NISAR CACHED EVIDENCE', 'status': 'blocked',
                        'provenance': 'UNVERIFIED NISAR-DERIVED CACHE', 'missing': missing}
            from scripts.validate_science_cache import audit
            result = audit(self.cache_dir)
            return {'source': 'NISAR CACHED EVIDENCE',
                    'status': 'unverified' if result['status'] == 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID' else 'blocked',
                    'provenance': 'UNVERIFIED NISAR-DERIVED CACHE', 'missing': [],
                    'validation_errors': result['errors']}
        if self.source == 'science_api':
            try:
                self.get_cases()
                return {'source': 'SCIENCE API', 'status': 'unverified', 'provenance': 'SOURCE NOT VERIFIED'}
            except (ScienceSourceUnavailable, ValueError):
                return {'source': 'SCIENCE API', 'status': 'blocked', 'provenance': 'SOURCE NOT VERIFIED'}
        return {'source': 'LIVE NISAR ANALYSIS' if self.source == 'live' else 'SYNTHETIC DEMO',
                'status': 'available' if self.source == 'synthetic' else 'requires_verified_data'}

    def _read(self, name: str) -> dict:
        path = self.cache_dir / name
        if not path.is_file():
            raise ScienceSourceUnavailable('Science cache missing: ' + name)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ScienceSourceUnavailable('Science cache invalid: ' + name) from None
        if not isinstance(data, dict):
            raise ScienceSourceUnavailable('Science cache root is not an object: ' + name)
        return data

    def _api(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            with httpx.Client(timeout=8, transport=self.transport) as client:
                response = client.request(method, self.base_url + path, json=body)
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Science API object expected')
            return data
        except (httpx.HTTPError, ValueError):
            raise ScienceSourceUnavailable('Science API unavailable or invalid') from None

    def get_cases(self) -> CasesListResponse:
        if self.source == 'science_api':
            return CasesListResponse.model_validate(self._api('GET', '/api/cases'))
        if self.source == 'live':
            return CasesListResponse(cases=(self.science or ScienceService()).get_cases())
        raise ScienceSourceUnavailable('Cases unavailable for this isolated source')

    def get_evidence(self, evidence_id: str) -> EvidenceRecord:
        if not re.fullmatch(r'E-[A-Za-z0-9_-]{1,148}', evidence_id):
            raise ScienceSourceUnavailable('Invalid Evidence ID')
        if self.source == 'science_api':
            raw = self._api('GET', '/api/evidence/' + evidence_id)
        elif self.source == 'cache':
            records = self._read('evidence_store.json').get('records')
            if not isinstance(records, list):
                raise ScienceSourceUnavailable('Evidence store records missing')
            raw = next((item for item in records if isinstance(item, dict) and item.get('evidence_id') == evidence_id), None)
            if raw is None:
                raise ScienceSourceUnavailable('Evidence ID not found in read-only cache')
        elif self.source == 'live':
            return (self.science or ScienceService()).get_evidence(evidence_id)
        else:
            raise ScienceSourceUnavailable('Synthetic evidence uses the spatial demo ledger only')
        evidence = EvidenceRecord.model_validate(raw)
        if evidence.evidence_id != evidence_id:
            raise ScienceSourceUnavailable('Evidence ID mismatch')
        return evidence

    def get_fingerprint(self, request: RadarFingerprintRequest) -> RadarFingerprintResponse:
        if self.source == 'science_api':
            raw = self._api('POST', '/api/radar-fingerprint', request.model_dump(mode='json'))
        elif self.source == 'cache':
            fingerprints = self._read('fingerprint_store.json').get('fingerprints')
            if not isinstance(fingerprints, dict):
                raise ScienceSourceUnavailable('Fingerprint store missing')
            matches = [value for value in fingerprints.values() if isinstance(value, dict)
                       and value.get('case_id') == request.case_id
                       and value.get('aoi_bbox_wgs84') == request.aoi_bbox_wgs84
                       and (request.aoi_id is None or value.get('roi_id') == request.aoi_id)]
            if len(matches) != 1:
                raise ScienceSourceUnavailable('No unique case/AOI fingerprint in read-only cache')
            raw = matches[0]
        elif self.source == 'live':
            return (self.science or ScienceService()).compute_radar_fingerprint(request)
        else:
            raise ScienceSourceUnavailable('Synthetic fingerprint requires explicit demo analysis')
        fingerprint = RadarFingerprintResponse.model_validate(raw)
        if fingerprint.case_id != request.case_id or fingerprint.aoi_bbox_wgs84 != request.aoi_bbox_wgs84:
            raise ScienceSourceUnavailable('Fingerprint case or AOI mismatch')
        if request.aoi_id and fingerprint.roi_id != request.aoi_id:
            raise ScienceSourceUnavailable('Fingerprint AOI ID mismatch')
        evidence = self.get_evidence(fingerprint.evidence_id)
        if fingerprint.evidence_record.evidence_id != evidence.evidence_id or evidence.roi_id != fingerprint.roi_id:
            raise ScienceSourceUnavailable('Fingerprint evidence provenance mismatch')
        if (request.scene_t0_id and evidence.scene_ids[0] != request.scene_t0_id) or (request.scene_t1_id and evidence.scene_ids[1] != request.scene_t1_id):
            raise ScienceSourceUnavailable('Fingerprint scene pair mismatch')
        return fingerprint

    def get_analysis(self, request: RadarFingerprintRequest, evidence_id: str) -> AnalyzeChangeResponse:
        if self.source != 'cache':
            raise ScienceSourceUnavailable('Read-only analysis lookup requires cache source')
        analyses = self._read('analysis_store.json').get('analyses')
        if not isinstance(analyses, dict) or evidence_id not in analyses:
            raise ScienceSourceUnavailable('Analysis Evidence ID not found in read-only cache')
        analysis = AnalyzeChangeResponse.model_validate(analyses[evidence_id])
        evidence = self.get_evidence(evidence_id)
        if (analysis.evidence_id != evidence_id or analysis.case_id != request.case_id
                or analysis.aoi_bbox_wgs84 != request.aoi_bbox_wgs84
                or (request.aoi_id and analysis.roi_id != request.aoi_id)
                or analysis.roi_id != evidence.roi_id
                or [analysis.scene_t0_id, analysis.scene_t1_id] != evidence.scene_ids):
            raise ScienceSourceUnavailable('Analysis case, AOI or scene pair mismatch')
        if (request.scene_t0_id and analysis.scene_t0_id != request.scene_t0_id) or (request.scene_t1_id and analysis.scene_t1_id != request.scene_t1_id):
            raise ScienceSourceUnavailable('Analysis requested scene pair mismatch')
        return analysis
