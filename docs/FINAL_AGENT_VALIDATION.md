# Final agent, science and demo validation

Validated locally on Windows, 2026-11-13. **Demo status: CONDITIONALLY READY.** Both demonstration paths work in Chrome. NISAR source provenance and real within-AOI spatial ranking remain unavailable; the interface labels those limits. The real Gemini model selected allowed GIS functions, while the backend generated the evidence-bounded scientific wording. It did not ask the model to calculate measurements.

## Scientific validity: AOI-OKI-04

`E-FLAGSHIP-OKI-004` records HH **−0.2128 dB**, HV **−0.2056 dB**, and **3,148,830** common valid pixels. The signed value is `median(10 log10(power_T1) − 10 log10(power_T0))` over valid pixels, **not** `median(T1) − median(T0)`. The original two date medians differ by other amounts, so treating those operations as interchangeable would be incorrect. The D-side Agent display now states the exact definition; B team's JSON values were not changed.

The cache includes signed change distributions and p10/p25/p50/p75/p90 percentiles. For HH, p10/p90 are −3.5025/3.1037 dB, median absolute change is 1.7207 dB and 46.6% of valid pixels have positive signed change. For HV, p10/p90 are −3.6299/3.1979 dB, median absolute change is 1.7834 dB and 46.9% are positive. Thus the near −0.2 dB signed medians can hide opposing local changes. The numbers are cached claims and have not been independently recomputed from source HDF5 here.

The recorded validity rule excludes mask 0/255, nonfinite and nonpositive power in both scenes/channels. The cached mask diagnostics report a 1770 × 1779 AOI window and 3,148,830 common valid pixels. A 10 m × 10 m grid makes its recorded 314.883 km² valid area arithmetically consistent. Parent Scene IDs, acquisition dates, provisional product maturity, CRID, processing method `sar2action-change-engine-v1.0.0`, and limits are present. There is no designated stable comparison region or significance test. Source raster, HDF5 SHA-256, original pixel recount, and processing commit confirmation are still missing. Therefore the valid scientific label is **OBSERVED BACKSCATTER DIFFERENCE**. The cache does not support **CONFIRMED SIGNIFICANT DISTURBANCE**, peat fire, forest recovery or ground subsidence.

The [claim audit](FINAL_SCIENTIFIC_CLAIM_AUDIT.json) validated 54 Analysis Claims and 54 corresponding Fingerprint Claims against registered Evidence, case, AOI, scene pair, unit and value. It checked the Agent explanation and every story frame for excessive causal language and consistent Evidence IDs: **108/108 claims and 11/11 audit gates passed**. Original B-team Claim wording for signed medians could be read as a difference of two date medians; the D-side UI now paraphrases those two Claim types with the pixelwise formula and preserves the original statement separately. This audit checks text and cache consistency, not source truth.

## Source reproducibility

The [B-team request](SCIENCE_REPRODUCIBILITY_REQUEST.md) and [read-only source verification script](../scripts/verify_nisar_source.py) are ready. The script hashes both original GCOV HDF5 files, confirms Scene IDs/dates/grid/AOI, independently applies the documented validity rule, recounts common valid pixels, recomputes HH/HV signed medians, checks 32 seeded pixels, and hashes derived arrays and optional archived raster files. It was compiled and its CLI checked here, **but it was not run against the absent HDF5 products**. The cache remains **PROVENANCE PENDING** until B team runs the script on the source machine and supplies processing/version metadata. A pass is a targeted reproducibility check; significance and causal attribution need separate review.

## Agent and user experience

The cached Agent path now surfaces measurement definition, signed p10–p90, median absolute change, direction fraction, mask rule, significance/control status, source scenes, dates, method, quality limits and provenance status. Evidence Cards show **Internally Consistent Cache · Provenance Pending · Verified Source: No**. Long Scene IDs and answers wrap within the wider Agent panel. The five-scene story retains the same Evidence ID and explicitly notes unconfirmed significance/cause. AOI change stales the old story and removes prior fingerprint results. The synthetic mode remains labeled **SIMULATED DATA — NOT NASA OBSERVATIONS**.

Chrome screenshot review found the Agent panel constrained to about 40% of the page with long evidence text overflowing. The Agent panel width and line wrapping were corrected; the cached Evidence/Story workflow was rerun and visually inspected. The main WebGIS still leaves substantial unused space on a wide desktop and its source Scene IDs are visually dense. Those broader layout issues belong to the shared interface and were not redesigned in this stage. Loading, failure and cancellation states remain available; the earlier model failure displayed an error and did not silently substitute deterministic output.

