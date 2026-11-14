"""Scan project deliverables for exact local Gemini credential without printing it."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / 'GERMINI API.txt'
TARGETS = [ROOT / name for name in ('backend', 'scripts', 'docs', 'frontend/src', 'frontend/dist',
                                    'frontend/test-results', 'frontend/playwright-report')]
SUFFIXES = {'.py', '.ps1', '.ts', '.tsx', '.js', '.json', '.md', '.html', '.css', '.txt', '.log', '.yaml', '.yml', '.env'}


def main() -> int:
    if not KEY_FILE.is_file():
        print('SECURITY_AUDIT_BLOCKED_CREDENTIAL_FILE_MISSING')
        return 2
    secret = KEY_FILE.read_text(encoding='utf-8-sig').strip()
    if secret.startswith('GEMINI_API_KEY='):
        secret = secret[len('GEMINI_API_KEY='):].strip()
    if len(secret) < 20:
        print('SECURITY_AUDIT_BLOCKED_CREDENTIAL_FORMAT')
        return 2
    needle = secret.encode('utf-8')
    scanned = 0
    leaks = []
    for folder in TARGETS:
        if not folder.exists():
            continue
        for path in folder.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if any(part in ('node_modules', '__pycache__', '.git') for part in path.parts):
                continue
            scanned += 1
            if needle in path.read_bytes():
                leaks.append(str(path.relative_to(ROOT)))
    for path in ROOT.iterdir():
        if path.is_file() and path != KEY_FILE and path.suffix.lower() in SUFFIXES:
            scanned += 1
            if needle in path.read_bytes():
                leaks.append(str(path.relative_to(ROOT)))
    output = {'status': 'PASS' if not leaks else 'FAIL', 'exact_credential_matches': len(leaks),
              'scanned_files': scanned, 'leaking_paths': leaks,
              'credential_file_in_deployment_scan': False,
              'git_history_audit': 'NOT_AVAILABLE_NO_GIT_REPOSITORY',
              'scope': [str(folder.relative_to(ROOT)) for folder in TARGETS]}
    (ROOT / 'docs/FINAL_SECURITY_AUDIT.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"FINAL_SECURITY_AUDIT {output['status']} matches {len(leaks)} files {scanned}")
    return 0 if not leaks else 1


if __name__ == '__main__':
    raise SystemExit(main())
