# Sources and license notes
- Project code authored for this package; no external satellite imagery, model weights or Hermes code are bundled.
- Official Hermes Agent: https://github.com/NousResearch/hermes-agent (check license, release and target commit at integration time).
- NASA/ASF NISAR docs: https://nisar-docs.asf.alaska.edu/gcov/
- NASA Space Apps hackathon terms and organizer pre-work policy: https://github.com/nasa/spaceapps/discussions/1827
- Backend Python runtime packages: FastAPI, Pydantic, uvicorn, NumPy and HTTPX; install from verified package indexes on your machine.
- Geospatial ingest helper requires Rasterio; include its license information in the final project dependency inventory.
- Synthetic NumPy fixture data generated from a fixed deterministic random seed; it does not originate from NISAR and must not be presented as observed satellite data.
- No real-world map boundary vectors were bundled. The frontend raster footprint is a schematic analysis viewport.
