# SAR2Action Phase 5 — scientific agent validation

Validated on Windows, 2026-11-12. The real local Gemma model chooses restricted GIS tools. **All successful measurements below use explicit Synthetic Demo pixels, not NASA observations.** Real NISAR analysis is **BLOCKED** because the B-team change raster and live manifest are absent.

## What changed

- `ScientificEvidenceReasoner` checks every ranked numeric claim against the current session's registered Evidence ID, AOI geometry, scene pair, polarization, deterministic measurement, unit and method/version. It refuses stale or mismatched evidence before returning a scientific assessment.
- The assessment separates `OBSERVED` measurements, a bounded `INFERRED` follow-up interpretation and `UNKNOWN` physical causes. Wildfire, displacement and recovery questions explicitly state that radar change alone cannot confirm the proposed cause. Synthetic questions say that no real NISAR observation supports a real-world conclusion. Next research steps and limitations are attached.
- The existing real-model runtime records its selected investigation plan, at most eight model tool attempts and three selection rounds. It de-duplicates completed tools, checks a 60-second planning limit, retries bounded model timeouts and preserves a validated partial result when an optional final model call times out. The model still cannot execute Python, JavaScript or shell.
- The model adapter can normalize **optional** `generate_story` presentation fields and `inspect_evidence` extra fields. For evidence inspection it retains an explicit ID only if it is registered for the current investigation. A stale ID, invalid type or malformed JSON is rejected and may be retried; it is never executed. Repairs are recorded in the trace.
- The React/MapLibre panel now shows an Investigation Plan, live tool progress, Observed/Inferred/Unknown findings, scientific limitations and next steps. Clicking an observed claim focuses the registered region, opens its Evidence card and navigates to its Radar Fingerprint. An AOI or layer change cancels an active request; cancellation remains cooperative while a model call is in flight.
- The [captured real-model scientific trace](phase5_scientific_agent_trace.json) shows a completed three-region ranking, comparison and evidence inspection, three evidence-bound observed findings and the final plan. It omits hidden model reasoning and credentials.
- The B-to-D manifest validator and live adapter now require declared scene versions, processing method/version, pixel spacing, source backscatter unit, output dB unit and conversion formula. The live adapter explicitly calls scene-pair compatibility QA for the manifest pair and AOI. They verify raster alignment, north-up EPSG:4326, declared NoData, finite valid pixels, checksums, ordered dates, polarization and parent Evidence. Already-dB source data declares `conversion_formula: "none"`; linear-power source data declares `10*log10(P)`. The D adapter reads a signed dB change raster and never reapplies logarithms.

## Real data readiness

The workspace has scene metadata (`data/scenes/scene_manifest.json`), GCOV QA sidecars and eight processed validity/missing masks. It has **no readable signed change GeoTIFF** under `data/processed`, no configured `SAR2ACTION_SPATIAL_MANIFEST` and no complete B-team parent Evidence handoff. [The validator report](phase5_nisar_handoff_report.json) returns `INVALID` with the missing-manifest error. There is no formal live ranking run and no live Radar Fingerprint claim. The six Python skips remain marked as unavailable real-scene tests.

The [spatial handoff contract](SPATIAL_RANKING_CONTRACT.md) now documents the additional mandatory metadata. The local contract test uses temporary generated GeoTIFFs to check schema behavior; it is **not** a NASA observation. A manifest declaration cannot prove whether source pixels were actually converted correctly or whether a scene version is authentic. B/A scientific approval and parent Evidence remain necessary. The live adapter refuses missing HH/HV data and does not substitute another polarization or synthetic pixels.

## Argument failure and model reliability

The Phase 4 benchmark recorded **49/50** valid tool arguments; its artifact retained the failing `story_science` scenario but did not save the malformed raw call. The Phase 5 real-model run identified `inspect_evidence` as the tool with rejected arguments in two scenarios. The exact malformed values were not retained, so we cannot assert they were the identical Phase 4 payload. The new mock tests prove that extra fields can be normalized while stale Evidence IDs remain rejected. In the final real-model run, **2 of 54 attempted calls were still rejected**, **0 repairs were triggered**, and bounded retry completed both tasks. This is **52/54 first-attempt validity (96.3%)**, not a claim of perfect parameter output. No rejected GIS call executed.

The first 17-question Phase 5 run passed 13/17. The failed causal paraphrases exposed missing `ground moved` and `recovered` wording, an adversarial refusal was mis-scored as failure, and one repeated task hit a 20-second model timeout. After fixes, the second run passed 16/17; an optional third model call timed out after a valid Chinese wildfire analysis. The final run passed **17/17**. All three repeated complex ranking/comparison/evidence tasks passed. We retain [first](phase5_agent_benchmark_initial.json), [second](phase5_agent_benchmark_second.json), [pre-argument-repair](phase5_agent_benchmark_pre_argument_repair.json) and [final](phase5_agent_benchmark.json) machine-readable results. These are successive runs on one local model and one explicit synthetic fixture, not a general deployment reliability estimate.

