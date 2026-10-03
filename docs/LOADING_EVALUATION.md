# Model loading and first-inference investigation

**Historical policy note:** RAM-gate failures and rejection conclusions in this report use the former mandatory 1 GiB reserve. [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), accepted later on 2026-10-03, makes that reserve advisory. Measurements/artifacts are preserved; this does not retrospectively establish microphone stability or quality. The current runtime/reporting implements ADR-014; these artifacts retain their historical policy.

Measured on 2026-10-03. The user requested investigation before adopting application changes. Only ignored diagnostic scripts/process hooks and documentation were added in this investigation. Application source, default configuration, provider contracts, model assets, decoding, devices, precision and acceptance margins were unchanged. No model replacement or automatic fallback was introduced.

The investigation found real removable host tensor storage in Kokoro. Clearing it released 214.6 MiB of private committed memory and 136.0 MiB of process RSS in one immediate before/after check. However, neither this change nor combined direct GPU loading/checkpoint mapping passed the full-run RAM margin. The combination completed two fresh runs with 90/90 successful observations each, about 0.48 s warm processing median, and 2.339 GiB peak dedicated VRAM; available RAM still dipped to about 315–320 MiB during first inference. It remains an experiment, not a validated microphone configuration.

## Configuration and protocol

All runs use `configs/all-gpu-fp32.toml`: Whisper small on GPU FP16, IndicTrans2 distilled 200M on GPU FP32, and Kokoro-82M `hf_alpha` on GPU FP32. CPU preprocessing and Python/native runtime work remain; GPU placement does not mean zero host memory. Batch size one, serial processing, eager translation attention, beam size five and existing duration/token bounds were preserved. Actual device/precision metadata matched the configuration in all nine runs.

Hardware: Intel i5-12500H, RTX 3050 Laptop GPU 4 GiB, 8,259,358,720 bytes system RAM, Windows build 26200, driver 610.88. Python 3.11.15; torch 2.7.1+cu126, CTranslate2 4.6.0, faster-whisper 1.2.1, transformers 4.51.3, Kokoro 0.9.4 and IndicTransToolkit 1.1.1. ASR uses the explicitly configured torch native DLL directory. Same immutable model revisions as the placement evaluation; no new model assets were downloaded.

Each configuration ran in a fresh process: cold loading/first inference, three warm-ups, then three passes over the same 30 cases (90 measured observations). Run order: baseline, mmap, stale-tensor cleanup, no_grad construction, GPU construction, GPU construction plus mmap, direct translation loading, combination, combination repeat. No other model benchmark overlapped. The last repeat avoided additional shell/Python inspection commands during measurement. Codex/Windows remained running; background memory was not fixed or forcibly trimmed. Power/thermal/AC conditions were not captured anew. This is a diagnostic comparison, not a randomized controlled estimate of each loader's RAM savings.

Manifest: `data/eval/asr-diagnostic-2/manifest.jsonl`, SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. SAPI English and authored Hindi drafts remain unreviewed. Category tags do not demonstrate real accent/noise coverage. Runtime used local cached assets and the offline socket guard; physically disconnected file/microphone acceptance remains pending. No raw text or generated audio was persisted by these runs.

## Measured results

RAM figures are available system RAM in MiB. The unchanged gate is at least 1024 MiB throughout the measured run and at most 3.5 GiB device-wide dedicated VRAM. Baseline means the `load_start` marker; Accelerate import for direct-loading experiments occurs before this marker, inside the full-run sampling period. Baselines varied considerably, and the original-loader baseline was already below 1024 MiB. Absolute outcomes are valid for each observed run; differences between runs do not isolate a causal RAM saving.

