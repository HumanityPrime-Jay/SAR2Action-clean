from __future__ import annotations
from pathlib import Path
import os
from fastapi import FastAPI,HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .models import ScenePairRequest,ChangeRequest,QueryRequest,StoryRequest
from .data import RadarDataService,DataUnavailable
from .agent import Investigator,VERSION

app=FastAPI(title='SAR2Action AI Investigator',version='1.0.0')
try:
    source=RadarDataService()
except (DataUnavailable,ValueError,KeyError) as exc:
    # FAIL CLOSED; misconfigured live inputs cannot silently fall back to synthetic data
    raise RuntimeError(f'Unable to load live NISAR dataset: {exc}') from exc
investigator=Investigator(source)

@app.get('/api/health')
def health():return {'status':'ok','mode':source.mode,'hermes_api_status':'not_checked','hermes_opt_in':investigator.narrator.enabled,'method_version':VERSION,'dataset': 'SIMULATED DATA — NOT NASA OBSERVATIONS (SYNTHETIC)' if source.mode=='fixture' else 'NISAR-derived B-provided data'}

@app.get('/api/capabilities')
def capabilities():return {'available_tools':['list_nisar_observations','validate_scene_pair','compute_change_map','summarize_selection','get_radar_fingerprint','inspect_provenance','set_map_view','build_evidence_story'],'mode':source.mode,'bbox':source.bbox.model_dump(),'polarizations':sorted(set().union(*(set(s.polarizations) for s in source.scenes.values()))),'scientific_limits':['Backscatter difference is not causal attribution','GCOV dB cannot directly represent cm displacement']}

@app.get('/api/scenes')
def scene_list():return {'mode':source.mode,'scenes':[s.model_dump(mode='json') for s in source.scene_list()],'dataset_bbox':source.bbox.model_dump()}

@app.post('/api/pair/validate')
def pair_validate(r:ScenePairRequest):return source.validate_pair(r.scene_before,r.scene_after)

@app.post('/api/change/compute')
def change_compute(r:ChangeRequest):
    try:
        stats,_,_=source.change(r.scene_before,r.scene_after,r.polarization,r.bbox)
        return {'status':'ok','mode':source.mode,'stats':stats,'layer_id':'difference','method_version':VERSION}
    except DataUnavailable as exc:raise HTTPException(422,detail=str(exc))

@app.get('/api/grid')
def grid(scene_before:str,scene_after:str,polarization:str='HV'):
    if polarization not in ('HH','HV','VV','VH'):raise HTTPException(400,'Invalid polarization')
    try:return source.grid(scene_before,scene_after,polarization)
    except DataUnavailable as exc:raise HTTPException(422,str(exc))

@app.post('/api/agent/investigate')
async def agent_run(r:QueryRequest):return (await investigator.investigate(r)).model_dump(mode='json')

@app.get('/api/evidence/{evidence_id}')
def evidence(evidence_id:str):
    obj=investigator.evidence(evidence_id)
    if not obj:raise HTTPException(404,'Evidence ID not found')
    return obj.model_dump(mode='json')

@app.post('/api/story/build')
def story_build(req:StoryRequest):
    try:return investigator.build_story(req).model_dump(mode='json')
    except ValueError as exc:raise HTTPException(422,str(exc))

@app.get('/api/story/{story_id}/validate')
def story_validate(story_id:str):
    result=investigator.story_check(story_id)
    if not result:raise HTTPException(404,'Story ID not found')
    return result

@app.get('/api/operations/{session_id}')
def operations(session_id:str):
    if len(session_id)>72 or not session_id.replace('-','').replace('_','').isalnum():raise HTTPException(400,'Invalid session')
    return {'session_id':session_id,'events':investigator.logs.get(session_id,[])}

_ROOT=Path(__file__).resolve().parents[2]
_FRONTEND=_ROOT/'frontend'
@app.get('/')
def homepage():return FileResponse(_FRONTEND/'index.html')
app.mount('/static',StaticFiles(directory=_FRONTEND),name='static')
