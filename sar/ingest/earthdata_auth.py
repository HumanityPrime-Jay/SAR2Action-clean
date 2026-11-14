"""Safe NASA Earthdata Login (.netrc) authenticated HTTP session helper.

Strict security rules:
- Reads credentials strictly from the user's local `~/.netrc` or `~/_netrc` outside the repository.
- Never prints, logs, returns, or serializes usernames, passwords, or tokens.
- Automatically handles NASA Earthdata OAuth redirects between `nisar.asf.earthdatacloud.nasa.gov`,
  `urs.earthdata.nasa.gov`, and signed CloudFront distribution URLs (`cloudfront.net`).
"""

from __future__ import annotations

import netrc
import pathlib
import requests

URS_HOST = "urs.earthdata.nasa.gov"


def find_local_netrc_path() -> pathlib.Path | None:
    """Locate the user's local `.netrc` or `_netrc` file outside the repository."""
    home = pathlib.Path.home()
    for name in (".netrc", "_netrc"):
        candidate = home / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def has_valid_earthdata_netrc() -> bool:
    """Return True if a local `.netrc` / `_netrc` exists with an entry for `urs.earthdata.nasa.gov`."""
    path = find_local_netrc_path()
    if path is None:
        return False
    try:
        parsed = netrc.netrc(str(path))
        auth = parsed.authenticators(URS_HOST)
        return auth is not None and bool(auth[0]) and bool(auth[2])
    except Exception:
        return False


class EarthdataOAuthSession(requests.Session):
    """Requests Session that attaches Earthdata Basic Auth only to `urs.earthdata.nasa.gov`."""

    def __init__(self) -> None:
        super().__init__()
        path = find_local_netrc_path()
        if path is None:
            raise RuntimeError("EARTHDATA_AUTH_REQUIRED: No local .netrc or _netrc found.")
        parsed = netrc.netrc(str(path))
        auth = parsed.authenticators(URS_HOST)
        if auth is None or not auth[0] or not auth[2]:
            raise RuntimeError(
                f"EARTHDATA_AUTH_REQUIRED: No {URS_HOST} entry found in {path.name}."
            )
        self._urs_creds = (auth[0], auth[2])

    def rebuild_auth(
        self,
        prepared_request: requests.PreparedRequest,
        response: requests.Response,
    ) -> None:
        headers = prepared_request.headers
        url = prepared_request.url or ""
        redirect_host = requests.utils.urlparse(url).hostname or ""

        if redirect_host == URS_HOST:
            prepared_request.prepare_auth(self._urs_creds)
        elif "Authorization" in headers:
            del headers["Authorization"]
