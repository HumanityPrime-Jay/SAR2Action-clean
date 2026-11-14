"""Official ASF Search and NASA Earthdata CMR metadata discovery client for NISAR L2 GCOV.

Enforces the Phase 1 Metadata-First rule:
- Searches official ASF / NASA Earthdata CMR catalogs without downloading multi-GB HDF5 granules.
- Extracts all available UMM-G / ASF metadata fields into `NormalizedSceneMetadata`.
- Parses official NISAR L2 GCOV granule naming convention tokens when present, while keeping
  any unavailable field as `None` (never fabricating values).
"""

from __future__ import annotations

import re
from typing import Any

import asf_search
import httpx

from sar.catalog.models import (
    COVERAGE_CODE_MAP,
    ORBIT_FIDELITY_CODE_MAP,
    SDS_LOCATION_CODE_MAP,
    NormalizedSceneMetadata,
)

CMR_GRANULES_UMM_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
CMR_COLLECTIONS_JSON_URL = "https://cmr.earthdata.nasa.gov/search/collections.json"

# Official NISAR L2 GCOV filename / granule ID pattern:
# NISAR_L2_PR_GCOV_<cycle>_<track>_<pass>_<frame>_<mode>_<pol>_<band>_<t0>_<t1>_<crid>_...
NISAR_GCOV_GRANULE_RE = re.compile(
    r"^NISAR_L2_(?P<prod_stream>[A-Z]{2})_GCOV_"
    r"(?P<cycle>\d{3})_"
    r"(?P<track>\d{3})_"
    r"(?P<pass_dir>[AD])_"
    r"(?P<frame>\d{3})(?:_\d+)?_"
    r"(?P<mode>\d{4})_"
    r"(?P<pol_code>[A-Z0-9]{4})_"
    r"(?P<band_code>[A-Z])_"
    r"(?P<start_dt>\d{8}T\d{6})_"
    r"(?P<end_dt>\d{8}T\d{6})_"
    r"(?P<crid>[A-Za-z0-9]{6})"
    r"(?:_(?P<accuracy>[A-Z])_(?P<coverage>[FP])_(?P<sds>[A-Z])_(?P<counter>\d{3}))?"
)

POL_CODE_MAP: dict[str, list[str]] = {
    "DHDH": ["HH", "HV"],
    "DVDV": ["VV", "VH"],
    "SHNA": ["HH"],
    "SVNA": ["VV"],
    "QPQP": ["HH", "HV", "VH", "VV"],
    "QPHV": ["HH", "HV", "VH", "VV"],
}


def parse_nisar_gcov_granule_id(scene_id: str) -> dict[str, Any]:
    """Extract deterministic metadata tokens embedded in an official NISAR L2 GCOV granule ID.

    Returns empty dict if `scene_id` does not follow the standard NISAR L2 GCOV naming convention.
    """
    clean_id = scene_id.removesuffix(".h5").removesuffix(".hdf5")
    match = NISAR_GCOV_GRANULE_RE.match(clean_id)
    if not match:
        return {}

    gd = match.groupdict()
    pass_dir = "ASCENDING" if gd["pass_dir"] == "A" else "DESCENDING"
    track_num = int(gd["track"])
    frame_num = int(gd["frame"])
    pol_code = gd["pol_code"]
    polarizations = POL_CODE_MAP.get(pol_code)
    crid = gd["crid"]
    maturity = None
    if crid.startswith("P"):
        maturity = "PROVISIONAL"
    elif crid.startswith("B") or crid.startswith("T"):
        maturity = "BETA"
    elif crid.startswith("V") or crid.startswith("R"):
        maturity = "VALIDATED"

    cov_flag = gd.get("coverage")
    is_full_frame: bool | None = None
    if cov_flag == "F":
        is_full_frame = True
    elif cov_flag == "P":
        is_full_frame = False

    acc_flag = gd.get("accuracy")
    fidelity_label = ORBIT_FIDELITY_CODE_MAP.get(acc_flag) if acc_flag else None
    cov_label = COVERAGE_CODE_MAP.get(cov_flag) if cov_flag else None
    sds_flag = gd.get("sds")
    sds_label = SDS_LOCATION_CODE_MAP.get(sds_flag, sds_flag) if sds_flag else None

    return {
        "product_type": "GCOV",
        "band": "L" if gd["band_code"] in ("A", "L") else gd["band_code"],
        "orbit_direction": pass_dir,
        "relative_orbit": track_num,
        "frame_number": frame_num,
        "track_or_frame": f"T{track_num:03d}_F{frame_num:03d}",
        "polarizations": polarizations,
        "crid": crid,
        "product_maturity": maturity,
        "orbit_pointing_fidelity_code": acc_flag,
        "orbit_pointing_fidelity": fidelity_label,
        "coverage_code": cov_flag,
        "coverage_indicator": cov_label,
        "is_full_frame": is_full_frame,
        "sds_location_code": sds_flag,
        "sds_location": sds_label,
    }


