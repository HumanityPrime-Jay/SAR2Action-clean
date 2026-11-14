"""Download only selected OPERA VH and mask COGs with Earthdata auth."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from shapely.geometry import shape

from .common import RASTER_DIR, ROOT, write_json
from .search_opera import eligible_scene
from .compare_years import EVENT_START, EVENT_END

MAX_COG_BYTES = 60_000_000


def select_minimum(rows: list[dict], fields: dict, per_year: int = 3) -> tuple[list[dict], str]:
    if not fields.get("features"):
        raise RuntimeError("No official agricultural field candidates")
    event_start = datetime.fromisoformat(EVENT_START)
    event_end = datetime.fromisoformat(EVENT_END)
    # Same platform, burst, direction, track and product version minimize processing differences.
    for feature in fields["features"]:
        geom = shape(feature["properties"]["interior_geometry"])
        groups: dict[tuple, dict[int, list[dict]]] = {}
        for row in rows:
            if not eligible_scene(row, geom):
                continue
            key = (str(row["relative_orbit"]), row["orbit_direction"], row["burst_id"],
                   row["product_version"], row["platform"])
            groups.setdefault(key, {2025: [], 2026: []})[row["year"]].append(row)
        viable = []
        for key, group in groups.items():
            current = group[2026]
            before = [r for r in current if datetime.fromisoformat(r["acquisition_datetime"]) < event_start]
            after = [r for r in current if datetime.fromisoformat(r["acquisition_datetime"]) > event_end]
            if before and after and len({r["acquisition_datetime"][:10] for r in current}) >= per_year:
                viable.append((key, group))
        if not viable:
            continue
        viable.sort(key=lambda x: (sum(len(x[1][y]) for y in (2025, 2026))), reverse=True)
        for _, group in viable:
            current = group[2026]
            before = max((r for r in current if datetime.fromisoformat(r["acquisition_datetime"]) < event_start),
                         key=lambda r: r["acquisition_datetime"])
            after = min((r for r in current if datetime.fromisoformat(r["acquisition_datetime"]) > event_end),
                        key=lambda r: r["acquisition_datetime"])
            chosen_current = [before, after]
            others = sorted((r for r in current if r not in chosen_current),
                            key=lambda r: abs((datetime.fromisoformat(r["acquisition_datetime"]) - event_start).total_seconds()))
            for row in others:
                if len(chosen_current) >= per_year:
                    break
                if row["acquisition_datetime"][:10] not in {r["acquisition_datetime"][:10] for r in chosen_current}:
                    chosen_current.append(row)
            if len(chosen_current) < per_year:
                continue
            chosen_old = []
            for current_row in chosen_current:
                date = datetime.fromisoformat(current_row["acquisition_datetime"])
                matches = sorted((r for r in group[2025] if r["acquisition_datetime"][:10] not in
                                  {x["acquisition_datetime"][:10] for x in chosen_old}),
                                 key=lambda r: abs((datetime.fromisoformat(r["acquisition_datetime"]).replace(year=2026)
                                                    - date).total_seconds()))
                if not matches or abs((datetime.fromisoformat(matches[0]["acquisition_datetime"]).replace(year=2026)
                                       - date).days) > 6:
                    break
                chosen_old.append(matches[0])
            if len(chosen_old) == per_year:
                return sorted(chosen_old + chosen_current, key=lambda r: r["acquisition_datetime"]), feature["properties"]["field_id"]
    raise RuntimeError("No field has event-bracketing VH/mask scenes and matched 2025 dates on one platform/burst/track/version")


def _session(interactive: bool):
    import os
    token_file = os.environ.get("EARTHDATA_TOKEN_FILE")
    if token_file:
        path = Path(token_file).resolve()
        if not path.is_file() or ROOT in path.parents:
            raise RuntimeError("Earthdata token file must exist outside the repository")
        token = path.read_text(encoding="utf-8-sig").strip()
        if not token or "\n" in token:
            raise RuntimeError("Earthdata token file must contain one bearer token")
        import requests
        session = requests.Session()
        session.headers.update({"Authorization": "Bearer " + token})
        return session
    from sar.ingest.earthdata_auth import EarthdataOAuthSession, has_valid_earthdata_netrc
    if has_valid_earthdata_netrc():
        return EarthdataOAuthSession()
    if not interactive:
        raise RuntimeError("EARTHDATA_AUTH_REQUIRED: run --interactive-login locally or in Colab; do not pass credentials to this program")
    import earthaccess
    earthaccess.login(strategy="interactive")
    return earthaccess.get_requests_https_session()


def _download_one(session, url: str, target: Path) -> dict:
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname.endswith("earthdatacloud.nasa.gov"):
        raise RuntimeError("Refusing non-ASF data URL")
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".tif.part")
    digest = hashlib.sha256()
    size = 0
    with session.get(url, stream=True, timeout=(15, 90)) as response:
        response.raise_for_status()
        if int(response.headers.get("Content-Length", "0")) > MAX_COG_BYTES:
            raise RuntimeError("COG exceeds bounded download size")
        with part.open("wb") as stream:
            for chunk in response.iter_content(1 << 20):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_COG_BYTES:
                    raise RuntimeError("COG exceeds bounded download size")
                stream.write(chunk)
                digest.update(chunk)
    if part.open("rb").read(4) not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        raise RuntimeError("Downloaded file is not TIFF")
    part.replace(target)
    return {"path": str(target), "bytes": size, "sha256": digest.hexdigest(), "source_url": url}


def download(selected: list[dict], *, interactive: bool = False) -> list[dict]:
    session = _session(interactive)
    records = []
    for row in selected:
        files = {}
        for layer in ("vh", "mask"):
            url = row[layer + "_url"]
            if not url:
                raise RuntimeError(f"{row['granule_id']} lacks {layer} URL")
            target = RASTER_DIR / (row["granule_id"] + "_" + ("VH" if layer == "vh" else "mask") + ".tif")
            if target.is_file():
                import rasterio
                with rasterio.open(target) as src:
                    if not src.crs or src.count != 1:
                        raise RuntimeError(f"Invalid cached raster: {target}")
                files[layer] = {"path": str(target), "bytes": target.stat().st_size,
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "source_url": url}
            else:
                files[layer] = _download_one(session, url, target)
        records.append({"scene": row, "files": files})
        write_json(RASTER_DIR / "download_manifest.json", records)
    return records