| Cohort | Final observed result |
| --- | --- |
| Deterministic HTTP tools | 3/3, measured separately |
| Mock model integration | 11/11 targeted tests, measured separately |
| Real LLM investigation | 17/17 scenarios, including causal uncertainty, invalid evidence, malicious shell request, fake numbers, story consistency, AOI switch and live-data refusal |
| Repeated complex task | 3/3 completed |
| Real tool argument attempts | 54 calls; 2 schema rejections; 0 observed normalizations; no rejected call executed |
| Evidence integrity | 17/17 programmatic checks; old Evidence story HTTP 422 |
| Unauthorized tool executions | 0 |
| Unmarked synthetic outputs | 0 |
| Real LLM HTTP latency | P50 13,643.1 ms; P95 15,294.1 ms among HTTP 200 runs |

The programmatic evidence check verifies IDs and typed observed entries; it is not a full semantic hallucination audit. The adversarial fake-number request was safely blocked rather than producing a fabricated value. The [Phase 4 benchmark](phase4_agent_benchmark.json) has 24 additional distinct prompts; the Phase 5 benchmark adds new paraphrases, continuous AOI use and three repetitions. The cohorts are never pooled into one success rate.

## Hermes and local resources

The GGUF metadata declares a **262,144-token native context**, while the actual [llama.cpp server probe](phase5_runtime_probe.json) reports **4,096 tokens**, four slots, a 14,249,047,104-byte model file and an RTX 5070 Ti with 16,303 MiB total VRAM. During the probe, 15,630 MiB was used, 366 MiB was free and system RAM available was 4.36 GiB; another reading during model load had only 112 MiB free VRAM. Moving from 4K to 64K allocates much more KV cache; precise Gemma 4 hybrid-attention cache consumption was not measured. With the measured near-full VRAM and limited free RAM, we did not attempt a 64K allocation that could disrupt the working llama.cpp agent.

The isolated Hermes v0.19.0 Gateway remains localhost-only with zero built-in tools. The authenticated [Hermes probe](phase5_hermes_probe.json) returned health **200**, models **200**, chat **500** in 827.6 ms. The gateway log states that actual model context 4,096 is below Hermes's 64,000-token minimum. Thus Hermes inference and Hermes-mediated tool calling remain **BLOCKED / NOT VERIFIED**. The direct llama.cpp real-model tool-calling path stays operational. A native GGUF context claim is not treated as allocated server context.

## Final verification and demo

| Check | Result |
| --- | --- |
| Full Python pytest | **83 passed, 6 skipped**, 4 warnings |
| Frontend unit | **9 passed** |
| TypeScript and Vite build | Passed; existing large-bundle warning |
| Chrome Playwright | **3 passed**, including real-model plan, evidence categories, MapLibre focus, comparison and five-scene story |
| Q1–Q5 HTTP regression | **5/5** deterministic synthetic cases; live missing-data refusal passed |
| Spatial ranking / scene QA / contract tests | Included in 83 passed; real-scene cases remain skipped |

Run from `D:\SAR2Action`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_phase4_demo.ps1
```

Open `http://127.0.0.1:5173`, select an AOI, choose **Synthetic Demo** and **Real AI Analysis**, and ask: `找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。` The UI shows the plan, three ranked regions, map focus, Radar Fingerprint, Evidence, scientific limits and Story. For a causal check ask `這個地方是不是發生森林火災？`; the answer must keep the cause unknown. [The Chrome screenshot](../frontend/test-results/agent-spatial-flow-real-lo-c7aba-e-GIS-tools-through-FastAPI-chrome/real-agent-flow.png) shows the real agent with explicit synthetic data. Stop launcher-owned services with `scripts\run_phase4_demo.ps1 -Stop`. The offline deterministic fallback remains `scripts\run_phase3_demo.ps1`.

## Remaining risks

1. No B-team signed change raster and parent Evidence; real NISAR science remains blocked. Metadata-only sidecars and masks cannot replace radar observations.
2. Hermes requires actual >=64K server context. The current GPU/RAM state has no demonstrated safe headroom for it.
3. Real model arguments still show occasional rejections; bounded retry protects execution, but 54 calls are a small sample. The failing Phase 4 raw payload is unavailable.
4. Model timeouts can produce a validated partial answer when optional follow-up selection fails. A requested but unexecuted comparison/story may require user retry. Session and cancellation state remain in process memory.