## Executed tests and observed failures

| Gate | Final observed result |
| --- | --- |
| Python `pytest -q` | **99 passed, 6 skipped**; skipped tests require absent full source HDF5 |
| Frontend Vitest | **9 passed** |
| TypeScript `tsc -b` / Vite build | **PASS / PASS**; Vite reports a large JavaScript chunk warning |
| Actual loopback HTTP E2E | **11/11 PASS**; exact JSON/API/Agent HH/HV, pixels, scenes, AOI, story and stale state |
| Chrome Playwright | **5/5 PASS** on final isolated run; map focus, both modes, real Gemini and story |
| Real Gemini science questions | **5/5 PASS** on final isolated run: 0.2 dB significance, peat fire, recovery, subsidence, malicious instruction |
| Cache claim and story audit | **108/108 Claims, 11/11 gates PASS** |
| Three-file cache integrity | **PASS**; 12 Evidence, 12 Fingerprints, 12 Analyses; six required IDs present |
| Exact credential leakage scan | **PASS: 0 matches in 143 files** after final build |
| Independent source HDF5 verification | **BLOCKED**; source products not present |
| Real within-AOI subregion ranking | **BLOCKED**; signed georeferenced change raster and valid mask not delivered |

The [real Gemini evaluation](FINAL_GEMINI_SCIENCE_EVAL.json) includes each scenario's checks, selected tools, status, duration and bounded response excerpt. The four benign questions all selected real science tools on the final run and referenced `E-FLAGSHIP-OKI-004`; the malicious request executed no shell and returned no invented 9.9 dB value. Tool selection was not perfectly reliable: an earlier five-question run blocked the subsidence question at model selection (4/5), and the first full Chrome run was 4/5 because real synthetic ranking similarly failed tool selection. The later isolated runs passed. The [intermittent failure record](FINAL_GEMINI_INTERMITTENT_FAILURE.json) and [initial evaluator result](FINAL_GEMINI_SCIENCE_EVAL_INITIAL.json) are retained. The initial evaluator also misclassified a safe refusal of the malicious request as a failure; its acceptance criterion was corrected. Root cause of the later model-selection failure was not captured beyond a backend `RuntimeError` and remains a reliability risk.

The first in-sandbox Chrome request could not reach loopback (`ERR_NETWORK_ACCESS_DENIED`). The services and test runner were then executed with local network permission. Python TestClient also hung at a health check in the restricted sandbox; the complete suite passed with local loopback permission. These were execution-environment failures, not scientific or UI passes.

## Security and demo operation

The Gemini key stays in the backend process environment. The launcher reads `GERMINI API.txt` into that process only; the real-model prompt contains user text and trusted case/AOI/tool context, never the key. The [security report](FINAL_SECURITY_AUDIT.json) scanned source, scripts, docs, frontend bundle, Playwright outputs and reports for exact credential bytes and found zero matches. `.gitignore` excludes the local key and data; deployment packaging must explicitly omit it. This workspace has **no Git repository**, so Git history was not audited. The scan cannot prove absence of a differently encoded credential outside the scanned files.

Start the backend with `powershell -NoProfile -ExecutionPolicy Bypass -File D:\SAR2Action\scripts\start_gemini_backend.ps1 -Port 8000`. In `D:\SAR2Action\frontend`, run `npm run dev -- --host 127.0.0.1` for port 5173. Confirm `/api/health` and `/api/agent/status`, then follow the two distinct flows in [demo readiness](FINAL_DEMO_READINESS.json). **Demo A:** flagship case → NISAR Cached Evidence → AOI-OKI-04 → Real AI Analysis → Fingerprint → Evidence → map focus → five-scene story. **Demo B:** Synthetic Demo → select AOI → rank/compare regions → map focus → synthetic Evidence → story. Never present Demo B's spatial ranking as NISAR observations. Gemma/llama.cpp remains the existing alternative provider, but it was not exercised in this final run.

## Outstanding handoffs

- **B team:** run the source-machine check, provide source HDF5 hashes, processing commit and QA definition; deliver a signed georeferenced change raster plus valid mask if real within-AOI ranking is desired; nominate stable controls and a defensible significance method.
- **A team:** review competition narration against the observed/inferred/unknown boundary, particularly the unverified source and lack of fire attribution.
- **C team:** review the remaining wide-desktop WebGIS whitespace and dense Scene ID presentation without changing the science source labels.

Formal demonstration is ready **with explicit provenance pending and synthetic labels**. A claim of source-verified NASA pixel values or statistically significant disturbance is **not ready**.
