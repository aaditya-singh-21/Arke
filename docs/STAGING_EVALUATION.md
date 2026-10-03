# Staging, precision and allocator evaluation

**Historical policy note:** RAM-gate failures and rejection conclusions in this report use the former mandatory 1 GiB reserve. [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), accepted later on 2026-10-03, makes that reserve advisory. Measurements/artifacts are preserved; this does not retrospectively establish microphone stability or quality. The current runtime/reporting implements ADR-014; these artifacts retain their historical policy.

Measured on 2026-10-03, after the [loading investigation](LOADING_EVALUATION.md). The human requested continued optimization evaluation and will provide human reference/listening review and microphone validation afterward. Those gates remain pending; no quality score or microphone result was fabricated. All changes in this evaluation are ignored diagnostic scripts/configurations and documentation. Application source/defaults are unchanged.

## Experiments and boundaries

The same cached Whisper small, IndicTrans2 distilled 200M and Kokoro-82M Hindi voice assets were used. Batch size one, serial English→Hindi, the same bounded audio/text/decoding and offline guard were retained. No model was replaced or downloaded. CPU preprocessing remains in every placement. Direct GPU translation loading, Kokoro checkpoint mmap and stale CPU WeightNorm-attribute cleanup from the preceding investigation were included throughout.

1. **Staged initialization:** load one provider, execute one explicit case-01 initialization call, then load the next provider. All models remain loaded afterward. Initialization is included in startup time and full-run memory; it is not hidden before sampling. The first composed call is after per-provider initialization, not the native cold first call.
2. **Staged residency:** serially load/close providers at startup for compatibility checks, then load/infer/close each provider for each utterance. Ordinary garbage collection and PyTorch CUDA cache release occur before the next stage. Every load, inference and cleanup cost is included in stage/processing timing. No operating-system working-set trimming is performed.
3. **CPU recognition:** Whisper small explicitly uses supported CPU `int8_float32`; translation and synthesis remain GPU FP32 and loaded for the session. This tests the same model with a different placement/precision, not an automatic fallback.
4. **Compact GPU precision:** explicitly select Whisper small GPU `int8_float16` and translation GPU `float16`; synthesis remains GPU FP32. This combined precision comparison cannot isolate each dtype's individual memory effect. Prior individual precision diagnostics remain in VALIDATION.md. Human quality review is required before adoption.
5. **Native allocator:** retain all-GPU ASR FP16 / translation and synthesis FP32 and change only the requested CTranslate2 allocator to `cub_caching` with `CT2_CUDA_CACHING_ALLOCATOR_CONFIG=4,3,12,0` (zero retained cached bytes). Both settings are scoped before the fresh process imports CTranslate2 and restored afterward. The [CTranslate2 4.6.0 allocator implementation](https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.6.0/src/cuda/allocator.cc) supports these settings. There is no exposed Python query for the resolved allocator; the record distinguishes the explicit request from a directly queried allocator identity.

Hardware/dependencies match LOADING_EVALUATION.md: Windows build 26200, Intel i5-12500H, RTX 3050 Laptop GPU 4 GiB, 8,259,358,720 bytes RAM, Python 3.11.15, torch 2.7.1+cu126, CTranslate2 4.6.0, faster-whisper 1.2.1, transformers 4.51.3, Kokoro 0.9.4. Direct loading uses isolated Accelerate 1.6.0 in `.cache/investigation-accelerate`; application dependencies are unchanged.

Each run was a fresh process with three warm-ups and three passes over the same fixed 30 unreviewed SAPI/draft cases (90 observations), plus a separate first composed call. Staged initialization adds one startup call per provider explicitly recorded in `initialization-calls.jsonl`. The manifest SHA256 remains `080410a68e06453b71cc10e2d66d6b3bd4b5601c3c87266c3ea48c53d3ed90d2`. Runs were serial in the table order. Codex/Windows remained open; RAM baseline/power/clock/thermal state was not fixed. During the long residency and CPU runs, small transient progress-reader processes were used; their measured RSS was approximately 19–26 MiB and is included in system RAM observations. Cross-run headroom differences are not a controlled estimate of model/runtime memory saved.

## Results

File processing ends at a complete Hindi audio buffer, excluding playback, release lag and acoustic onset. p50/p95 use linear interpolation on successful observations; all failures are reported separately. Diagnostic hooks add first-call snapshot/mapping overhead and small warm metadata overhead. Staged-residency RTFs include its reload/cleanup cost, not just model inference. Margins remain 1024 MiB available RAM and 3.5 GiB total dedicated device VRAM. Full-run minima include startup and first calls.

| Experiment | Successes | Processing p50 / p95 (s) | Cold load (s) | First composed processing (s) | Full RAM minimum (MiB) | Peak dedicated VRAM (GiB) | Memory gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Per-provider initialization, all GPU | 90/90 | 0.495 / 0.579 | 20.678 | 0.564 | 170.1 | 2.351 | fail |
| One resident provider, all GPU | 90/90 | 5.773 / 6.445 | 15.789 | 10.102 | 325.6 | 3.124 | fail |
| CPU ASR INT8/FP32; GPU MT/TTS FP32 | 90/90 | 2.365 / 2.651 | 17.212 | 5.077 | 429.1 | 1.571 | fail |
| GPU ASR INT8/FP16; MT FP16; TTS FP32 | 90/90 | 0.495 / 0.603 | 16.664 | 3.879 | 334.6 | 1.634 | fail |
| All GPU FP32 MT; CT2 CUB cache=0 | 90/90 | 0.623 / 0.752 | 16.727 | 4.181 | 367.3 | 2.962 | fail |

