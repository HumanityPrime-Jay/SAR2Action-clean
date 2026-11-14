"""Refuse to start Hermes if its isolated API profile exposes built-in tools."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools


profile = Path(os.environ['HERMES_HOME']).resolve()
assert profile == Path(__file__).resolve().parents[1] / '.phase4_hermes'
config = load_config()
assert _get_platform_tools(config, 'api_server') == set(), 'Hermes built-in tools enabled'
model = config['model']
assert model['provider'] == 'custom'
endpoint = urlparse(model['base_url'])
assert endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1' and endpoint.port == 8086
env_text = (profile / '.env').read_text(encoding='utf-8-sig')
assert 'API_SERVER_HOST=127.0.0.1' in env_text
assert 'API_SERVER_PORT=8642' in env_text
assert 'API_SERVER_KEY=' in env_text
print('Hermes profile restricted to localhost and zero built-in tools')
