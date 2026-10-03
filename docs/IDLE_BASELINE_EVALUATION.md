# Idle-desktop follow-up

**Historical policy note:** RAM-gate failures and rejection conclusions in this report use the former mandatory 1 GiB reserve. [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), accepted later on 2026-10-03, makes that reserve advisory. Measurements/artifacts are preserved. These successful fast file runs qualify a candidate for further validation; they do not retrospectively establish microphone stability or quality. The current runtime/reporting implements ADR-014; these artifacts retain their historical policy.

Measured 2026-10-03 after the human confirmed closing unnecessary applications and leaving the machine idle. See [OPTIMIZATION_REVIEW.md](OPTIMIZATION_REVIEW.md) for the goal review. Application source/defaults and the 1 GiB available-RAM / 3.5 GiB dedicated-VRAM targets remain unchanged. This follow-up separates a cleaner desktop baseline from earlier changing-load experiments; it cannot hold Windows service activity or thermal state constant.

The strongest prior same-model loading profile uses Whisper small GPU FP16, IndicTrans2 distilled 200M GPU FP32 with explicit root device mapping, and Kokoro GPU FP32 with checkpoint mmap and stale CPU WeightNorm-attribute cleanup. The isolated Accelerate 1.6.0 path is explicit. Cached source revisions and decoding remain unchanged; no model was downloaded or replaced. Original loader text and seeded TTS parity evidence remains in LOADING_EVALUATION.md. Inference uses the offline guard; physical network disconnection remains a separate pending check.

## Baseline and full runs

Each fresh process uses three warm-ups and three passes over the fixed 30 SAPI/draft cases, plus a separate first call. Manifest SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Full-run memory includes loading, inference and cleanup. Percentiles use linear interpolation over successful observations; failed timings are excluded but all failures remain recorded. File processing excludes playback/acoustic onset and is not microphone response timing. Model-free inventory observers use about 25 MiB RSS and are included in available-RAM observations; they exit before each benchmark. Small transient progress readers are likewise included.

| Run | Model-free available RAM (MiB) | Calls | Processing p50 / p95 (s) | Cold load (s) | First processing (s) | Full RAM min (MiB) | Dedicated VRAM (GiB) | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| option6-idle-gpu-combined | 1583.2 | 90/90 | 0.496 / 0.602 | 22.237 | 6.256 | 247.7 | 2.339 | fail |
| option6-idle-gpu-combined-repeat | 1719.8 | 90/90 | 0.481 / 0.589 | 17.974 | 3.329 | 75.0 | 2.339 | fail |

| Run | Loading / first / measured RAM min (MiB) | Peak RSS / private commit (GiB) | Actual sample interval p50 / p95 (ms) | English / Hindi matches |
|---|---|---|---|---|
| option6-idle-gpu-combined | 284.7 / 247.7 / 585.8 | 1.510 / 6.780 | 111.0 / 115.3 | 94/94 / 94/94 |
| option6-idle-gpu-combined-repeat | 75.0 / 143.4 / 222.3 | 1.551 / 6.385 | 111.0 / 112.2 | 94/94 / 94/94 |

All measured calls succeeded without provider/OOM failures or telemetry errors; both full-run RAM gates failed. Diagnostic WER was 9.44%, not human WER. Category summaries, stage timings, ASR/TTS RTFs, behavior outcomes, complete samples and actual device/revision metadata remain in each artifact directory. Sampling requested 100 ms; brief peaks can be missed. Hook checkpoint observations and sampled minima need not coincide. Private commit is not physical RSS; DLL mapping-region sizes are not resident-page ownership. Dedicated VRAM includes background GPU use. Low steady-state RSS can reflect paging/compression rather than sufficient headroom. No timing or memory difference is asserted as causal savings.

The model-free baselines were about 1.55 and 1.68 GiB available RAM. Retaining the 1 GiB reserve leaves only roughly 0.55–0.68 GiB of additional headroom, although other processes can change residency. Windows nonpaged kernel memory was about 1.16–1.17 GiB in these snapshots. OCControl.Service resident memory varied from about 866 MiB before the first run to 598 MiB before the repeat. Process RSS can double-count shared pages; these snapshots do not establish a service/driver leak or exact ownership of unavailable RAM. No background process was stopped by the agent and no operating-system working sets were trimmed.

## Explicit mixed-runtime probe

Following the two full runs, one bounded diagnostic probe used CTranslate2 GPU ASR FP16 with the official isolated torch 2.7.1+cpu runtime for CPU quantized translation and CPU FP32 fused Kokoro. Native ASR CUDA libraries remained explicitly sourced from the existing pinned environment. Actual ASR metadata confirmed GPU FP16. `torch.cuda.is_initialized()` being false refers only to PyTorch; it does not mean CTranslate2 used CPU. This probe is not a 90-observation benchmark or an accepted configuration.

Probe status ok; load 14.100 s; first processing 5.084 s; minimum available RAM 322.3 MiB; peak RSS 1.434 GiB; dedicated VRAM 0.767 GiB; memory gate **fail**. No provider/fatal or telemetry error. It was rejected as a solution at the resource-probe stage rather than running another full benchmark. Numerical parity of the derived CPU weights and human quantization quality remain unvalidated.

## Interpretation and reproduction

Closing unnecessary apps did not make the strongest tested GPU pipeline pass. Warm computation and dedicated VRAM are satisfactory diagnostics, while full-run and warm available-RAM headroom remain insufficient. Startup/first-call spikes cannot be hidden by considering only successful warm timings. Replacing a model solely because of low RAM is premature: source weights, native runtime footprint and the substantial baseline must be distinguished. A lighter runtime/representation or deliberately selected smaller candidate would need fresh memory, latency and human quality evidence. The current app must keep its explicit memory failure; no default or guard is changed.

```powershell
.\.venv\Scripts\python.exe artifacts/system_memory_inventory.py --output artifacts/idle-baseline-new.json
.\artifacts\run-loading-benchmark.ps1 -Experiment device_map_mmap_clear -Output artifacts/idle-gpu-new
```

These are ignored local diagnostic scripts, not supported application interfaces. Original `configs/v1.toml` remains provisional. Human recordings/references, Hindi listening, acoustic response, physical disconnected operation and 30 microphone turns remain pending. V1 is not validated and optimization goals are not declared achieved.
