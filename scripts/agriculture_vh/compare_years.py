"""Observed-only year comparison; no interpolation or causal attribution."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .common import OUTPUT, write_json

PAIR_TOLERANCE_DAYS = 6
EVENT_START = "2026-10-22T11:30:00+08:00"
EVENT_END = "2026-10-24T14:30:00+08:00"


def _day_number(time: str) -> int:
    date = datetime.fromisoformat(time.replace("Z", "+00:00"))
    return (date.month, date.day)


def compare(observations: list[dict], *, persist: bool = True) -> dict:
    valid = [r for r in observations if r["vh_median_db"] is not None
             and "INSUFFICIENT_SPATIAL_SUPPORT" not in r["qa_flags"]]
    groups: dict[str, dict[int, list[dict]]] = defaultdict(lambda: {2025: [], 2026: []})
    for row in valid:
        groups[row["field_id"]][row["year"]].append(row)
    fields = []
    for field_id, by_year in sorted(groups.items()):
        pairings = []
        for current in by_year[2026]:
            current_month, current_day = _day_number(current["acquisition_datetime"])
            current_doy = datetime(2025, current_month, current_day).timetuple().tm_yday
            matches = []
            for old in by_year[2025]:
                if (old["relative_orbit"], old["orbit_direction"], old["burst_id"], old["product_version"],
                    old.get("source_collection", "OPERA_RTC-S1")) != (
                    current["relative_orbit"], current["orbit_direction"], current["burst_id"], current["product_version"],
                    current.get("source_collection", "OPERA_RTC-S1")):
                    continue
                old_month, old_day = _day_number(old["acquisition_datetime"])
                offset = abs(datetime(2025, old_month, old_day).timetuple().tm_yday - current_doy)
                if offset <= PAIR_TOLERANCE_DAYS:
                    matches.append((offset, old))
            if matches:
                gap, old = min(matches, key=lambda pair: pair[0])
                pairings.append({"2025_evidence_id": old["evidence_id"], "2026_evidence_id": current["evidence_id"],
                                 "2025_date": old["acquisition_datetime"], "2026_date": current["acquisition_datetime"],
                                 "day_of_year_gap": gap,
                                 "median_vh_difference_db": round(current["vh_median_db"] - old["vh_median_db"], 5),
                                 "platforms": [old["platform"], current["platform"]],
                                 "cross_platform": old["platform"] != current["platform"]})
        fields.append({"field_id": field_id, "valid_observations": {str(y): len(by_year[y]) for y in (2025, 2026)},
                       "date_matched_pairs": pairings,
                       "cross_platform_qa": "NEEDS_INCIDENCE_ANGLE_AND_PLATFORM_VALIDATION" if any(p["cross_platform"] for p in pairings) else "SAME_PLATFORM_IN_MATCHED_PAIRS",
                       "unusual_change": None, "typhoon_causation": "UNKNOWN"})
    source = "Earth Engine COPERNICUS/S1_GRD VH dB" if valid and valid[0].get("source_collection") == "COPERNICUS/S1_GRD" else "OPERA RTC-S1 VH gamma0"
    stats = {"status": "OBSERVED_DESCRIPTIVE_ONLY" if fields else "INSUFFICIENT_EVIDENCE",
             "source": source, "date_pair_tolerance_days": PAIR_TOLERANCE_DAYS,
             "interpolation": "NONE", "event_local_window": [EVENT_START, EVENT_END],
             "normal_baseline_validated": False, "fields": fields}
    if persist:
        write_json(OUTPUT / "vh_statistics.json", stats)
    return stats
