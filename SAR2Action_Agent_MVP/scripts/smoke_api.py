from __future__ import annotations
import os,sys,json
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
scene=c.get('/api/scenes').json()
ids=[x['scene_id'] for x in scene['scenes']]
assert len(ids)>=2
assert c.post('/api/pair/validate',json={'scene_before':ids[0],'scene_after':ids[-1]}).json()['compatible']
box=scene['dataset_bbox']
result=c.post('/api/agent/investigate',json={'scene_before':ids[0],'scene_after':ids[-1],
    'polarization':scene['scenes'][0]['polarizations'][0],'bbox':box,'session_id':'smoke',
    'query':'Show measured change, evidence and uncertainty', 'intent':'story'}).json()
assert result['status']=='completed',result
assert len(result['story']['frames'])==5
for evidence_id in result['evidence_refs']:
    assert c.get(f'/api/evidence/{evidence_id}').status_code==200
print(json.dumps({'status':'passed','mode':result['mode'],'tool_steps':len(result['steps']),
   'evidence_refs':result['evidence_refs'],'story_frames':len(result['story']['frames'])},indent=2))
