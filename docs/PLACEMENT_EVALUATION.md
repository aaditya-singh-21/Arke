# CPU/GPU placement evaluation

**Historical policy note:** RAM-gate failures and rejection conclusions in this report use the former mandatory 1 GiB reserve. [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), accepted later on 2026-10-03, makes that reserve advisory. Measurements/artifacts are preserved; this does not retrospectively establish microphone stability or quality. The current runtime/reporting implements ADR-014; these artifacts retain their historical policy.

Measured on 2026-10-03. This evaluates V1 candidates; application source, defaults and acceptance targets were unchanged during this experiment. The new TOMLs are explicit experiment configurations, not accepted defaults.

The same cached immutable Whisper small, IndicTrans2 distilled 200M and Kokoro-82M stock Hindi voice assets were used. Whisper stays GPU FP16, Kokoro stays FP32. Translation stays FP32 for the placement-only comparisons; the final all-GPU run changes translation to FP16 separately. Batch size one, serial inference, decoding/limits unchanged. Original loaders were used; the option-1 memory-mapping hook was not applied.

The fixed 30-case SAPI/draft manifest is unreviewed. Each fresh process separately measured load and first inference, then three warm-ups and three passes (90 observations). Runs were serial in this order: standalone GPU synthesis, GPU synthesis in the pipeline, all-GPU FP32 translation, all-GPU FP16 translation, original placement. No simultaneous model benchmark was running. Configuration/package/model metadata, every outcome, per-category distributions, WER and real-time factors are preserved in the local artifacts.

Hardware: Intel i5-12500H, RTX 3050 Laptop GPU 4 GiB, 8,259,358,720 bytes system RAM, Windows build 26200. Python 3.11.15, torch 2.7.1+cu126, CTranslate2 4.6.0, faster-whisper 1.2.1, transformers 4.51.3, Kokoro 0.9.4. Windows power scheme was Balanced; AC/battery state and exact device clock/thermal conditions were not captured. Codex desktop remained open. No models, dependencies or infrastructure were downloaded/installed.

## Composed file processing

Times below are processing start to complete Hindi audio buffer. They exclude playback, human release lag and acoustic onset, so they do not pass the microphone response-latency gate. Percentiles use linear interpolation on successful observations; failures remain reported beside them.

| Placement (ASR / translation / synthesis) | Successes | Processing p50 / p95 (s) | Cold launch to ready (s) | First processing (s) | Peak dedicated VRAM (GiB) | Full-run RAM minimum (MiB) | Memory gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Original: GPU / CPU / CPU | 90/90 | 1.988 / 2.609 | 13.395 | 4.281 | 0.838 | 232.4 | fail |
| GPU synthesis: GPU / CPU / GPU | 90/90 | 0.846 / 1.131 | 14.971 | 6.472 | 1.596 | 46.9 | fail |
| All GPU, translation FP32 | 90/90 | 0.478 / 0.592 | 14.736 | 4.452 | 2.398 | 80.3 | fail |
| All GPU, translation FP16 | 90/90 | 0.480 / 0.598 | 15.272 | 3.085 | 1.982 | 123.8 | fail |

## RAM by phase

The margin remains at least 1 GiB = 1024 MiB available RAM. A warm-phase result does not waive loading or first-call failures. The phase diagnostic saved system/RSS/native-GPU samples and monotonic boundaries without changing model calls. Phase summaries inherit any telemetry errors recorded in the full summary.

| Placement | Baseline available (MiB) | Loading minimum (MiB) | First inference minimum (MiB) | Measured warm minimum (MiB) | Full-run peak RSS (GiB) |
|---|---:|---:|---:|---:|---:|
| Original: GPU / CPU / CPU | 2353.6 | 633.8 | 309.0 | 232.4 | 2.191 |
| GPU synthesis: GPU / CPU / GPU | 1329.9 | 59.7 | 46.9 | 286.2 | 1.712 |
| All GPU, translation FP32 | 1993.9 | 338.0 | 80.3 | 1021.7 | 1.783 |
| All GPU, translation FP16 | 2588.8 | 123.8 | 351.5 | 564.7 | 2.418 |

