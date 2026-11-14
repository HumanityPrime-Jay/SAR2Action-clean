#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/backend"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port "${SAR2ACTION_PORT:-8765}"
