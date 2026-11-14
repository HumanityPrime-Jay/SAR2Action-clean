# SAR2Action — Science Contract

> **Status:** ACTIVE & NON-NEGOTIABLE (`science-contract-v1.0`)  
> **Scope:** All SAR ingestion, validation, radiometric change calculations, API schemas, frontend map labels, AI Investigator prompts/guardrails, and Evidence Stories in **SAR2Action**.

---

## 1. What NISAR Level-2 GCOV Measures

### 1.1 Primary Scientific Product
- **Product:** **NISAR L-band Level-2 GCOV** (Geocoded Polarimetric Covariance Matrix).
- **Wavelength / Frequency:** L-band ($\lambda \approx 24\text{ cm}$, center frequency $\approx 1.257\text{ GHz}$).
- **Measured Physical Quantity:** Radiometrically Terrain-Corrected (RTC) gamma-naught ($\gamma^0$) radar backscatter power in the diagonal covariance terms:
  - `HHHH` ($P_{\text{HH}}$): Horizontal transmit, horizontal receive linear power.
  - `HVHV` ($P_{\text{HV}}$): Horizontal transmit, vertical receive linear power (when acquired in dual-pol or quad-pol modes).
  - `VVVV` ($P_{\text{VV}}$): Vertical transmit, vertical receive linear power (when applicable).
- **Physical Sensitivity of L-band Backscatter ($\gamma^0$):**
  - **Woody structure & canopy volume** (trunks, primary branches, biomass geometry).
  - **Surface roughness** at the centimeter-to-decimeter scale.
  - **Dielectric constant** (surface and near-surface moisture content, standing water / inundation state).
  - **Local viewing & terrain geometry** (incidence angle, aspect, residual layover/shadow).

### 1.2 Strict Product Boundary (No Mixing of Physical Meanings)
- **GCOV $\neq$ GUNW:** GCOV measures backscatter power ($\gamma^0$). It does **not** measure interferometric phase or line-of-sight surface displacement/subsidence (`GUNW`).
- **GCOV $\neq$ SME2:** GCOV backscatter changes can be influenced by dielectric moisture shifts, but GCOV is **not** a calibrated volumetric soil moisture retrieval (`SME2`), nor can either product be automatically interpreted as underground peat water-table depth.

---

## 2. What SAR2Action Calculates

Let $P(t, p)$ denote the valid, finite, strictly positive linear $\gamma^0$ backscatter power ($P(t, p) > 0$) at acquisition time $t \in \{T_0, T_1\}$ (with $T_0 < T_1$) and polarization $p \in \{\text{HH}, \text{HV}, \text{VV}\}$.

### 2.1 Single-Epoch Radiometric Backscatter (dB)
$$B(t, p) = 10 \log_{10}\!\left(P(t, p)\right) \quad [\text{dB}]$$
Computed **only** where pixel $(x, y)$ passes all validity masks at epoch $t$.

### 2.2 Signed Multi-Temporal Backscatter Change (dB)
$$\Delta(p) = B(T_1, p) - B(T_0, p) = 10 \log_{10}\!\left(\frac{P(T_1, p)}{P(T_0, p)}\right) \quad [\text{dB}]$$
- $\Delta(p) > 0$: Radar backscatter power increased between $T_0$ and $T_1$.
- $\Delta(p) < 0$: Radar backscatter power decreased between $T_0$ and $T_1$.
- Computed **only** where pixel $(x, y)$ is simultaneously valid at **both** $T_0$ and $T_1$ and the scene pair passed `validate_scene_pair`.

### 2.3 Sign-Agnostic Change Magnitude (dB)
$$\text{Magnitude}(p) = |\Delta(p)| = \left|B(T_1, p) - B(T_0, p)\right| \quad [\text{dB}]$$
- Captures the strength of radar scattering change regardless of sign, because surface disturbances (including fire, flooding, logging, or moisture shifts) can produce either positive or negative $\Delta(p)$ depending on scattering mechanism transitions.

### 2.4 Optional Dual-Polarization Visualization Metric ($D$)
When **both** `HH` and `HV` are present and valid at $(x, y)$ in both $T_0$ and $T_1$:
$$D = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}| \quad [\text{dB}]$$
- **Mandatory UI & API Label:** `Combined Radar Change`
- **Mandatory Disclaimer:** *Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.*
- If either `HH` or `HV` is unavailable, $D$ is `null` and is never computed.

---

## 3. Allowed vs. Forbidden Conclusions

### 3.1 Allowed Conclusions (Supported by Evidence)
1. **Radiometric Observation Statements:**
   - *"Within ROI-01, mean HV backscatter changed by $-2.84\text{ dB}$ between $T_0$ and $T_1$ across $14,210$ valid comparable pixels (`[E-0004]`)."*
2. **Data Coverage & Quality Statements:**
   - *"Comparable valid pixel coverage within the selected polygon is $87.4\%$; $12.6\%$ of the area is masked due to radar shadow/layover or invalid power (`[E-0004]`)."*
