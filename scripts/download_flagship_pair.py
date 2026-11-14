"""Download the locked 2-scene Primary Flagship Pair (Phase 2C.5).

Locked Pair (Candidate F2 — T010_F176 ASCENDING, South Sumatra / OKI Peatland Corridor):
- T0 (2026-09-06): NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001.h5 (5,930,745,856 bytes)
- T1 (2026-09-18): NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001.h5 (5,934,940,160 bytes)
"""

from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sar.ingest.earthdata_auth import EarthdataOAuthSession  # noqa: E402

SCENES = [
    (
        "NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001",
        5_930_745_856,
    ),
    (
        "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001",
        5_934_940_160,
    ),
]


def download_granule(session: EarthdataOAuthSession, scene_id: str, expected_bytes: int, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{scene_id}.h5"
    part_path = out_dir / f"{scene_id}.h5.part"

    if final_path.exists() and final_path.stat().st_size == expected_bytes:
        print(f"[SKIP] {final_path.name} already exists with exact size {expected_bytes:,} bytes.", flush=True)
        return final_path

    url = f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/{scene_id}/{scene_id}.h5"
    resume_pos = part_path.stat().st_size if part_path.exists() else 0
    headers = {"Range": f"bytes={resume_pos}-"} if resume_pos > 0 else None

    print(f"[START] Downloading {scene_id}.h5 (resume_pos={resume_pos:,} / {expected_bytes:,} bytes)...", flush=True)
    t_start = time.perf_counter()
    last_log = t_start

    resp = session.get(url, stream=True, timeout=120, headers=headers)
    resp.raise_for_status()

    mode = "ab" if (resume_pos > 0 and resp.status_code == 206) else "wb"
    if mode == "wb":
        resume_pos = 0

    bytes_written = resume_pos
    with open(part_path, mode) as f:
        for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            bytes_written += len(chunk)
            now = time.perf_counter()
            if now - last_log >= 10.0:
                elapsed = now - t_start
                speed_mb_s = ((bytes_written - resume_pos) / (1024**2)) / max(elapsed, 0.001)
                pct = 100.0 * bytes_written / expected_bytes
                print(
                    f"  [{scene_id[-25:]}] {bytes_written / (1024**3):.2f} / {expected_bytes / (1024**3):.2f} GiB "
                    f"({pct:.1f}%) at {speed_mb_s:.1f} MiB/s",
                    flush=True,
                )
                last_log = now

    resp.close()
    actual_size = part_path.stat().st_size
    if actual_size != expected_bytes:
        raise RuntimeError(f"Size mismatch for {scene_id}: got {actual_size}, expected {expected_bytes}")

    with open(part_path, "rb") as f:
        sig = f.read(8)
    if sig != b"\x89HDF\r\n\x1a\n":
        raise RuntimeError(f"Invalid HDF5 signature for {scene_id}: {sig!r}")

    if final_path.exists():
        final_path.unlink()
    part_path.rename(final_path)
    total_time = time.perf_counter() - t_start
    print(f"[DONE] {final_path.name} verified ({actual_size:,} bytes in {total_time:.1f}s).", flush=True)
    return final_path


def main() -> None:
    session = EarthdataOAuthSession()
    scenes_dir = ROOT / "data" / "raw" / "scenes"
    for sid, expected_bytes in SCENES:
        download_granule(session, sid, expected_bytes, scenes_dir)
    print("All 2 locked flagship granules downloaded and verified!", flush=True)


if __name__ == "__main__":
    main()
