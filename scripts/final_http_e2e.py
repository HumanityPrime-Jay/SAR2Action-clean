"""Exercise the running loopback FastAPI cache investigation with exact evidence checks."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EID = 'E-FLAGSHIP-OKI-004'


def main() -> int:
    client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=30)
    source = next(x for x in json.loads((ROOT / 'data/cache/evidence_store.json').read_text(encoding='utf-8'))['records']
                  if x['evidence_id'] == EID)
    base = {'case_id': 'case-flagship-oki-f2', 'aoi_id': 'AOI-OKI-04',
            'aoi_bbox_wgs84': [105.08, -2.92, 105.24, -2.76]}
    health = client.get('/api/health')
    cases = client.get('/api/cases')
    fp = client.post('/api/radar-fingerprint', json=base)
    ev = client.get('/api/evidence/' + EID)
    agent = client.post('/api/agent/investigate', json={**base, 'query': 'Explain HH/HV and evidence',
                        'data_mode': 'cache', 'agent_mode': 'deterministic', 'session_id': 'final-http-e2e'})
    story = client.post('/api/agent/story', json={'session_id': 'final-http-e2e',
                         'evidence_id': EID, 'locale': 'en', 'audience': 'scientific'})
    other = client.post('/api/agent/investigate', json={**base, 'aoi_id': 'AOI-OKI-02',
                        'aoi_bbox_wgs84': [104.98, -3.32, 105.16, -3.14],
                        'query': 'Explain evidence', 'data_mode': 'cache',
                        'agent_mode': 'deterministic', 'session_id': 'final-http-e2e'})
    stale = client.get('/api/agent/story/' + story.json().get('story_id', 'missing'))
    body = agent.json()
    checks = {
        'all_routes_200': all(r.status_code == 200 for r in (health, cases, fp, ev, agent, story, other, stale)),
        'case_present': any(c['case_id'] == base['case_id'] for c in cases.json().get('cases', [])),
        'same_evidence_id': fp.json().get('evidence_id') == ev.json().get('evidence_id') == EID and body.get('evidence_ids') == [EID],
        'hh_exact': body.get('fingerprint_details', {}).get('hh_delta_median_db') == source['summary_statistics']['per_polarization']['HH']['median_delta_db'] == -0.2128,
        'hv_exact': body.get('fingerprint_details', {}).get('hv_delta_median_db') == source['summary_statistics']['per_polarization']['HV']['median_delta_db'] == -0.2056,
        'pixel_count_exact': body.get('fingerprint_details', {}).get('valid_pixel_count') == source['valid_pixel_count'] == 3148830,
        'scene_pair_exact': body.get('fingerprint_details', {}).get('scene_ids') == ev.json().get('scene_ids') == source['scene_ids'],
        'aoi_exact': body.get('fingerprint_details', {}).get('roi_id') == 'AOI-OKI-04',
        'map_focused': any(a.get('type') == 'map.focus_bbox' and a.get('payload', {}).get('bbox') == base['aoi_bbox_wgs84'] for a in body.get('map_actions', [])),
        'story_consistent': len(story.json().get('frames', [])) == 5 and all(f.get('evidence_ids') == [EID] for f in story.json().get('frames', [])),
        'cross_aoi_stale': other.json().get('evidence_ids') != [EID] and stale.json().get('status') == 'stale',
    }
    output = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
              'http_statuses': {name: r.status_code for name, r in
                                [('health', health), ('cases', cases), ('fingerprint', fp), ('evidence', ev),
                                 ('agent', agent), ('story', story), ('other_aoi', other), ('stale_story', stale)]},
              'evidence_id': EID, 'source_hdf5_independently_verified': False}
    (ROOT / 'docs/FINAL_HTTP_E2E.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"FINAL_HTTP_E2E {output['status']} {sum(checks.values())}/{len(checks)}")
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
