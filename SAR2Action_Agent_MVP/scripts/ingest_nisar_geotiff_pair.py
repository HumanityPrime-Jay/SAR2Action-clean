#!/usr/bin/env python3
"""Prepare a small, already co-registered pair of NISAR GCOV-derived GeoTIFFs for SAR2Action.

Input provenance must be supplied by B/SAR lead; do not falsely label non-NISAR rasters as NISAR.
Grid is deliberately *not* silently reprojected. Reprojection/corrections belong in B's science pipeline.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.crs import CRS

def go():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before',required=True,help='Before NISAR GCOV polarization GeoTIFF')
    ap.add_argument('--after',required=True,help='After NISAR GCOV polarization GeoTIFF on EXACT same grid')
    ap.add_argument('--before-id',required=True)
    ap.add_argument('--after-id',required=True)
    ap.add_argument('--before-date',required=True,help='ISO 8601 UTC, e.g. 2026-08-19T02:00:00Z')
    ap.add_argument('--after-date',required=True)
    ap.add_argument('--before-granule',required=True,help='Exact real ASF/NISAR source granule identifier')
    ap.add_argument('--after-granule',required=True)
    ap.add_argument('--orbit-track',required=True)
    ap.add_argument('--look-direction',required=True,choices=['left','right'])
    ap.add_argument('--crid',required=True)
    ap.add_argument('--product-maturity',required=True)
    ap.add_argument('--polarization',required=True,choices=['HH','HV','VV','VH'])
    ap.add_argument('--input-units',choices=['db','power'],required=True,help='Use power for GCOV covariance diagonal gamma-nought power')
    ap.add_argument('--output-dir',required=True)
    a=ap.parse_args()
    if not a.before_id.isidentifier() or not a.after_id.isidentifier():sys.exit('Scene IDs must be simple identifiers (letters, numbers, underscores).')
    if a.before_id==a.after_id:sys.exit('Before and after scene IDs must differ')
    try:
        from datetime import datetime
        d0=datetime.fromisoformat(a.before_date.replace('Z','+00:00'));d1=datetime.fromisoformat(a.after_date.replace('Z','+00:00'))
        assert d0.tzinfo and d1.tzinfo and d0<d1
    except Exception:sys.exit('Dates must be timezone-aware ISO 8601, with before < after')
    with rasterio.open(a.before) as left,rasterio.open(a.after) as right:
        if left.crs!=CRS.from_epsg(4326) or right.crs!=left.crs:
            sys.exit('Input rasters must be georeferenced EPSG:4326; ask B to reproject first')
        if left.transform!=right.transform or left.shape!=right.shape:
            sys.exit('Scene pair is not on the exact same geocoded pixel grid; ask B to align before running')
        if left.width>1024 or left.height>1024:sys.exit('Input AOI is too large. Crop to <=1024x1024 original pixels first.')
        if abs(left.transform.b)>1e-10 or abs(left.transform.d)>1e-10 or left.transform.a<=0 or left.transform.e>=0:
            sys.exit('Only north-up EPSG:4326 rasters supported')
        bbox={'west':left.bounds.left,'south':left.bounds.bottom,'east':left.bounds.right,'north':left.bounds.top}
        if bbox['east']-bbox['west']>5 or bbox['north']-bbox['south']>5:sys.exit('AOI must be <=5x5 degrees')
        r0=left.read(1).astype('float32');r1=right.read(1).astype('float32')
        m0=(left.read_masks(1)>0)&np.isfinite(r0);m1=(right.read_masks(1)>0)&np.isfinite(r1)
        if a.input_units=='power':
            m0 &= r0>0;m1 &= r1>0
            r0=np.where(m0,10*np.log10(np.maximum(r0,1e-30)),np.nan)
            r1=np.where(m1,10*np.log10(np.maximum(r1,1e-30)),np.nan)
        o=Path(a.output_dir);o.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(o/'radar_pair.npz',**{
            f'{a.before_id}__{a.polarization}':r0,
            f'{a.after_id}__{a.polarization}':r1,
            f'{a.before_id}__valid':m0,
            f'{a.after_id}__valid':m1})
        scenes=[]
        for scene,date,gran in [(a.before_id,a.before_date,a.before_granule),(a.after_id,a.after_date,a.after_granule)]:
            scenes.append({'scene_id':scene,'acquired_at':date,'polarizations':[a.polarization],
                'orbit_track':a.orbit_track,'look_direction':a.look_direction,
                'grid_id':f'EPSG4326-{left.transform.a:.9f}-{left.transform.e:.9f}-{left.width}x{left.height}',
                'product_maturity':a.product_maturity,'crid':a.crid,'source_granule':gran,'simulated':False})
        manifest={'schema_version':'1','data_kind':'nisar','bbox':bbox,'pixel_spacing_m':None,
            'raster_npz':'radar_pair.npz','scenes':scenes,
            'notes':'Only processed NISAR-derived data; pixels are in decibel backscatter; not burn severity or displacement. Science QA must verify orbit and acquisition compatibility.'}
        (o/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
        print('Created',o/'manifest.json','with',left.width*left.height,'raster pixels.')
        print('QA REQUIREMENT: Confirm B/SAR-lead approved orbit, CRID, calibration, geometry, valid-mask rules.')
if __name__=='__main__':go()
