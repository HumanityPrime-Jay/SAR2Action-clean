# Scientific Data Provisioning & Bootstrap Guide

SAR2Action separates **tracked recorded-demo artifacts** (JSON/GeoJSON/PNG in `data/exports/` and `frontend/public/studio/`) from **excluded large binary scientific rasters** (NISAR GeoTIFFs, OPERA RTC-S1 COGs, and TW-03 QA rasters).

## Configuration: `SAR2ACTION_DATA_ROOT`

Set `SAR2ACTION_DATA_ROOT` to point to the directory containing the local scientific data tree (defaults to `<repo>/data` when unset or empty):

```powershell
$env:SAR2ACTION_DATA_ROOT = "<path-to-sar2action-data>"
```

When `SAR2ACTION_DATA_ROOT` does not contain the excluded raw rasters:
- **Recorded Demo mode** in Investigation Studio works from the verified, tracked JSON/PNG snapshots in `frontend/public/studio/` and `data/exports/`.
- **Live Investigation V3** fails closed with HTTP `422` (`Required science asset unavailable: ...`) rather than fabricating NISAR or Sentinel-1 VH values.

## Data Sources, Scene IDs, Versions, and SHA-256

### 1. NISAR L2 GCOV Subset (Typhoon CHAMPI, Taixi)
- **Data Source**: NASA ASF Earthdata Cloud (`NISAR_L2_GCOV_PROVISIONAL_V1` / `NISAR_L2_GCOV_V1`)
- **Access & Authorization**: Requires a free NASA Earthdata Login account (`~/.netrc` or interactive `earthaccess` login). Do not commit credentials.
- **Pre-event Scene**: `NISAR_L2_PR_GCOV_030_039_A_013_4005_DHDH_A_20260908T212423_20260908T212501_P05023_N_F_J_001` (CRID `P05023`, `PROVISIONAL`)
- **Post-event Scene**: `NISAR_L2_PR_GCOV_031_039_A_013_4005_DHDH_A_20261026T212321_20261026T212359_P05036_N_F_J_001` (CRID `P05036`, `PROVISIONAL`)
- **Expected SHA-256**: Verified against `data/exports/typhoon_champi/science_manifest.json` (13 input/output files).

### 2. OPERA L2 RTC-S1 v1.0 (Sentinel-1C VH, Yunlin Five Fields)
- **Data Source**: NASA ASF Earthdata Cloud (`OPERA_L2_RTC-S1`, Product Version `v1.0`, Relative Orbit `105`, Burst `105-224320-IW3`)
- **Access & Authorization**: Requires NASA Earthdata Login (`~/.netrc` or `earthaccess`). Redistributable only per NASA Earthdata/ASF terms; large COGs are excluded from Git.
- **Granules & SHA-256**:
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20251008T215154Z_20251009T011425Z_S1C_30_v1.0` (`_VH.tif`: `6cfc01875c279b25753821a017677b0cc009d7eea43395542088d4c1af70a1ec`, `_mask.tif`: `62daaf7ea503f71362b62f810cab8f7d1ad2585eb6a59002b69ad9b2e4a53d36`)
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20251020T215154Z_20251021T015140Z_S1C_30_v1.0` (`_VH.tif`: `4e552710092b31d638f9fa9d02ad06deb33ff44947da5665abea92aad05f95cb`, `_mask.tif`: `a81ed25eb95a5d26460bf0d54b54cfaaa7e142ffd21d5b8f0abe7cef9c659454`)
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20251101T215154Z_20251102T011849Z_S1C_30_v1.0` (`_VH.tif`: `bfe3c016228cb17c7265e11e3b189dfb2b2190e2a504c8ca2f650537fc9a82a8`, `_mask.tif`: `876c111950eec30b1cf8d25f2b727da2b21f8b818795c46cf1b33992a8b7729d`)
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20261010T215156Z_20261011T203150Z_S1C_30_v1.0` (`_VH.tif`: `8bd0cfc981fa7cfeac36f23d60de46de032115c0eb210600adc9390dad11d901`, `_mask.tif`: `a73953df4a570c61980d2afc8e5a00bdc8fd355f6fde0a4da6fc097b0323d8ac`)
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20261022T215156Z_20261023T065025Z_S1C_30_v1.0` (`_VH.tif`: `e19d4674835ee9174afb99b171c24f2de8222e0266d270c8fc66779e5bc49d6c`, `_mask.tif`: `6e85a5e1e39014cf4abf7e7607b566925a4b5b2a822827a4707aec2679e64184`)
  - `OPERA_L2_RTC-S1_T105-224320-IW3_20261103T215156Z_20261105T191651Z_S1C_30_v1.0` (`_VH.tif`: `f3a7c227da82ecad38e6e1edab859c9b4ae6bcc2e0f889177546f4c7d690a952`, `_mask.tif`: `7b1462b1ff88645e6995c1e9115036e82a325f782605b6ff81af8b1ad4db1577`)

## Verification & Bootstrap Commands

```powershell
# Print source scene IDs, versions, and SHA-256 digests
python -m scripts.bootstrap_science_data --print-sources

# Verify local data root against all SHA-256 manifests
python -m scripts.bootstrap_science_data --data-root "<path-to-sar2action-data>" --check

# Download OPERA COGs using existing Earthdata credentials (~/.netrc)
python -m scripts.bootstrap_science_data --data-root "<path-to-sar2action-data>" --download-opera
```