| Experiment | Baseline RAM | Loading minimum | First-call minimum | Warm measured minimum | Full-run minimum | Peak VRAM (GiB) | Processing p50 / p95 (s) | Memory gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Original loading | 757.4 | 15.8 | 49.9 | 944.0 | 15.8 | 2.390 | 0.478 / 0.576 | fail |
| Kokoro checkpoint mmap | 1945.5 | 514.5 | 151.0 | 657.5 | 151.0 | 2.390 | 0.479 / 0.584 | fail |
| Clear stale Kokoro CPU tensors | 2287.4 | 577.6 | 345.1 | 1067.6 | 345.1 | 2.390 | 0.482 / 0.588 | fail |
| Kokoro construction with no_grad | 2291.1 | 885.9 | 341.5 | 709.3 | 341.5 | 2.390 | 0.493 / 0.608 | fail |
| Construct Kokoro on GPU | 2101.6 | 518.4 | 337.8 | 646.1 | 337.8 | 2.409 | 0.485 / 0.587 | fail |
| GPU Kokoro construction + mmap | 2234.1 | 639.9 | 445.7 | 675.7 | 445.7 | 2.409 | 0.483 / 0.570 | fail |
| Direct translation GPU loading | 1773.1 | 453.0 | 224.2 | 926.5 | 224.2 | 2.339 | 0.484 / 0.577 | fail |
| Direct translation + mmap + clear | 1895.5 | 580.1 | 315.4 | 921.8 | 315.4 | 2.339 | 0.487 / 0.590 | fail |
| Same combination, fresh repeat | 1744.8 | 435.7 | 319.6 | 932.0 | 319.6 | 2.339 | 0.480 / 0.598 | fail |

Stale-tensor cleanup alone happened to meet the warm measured margin (1067.6 MiB) in that run. Loading/first inference still failed. The combination's two warm minima were 921.8 and 932.0 MiB, below the target. Neither warm-phase results nor successful inference waive the loading/first-call margin.

All nine configurations completed 90/90 measured observations, plus their first call and three warm-ups, without provider failures, fatal errors, observed OOM or reported memory telemetry errors. This is 810 successful measured file observations, not a 30-turn microphone session. Diagnostic WER was 9.44% throughout; it is not a human-reviewed clean-WER gate result. Percentiles use linear interpolation at `(n-1)*q`, with failed calls excluded from timing distributions and their counts still reported.

After all model processes exited, `.venv/Scripts/python.exe -m pytest -q tests/unit` completed with 32 passed in 3.63 s. The aggregate/report checks verified every run's manifest hash, actual provider device/precision, 30 distinct cases, one first call, three warm-ups, 90 measured calls and matching English/Hindi fingerprints. `git diff --check` found no whitespace errors. A default-environment probe confirmed Accelerate is absent without the isolated Python path. Evidence of the deterministic check is in `artifacts/option3-unit-tests.txt`.

Timings end at a complete synthesized audio buffer; they exclude playback and acoustic onset. Cold/first-call timings additionally contain diagnostic snapshots/module-mapping inspections. Warm calls contain fingerprint/JSON overhead. These are instrumented diagnostics, not canonical microphone response timings.

| Experiment | Cold load (s) | First processing (s) | Peak RSS (GiB) | Peak private commit (GiB) | Actual sample interval p50 / p95 (ms) | ASR RTF p50 / p95 | TTS RTF p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original loading | 18.261 | 5.023 | 1.401 | 6.359 | 110.9 / 112.1 | 0.076 / 0.085 | 0.034 / 0.055 |
| Kokoro checkpoint mmap | 15.372 | 3.448 | 1.735 | 6.257 | 110.4 / 112.1 | 0.075 / 0.084 | 0.033 / 0.055 |
| Clear stale Kokoro CPU tensors | 13.816 | 4.870 | 1.965 | 7.082 | 110.2 / 112.1 | 0.076 / 0.086 | 0.034 / 0.054 |
| Kokoro construction with no_grad | 13.870 | 4.055 | 2.244 | 6.586 | 110.3 / 112.1 | 0.077 / 0.087 | 0.034 / 0.056 |
| Construct Kokoro on GPU | 14.500 | 3.709 | 1.897 | 6.554 | 110.1 / 112.1 | 0.076 / 0.088 | 0.034 / 0.050 |
| GPU Kokoro construction + mmap | 13.371 | 3.331 | 1.666 | 6.362 | 110.9 / 112.1 | 0.076 / 0.086 | 0.034 / 0.048 |
| Direct translation GPU loading | 15.825 | 3.974 | 1.852 | 6.770 | 110.3 / 112.3 | 0.076 / 0.085 | 0.034 / 0.055 |
| Direct translation + mmap + clear | 15.967 | 4.127 | 1.826 | 6.391 | 110.2 / 112.3 | 0.078 / 0.084 | 0.033 / 0.056 |
| Same combination, fresh repeat | 13.974 | 3.359 | 1.849 | 6.837 | 110.1 / 112.1 | 0.078 / 0.087 | 0.033 / 0.057 |

