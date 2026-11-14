"""Deterministic connected-region ranking on georeferenced dB change rasters.

Fixture mode is explicit and never presented as NISAR observations. Live mode
requires a B-team manifest and a matching persisted science evidence record.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator
from scipy import ndimage
from pyproj import Geod


class SpatialRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=120)
    aoi_bbox_wgs84: list[float] = Field(min_length=4, max_length=4)
    polarization: Literal['HH', 'HV', 'VV', 'VH'] = 'HV'
    mode: Literal['live', 'fixture'] = 'live'
    limit: int = Field(default=3, ge=1, le=10)
    min_pixels: int = Field(default=6, ge=2, le=10000)
    min_area_km2: float = Field(default=0.001, ge=0, le=10000)
    threshold_db: float = Field(default=2.0, ge=0.1, le=30)
    min_valid_fraction: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode='after')
    def check_bbox(self):
        w, s, e, n = self.aoi_bbox_wgs84
        if not all(np.isfinite(v) for v in (w, s, e, n)) or not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError('Invalid WGS84 AOI')
        if e-w > 5 or n-s > 5:
            raise ValueError('AOI exceeds spatial analysis limit')
        return self


class SpatialDataUnavailable(ValueError):
    pass


class SpatialRankingService:
    def __init__(self, science=None):
        self.science = science
        self.evidence: dict[str, dict] = {}

    def _fixture(self, request: SpatialRequest):
        size = 96
        yy, xx = np.mgrid[0:size, 0:size]
        # Three contiguous patches; isolated extreme pixels must fail min_pixels.
        peaks = [(28, 25, 4.9, 10), (70, 65, -3.9, 12), (30, 73, 3.1, 8)]
        delta = np.zeros((size, size), dtype=np.float32)
        for cy, cx, amplitude, radius in peaks:
            delta += amplitude * np.exp(-((xx-cx)**2 + (yy-cy)**2)/(2*radius**2))
        delta[2, 2] = 25.0
        valid = np.ones((size, size), dtype=bool)
        valid[0:4, :] = False
        valid[50:56, 42:48] = False
        bbox = request.aoi_bbox_wgs84
        metadata = {'data_kind': 'synthetic', 'crs': 'EPSG:4326',
                    'scene_ids': ['SIMULATED_T0', 'SIMULATED_T1'],
                    'observation_times': ['SIMULATED_T0', 'SIMULATED_T1'],
                    'polarization': request.polarization, 'method': 'synthetic_connected_change_v1',
                    'parent_evidence_id': None,
                    'limitations': ['SIMULATED DATA — NOT NASA OBSERVATIONS',
                                    'Synthetic backscatter change cannot establish physical cause.']}
        return delta, valid, bbox, metadata

    def _live(self, request: SpatialRequest):
        import rasterio
        from rasterio.windows import from_bounds

        raw_path = os.environ.get('SAR2ACTION_SPATIAL_MANIFEST', '').strip()
        if not raw_path:
            raise SpatialDataUnavailable('Live spatial manifest is not configured; no synthetic fallback')
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise SpatialDataUnavailable('Live spatial manifest is missing')
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise SpatialDataUnavailable('Live spatial manifest is unreadable JSON') from exc
        if not isinstance(manifest, dict):
            raise SpatialDataUnavailable('Live spatial manifest must be a JSON object')
        required = ('schema_version', 'data_kind', 'case_id', 'polarization', 'scene_ids',
                    'observation_times', 'parent_evidence_id', 'change_geotiff', 'valid_mask_geotiff',
                    'change_sha256', 'valid_mask_sha256', 'method', 'scene_versions',
                    'pixel_resolution_deg', 'source_backscatter_unit', 'change_unit', 'conversion_formula')
        if any(key not in manifest for key in required) or manifest['schema_version'] != '1' or manifest['data_kind'] != 'nisar':
            raise SpatialDataUnavailable('Invalid live spatial manifest contract')
        if manifest['case_id'] != request.case_id or manifest['polarization'] != request.polarization:
            raise SpatialDataUnavailable('Manifest case or polarization mismatch')
        if (not isinstance(manifest['scene_ids'], list) or len(manifest['scene_ids']) != 2 or
                not all(isinstance(x, str) and x for x in manifest['scene_ids']) or
                not isinstance(manifest['observation_times'], list) or len(manifest['observation_times']) != 2):
            raise SpatialDataUnavailable('Invalid scene provenance')
        if (not isinstance(manifest['scene_versions'], list) or len(manifest['scene_versions']) != 2 or
                not all(isinstance(x, str) and x for x in manifest['scene_versions']) or
                manifest['change_unit'] != 'dB' or not isinstance(manifest['method'], str) or not manifest['method']):
            raise SpatialDataUnavailable('Invalid scene version, method or dB unit')
        if (manifest['source_backscatter_unit'], manifest['conversion_formula']) not in (
                ('linear_power', '10*log10(P)'), ('dB', 'none')):
            raise SpatialDataUnavailable('Invalid source backscatter conversion declaration')
        if self.science is None:
            raise SpatialDataUnavailable('Science evidence service unavailable')
        from backend.app.schemas.api import ValidatePairRequest
        try:
            pair = self.science.validate_pair(ValidatePairRequest(
                case_id=request.case_id, scene_t0_id=manifest['scene_ids'][0],
                scene_t1_id=manifest['scene_ids'][1], aoi_bbox_wgs84=request.aoi_bbox_wgs84))
        except Exception as exc:
            raise SpatialDataUnavailable('Scene pair compatibility check failed') from exc
        if not pair.result.compatible:
            raise SpatialDataUnavailable('Scene pair is scientifically incompatible')
        try:
            parent = self.science.get_evidence(manifest['parent_evidence_id'])
        except Exception as exc:
            raise SpatialDataUnavailable('Parent Evidence ID is not registered') from exc
        if list(parent.scene_ids) != manifest['scene_ids'] or request.polarization not in [str(p.value if hasattr(p, 'value') else p) for p in parent.polarizations]:
            raise SpatialDataUnavailable('Live raster provenance does not match science evidence')
        if str(parent.quality_status.value if hasattr(parent.quality_status, 'value') else parent.quality_status) not in ('COMPARABLE', 'LIMITED') or parent.valid_pixel_count == 0:
            raise SpatialDataUnavailable('Parent evidence is not comparable')
        provenance = parent.processing_metadata.model_dump() if hasattr(parent.processing_metadata, 'model_dump') else parent.processing_metadata
        crids = [provenance.get('t0_crid'), provenance.get('t1_crid')]
        if any(crids) and any(crid and crid != version for crid, version in zip(crids, manifest['scene_versions'])):
            raise SpatialDataUnavailable('Scene version does not match parent evidence')
        def parsed(value):
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        try:
            if parsed(provenance['t0_acquisition_utc']) != parsed(manifest['observation_times'][0]) or parsed(provenance['t1_acquisition_utc']) != parsed(manifest['observation_times'][1]):
                raise SpatialDataUnavailable('Observation timestamps do not match parent evidence')
        except (KeyError, ValueError, TypeError) as exc:
            raise SpatialDataUnavailable('Invalid observation timestamps') from exc
        def within(name: str) -> Path:
            if not isinstance(manifest[name], str) or not manifest[name]:
                raise SpatialDataUnavailable(f'Invalid {name} path')
            p = (path.parent / manifest[name]).resolve()
            if not p.is_relative_to(path.parent) or not p.is_file():
                raise SpatialDataUnavailable(f'Invalid {name} path')
            return p
        change_path, mask_path = within('change_geotiff'), within('valid_mask_geotiff')
        def sha256_file(file: Path) -> str:
            digest = hashlib.sha256()
            with file.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            return digest.hexdigest()
        if sha256_file(change_path) != manifest['change_sha256'] or sha256_file(mask_path) != manifest['valid_mask_sha256']:
            raise SpatialDataUnavailable('GeoTIFF checksum does not match manifest')
        try:
            change = rasterio.open(change_path)
            mask = rasterio.open(mask_path)
        except (rasterio.errors.RasterioError, OSError) as exc:
            if 'change' in locals():
                change.close()
            raise SpatialDataUnavailable('Live change or mask GeoTIFF cannot be opened') from exc
        with change, mask:
            if change.crs is None or change.crs.to_epsg() != 4326 or mask.crs != change.crs or mask.transform != change.transform or mask.shape != change.shape or change.count != 1 or mask.count != 1:
                raise SpatialDataUnavailable('Raster pair must be aligned single-band EPSG:4326 GeoTIFFs')
            if abs(change.transform.b) > 1e-10 or abs(change.transform.d) > 1e-10 or change.transform.a <= 0 or change.transform.e >= 0:
                raise SpatialDataUnavailable('Live rasters must be north-up and unrotated')
            resolution = manifest['pixel_resolution_deg']
            if (not isinstance(resolution, list) or len(resolution) != 2 or
                    any(not isinstance(x, (int, float)) or not np.isfinite(x) or x <= 0 for x in resolution) or
                    abs(change.transform.a - resolution[0]) > 1e-9 or
                    abs(abs(change.transform.e) - resolution[1]) > 1e-9):
                raise SpatialDataUnavailable('Declared pixel resolution does not match GeoTIFF')
            if change.nodata is None or mask.nodata is None:
                raise SpatialDataUnavailable('Live raster and mask must declare NoData')
            w, s, e, n = request.aoi_bbox_wgs84
            bounds = change.bounds
            if w < bounds.left or s < bounds.bottom or e > bounds.right or n > bounds.top:
                raise SpatialDataUnavailable('AOI outside live raster coverage')
            window = from_bounds(w, s, e, n, transform=change.transform).round_offsets().round_lengths()
            if window.width * window.height > 2_000_000 or window.width < 1 or window.height < 1:
                raise SpatialDataUnavailable('AOI pixel count outside supported range')
            delta = change.read(1, window=window)
            mask_values = mask.read(1, window=window)
            valid = ((mask_values > 0) & (mask.read_masks(1, window=window) > 0) &
                     np.isfinite(delta) & (change.read_masks(1, window=window) > 0))
            transform = change.window_transform(window)
            actual_bbox = [transform.c, transform.f + transform.e * delta.shape[0],
                           transform.c + transform.a * delta.shape[1], transform.f]
        metadata = {'data_kind': 'nisar', 'crs': 'EPSG:4326',
                    'scene_ids': manifest['scene_ids'], 'observation_times': manifest['observation_times'],
                    'polarization': request.polarization, 'method': manifest['method'],
                    'parent_evidence_id': manifest['parent_evidence_id'],
                    'scene_versions': manifest['scene_versions'],
                    'change_sha256': manifest['change_sha256'],
                    'valid_mask_sha256': manifest['valid_mask_sha256'],
                    'source_backscatter_unit': manifest['source_backscatter_unit'],
                    'conversion_formula': manifest['conversion_formula'],
                    'quality_status': str(parent.quality_status.value if hasattr(parent.quality_status, 'value') else parent.quality_status),
                    'limitations': list(parent.limitations) + ['Spatial ranking is descriptive and does not establish cause.']}
        return delta, valid, actual_bbox, metadata

    def analyze_spatial_changes(self, request: SpatialRequest) -> dict:
        delta, valid, bbox, meta = self._fixture(request) if request.mode == 'fixture' else self._live(request)
        if delta.ndim != 2 or valid.shape != delta.shape or not valid.any():
            raise SpatialDataUnavailable('No valid georeferenced change pixels')
        return {'delta': delta, 'valid': valid, 'bbox': bbox, 'metadata': meta}

    def rank_change_regions(self, analysis: dict, request: SpatialRequest) -> dict:
        delta, valid, bbox, meta = (analysis[k] for k in ('delta', 'valid', 'bbox', 'metadata'))
        # Four-neighbour connectivity prevents diagonal contacts from merging patches.
        candidate = valid & (np.abs(delta) >= request.threshold_db)
        labels, count = ndimage.label(candidate, structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
        height, width = delta.shape
        w, s, e, n = bbox
        regions = []
        for index in range(1, count+1):
            rows, cols = np.where(labels == index)
            if len(rows) < request.min_pixels:
                continue
            r0, r1, c0, c1 = int(rows.min()), int(rows.max()+1), int(cols.min()), int(cols.max()+1)
            block_valid = valid[r0:r1, c0:c1]
            coverage = float(block_valid.mean())
            if coverage < request.min_valid_fraction:
                continue
            values = delta[rows, cols]
            median_abs = float(np.median(np.abs(values)))
            region_bbox = [w+(e-w)*c0/width, n-(n-s)*r1/height,
                           w+(e-w)*c1/width, n-(n-s)*r0/height]
            # WGS84 geodesic cell area varies with latitude. Sum each occupied
            # raster row once, weighted by the number of component pixels.
            geod = Geod(ellps='WGS84')
            lon0, lon1 = w + (e-w)*c0/width, w + (e-w)*(c0+1)/width
            occupied_rows, row_counts = np.unique(rows, return_counts=True)
            area_km2 = 0.0
            for row, row_count in zip(occupied_rows, row_counts):
                lat_n = n - (n-s)*int(row)/height
                lat_s = n - (n-s)*(int(row)+1)/height
                cell_area, _ = geod.polygon_area_perimeter(
                    [lon0, lon1, lon1, lon0], [lat_s, lat_s, lat_n, lat_n])
                area_km2 += abs(cell_area) * int(row_count) / 1_000_000
            if area_km2 < request.min_area_km2:
                continue
            fingerprint = hashlib.sha256(json.dumps([meta['scene_ids'], meta.get('scene_versions'),
                                                      meta.get('parent_evidence_id'), meta.get('change_sha256'),
                                                      meta.get('valid_mask_sha256'), request.aoi_bbox_wgs84,
                                                      region_bbox, meta['polarization'], meta['method'],
                                                      round(median_abs, 6), round(float(np.median(values)), 6), len(rows)], sort_keys=True).encode()).hexdigest()[:16].upper()
            evidence_id = ('SYN-SP-' if meta['data_kind'] == 'synthetic' else 'NISAR-SP-') + fingerprint
            region = {'region_id': 'REG-' + fingerprint, 'rank': 0, 'bbox_wgs84': region_bbox,
                      'geometry': {'type': 'Polygon', 'coordinates': [[[region_bbox[0],region_bbox[1]],
                          [region_bbox[2],region_bbox[1]],[region_bbox[2],region_bbox[3]],
                          [region_bbox[0],region_bbox[3]],[region_bbox[0],region_bbox[1]]]]},
                      'crs': 'EPSG:4326', 'pixel_count': int(len(rows)), 'area_km2_approx': round(area_km2, 4),
                      'valid_pixel_percentage': round(coverage*100, 2),
                      'median_abs_change_db': round(median_abs, 3),
                      'median_signed_change_db': round(float(np.median(values)), 3),
                      'score': round(median_abs * coverage * np.log1p(len(rows)), 4),
                      'unit': 'dB', 'polarization': meta['polarization'],
                      'observation_times': meta['observation_times'], 'scene_ids': meta['scene_ids'],
                      'scene_versions': meta.get('scene_versions', []), 'method': meta['method'],
                      'evidence_ids': [evidence_id], 'quality_status': 'SIMULATED' if meta['data_kind'] == 'synthetic' else meta['quality_status'],
                      'limitations': meta['limitations'] + ['Region geometry is a bounding rectangle; component pixels are disjoint.']}
            self.evidence[evidence_id] = {'evidence_id': evidence_id, 'parent_evidence_id': meta['parent_evidence_id'],
                                          'data_kind': meta['data_kind'], 'bbox_wgs84': region_bbox, 'geometry': region['geometry'],
                                          'analysis_aoi_bbox_wgs84': request.aoi_bbox_wgs84,
                                          'crs': 'EPSG:4326', 'quality_status': region['quality_status'],
                                          'scene_ids': meta['scene_ids'], 'observation_times': meta['observation_times'],
                                          'scene_versions': meta.get('scene_versions', []),
                                          'change_sha256': meta.get('change_sha256'),
                                          'valid_mask_sha256': meta.get('valid_mask_sha256'),
                                          'source_backscatter_unit': meta.get('source_backscatter_unit'),
                                          'conversion_formula': meta.get('conversion_formula'),
                                          'polarization': meta['polarization'], 'method': meta['method'],
                                          'measurements': {'median_abs_change_db': region['median_abs_change_db'],
                                                           'median_signed_change_db': region['median_signed_change_db'],
                                                           'unit': 'dB', 'valid_pixel_percentage': region['valid_pixel_percentage'],
                                                           'pixel_count': region['pixel_count']},
                                          'limitations': meta['limitations']}
            regions.append(region)
        regions.sort(key=lambda region: (-region['score'], region['region_id']))
        for rank, region in enumerate(regions[:request.limit], 1):
            region['rank'] = rank
        return {'mode': request.mode, 'data_notice': 'SIMULATED DATA — NOT NASA OBSERVATIONS' if request.mode == 'fixture' else 'NISAR-derived B-team raster',
                'bbox_wgs84': request.aoi_bbox_wgs84, 'crs': 'EPSG:4326', 'threshold_db': request.threshold_db,
                'regions': regions[:request.limit], 'candidate_count': len(regions),
                'limitations': meta['limitations']}

    def focus_change_region(self, region: dict) -> dict:
        if region['evidence_ids'][0] not in self.evidence:
            raise SpatialDataUnavailable('Unknown region evidence')
        return {'type': 'map.focus_bbox', 'payload': {'bbox': region['bbox_wgs84'], 'crs': 'EPSG:4326'}}

    def compare_change_regions(self, first_id: str, second_id: str) -> dict:
        a, b = self.evidence.get(first_id), self.evidence.get(second_id)
        if not a or not b or any(a.get(key) != b.get(key) for key in
                                 ('scene_ids', 'scene_versions', 'polarization', 'data_kind',
                                  'parent_evidence_id', 'change_sha256', 'valid_mask_sha256',
                                  'method', 'analysis_aoi_bbox_wgs84')):
            raise SpatialDataUnavailable('Regions are missing or not comparable')
        return {'evidence_ids': [first_id, second_id], 'unit': 'dB',
                'median_abs_difference_db': round(a['measurements']['median_abs_change_db'] - b['measurements']['median_abs_change_db'], 3),
                'limitations': a['limitations']}

    def run(self, request: SpatialRequest) -> dict:
        return self.rank_change_regions(self.analyze_spatial_changes(request), request)
