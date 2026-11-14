"""Bounded falsification-first investigation over the read-only B-team cache.

No model text can create observations or select arbitrary tools here. The source
cache remains provenance-pending until original products are independently checked.
"""
from __future__ import annotations

import hashlib
import json
import re

from backend.app.schemas.api import RadarFingerprintRequest
from backend.app.schemas.investigation import (
    EvidenceGraph, EvidenceLinkedStatement, GraphEdge, GraphNode, Hypothesis,
    HypothesisStatus, InvestigationRequest, InvestigationResult,
    ObservationMetadata, ToolStep,
)
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider, ScienceSourceUnavailable
from backend.app.services.science_service import ScienceService


MAX_STEPS = 4


def compatible_for_direct_difference(first: ObservationMetadata, second: ObservationMetadata) -> tuple[bool, str]:
    """Fail closed on missing calibration metadata or cross-mission subtraction."""
    if first.mission != second.mission:
        return False, 'Cross-mission backscatter subtraction requires validated calibration and harmonization.'
    for field in ('sensor', 'frequency_band', 'product_type', 'radiometric_convention'):
        left, right = getattr(first, field), getattr(second, field)
        if not left or not right or left != right:
            return False, f'{field} is missing or incompatible.'
    if not set(first.polarization).intersection(second.polarization):
        return False, 'No common polarization.'
    return True, 'Metadata precheck only; product-level geometry and calibration must still be validated.'