3. **Conditional Physical Hypotheses (Clearly Labeled as Possible Interpretations):**
   - *"A decrease in L-band HV cross-polarized backscatter is physically consistent with a reduction in depolarizing volume scatterers (such as canopy branches/foliage) or a decrease in surface dielectric moisture, among other surface changes."*

### 3.2 Forbidden Conclusions (Strictly Prohibited)
1. **Forbidden Causal Equation (`CHANGE = CAUSE`):**
   - Never state that radar change *proves* a wildfire occurred, or that every high-$|\Delta|$ pixel was burned.
2. **Forbidden Unvalidated Hazard Labels:**
   - Never label a GCOV change layer as `Burn Severity`, `Fire Risk`, `Damage Probability`, `Burned Area (ha)`, `Underground Peat Combustion`, or `Ecosystem Recovery`.
3. **Forbidden Temporal Extrapolation:**
   - Never claim that two observations ($T_0, T_1$) pinpoint the exact hour/day a disturbance occurred between $T_0$ and $T_1$, or establish long-term ecological recovery.
4. **Forbidden Out-of-Scope Environmental Claims:**
   - Never derive smoke dispersion, $\text{PM}_{2.5}$ concentration, or human population exposure from NISAR GCOV data.

---

## 4. Unit Conventions

| Quantity | Symbol | Unit | Valid Domain | Storage / Wire Format |
| :--- | :---: | :---: | :--- | :--- |
| Linear Backscatter Power | $P(t, p)$ | Linear $\gamma^0$ ($\text{m}^2/\text{m}^2$) | $(0, +\infty)$ | `float32` / `float64` |
| Logarithmic Backscatter | $B(t, p)$ | $\text{dB}$ | $(-\infty, +\infty)$, typical $[-35, +10]\text{ dB}$ | `float32` |
| Signed Radar Change | $\Delta(p)$ | $\text{dB}$ | $(-\infty, +\infty)$ | `float32` |
| Change Magnitude | $|\Delta(p)|$ | $\text{dB}$ | $[0, +\infty)$ | `float32` |
| Combined Radar Change | $D$ | $\text{dB}$ | $[0, +\infty)$ | `float32` or `null` |
| Coverage / Overlap Ratios | $r_{\text{cov}}$ | Dimensionless $[0.0, 1.0]$ | $[0.0, 1.0]$ (UI displays $0\text{–}100\%$) | `float` |
| Timestamps | $T_0, T_1$ | ISO-8601 UTC | `YYYY-MM-DDTHH:MM:SSZ` | `string` |
| Spatial Coordinates (Rasters) | $(x, y)$ | Native projected meters (e.g., UTM EPSG) | Finite real coordinates | GeoTIFF / HDF5 grid |
| Spatial Coordinates (API/UI) | $(\text{lon}, \text{lat})$ | Degrees (`EPSG:4326`) | WGS84 GeoJSON | GeoJSON `Polygon` / `Point` |

---

## 5. Nodata & Invalid Value Behavior

1. **Invalid Input Conditions:**
   A pixel at epoch $t$ and polarization $p$ is **invalid** if any of the following hold:
   - $P(t, p)$ is `NaN` or $\pm\infty$.
   - $P(t, p)$ equals the dataset `_FillValue` or `noDataValue`.
   - $P(t, p) \le 0$ (non-positive linear power cannot be transformed via $\log_{10}$).
   - The GCOV `mask` dataset marks the pixel as invalid, fill, radar shadow, or layover.
2. **Propagation Rule:**
   - If a pixel is invalid at $T_0$ **or** invalid at $T_1$, then $\Delta(p)$, $|\Delta(p)|$, and $D$ at that pixel **must** be `NaN` (masked/nodata).
3. **Anti-Coercion Rule:**
   - Invalid or missing pixels must **never** be filled with `0.0` (which would falsely indicate `0.0 dB` change / "stable surface").
   - In all UI maps and statistical summaries, invalid/missing pixels are separated into `missing_data_ratio` and rendered with a distinct **Insufficient Evidence / Missing Data** pattern.

---

## 6. Missing Polarization Behavior

1. NISAR GCOV scenes may contain dual-pol (`HH`, `HV`), single-pol (`HH` or `VV`), or quad-pol terms depending on the acquisition mode and observation plan.
2. **No Channel Synthesis:** If `HV` (i.e., `HVHV`) is absent in $T_0$ or $T_1$, the backend and frontend must set `hv_t0 = null`, `hv_t1 = null`, `delta_hv = null`, and `combined_change_db = null`.
3. Never estimate or synthesize a missing polarization from another channel.

---

## 7. Scene Pair Compatibility Rules (`validate_scene_pair`)

Before any multi-temporal comparison between `scene_a` ($T_0$) and `scene_b` ($T_1$) over `aoi`, `validate_scene_pair(scene_a, scene_b, aoi)` evaluates:

