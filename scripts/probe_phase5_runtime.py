"""Read actual llama.cpp context, GGUF native context and host memory metadata."""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import urllib.request
from pathlib import Path

import psutil


ROOT = Path(__file__).resolve().parents[1]
MODEL = Path('D:/models/gemma4-26b-qat/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf')
with MODEL.open('rb') as handle:
    header = handle.read(8 * 1024 * 1024)
if header[:4] != b'GGUF':
    raise SystemExit('Model is not a GGUF file')
def metadata_u32(key: str) -> int:
    raw = key.encode('ascii')
    index = header.find(raw)
    if index < 0 or index < 8 or struct.unpack_from('<Q', header, index-8)[0] != len(raw):
        raise ValueError(f'GGUF metadata key missing: {key}')
    if struct.unpack_from('<I', header, index+len(raw))[0] != 4:
        raise ValueError(f'GGUF metadata key is not uint32: {key}')
    return struct.unpack_from('<I', header, index+len(raw)+4)[0]
with urllib.request.urlopen('http://127.0.0.1:8086/props', timeout=10) as response:
    props = json.load(response)
gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.free,memory.total',
                      '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
report = {'gguf_file_size_bytes': MODEL.stat().st_size,
          'gguf_native_context_tokens': metadata_u32('gemma4.context_length'),
          'gguf_layers': metadata_u32('gemma4.block_count'),
          'server_actual_context_tokens': props['default_generation_settings']['n_ctx'],
          'server_slots': props['total_slots'],
          'gpu_readout': gpu.stdout.strip(),
          'system_ram_available_gib': round(psutil.virtual_memory().available / 2**30, 2),
          'hermes_minimum_context_tokens': 64000,
          'hermes_inference_status': 'BLOCKED_ACTUAL_SERVER_CONTEXT',
          'note': 'Native GGUF capability is not allocated server context. 64K was not attempted with near-full VRAM.'}
output = ROOT/'docs'/'phase5_runtime_probe.json'
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
