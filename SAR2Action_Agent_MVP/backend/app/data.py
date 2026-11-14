"""NISAR-only data interface; synthetic fixture MUST NEVER be presented as observed satellite data."""
from __future__ import annotations
import os,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from .models import Scene, BoundingBox

DEMO_BBOX = BoundingBox(west=101.0,south=-0.9,east=102.6,north=0.7)
SCENE_IDS = ['SYNTHETIC_NISAR_A_20260818','SYNTHETIC_NISAR_B_20260909','SYNTHETIC_NISAR_C_20261012']

class DataUnavailable(RuntimeError): pass

class RadarDataService:
    def __init__(self):
        manifest_path = os.getenv('SAR2ACTION_LIVE_MANIFEST','').strip()
        self.mode='live' if manifest_path else 'fixture'
        self.bbox = DEMO_BBOX
        self.scenes:dict[str,Scene] = {}
        self.arrays:dict[tuple[str,str],np.ndarray] = {}
        self.masks:dict[str,np.ndarray] = {}
        self.pixel_spacing_m=None
        if self.mode=='live': self._read_live(Path(manifest_path))
        else: self._fixture()
        self.height,self.width = next(iter(self.arrays.values())).shape

    def _fixture(self):
        rng=np.random.default_rng(7816)
        yy,xx=np.mgrid[0:56,0:72]
        gaussian=np.exp(-((xx-41)**2/(2*10**2)+(yy-26)**2/(2*12**2)))
        secondary=np.exp(-((xx-20)**2/(2*6**2)+(yy-40)**2/(2*7**2)))
        for i,s in enumerate(SCENE_IDS):
            self.scenes[s]=Scene(scene_id=s,acquired_at=datetime.fromisoformat(['2026-08-18T02:00:00+00:00','2026-09-09T02:00:00+00:00','2026-10-12T02:00:00+00:00'][i]),polarizations=['HH','HV'],orbit_track='DEMO-42',look_direction='right',grid_id='DEMO-GRID-V1',product_maturity='SYNTHETIC',crid='DEMO',source_granule='NO_REAL_GRANULE',simulated=True)
            mask=rng.random((56,72))>.045
            mask[:3,:]=False
            self.masks[s]=mask
            for p,offset in [('HH',-11.2),('HV',-18.7)]:
                base=offset+1.2*np.sin(xx/10)+.7*np.cos(yy/8)
                value=base+rng.normal(0,.18,(56,72))
                if i==1: value=value+(3.2 if p=='HV' else 2.2)*gaussian-1.0*secondary
                if i==2: value=value+(4.6 if p=='HV' else 2.9)*gaussian-1.8*secondary
                self.arrays[(s,p)]=value.astype('float32')

    def _read_live(self,path:Path):
        if not path.is_file(): raise DataUnavailable(f'Live manifest missing: {path}')
        obj=json.loads(path.read_text('utf-8'))
        if obj.get('data_kind')!='nisar' or obj.get('schema_version')!='1': raise DataUnavailable('Live manifest must explicitly declare data_kind=nisar and schema_version=1')
        self.bbox=BoundingBox.model_validate(obj['bbox'])
        self.pixel_spacing_m=obj.get('pixel_spacing_m')
        for raw in obj['scenes']:
            s=Scene.model_validate(raw)
            if s.simulated or not s.source_granule or s.source_granule=='NO_REAL_GRANULE': raise DataUnavailable('Live scene must include real source granule')
            self.scenes[s.scene_id]=s
        cube_path=(path.parent / obj['raster_npz']).resolve()
        if not cube_path.is_relative_to(path.parent.resolve()): raise DataUnavailable('Data path may not escape manifest folder')
        if not cube_path.is_file(): raise DataUnavailable('Raster .npz not found')
        with np.load(cube_path,allow_pickle=False) as z:
            for scene in self.scenes.values():
                maskkey=f'{scene.scene_id}__valid'
                if maskkey not in z: raise DataUnavailable(f'Missing mask: {maskkey}')
                mask=np.asarray(z[maskkey],dtype=bool)
                self.masks[scene.scene_id]=mask
                for p in scene.polarizations:
                    key=f'{scene.scene_id}__{p}'
                    if key not in z:raise DataUnavailable(f'Missing raster: {key}')
                    arr=np.asarray(z[key],dtype=np.float32)
                    if arr.shape !=mask.shape or arr.ndim!=2:raise DataUnavailable(f'Invalid shape: {key}')
                    self.arrays[(scene.scene_id,p)]=arr
        shapes={a.shape for a in self.arrays.values()}
        if len(shapes)!=1: raise DataUnavailable('Live raster arrays must share one grid; B must align/resample before export')

    def scene_list(self):return sorted(self.scenes.values(),key=lambda x:x.acquired_at)

    def validate_pair(self,a:str,b:str)->dict:
        if a not in self.scenes or b not in self.scenes:
            return dict(compatible=False,reasons=['scene_not_found'],common_polarizations=[],valid_overlap_fraction=0)
        A,B=self.scenes[a],self.scenes[b]
        issues=[]
        if A.acquired_at>=B.acquired_at:issues.append('scene_before_not_earlier')
        if A.orbit_track!=B.orbit_track: issues.append('orbit_track_mismatch')
        if A.look_direction!=B.look_direction: issues.append('look_direction_mismatch')
        if A.grid_id!=B.grid_id:issues.append('grid_mismatch')
        if A.product_maturity!=B.product_maturity:issues.append('maturity_mismatch')
        if A.crid!=B.crid: issues.append('crid_mismatch')
        polar=sorted(set(A.polarizations)&set(B.polarizations))
        if not polar:issues.append('no_common_polarization')
        overlap=np.mean(self.masks[a]&self.masks[b])
        if overlap<.3:issues.append('insufficient_valid_overlap')
        return dict(compatible=not issues,reasons=issues,common_polarizations=polar,valid_overlap_fraction=round(float(overlap),4),mode=self.mode)

    def _pixels(self,bbox:BoundingBox):
        coverage=self.bbox
        # clip intersection; outside datasets have no valid cells
        x0=max(0,min(self.width, int(np.floor((bbox.west-coverage.west)/(coverage.east-coverage.west)*self.width))))
        x1=max(0,min(self.width, int(np.ceil((bbox.east-coverage.west)/(coverage.east-coverage.west)*self.width))))
        y0=max(0,min(self.height,int(np.floor((coverage.north-bbox.north)/(coverage.north-coverage.south)*self.height))))
        y1=max(0,min(self.height,int(np.ceil((coverage.north-bbox.south)/(coverage.north-coverage.south)*self.height))))
        return slice(y0,y1),slice(x0,x1)

    def change(self,a:str,b:str,p:str,bbox:BoundingBox):
        qa=self.validate_pair(a,b)
        if not qa['compatible']:raise DataUnavailable('pair QA failed: '+','.join(qa['reasons']))
        if p not in qa['common_polarizations']:raise DataUnavailable('polarization not present in both scenes')
        ys,xs=self._pixels(bbox)
        before=self.arrays[(a,p)][ys,xs]
        after=self.arrays[(b,p)][ys,xs]
        valid=self.masks[a][ys,xs]&self.masks[b][ys,xs]&np.isfinite(before)&np.isfinite(after)
        if valid.size==0 or not valid.any():raise DataUnavailable('no valid data inside selected AOI')
        delta=np.where(valid,after-before,np.nan)
        x=delta[valid]
        result={
          'unit':'dB','polarization':p,'n_valid':int(x.size),'n_total':int(valid.size),
          'valid_fraction':round(float(valid.mean()),4),'mean_delta_db':round(float(x.mean()),3),
          'median_delta_db':round(float(np.median(x)),3),'min_delta_db':round(float(x.min()),3),
          'max_delta_db':round(float(x.max()),3),'std_delta_db':round(float(x.std()),3),
          'fraction_abs_gt_2db':round(float((np.abs(x)>2).mean()),4),
          'method':'pairwise_gamma0_db_difference_v1',
        }
        return result,delta,valid

    def fingerprint(self,scene_ids:list[str],p:str,bbox:BoundingBox):
        out=[]
        ys,xs=self._pixels(bbox)
        for sid in scene_ids:
            s=self.scenes.get(sid)
            if not s or p not in s.polarizations: out.append(dict(scene_id=sid,median_db=None,n_valid=0));continue
            data=self.arrays[(sid,p)][ys,xs]
            valid=self.masks[sid][ys,xs]&np.isfinite(data)
            out.append(dict(scene_id=sid,acquired_at=s.acquired_at.isoformat(),median_db=round(float(np.median(data[valid])),3) if valid.any() else None,n_valid=int(valid.sum()),polarization=p))
        return out

    def grid(self,scene_before:str,scene_after:str,p:str):
        bbox=self.bbox
        stats,delta,valid=self.change(scene_before,scene_after,p,bbox)
        # 56x72 synthetic or limited-sized live grid, downsample to <= 84x84 tiles for frontend
        ys=np.linspace(0,delta.shape[0]-1,min(56,delta.shape[0]),dtype=int)
        xs=np.linspace(0,delta.shape[1]-1,min(72,delta.shape[1]),dtype=int)
        sample=delta[np.ix_(ys,xs)]
        return {'width':int(sample.shape[1]),'height':int(sample.shape[0]),'bbox':self.bbox.model_dump(), 'unit':'dB','values':[[round(float(t),2) if np.isfinite(t) else None for t in row] for row in sample], 'mode':self.mode,'stats':stats}