Sampling requested 100 ms. Actual intervals and all raw samples are retained. Brief peaks can be missed. Process RSS includes resident native/CTranslate2 memory; GPU telemetry is total dedicated device memory, not just PyTorch counters. Private bytes are committed memory, not physical resident RAM. PyTorch counters and tensor-storage inventories are supplementary and do not establish the memory gate.

## Findings and numerical checks

Kokoro uses legacy `weight_norm`. PyTorch registers `weight_g`/`weight_v`, stores a derived weight as a tensor attribute, and recomputes that attribute in a forward pre-hook. See the [tested PyTorch 2.7.1 implementation](https://github.com/pytorch/pytorch/blob/v2.7.1/torch/nn/utils/weight_norm.py). Inspecting this Kokoro model after GPU loading found 327,248,280 bytes of registered GPU storage and 230,545,284 bytes of direct unregistered CPU tensor storage. The first synthesis replaced 230,545,200 of those bytes with GPU tensors.

The cleanup experiment removed 89 stale CPU attributes with corresponding WeightNorm pre-hooks, leaving 84 CPU bytes. It did not remove/rewrite registered parameters or their hooks. Immediate private commit fell from 5,398,425,600 to 5,173,366,784 bytes (214.6 MiB); RSS fell from 1,847,418,880 to 1,704,771,584 bytes (136.0 MiB). This is a measured cleanup effect in that process; the increase in available system RAM is not a guaranteed saving across desktop baselines. Tensor inventory does not traverse arbitrary object graphs or native allocations.

Checkpoint mmap, construction under no_grad, GPU construction and direct translation loading were tested separately before combining. Direct translation loading used the explicit `device_map={"": "cuda:0"}` path rather than automatic placement/offload, with pinned Accelerate 1.6.0. See the [tested Transformers 4.51.3 loading implementation](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/modeling_utils.py). That helper was installed only into ignored `.cache/investigation-accelerate`; it is not installed into the application's environment or added to requirements. Existing dependencies were reused. The combined experiment retained ordinary CPU Kokoro construction, checkpoint mmap and stale-attribute cleanup, plus direct translation GPU loading.

All English/Hindi output fingerprints matched the baseline in order for all 94 calls per run (first call, warm-ups and measured calls). Unseeded Kokoro wave hashes are not a useful parity test because its installed 0.9.4 `istftnet.py` intentionally generates random noise. Separate seeded TTS checks reset CPU/GPU seeds to `10000 + case index` for each of 30 authored Hindi cases. The baseline repeated first case matched exactly. Registered parameter/buffer hashes matched for every tested loader. Results:

| Loader modification | Same waveform length | Bit-exact waveforms | Within rtol=1e-4, atol=1e-5 | Human listening |
|---|---:|---:|---:|---|
| Kokoro mmap | 30/30 | 30/30 | 30/30 | pending |
| Clear stale CPU attributes | 30/30 | 30/30 | 30/30 | pending |
| no_grad construction | 30/30 | 30/30 | 30/30 | pending |
| GPU construction | 30/30 | 0/30 | 0/30 | pending |
| GPU construction + mmap | 30/30 | 0/30 | 0/30 | pending |
| Combined mmap/cleanup path (TTS portion) | 30/30 | 30/30 | 30/30 | pending |

GPU construction produced a maximum absolute waveform difference of 0.002095312 and maximum per-case RMSE of 0.0000478161. The reason was not isolated; audibility or semantic quality is not inferred from those figures. That path was left unadopted. The combination's parity check only loaded TTS: translation parity is established by the pipeline text fingerprints, not by an unrun translation parameter comparison. Baseline audio stayed only in the parity process's RAM; no WAV/reference audio was persisted. These numerical checks do not replace bilingual/listening review.

The repeat shows the remaining RAM dip also occurs before synthesis: after loading all providers, one checkpoint reported 1113.5 MiB available; after first ASR, 729.0 MiB; after first translation, 310.8 MiB. The sampled first-phase minimum was 319.6 MiB, illustrating that 100 ms sampling can miss lower point-in-time readings. Registered translation storage remained on GPU. Private commit increased during these first calls, but these coarse checkpoints cannot attribute all host memory to a particular native library, workspace, WDDM behavior or background process. Removing the Kokoro CPU copies cannot by itself account for the remaining deficit.

Early baseline/mmap hook files used `runtime_mapped_pages`/`rss_bytes` for the values returned by Windows psutil `memory_maps()`. Those names were misleading: returned DLL regions can exceed the entire process RSS and were not verified as resident physical pages. Treat them only as module/mapping inventory, never sum them as RAM or use them for library ownership. `mapping-interpretation.json` annotates those historical files; later hooks use `runtime_mappings`/`reported_map_bytes`. Authoritative RSS/system-RAM/dedicated-VRAM measurements above are unaffected. Historical experiment metadata with the phrase "mapped pages" inherits this correction.

## Reproduction and artifacts

These are local ignored investigation scripts, not new supported application commands. Use cached provisioned assets, the tested environment, and new empty output directories. Standard application setup/run commands remain in SETUP.md and README.md; `configs/v1.toml` is unchanged. No new model-download step was needed.

```powershell
# Only if the isolated helper folder has not already been provisioned:
uv pip install --python .venv/Scripts/python.exe --target .cache/investigation-accelerate --no-deps --cache-dir .cache/uv accelerate==1.6.0

.\artifacts\run-loading-benchmark.ps1 -Experiment baseline -Output artifacts/loading-baseline-new
.\artifacts\run-loading-benchmark.ps1 -Experiment kokoro_clear_stale -Output artifacts/loading-clear-new
.\artifacts\run-loading-benchmark.ps1 -Experiment device_map_mmap_clear -Output artifacts/loading-combination-new
```

The launcher scopes PYTHONPATH to the isolated helper for direct-loading modes and restores it afterward. Diagnostics restore temporary vendor callable overrides and close providers. Seeded parity: `.venv/Scripts/python.exe artifacts/loading_numerical_check.py --output artifacts/seeded-loading-new` for the default single-loader matrix; combined parity additionally needs the isolated helper on the current process's Python path and `--modes baseline device_map_mmap_clear`. It is separate from residency measurement and reuses one process for sequential TTS variants.

Each run contains `metadata.json`, `loading-experiment.json`, `summary.json`, `summary.md`, `records.jsonl`, category distributions, `behavior.jsonl`, `memory-samples.jsonl`, `placement-phases.jsonl`, `placement-memory.json`, `hook-checkpoints.jsonl` and content-free output fingerprints. Console logs sit alongside run directories. The aggregate is `artifacts/option3-loading-overview.json`; seeded evidence is `artifacts/option3-seeded-numerical-check/summary.json` and `artifacts/option3-combined-seeded-check/summary.json`.

| Local run directory | Run ID |
|---|---|
| `artifacts/option3-load-baseline` | `187de8c2-0630-49ce-948f-80fff9a3c10d` |
| `artifacts/option3-load-mmap` | `c080dd9d-4f82-4a82-98c9-79ba83d86f94` |
| `artifacts/option3-load-clear-stale` | `a5498d77-4cd1-4847-bda3-febda900e584` |
| `artifacts/option3-load-no-grad` | `34348dea-9c51-4e36-a740-765435cbbc09` |
| `artifacts/option3-load-cuda-construct` | `68dd12f8-f918-4114-aa4e-f3755ee5bfc0` |
| `artifacts/option3-load-cuda-mmap` | `12bd5236-a1d2-47cf-a819-c840a7d8a032` |
| `artifacts/option3-load-translation-direct` | `2ce9a304-9a2b-4b7f-998b-f95af6ca154d` |
| `artifacts/option3-load-combined-safe` | `f335a9b3-a63b-42f7-95ed-94d11085a97b` |
| `artifacts/option3-load-combined-safe-repeat` | `55ac8710-a0a3-4922-9dbd-5c21e8ed6890` |

## Decision and remaining work

No loader or placement was adopted. The removable CPU copies are worth addressing in a future reviewed adapter change, but the combined loading path does not pass the memory margin. The evidence favors further isolation of ASR/translation first-call host/runtime allocations and explicit staged initialization/residency experiments before assuming a model replacement is necessary. Staged residency must include repeated load costs in end-to-end timings; it is not yet implemented or benchmarked here. Changing Windows/Python process working sets to manufacture a passing sample was not attempted.

CuDNN disabling, CUDA lazy-module tuning and the direct-translation-plus-GPU-Kokoro-construction combination were not benchmarked. They are not reported as solutions. Models and precision remain unchanged, and the margin remains 1 GiB RAM / 3.5 GiB VRAM. Human adequacy, critical-detail review, Hindi listening, actual acoustic response, physically disconnected execution and 30 microphone turns are still pending. Successful diagnostic inference under low memory proves execution on those cases, not sustained-session acceptance.