class ScientificInvestigator:
    def __init__(self, provider: ScienceEvidenceProvider | None = None, science: ScienceService | None = None):
        self.provider = provider or ScienceEvidenceProvider('cache')
        self.science = science or ScienceService()

    def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        trace: list[ToolStep] = []
        if self.provider.source != 'cache':
            raise ScienceSourceUnavailable('This bounded investigation accepts only the read-only NISAR cache')
        status = self.provider.status()
        trace.append(ToolStep(tool='audit_cache', status='complete' if status['status'] == 'unverified' else 'blocked'))
        if status['status'] != 'unverified':
            raise ScienceSourceUnavailable('NISAR cache is missing or failed its internal audit')

        case = self.science.get_case(request.case_id)
        fp_request = RadarFingerprintRequest(case_id=request.case_id, aoi_id=request.aoi_id,
                                              aoi_bbox_wgs84=request.aoi_bbox_wgs84)
        fingerprint = self.provider.get_fingerprint(fp_request)
        trace.append(ToolStep(tool='get_radar_fingerprint', status='complete'))
        if not fingerprint.fingerprint.pair_compatibility.compatible:
            raise ScienceSourceUnavailable('Cached NISAR scene pair is not comparable')
        evidence = self.provider.get_evidence(fingerprint.evidence_id)
        trace.append(ToolStep(tool='get_evidence', status='complete'))
        analysis = self.provider.get_analysis(fp_request, evidence.evidence_id)
        trace.append(ToolStep(tool='get_analysis', status='complete'))
        assert len(trace) <= MAX_STEPS

        if (evidence.scene_ids != [case.default_t0_scene_id, case.default_t1_scene_id]
                or evidence.quality_status.value != 'COMPARABLE'
                or fingerprint.valid_pixel_count != evidence.valid_pixel_count
                or analysis.valid_pixel_count != evidence.valid_pixel_count
                or {c.claim_id: (c.metric_name, c.metric_value, c.unit) for c in fingerprint.claims}
                != {c.claim_id: (c.metric_name, c.metric_value, c.unit) for c in analysis.claims}):
            raise ScienceSourceUnavailable('Cached investigation records disagree on scene pair, pixels or claims')

        metadata = evidence.processing_metadata.model_dump(mode='json') if hasattr(evidence.processing_metadata, 'model_dump') else evidence.processing_metadata
        values = evidence.summary_statistics.get('per_polarization', {})
        observed = []
        graph_nodes = [
            GraphNode(node_id='evidence', node_type='evidence', label=evidence.evidence_id,
                      attributes={'valid_pixel_count': evidence.valid_pixel_count}),
            GraphNode(node_id='analysis', node_type='analysis', label=evidence.algorithm_version),
            GraphNode(node_id='aoi', node_type='aoi', label=evidence.roi_id),
            GraphNode(node_id='scene_pair', node_type='scene_pair', label='Two NISAR GCOV observations',
                      attributes={'t0_scene_id': evidence.scene_ids[0], 't1_scene_id': evidence.scene_ids[1]}),
            GraphNode(node_id='metadata', node_type='observation_metadata', label='Recorded product metadata',
                      attributes={'t0_acquisition_utc': metadata.get('t0_acquisition_utc'),
                                  't1_acquisition_utc': metadata.get('t1_acquisition_utc'),
                                  'product_type': metadata.get('product_type'),
                                  'data_maturity': metadata.get('data_maturity')}),
            GraphNode(node_id='provenance', node_type='provenance', label='NISAR-DERIVED CACHE — PROVENANCE PENDING',
                      attributes={'source_products_independently_verified': False}),
        ]
        graph_edges = [GraphEdge(source=a, target=b, relation=relation) for a, b, relation in (
            ('evidence', 'analysis', 'produced_by'), ('analysis', 'aoi', 'measured_over'),
            ('aoi', 'scene_pair', 'compares'), ('scene_pair', 'metadata', 'described_by'),
            ('metadata', 'provenance', 'source_status'),
        )]
        for pol in ('HH', 'HV'):
            metric = values.get(pol, {}).get('median_delta_db')
            detail = getattr(fingerprint, pol.lower() + '_detail')
            if metric is None or detail.delta_median_db != metric:
                continue
            statement = (f'{pol} median valid pixelwise T1-minus-T0 backscatter difference: '
                         f'{metric:.4f} dB over {evidence.valid_pixel_count:,} recorded common valid pixels.')
            observed.append(EvidenceLinkedStatement(statement=statement,
                                                   evidence_ids=[evidence.evidence_id], epistemic_status='OBSERVED'))
            graph_nodes.append(GraphNode(node_id='claim_' + pol.lower(), node_type='claim', label=statement))
            graph_edges.append(GraphEdge(source='claim_' + pol.lower(), target='evidence', relation='supported_by'))
        if not observed:
            raise ScienceSourceUnavailable('No matching HH/HV measurement in the cached records')

        alternatives = (
            ('wildfire', 'Peatland wildfire caused the observed change.',
             'Independent thermal or optical fire observations and field confirmation.'),
            ('vegetation', 'Vegetation structure changed between acquisitions.',
             'Comparable optical vegetation observations or field vegetation measurements.'),
            ('moisture', 'Surface or vegetation moisture changed.',
             'Concurrent moisture observations and a stable control area.'),
            ('geometry', 'Observation geometry contributed to the difference.',
             'Source product geometry and incidence-angle comparison.'),
            ('processing', 'Processing or calibration artifacts contributed to the difference.',
             'Original HDF5 products, processing logs and an independent pixel recount.'),
        )
        if re.search(r'displac|subsiden|位移|沉降', request.question, re.I):
            alternatives += (('displacement', 'Surface displacement caused the observed change.',
                              'Independent interferometric phase or geodetic measurements; GCOV intensity is not direct displacement.'),)
        hypotheses = [Hypothesis(hypothesis_id=key, statement=statement,
                                 status=HypothesisStatus.UNRESOLVED,
                                 discriminating_observation=discriminator,
                                 limitation='Two-date cached GCOV statistics cannot uniquely identify a physical cause.')
                      for key, statement, discriminator in alternatives]
        observations = [ObservationMetadata(
            mission='NASA–ISRO NISAR', sensor='L-band SAR', frequency_band=str(metadata.get('frequency_band') or '') or None,
            polarization=[p.value for p in evidence.polarizations],
            acquisition_time=metadata.get(key), orbit_direction=metadata.get('orbit_pass_direction'),
            product_type=metadata.get('product_type'), radiometric_convention=None,
            spatial_resolution_m=None, source_reference=scene,
            product_maturity=metadata.get('data_maturity'), data_license=None,
            scientific_limitations=['Source HDF5 and georeferenced change raster not independently verified.'])
            for key, scene in zip(('t0_acquisition_utc', 't1_acquisition_utc'), evidence.scene_ids)]
        graph = EvidenceGraph(nodes=graph_nodes, edges=graph_edges)
        digest = hashlib.sha256(json.dumps([request.case_id, request.aoi_id, evidence.evidence_id,
                                            evidence.scene_ids], sort_keys=True).encode()).hexdigest()[:20]
        return InvestigationResult(
            investigation_id='investigation-' + digest, case_id=request.case_id, aoi_id=request.aoi_id,
            scene_pair=evidence.scene_ids, data_mode='cache', research_question=request.question,
            observable_variables=['HH valid pixelwise T1-minus-T0 backscatter difference (dB)',
                                  'HV valid pixelwise T1-minus-T0 backscatter difference (dB)',
                                  'Common valid pixel count'],
            observation_summary=observed,
            evidence_ids=[evidence.evidence_id], hypotheses=hypotheses,
            supporting_evidence=[], contradicting_evidence=[],
            unresolved_questions=['Was the change significant relative to a stable control?',
                                  'Which physical or processing explanation, if any, is supported by independent data?',
                                  'Can the cached values be reproduced from the original source products?'],
            scientific_limitations=list(dict.fromkeys(evidence.limitations + [
                'NISAR-DERIVED CACHE — PROVENANCE PENDING.',
                'No causal or statistical-significance conclusion is supported.',
                'GCOV backscatter differences are not direct surface displacement.',
                'No georeferenced pixel-level ranking is available from this cache.'])),
            recommended_next_observation=[
                'Verify original HDF5 products and reproduce the AOI statistics, then compare a stable control and independent optical, thermal or field observations.'],
            map_actions=[{'type': 'map.focus_bbox', 'payload': {'bbox': request.aoi_bbox_wgs84, 'crs': 'EPSG:4326'}},
                         {'type': 'evidence.open', 'payload': {'evidence_id': evidence.evidence_id}}],
            tool_trace=trace, validation_status='INTERNALLY_CONSISTENT_SOURCE_UNVERIFIED',
            evidence_graph=graph, observation_metadata=observations)