Baseline RAM varied substantially between fresh processes. These are measured outcomes under the observed desktop workload, not a controlled estimate of RAM saved by changing a device. File-backed pages, OS working-set decisions and native/runtime allocations affect RSS and available RAM. Windows private-byte figures in the artifacts are committed memory and must not be interpreted as resident physical RAM.

## Stage timings within the pipeline

| Placement | ASR p50 / p95 (s) | Translation p50 / p95 (s) | Synthesis p50 / p95 (s) |
|---|---:|---:|---:|
| Original: GPU / CPU / CPU | 0.200 / 0.448 | 0.536 / 0.786 | 1.158 / 1.567 |
| GPU synthesis: GPU / CPU / GPU | 0.173 / 0.191 | 0.542 / 0.817 | 0.115 / 0.186 |
| All GPU, translation FP32 | 0.172 / 0.188 | 0.184 / 0.254 | 0.113 / 0.183 |
| All GPU, translation FP16 | 0.170 / 0.186 | 0.187 / 0.270 | 0.113 / 0.180 |

Standalone GPU FP32 synthesis succeeded on 90/90 observations. Warm synthesis p50/p95: 0.116/0.178 s; TTS real-time factor p50/p95: 0.033/0.056. Its full-run memory gate was fail; peak dedicated GPU memory 0.810 GiB. These Hindi references remain unreviewed.

## Failures, telemetry and quality

| Placement | Failed/skipped measured calls | Fatal error | Telemetry errors | Sampling interval p50 / p95 (ms) | Diagnostic WER |
|---|---:|---|---|---:|---:|
| Original: GPU / CPU / CPU | 0 | None | none | 110.6 / 112.7 | 9.44% |
| GPU synthesis: GPU / CPU / GPU | 0 | None | none | 110.5 / 112.2 | 9.44% |
| All GPU, translation FP32 | 0 | None | none | 110.9 / 112.1 | 9.44% |
| All GPU, translation FP16 | 0 | None | none | 110.0 / 112.1 | 9.44% |

Sampling was requested every 100 ms. Brief peaks may be missed. Total dedicated VRAM includes other device use, including Codex/Windows; PyTorch counters alone were not used. No provider failure or OOM was observed in these file benchmarks. That does not establish the required 30-turn microphone stability gate.

WER applies only to SAPI diagnostic English with unreviewed references. Tags include intended accent/noise coverage, but the synthetic recordings do not validate those real conditions. Bilingual adequacy, names/numbers/negation correctness and Hindi listening scores remain unreviewed. Raw text/audio was not retained in these placement runs. Offline socket guards and cached assets were used, but a physically disconnected real microphone/file acceptance run remains pending.

Deterministic checks after the model processes exited: `.venv/Scripts/python.exe -m pytest -q tests/unit` completed with 32 passed in 5.42 s (`artifacts/option2-unit-tests.txt`). All four configuration files parsed successfully. Record checks confirmed one first call, three warm-ups, 90 measured observations and 30 distinct cases in each run, with actual provider device/precision metadata matching the selected configurations.

## Interpretation and next decision

GPU synthesis is the main measured speed improvement. Moving translation to the GPU gives a further processing improvement. All-GPU FP32 and FP16 translation have very similar warm timings here; FP16 reduces dedicated VRAM but did not establish the RAM margin. All sampled GPU peaks were below the unchanged 3.5 GiB ceiling.

All-GPU FP32 is a promising next memory/loading experiment because it combines short processing time with warm available RAM close to the target. It is not accepted: the measured minimum still fell below 1024 MiB, and loading/first inference failed the margin much more substantially. The translation and synthesis adapters first construct/load models on CPU and then move them to the configured device; GPU placement does not eliminate their transient CPU loading or native runtime/workspace memory.