| Experiment | Loading RAM min (MiB) | First RAM min (MiB) | Measured RAM min (MiB) | Peak RSS / private commit (GiB) | Sample interval p50 / p95 (ms) | Diagnostic WER | ASR / Hindi text matches vs FP32 baseline |
|---|---:|---:|---:|---:|---:|---:|---|
| Per-provider initialization, all GPU | 170.1 | 480.6 | 400.5 | 1.730 / 6.412 | 110.2 / 112.0 | 9.44% | 94/94; 94/94 |
| One resident provider, all GPU | 325.6 | 424.6 | 565.2 | 1.931 / 8.412 | 110.7 / 175.2 | 9.44% | 94/94; 94/94 |
| CPU ASR INT8/FP32; GPU MT/TTS FP32 | 441.4 | 447.3 | 504.3 | 2.015 / 6.032 | 110.1 / 112.9 | 9.44% | 91/94; 94/94 |
| GPU ASR INT8/FP16; MT FP16; TTS FP32 | 431.0 | 472.2 | 346.6 | 1.888 / 5.661 | 110.3 / 112.2 | 9.44% | 91/94; 94/94 |
| All GPU FP32 MT; CT2 CUB cache=0 | 430.7 | 381.4 | 367.3 | 1.548 / 6.988 | 110.1 / 112.1 | 9.44% | 94/94; 94/94 |

Requested memory interval was 100 ms; actual intervals are reported above, and brief peaks may be missed. RSS includes resident native allocations; private bytes are committed memory rather than physical RAM. Dedicated VRAM is device-wide, including background use; PyTorch counters alone do not establish the gate. DLL region inventories are not resident-page attribution (see the correction in LOADING_EVALUATION.md). Category summaries and ASR/TTS RTFs remain in each complete summary, with all outcomes and samples retained.

| Experiment | Failed/skipped measured calls | Fatal error | Telemetry errors | Actual ASR / translation / synthesis |
|---|---:|---|---|---|
| Per-provider initialization, all GPU | 0 | None | [] | cuda float16 / cuda float32 / cuda float32 |
| One resident provider, all GPU | 0 | None | [] | cuda float16 / cuda float32 / cuda float32 |
| CPU ASR INT8/FP32; GPU MT/TTS FP32 | 0 | None | [] | cpu int8_float32 / cuda float32 / cuda float32 |
| GPU ASR INT8/FP16; MT FP16; TTS FP32 | 0 | None | [] | cuda int8_float16 / cuda float16 / cuda float32 |
| All GPU FP32 MT; CT2 CUB cache=0 | 0 | None | [] | cuda float16 / cuda float32 / cuda float32 |

Quality remains unreviewed. Intended accent/noise categories are not actual population coverage in synthetic speech. Text fingerprints diagnose numerical output changes; they do not establish bilingual adequacy or critical-detail correctness. Seeded TTS parity from the previous investigation is limited to those loader modifications and cases; it is not a new listening score for these configurations.

An initial staged-initialization harness attempt used the manifest-relative audio path instead of `resolved_audio_path` and failed with invalid input before model loading. The corrected fresh run is shown above; the failed attempt remains at `artifacts/option4-staged-initialization`. It is a diagnostic harness failure, not a successful model run.

## Interpretation

Neither changing initialization order nor closing/reloading each provider solved the available-RAM gate. Reloading adds a substantial response cost and does not prove that process/runtime allocations are returned to the operating system. CPU ASR and compact GPU precision lower dedicated VRAM in these observations, but the required host RAM margin remains unmet. The explicit allocator comparison also fails that margin. These findings narrow the next investigation to CPU runtime/weight representation or another explicitly evaluated model candidate; they do not establish that a model replacement is necessary or sufficient. Application defaults and provisional targets remain unchanged.

## Evidence and reproduction

These are ignored local investigation scripts, not supported application interfaces. Use new empty output directories. No additional model provisioning is required on this machine. The CPU/compact TOMLs are ignored experiment configurations, not defaults. The launcher sets/restores the isolated Accelerate path and allocator settings.

```powershell
.\artifacts\run-loading-benchmark.ps1 -Experiment staged_initialization -Output artifacts/staged-init-new
.\artifacts\run-loading-benchmark.ps1 -Experiment staged_residency -Output artifacts/staged-residency-new
.\artifacts\run-loading-benchmark.ps1 -Experiment cpu_asr_device_map_mmap_clear -Output artifacts/cpu-asr-gpu-new
.\artifacts\run-loading-benchmark.ps1 -Experiment gpu_compact_device_map_mmap_clear -Output artifacts/compact-gpu-new
.\artifacts\run-loading-benchmark.ps1 -Experiment device_map_mmap_clear_cub_no_cache -Output artifacts/cub-no-cache-new
```

Every directory contains model/dependency/configuration metadata, complete outcome/category/RTF summaries, memory samples, phase markers, hook checkpoints, behavior checks and content-free fingerprints. Residency and initialization add explicit lifetime/call records; allocator settings have their own record. Raw generated audio and text were not persisted.

| Local directory | Run ID |
|---|---|
| `artifacts/option4-staged-initialization-fixed` | `9b703d38-6b4d-4be7-b4ee-6b489387b8b7` |
| `artifacts/option4-staged-residency` | `e43a2550-9ec4-4f7f-8c0c-c47c427bf7cd` |
| `artifacts/option4-cpu-asr-gpu` | `8d6f7b66-6edb-4601-b629-dbf2757ddd03` |
| `artifacts/option4-compact-gpu` | `9e4207ea-ca73-40eb-b7f7-f05c60500e4c` |
| `artifacts/option4-cub-no-cache` | `981ee297-c3ad-49ab-a239-36b72d036d10` |