| Check ID | Criterion | Hard Failure (`INSUFFICIENT_EVIDENCE`) | Degraded Warning (`LIMITED`) |
| :--- | :--- | :--- | :--- |
| **QA-01** | Temporal Distinctness | $T_0 == T_1$ or identical granule ID | $\Delta t < 1\text{ day}$ |
| **QA-02** | Radar Band & Product Type | Non-L-band or non-GCOV product | Frequency group mismatch if resampled |
| **QA-03** | Common Polarizations | $P_{\{avail\}}(T_0) \cap P_{\{avail\}}(T_1) = \emptyset$ | One scene has `HH+HV`, the other only `HH` (restrict analysis to `HH`) |
| **QA-04** | Spatial Overlap & Actual SAR Illumination | Valid spatial intersection with AOI $< 10\%$ (`min_overlap_ratio`), OR partial-frame (`isFullFrame=False`) whose actual illuminated swath (`_LATLON.kml` / `boundingPolygon`) has $< 10\%$ overlap with the intended AOI | Overlap between $10\%$ and $50\%$, or `isFullFrame=False` partial-frame scene whose actual illuminated footprint has not yet been verified via `_LATLON.kml` / `boundingPolygon` |
| **QA-05** | Viewing Geometry / Orbit | Opposite look direction (`Left` vs `Right`) or opposite pass (`Ascending` vs `Descending`) by default | Cross-track incidence angle difference with user-acknowledged `LIMITED` flag |
| **QA-06** | Processing Maturity / CRID | Corrupt metadata or incompatible radiometric convention | Major CRID version difference between $T_0$ and $T_1$ |
| **QA-07** | CRS & Grid Alignment | Unprojectable or missing CRS metadata | Requires bilinear/nearest grid alignment across differing spacings |
| **QA-08** | Valid Pixel Intersection | Valid positive ($P>0$, `0 < mask < 255`) pixel count in intersection $= 0$ or ratio $< 10\%$ | Valid pixel intersection ratio between $10\%$ and $50\%$ |

- **Gate Enforcement:** When `compatible == False`, change computation halts immediately. No change raster or delta statistics may be emitted.
- **Actual Illumination Rule (Gate A.2 Discovery):** NASA CMR / frame-grid bounding-box overlap is **not** sufficient evidence of actual SAR illumination because NISAR L2 GCOV allocates the fixed ~`328 × 336 km` UTM frame grid even for short partial-frame datatakes (`isFullFrame = False`). Before approving any flagship scene pair:
  1. Inspect `isFullFrame` (`FULL_FRAME` in CMR / `/science/LSAR/identification/isFullFrame` in HDF5).
  2. Prefer `isFullFrame = True` granules.
  3. If `isFullFrame = False` (or unknown), inspect the companion `_LATLON.kml` or `/science/LSAR/identification/boundingPolygon` actual illuminated footprint before downloading multi-GB HDF5 granules.
  4. Require actual illuminated overlap with the intended target AOI.
- **Official GCOV Mask Rule (Gate A.2 Discovery):** Pixels in NISAR L2 GCOV may contain finite positive `HHHH`/`HVHV` values even when `/science/LSAR/GCOV/grids/frequencyA/mask == 0` (partially focused or invalid radar samples in the averaging set). Scientific validity strictly requires:
  $$\text{valid} = (0 < \text{mask} < 255) \land \text{isfinite}(P) \land (P > 0)$$

---

## 8. Uncertainty & Epistemic States

Every scene, scene pair, AOI selection, and `EvidenceRecord` must carry exactly one of four explicit epistemic states:

1. **`OBSERVED`**: Single-epoch NISAR GCOV observation has valid, finite, positive backscatter measurements within the region, without multi-temporal change comparison.
2. **`COMPARABLE`**: Two NISAR GCOV observations ($T_0, T_1$) pass all compatibility checks in `validate_scene_pair` with no geometry/maturity degradation and valid pixel coverage $\ge 50\%$.
3. **`LIMITED`**: Change calculation is mathematically permissible (`compatible == True`), but has documented scientific caveats (e.g., valid coverage between $10\%$ and $50\%$, CRID version difference, or only single polarization `HH` available). Caveats are populated in `limitations` and `warnings`.
4. **`INSUFFICIENT_EVIDENCE`**: Scene pair fails `validate_scene_pair`, or the selected polygon has $< 10\%$ valid comparable pixels (or $< N_{\min}$ valid pixels). Quantitative change conclusions are refused.

---

## 9. Mandatory Epistemic Structure (Observation vs. Attribution)

Every scientific explanation or AI Investigator output must separate findings into four explicit sections:

1. **Observation (`WHAT WE OBSERVED`)**: Quantitative facts derived strictly from deterministic NISAR GCOV calculations (`ΔHH`, `ΔHV`, valid pixel count, coverage %, dates), each tagged with `[E-xxxx]`.
2. **Possible Interpretation (`POSSIBLE INTERPRETATION`)**: Physical radar scattering hypotheses (e.g., canopy structure change, surface roughness change, dielectric moisture shift) framed conditionally (*"can be associated with..."*).
3. **Unknown / Limitation (`WHAT WE DO NOT KNOW`)**: Explicit statement of what radar backscatter intensity alone cannot determine (e.g., *"NISAR GCOV intensity alone does not determine whether wildfire was the cause, nor does it measure burn severity or underground peat combustion"*).
4. **Evidence (`EVIDENCE TRAIL`)**: Clickable list of `evidence_id`s resolving to the scene pair, AOI geometry, polarization, and provenance metadata.