The current original-placement rerun is faster than the earlier historical composed diagnostic. Neither implementation nor default changed in this experiment. Desktop headroom, OS/file caches and device clock conditions can change observed timing; these runs do not isolate the cause of the historical difference. Historical results remain in VALIDATION.md.

No model/device/precision default or safety gate was changed. No model replacement is justified solely by these results. The next useful experiment is to address transient host loading/first-call allocations while preserving the promising GPU placement, then repeat the full protocol and the human/hardware gates. The isolated option-1 checkpoint experiment is not proof that combining it with this placement will pass.

CPU ASR was not rerun in this matrix: earlier isolated CPU-ASR diagnostics were slower, and current GPU VRAM headroom does not require moving recognition off GPU. This matrix is not an exhaustive placement search; prior CPU-ASR evidence remains in VALIDATION.md.

## Reproduce and inspect

Use a provisioned local environment and new empty output directories. The standard benchmark command reproduces complete processing/memory summaries; additional phase files in this experiment came from the ignored local diagnostic runner `artifacts/placement_benchmark.py`.

```powershell
.\scripts\benchmark-process.ps1 -Stage pipeline -Config configs/v1.toml -Manifest data/eval/asr-diagnostic-2/manifest.jsonl -Output artifacts/option2-pipeline-original-repeat -AllowUnreviewed -BaselineNote "Describe current power and desktop workload"
.\scripts\benchmark-process.ps1 -Stage pipeline -Config configs/gpu-tts.toml -Manifest data/eval/asr-diagnostic-2/manifest.jsonl -Output artifacts/option2-pipeline-gpu-tts-repeat -AllowUnreviewed -BaselineNote "Describe current power and desktop workload"
.\scripts\benchmark-process.ps1 -Stage pipeline -Config configs/all-gpu-fp32.toml -Manifest data/eval/asr-diagnostic-2/manifest.jsonl -Output artifacts/option2-pipeline-all-gpu-fp32-repeat -AllowUnreviewed -BaselineNote "Describe current power and desktop workload"
.\scripts\benchmark-process.ps1 -Stage pipeline -Config configs/all-gpu.toml -Manifest data/eval/asr-diagnostic-2/manifest.jsonl -Output artifacts/option2-pipeline-all-gpu-fp16-repeat -AllowUnreviewed -BaselineNote "Describe current power and desktop workload"
```

Local evidence:

- `artifacts\option2-pipeline-original`: run `15b8e41d-5556-4a9e-b255-45d9775dfa63`, config `configs/v1.toml`, manifest SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Contains summary JSON/Markdown, metadata, complete outcome records, separate behavior checks, native memory samples and phase summaries.
- `artifacts\option2-pipeline-gpu-tts`: run `9aae964c-21b9-4685-9a87-573d63e81891`, config `configs/gpu-tts.toml`, manifest SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Contains summary JSON/Markdown, metadata, complete outcome records, separate behavior checks, native memory samples and phase summaries.
- `artifacts\option2-pipeline-all-gpu-fp32`: run `0684a000-5f59-4761-91b2-e1f3f00d09c5`, config `configs/all-gpu-fp32.toml`, manifest SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Contains summary JSON/Markdown, metadata, complete outcome records, separate behavior checks, native memory samples and phase summaries.
- `artifacts\option2-pipeline-all-gpu-fp16`: run `d920e67c-894f-40c8-b212-ac478f3a6764`, config `configs/all-gpu.toml`, manifest SHA256 `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Contains summary JSON/Markdown, metadata, complete outcome records, separate behavior checks, native memory samples and phase summaries.

Standalone synthesis: `artifacts/option2-tts-gpu-fp32`. Power scheme: `artifacts/option2-power-scheme.txt`. Each console log is preserved separately. Only performance metadata was persisted.
