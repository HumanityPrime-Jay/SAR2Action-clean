"""Plot only QA-passing real field observations; missing dates stay absent."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .compare_years import EVENT_START, EVENT_END

TAIWAN_TZ = timezone(timedelta(hours=8))


def plot(observations: list[dict], destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    usable = [r for r in observations if r.get("vh_median_db") is not None
              and "INSUFFICIENT_SPATIAL_SUPPORT" not in r.get("qa_flags", [])]
    fields = sorted({r["field_id"] for r in usable})
    if not fields or any(sum(r["field_id"] == f and r["year"] == y for r in usable) < 2
                         for f in fields for y in (2025, 2026)):
        raise RuntimeError("No real two-year VH curve with >=2 QA-passing observations per year")
    fig, axes = plt.subplots(len(fields), 1, figsize=(12, max(4.2, 3.4 * len(fields))), sharex=True)
    if len(fields) == 1:
        axes = [axes]
    colors = {2025: "#3279a8", 2026: "#dd7138"}
    for ax, field in zip(axes, fields):
        for year in (2025, 2026):
            rows = sorted((r for r in usable if r["field_id"] == field and r["year"] == year),
                          key=lambda r: r["acquisition_datetime"])
            x = [datetime.fromisoformat(r["acquisition_datetime"]).astimezone(TAIWAN_TZ)
                 .replace(year=2025, tzinfo=None) for r in rows]
            y = [r["vh_median_db"] for r in rows]
            segment_start = 0
            for index in range(1, len(rows) + 1):
                boundary = index == len(rows) or (
                    datetime.fromisoformat(rows[index]["acquisition_datetime"]) -
                    datetime.fromisoformat(rows[index - 1]["acquisition_datetime"])).days > 24
                if boundary:
                    ax.plot(x[segment_start:index], y[segment_start:index], marker="o", linewidth=1.6,
                            markersize=4, color=colors[year], label=str(year) if segment_start == 0 else None)
                    segment_start = index
        warning_start = datetime.fromisoformat(EVENT_START).replace(year=2025, tzinfo=None)
        warning_end = datetime.fromisoformat(EVENT_END).replace(year=2025, tzinfo=None)
        ax.axvspan(warning_start, warning_end, alpha=0.14,
                   color="red", label="2026 CWA land-warning window")
        ax.set_ylabel("VH backscatter (dB)")
        ax.set_title(field + " | agricultural field candidate; rice unverified", loc="left")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8, loc="best")
    axes[-1].set_xlabel("Taiwan month / day (aligned by local calendar date)")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    gee = any(r.get('source_collection') == 'COPERNICUS/S1_GRD' for r in usable)
    fig.suptitle("Taixi Earth Engine S1 GRD VH | observed dates only" if gee else
                 "Taixi OPERA RTC-S1 VH | observed dates only", fontsize=15)
    first = usable[0]
    source_note = ("Earth Engine COPERNICUS/S1_GRD VH already in dB (10 m)" if gee else
                   "NASA OPERA RTC-S1 gamma0 (30 m)")
    fig.text(0.01, 0.015,
             f"{source_note}; orbit {first['relative_orbit']} {first['orbit_direction']}"
             + ("." if gee else f"; burst {first['burst_id']}.") + "\n"
             "Lines connect observed dates only. Missing dates are not measurements; crop damage is unverified.", fontsize=8)
    fig.tight_layout(rect=(0, 0.085, 1, 0.95))
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("timeseries_json", type=Path)
    parser.add_argument("output_png", type=Path)
    args = parser.parse_args()
    data = json.loads(args.timeseries_json.read_text(encoding="utf-8"))
    if data.get("status") != "OBSERVED_OPERA_RTC_S1":
        raise SystemExit("Refusing to plot non-observed data")
    plot(data["observations"], args.output_png)