def _polygon_points_to_bbox_and_geojson(
    points: list[dict[str, float]],
) -> tuple[list[float] | None, dict[str, Any] | None]:
    if not points:
        return None, None
    lons = [float(p["Longitude"]) for p in points]
    lats = [float(p["Latitude"]) for p in points]
    bbox = [min(lons), min(lats), max(lons), max(lats)]
    ring = [[float(p["Longitude"]), float(p["Latitude"])] for p in points]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    geojson = {"type": "Polygon", "coordinates": [ring]}
    return bbox, geojson


def normalize_cmr_umm_item(
    item: dict[str, Any],
    *,
    candidate_id: str,
    aoi_id: str,
    aoi_name: str,
    event_context: str = "",
) -> NormalizedSceneMetadata:
    """Convert a single NASA CMR UMM-G granule entry into `NormalizedSceneMetadata`."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})

    scene_id = umm.get("GranuleUR") or meta.get("native-id") or "UNKNOWN_GRANULE"
    parsed_tokens = parse_nisar_gcov_granule_id(scene_id)

    coll_ref = umm.get("CollectionReference", {})
    short_name = coll_ref.get("ShortName")
    version = coll_ref.get("Version")

    # Temporal extent
    temporal = umm.get("TemporalExtent", {}).get("RangeDateTime", {})
    start_utc = temporal.get("BeginningDateTime")
    end_utc = temporal.get("EndingDateTime")

    # Spatial extent
    bbox: list[float] | None = None
    geojson: dict[str, Any] | None = None
    horiz = (
        umm.get("SpatialExtent", {})
        .get("HorizontalSpatialDomain", {})
        .get("Geometry", {})
    )
    gpolygons = horiz.get("GPolygons", [])
    if gpolygons:
        pts = gpolygons[0].get("Boundary", {}).get("Points", [])
        bbox, geojson = _polygon_points_to_bbox_and_geojson(pts)
    elif horiz.get("BoundingRectangles"):
        rect = horiz["BoundingRectangles"][0]
        bbox = [
            float(rect["WestBoundingCoordinate"]),
            float(rect["SouthBoundingCoordinate"]),
            float(rect["EastBoundingCoordinate"]),
            float(rect["NorthBoundingCoordinate"]),
        ]
        geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]],
                    [bbox[0], bbox[1]],
                ]
            ],
        }

    # AdditionalAttributes from CMR UMM-G
    add_attrs: dict[str, list[Any]] = {}
    for attr in umm.get("AdditionalAttributes", []):
        name = attr.get("Name")
        vals = attr.get("Values", [])
        if name and vals:
            add_attrs[name.upper()] = vals

    orbit_dir = parsed_tokens.get("orbit_direction")
    for key in ("ASCENDING_DESCENDING", "FLIGHT_DIRECTION", "PASS_DIRECTION"):
        if key in add_attrs and add_attrs[key]:
            orbit_dir = str(add_attrs[key][0]).upper()
            break

    if not orbit_dir:
        orbit_domains = umm.get("OrbitCalculatedSpatialDomains", [])
        if orbit_domains:
            orb_val = orbit_domains[0].get("OrbitalModelName") or orbit_domains[0].get(
                "EquatorCrossingDateTime"
            )
            _ = orb_val

    look_dir = None
    for key in ("LOOK_DIRECTION", "POINTING_DIRECTION"):
        if key in add_attrs and add_attrs[key]:
            look_dir = str(add_attrs[key][0]).upper()
            break
    if not look_dir:
        for plat in umm.get("Platforms", []):
            for inst in plat.get("Instruments", []):
                for char in inst.get("Characteristics", []):
                    if str(char.get("Name", "")).upper() == "LOOKDIRECTION" and char.get("Value"):
                        look_dir = str(char["Value"]).upper()
                        break

    polarizations = parsed_tokens.get("polarizations")
    for key in (
        "FREQUENCY_A_POLARIZATION",
        "POLARIZATION",
        "POLARIZATION_TYPE",
        "FREQUENCYPOLARIZATION",
    ):
        if key in add_attrs and add_attrs[key]:
            raw_pols = [str(v).upper() for v in add_attrs[key]]
            clean_pols: list[str] = []
            for p in raw_pols:
                for ch in ("HH", "HV", "VH", "VV"):
                    if ch in p and ch not in clean_pols:
                        clean_pols.append(ch)
            if clean_pols:
                polarizations = clean_pols
                break

    track_or_frame = parsed_tokens.get("track_or_frame")
    rel_orbit = parsed_tokens.get("relative_orbit")
    frame_num = parsed_tokens.get("frame_number")
    if "PATH_NUMBER" in add_attrs or "TRACK_NUMBER" in add_attrs:
        t_val = (add_attrs.get("TRACK_NUMBER") or add_attrs.get("PATH_NUMBER") or [None])[0]
        if t_val is not None:
            try:
                rel_orbit = int(t_val)
            except ValueError:
                pass
    if "FRAME_NUMBER" in add_attrs:
        f_val = add_attrs["FRAME_NUMBER"][0]
        try:
            frame_num = int(f_val)
        except ValueError:
            pass
    if rel_orbit is not None and frame_num is not None and not track_or_frame:
        track_or_frame = f"T{rel_orbit:03d}_F{frame_num:03d}"

    # File size & download URLs
    size_bytes: int | None = None
    archive_info = (
        umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
    )
    for info in archive_info:
        if "SizeInBytes" in info:
            size_bytes = int(info["SizeInBytes"])
            break
        elif "Size" in info:
            unit = str(info.get("SizeUnit", "MB")).upper()
            mult = 1024**3 if "GB" in unit else (1024**2 if "MB" in unit else 1)
            size_bytes = int(float(info["Size"]) * mult)
            break

    download_url: str | None = None
    s3_url: str | None = None
    for rel in umm.get("RelatedUrls", []):
        url = rel.get("URL", "")
        rtype = rel.get("Type", "")
        if "GET DATA" in rtype and url.startswith("https://") and url.endswith((".h5", ".hdf5")):
            download_url = url
        elif url.startswith("s3://") and url.endswith((".h5", ".hdf5")):
            s3_url = url
        elif "GET DATA" in rtype and url.startswith("https://") and not download_url:
            download_url = url

    maturity = parsed_tokens.get("product_maturity")
    if short_name:
        if "PROVISIONAL" in short_name.upper():
            maturity = "PROVISIONAL"
        elif "BETA" in short_name.upper():
            maturity = "BETA"
        elif "VALIDATED" in short_name.upper():
            maturity = "VALIDATED"

    pge_ver = umm.get("PGEVersionClass", {}).get("PGEVersion")
    prod_ver = (add_attrs.get("PRODUCT_VERSION") or [None])[0]
    proc_version = pge_ver or prod_ver or version

    bw_a = (add_attrs.get("FREQUENCY_A_RANGE_BANDWIDTH") or [None])[0]
    full_frame = (add_attrs.get("FULL_FRAME") or [None])[0]
    is_full_bool: bool | None = parsed_tokens.get("is_full_frame")
    if full_frame is not None:
        if str(full_frame).strip().upper() == "TRUE":
            is_full_bool = True
        elif str(full_frame).strip().upper() == "FALSE":
            is_full_bool = False

    stack_id = (add_attrs.get("STACK_ID") or [None])[0]
    note_parts = []
    if meta.get("concept-id"):
        note_parts.append(f"concept_id={meta['concept-id']}")
    if stack_id:
        note_parts.append(f"stack_id={stack_id}")
    if bw_a:
        note_parts.append(f"freqA_bw_mhz={bw_a}")
    if full_frame:
        note_parts.append(f"full_frame={full_frame}")
    if prod_ver:
        note_parts.append(f"product_version={prod_ver}")

    return NormalizedSceneMetadata(
        candidate_id=candidate_id,
        aoi_id=aoi_id,
        aoi_name=aoi_name,
        event_context=event_context,
        scene_id=scene_id,
        product_short_name=short_name,
        product_type=parsed_tokens.get("product_type") or "GCOV",
        acquisition_start_utc=start_utc,
        acquisition_end_utc=end_utc,
        band=parsed_tokens.get("band") or "L",
        polarizations=polarizations,
        orbit_direction=orbit_dir,
        look_direction=look_dir,
        track_or_frame=track_or_frame,
        relative_orbit=rel_orbit,
        frame_number=frame_num,
        product_maturity=maturity,
        crid=parsed_tokens.get("crid"),
        processing_version=proc_version,
        grid_spacing_m=None,
        is_full_frame=is_full_bool,
        bbox=bbox,
        bounding_geometry=geojson,
        catalog_source="NASA_CMR",
        catalog_reference=meta.get("concept-id"),
        download_url=download_url,
        s3_url=s3_url,
        approx_file_size_bytes=size_bytes,
        metadata_status="CATALOG_ONLY",
        local_status="NOT_DOWNLOADED",
        notes="; ".join(note_parts) if note_parts else None,
    )


def search_cmr_nisar_gcov(
    *,
    short_name: str = "NISAR_L2_GCOV_PROVISIONAL_V1",
    bbox: list[float] | None = None,
    candidate_id: str = "Candidate",
    aoi_id: str = "AOI",
    aoi_name: str = "AOI",
    event_context: str = "",
    page_size: int = 200,
    timeout_s: float = 30.0,
) -> list[NormalizedSceneMetadata]:
    """Query NASA Earthdata CMR for NISAR L2 GCOV granules (metadata only, unauthenticated)."""
    params: dict[str, Any] = {
        "short_name": short_name,
        "page_size": page_size,
        "sort_key": "-start_date",
    }
    if bbox is not None:
        params["bounding_box"] = ",".join(str(v) for v in bbox)

    with httpx.Client(timeout=timeout_s) as client:
        resp = client.get(CMR_GRANULES_UMM_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    items = payload.get("items", [])
    return [
        normalize_cmr_umm_item(
            item,
            candidate_id=candidate_id,
            aoi_id=aoi_id,
            aoi_name=aoi_name,
            event_context=event_context,
        )
        for item in items
    ]


def search_asf_nisar_gcov(
    *,
    bbox: list[float] | None = None,
    candidate_id: str = "Candidate",
    aoi_id: str = "AOI",
    aoi_name: str = "AOI",
    event_context: str = "",
    max_results: int = 200,
) -> list[NormalizedSceneMetadata]:
    """Query ASF Search API for NISAR GCOV products and normalize into `NormalizedSceneMetadata`."""
    kwargs: dict[str, Any] = {
        "dataset": "NISAR",
        "processingLevel": ["GCOV"],
        "maxResults": max_results,
    }
    if bbox is not None:
        w, s, e, n = bbox
        kwargs["intersectsWith"] = (
            f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
        )

    results = asf_search.search(**kwargs)
    normalized: list[NormalizedSceneMetadata] = []
    for prod in results:
        props = getattr(prod, "properties", {}) or {}
        geom = getattr(prod, "geometry", None)
        scene_id = str(props.get("sceneName") or props.get("fileID") or "UNKNOWN")
        parsed_tokens = parse_nisar_gcov_granule_id(scene_id)

        prod_bbox: list[float] | None = None
        if geom and geom.get("coordinates"):
            coords = geom["coordinates"][0]
            if isinstance(coords[0][0], (list, tuple)):
                coords = coords[0]
            lons = [float(c[0]) for c in coords]
            lats = [float(c[1]) for c in coords]
            prod_bbox = [min(lons), min(lats), max(lons), max(lats)]

        pol_raw = props.get("polarization")
        polarizations = parsed_tokens.get("polarizations")
        if pol_raw:
            if isinstance(pol_raw, list):
                polarizations = [str(p).upper() for p in pol_raw]
            elif isinstance(pol_raw, str):
                polarizations = [
                    p.strip().upper()
                    for p in re.split(r"[,+/;\s]+", pol_raw)
                    if p.strip() in ("HH", "HV", "VH", "VV")
                ] or polarizations

        rel_orbit = props.get("pathNumber") or parsed_tokens.get("relative_orbit")
        frame_num = props.get("frameNumber") or parsed_tokens.get("frame_number")
        track_or_frame = parsed_tokens.get("track_or_frame")
        if rel_orbit is not None and frame_num is not None and not track_or_frame:
            track_or_frame = f"T{int(rel_orbit):03d}_F{int(frame_num):03d}"

        size_bytes = props.get("bytes")
        if size_bytes is not None:
            try:
                size_bytes = int(size_bytes)
            except (TypeError, ValueError):
                size_bytes = None

        short_name = props.get("collectionName") or "NISAR_L2_GCOV_PROVISIONAL_V1"
        maturity = parsed_tokens.get("product_maturity")
        if "PROVISIONAL" in str(short_name).upper():
            maturity = "PROVISIONAL"
        elif "BETA" in str(short_name).upper():
            maturity = "BETA"

        normalized.append(
            NormalizedSceneMetadata(
                candidate_id=candidate_id,
                aoi_id=aoi_id,
                aoi_name=aoi_name,
                event_context=event_context,
                scene_id=scene_id,
                product_short_name=short_name,
                product_type=str(props.get("processingLevel") or "GCOV"),
                acquisition_start_utc=props.get("startTime"),
                acquisition_end_utc=props.get("stopTime"),
                band=parsed_tokens.get("band") or "L",
                polarizations=polarizations,
                orbit_direction=(
                    str(props.get("flightDirection")).upper()
                    if props.get("flightDirection")
                    else parsed_tokens.get("orbit_direction")
                ),
                look_direction=props.get("lookDirection"),
                track_or_frame=track_or_frame,
                relative_orbit=int(rel_orbit) if rel_orbit is not None else None,
                frame_number=int(frame_num) if frame_num is not None else None,
                product_maturity=maturity,
                crid=parsed_tokens.get("crid"),
                processing_version=props.get("pgeVersion"),
                grid_spacing_m=None,
                bbox=prod_bbox,
                bounding_geometry=geom,
                catalog_source="ASF_SEARCH",
                catalog_reference=props.get("GranuleUR") or props.get("fileID"),
                download_url=props.get("url"),
                s3_url=(props.get("s3Urls") or [None])[0] if props.get("s3Urls") else None,
                approx_file_size_bytes=size_bytes,
                metadata_status="CATALOG_ONLY",
                local_status="NOT_DOWNLOADED",
                notes=props.get("beamModeType"),
            )
        )
    return normalized
