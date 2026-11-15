"""Satellite Catalog Search (Phase C2) over NASA CMR / ASF / OPERA / NISAR.

Supports real NASA CMR HTTP queries and injectable transport for offline Fake Catalog tests.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

COLLECTION_SHORT_NAMES = {
    "OPERA_RTC_S1": "OPERA_L2_RTC-S1_V1",
    "NISAR_GCOV": "NISAR_L2_GCOV_BETA_V1",
    "SENTINEL1_SLC": "SENTINEL-1A_SLC",
}


@dataclass
class CatalogSearchQuery:
    aoi_bbox: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    start_utc: str
    end_utc: str
    product_family: str = "OPERA_RTC_S1"
    polarization: str | None = "VH"
    orbit_direction: str | None = None
    product_version: str | None = None
    page_size: int = 10


@dataclass
class CatalogScene:
    scene_id: str
    product_family: str
    acquisition_start_utc: str
    orbit_direction: str | None
    polarization: str | None
    product_version: str | None
    compatible: bool
    compatibility_notes: list[str] = field(default_factory=list)
    download_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_http_get(url: str, timeout: float = 10.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "SAR2Action-Research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class SatelliteCatalogSearcher:
    """Search NASA CMR for compatible OPERA RTC-S1 / NISAR / Sentinel-1 scenes."""

    def __init__(self, http_get: Callable[[str, float], dict[str, Any]] | None = None):
        self._http_get = http_get or _default_http_get

    def search(self, query: CatalogSearchQuery, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
        short_name = COLLECTION_SHORT_NAMES.get(query.product_family, query.product_family)
        bbox_str = ",".join(str(x) for x in query.aoi_bbox)
        params = {
            "short_name": short_name,
            "bounding_box": bbox_str,
            "temporal": f"{query.start_utc},{query.end_utc}",
            "page_size": str(query.page_size),
        }
        url = f"{CMR_GRANULES_URL}?{urllib.parse.urlencode(params)}"
        try:
            payload = self._http_get(url, timeout_seconds)
        except Exception as exc:
            return {
                "status": "SEARCH_ERROR",
                "is_live_network": self._http_get is _default_http_get,
                "error": f"{type(exc).__name__}: {exc}",
                "scenes": [],
            }

        entries = (payload.get("feed") or {}).get("entry") or []
        scenes: list[dict[str, Any]] = []
        for entry in entries:
            title = str(entry.get("title") or entry.get("producer_granule_id") or entry.get("id") or "")
            orbit = entry.get("orbit_direction")
            pol = entry.get("polarization")
            ver = entry.get("version") or entry.get("collection_concept_id")
            notes: list[str] = []
            compatible = True
            if query.orbit_direction and orbit and orbit.upper() != query.orbit_direction.upper():
                compatible = False
                notes.append(f"Orbit mismatch: {orbit} != {query.orbit_direction}")
            if query.polarization and pol and query.polarization.upper() not in pol.upper():
                compatible = False
                notes.append(f"Polarization mismatch: {pol} lacks {query.polarization}")
            if query.product_version and ver and str(ver) != str(query.product_version):
                compatible = False
                notes.append(f"Product version mismatch: {ver} != {query.product_version}")

            links = entry.get("links") or []
            dl = next((lk.get("href") for lk in links if str(lk.get("rel", "")).endswith("data#")), None)
            scenes.append(
                CatalogScene(
                    scene_id=title,
                    product_family=query.product_family,
                    acquisition_start_utc=str(entry.get("time_start", "")),
                    orbit_direction=orbit,
                    polarization=pol,
                    product_version=str(ver) if ver else None,
                    compatible=compatible,
                    compatibility_notes=notes,
                    download_url=dl,
                ).to_dict()
            )

        return {
            "status": "OK",
            "is_live_network": self._http_get is _default_http_get,
            "query_url": url,
            "count": len(scenes),
            "scenes": scenes,
        }
