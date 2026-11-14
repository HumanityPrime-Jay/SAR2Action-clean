#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
python -m pytest backend/tests -q
python -m compileall -q backend/app
node --check frontend/app.js
