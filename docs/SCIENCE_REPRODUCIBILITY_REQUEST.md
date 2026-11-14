# NISAR source reproducibility request

**Status: source HDF5 verification pending.** The three delivered JSON files pass internal schema and cross-file checks. They do not establish that the cached pixel values were computed from the named NASA granules. D team does not need a copy of the 13.3 GB HDF5 files.

## B team source-machine run

Run from the SAR2Action repository on the machine holding the two original GCOV granules. The script reads the files and cache, writes only the specified report, and does not access credentials.

```powershell
python scripts/verify_nisar_source.py --t0 "<path-to-T0-GCOV.h5>" --t1 "<path-to-T1-GCOV.h5>" --cache-dir data/cache --evidence-id E-FLAGSHIP-OKI-004 --output nisar_source_reproducibility.json
```

Send the report and the processing code commit or release identifier. Please do not send secrets or URLs with tokens. A passing report is needed before the product can show **Verified Source**. A failure requires investigation; cached scientific values must not be edited to make the report pass.

If archived georeferenced change rasters or masks exist, add `--derived "<path-to-product.tif>"` once per file. The report will include their SHA-256 hashes. Send the raster CRS, transform and nodata definition alongside the report; this script does not certify those archived files' spatial metadata.

The report checks granule IDs and observation dates against the cache, computes SHA-256 of both HDF5 products and all three cache files, checks the AOI bounding box, EPSG CRS and 10 m grid spacing, applies the recorded GCOV mask rule to both scenes and HH/HV channels, recounts valid pixels, independently recomputes the median of valid pixelwise dB differences, and checks 32 seeded random pixels. It hashes the recalculated valid mask and HH/HV delta arrays. The sampling is a targeted reproducibility check, not an independent review of every source pixel or a statistical significance test.

## Minimum handoff metadata

| Item | Required evidence |
| --- | --- |
| Original scenes | Full T0/T1 NISAR granule IDs and product versions/CRIDs |
| Source integrity | SHA-256 of both complete HDF5 files; acquisition source or publication reference |
| AOI | AOI-OKI-04 geometry and CRS, not only its display name |
| Grid | EPSG code, pixel resolution, alignment and geotransform |
| Polarization | HH/HV dataset names, units and radiometric calibration |
| QA | Mask value semantics, intersection across scenes/channels, excluded counts, RFI/looks handling |
| Radiometry | Linear power to dB formula and nonpositive/NaN policy |
| Change | Per-pixel T1−T0 computation, signed/magnitude percentiles, AOI aggregation definition |
| Processing | Code commit/release, library versions and exact invocation |
| Spot check | Seeded random pixel locations, raw power values or independently computed deltas |
| Derived products | SHA-256 of any archived georeferenced change rasters and masks, with CRS and provenance |

For AOI-OKI-04, the cache reports HH −0.2128 dB, HV −0.2056 dB and 3,148,830 common valid pixels. The audit must confirm these are medians of pixelwise differences under the documented mask. A stable control area, source raster review, uncertainty model and independent ground observations are separately needed before a claim of significant disturbance or peat fire. This request does not ask B team to transfer the full HDF5 to D team.
