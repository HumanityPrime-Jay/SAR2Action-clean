"""Checks configured Hermes API. Never prints secrets or invokes Hermes tools."""
from __future__ import annotations
import os,sys,httpx
base=os.getenv('HERMES_API_URL','http://127.0.0.1:8642/v1/chat/completions')
key=os.getenv('HERMES_API_KEY','')
if not key:
    print('NOT CONFIGURED: HERMES_API_KEY unset. SAR2Action deterministic fallback remains available.');sys.exit(2)
url=base.rsplit('/v1/chat/completions',1)[0]+'/v1/models'
try:
 r=httpx.get(url,headers={'Authorization':'Bearer '+key},timeout=5)
 r.raise_for_status()
 print('Hermes HTTP server reachable; models endpoint responded HTTP',r.status_code)
 print('NOTE: This proves API connectivity only, not that built-in tool permissions are sandboxed.')
except Exception as exc:
 print('Hermes not reachable:',type(exc).__name__);sys.exit(1)
