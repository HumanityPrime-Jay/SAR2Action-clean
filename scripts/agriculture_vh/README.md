# Yunlin agricultural VH pipeline

Run from the repository root with a Python environment containing `asf_search`, `earthaccess`, `geopandas`, `rasterio`, `numpy`, `pandas`, `matplotlib`, `shapely`, `pyproj`, and `requests`:

```powershell
python -m scripts.agriculture_vh.run_pipeline --field-source "data/raw/P雲林縣_農田坵塊圖.zip" --metadata-only
python -m scripts.agriculture_vh.run_pipeline --field-source "data/raw/P雲林縣_農田坵塊圖.zip" --interactive-login
```

The first command searches real ASF metadata for August 1–November 14 in each year without downloading pixels. The second selects three matched Sentinel-1C scenes per year spanning the 2026 event, downloads only their VH and mask COGs, extracts 30 m interior pixel statistics for up to five official farmland candidates, and creates the observed plot and Evidence JSON. If a local `.netrc` already provides Earthdata authentication, omit `--interactive-login`. The pipeline obtains the Yunlin farmland ZIP from the [official Ministry of Agriculture source](https://data.moa.gov.tw/GetOpenDataFile.aspx?id=I75&FileType=DataMore&RID=44143) when it is missing. Never enter credentials into chat or a command argument.

Use `notebooks/yunlin_vh_analysis.ipynb` in Colab with the project and official Taixi GeoJSON copied to Google Drive. The notebook runs the same module, performs Colab-side connectivity checks, and offers a separate Earth Engine fallback requiring an authorized project. A failed search, download, raster QA, or minimum date count does not create a new real-data `vh_comparison.png`.

Evidence functions are exposed through `POST /api/agent/agriculture-vh/tool` with `tool` equal to `get_field_vh_timeseries`, `compare_seasonal_backscatter`, `check_event_temporal_alignment`, `evaluate_field_hypotheses`, or `find_missing_observations`. They return `UNKNOWN` until observed OPERA records exist. They do not change the NISAR TW-03 path.

OPERA product definitions: <https://www.jpl.nasa.gov/go/opera/products/rtc-product/>, <https://d2pn8kiwq2w21t.cloudfront.net/documents/ProductSpec_RTC-S1.pdf>. The product uses linear gamma0 power and a mask with class 0 for valid, unshadowed and unlaid-over samples. This pipeline converts each valid power pixel to dB before computing mean, median and quartiles. An official farmland boundary is only an `AGRICULTURAL_FIELD_CANDIDATE`; crop type and mixed land use require separate verification.
