"""Download the pinned RTC assets with local Earthdata credentials."""
import sys
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from build_demo import INPUT, asset_records
from sar.ingest.earthdata_auth import EarthdataOAuthSession


def main():
    INPUT.mkdir(exist_ok=True)
    scenes, _ = asset_records()
    failures = 0
    for scene in scenes:
        for band, asset in scene["assets"].items():
            if asset["downloaded"]:
                continue
            path = INPUT / asset["filename"]
            part = path.with_suffix(".tif.part")
            try:
                with EarthdataOAuthSession() as session, session.get(
                    asset["url"], params={"tw01": uuid4().hex},
                    stream=True, timeout=(15, 45)
                ) as response:
                    if response.status_code != 200:
                        params = parse_qs(urlsplit(response.url).query)
                        needs_approval = "/approve_app" in params.get("resolution_url", [""])[0]
                        print(scene["cmr_granule_id"], band, response.status_code,
                              "application_approval_required" if needs_approval else "download_failed")
                        failures += 1
                        continue
                    blocks = response.iter_content(131072)
                    first = next(blocks, b"")
                    if not first.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
                        raise ValueError("Invalid TIFF signature")
                    with part.open("wb") as stream:
                        stream.write(first)
                        for block in blocks:
                            stream.write(block)
                    if part.stat().st_size != asset["expected_bytes"]:
                        raise ValueError("Size differs from ASF metadata")
                    part.replace(path)
                    print(scene["cmr_granule_id"], band, path.stat().st_size)
            except Exception as exc:
                print(scene["cmr_granule_id"], band, type(exc).__name__)
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
