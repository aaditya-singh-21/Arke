# V1 validation evidence

Status: V1 application and evaluation tooling implemented. Acceptance remains pending human reference/listening review, a 30-turn microphone session, disconnected real flows, and measured stability/memory evidence.

**Current policy — ADR-014 (2026-10-03), runtime/reporting implemented:** the 1 GiB available-RAM reserve is advisory. `listen` warns and continues on low RAM; excess dedicated VRAM, incomplete telemetry and actual device/OOM failures remain explicit blockers. Checks are recorded after loading and each utterance. New reports identify the policy and separate the RAM advisory from VRAM/telemetry status. Successful execution is reported separately from pending memory/latency trend review. The strongest GPU loading hooks remain diagnostic, not an integrated or accepted default. Earlier failure labels and measurements retain their historical policy meaning; none is retroactively changed to a stability or quality pass. See [the decision](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability).

Runtime-guard verification: **45 passed, 3 skipped in 3.04 s** (`artifacts/adr014-runtime-tests.txt`). Focused checks passed **19/19**, including a mocked 30-turn low-RAM session, missing/gapped telemetry, VRAM limits at startup and after an utterance, actual OOM handling, warning visibility and cleanup. These are deterministic model-free checks, not real microphone or sustained hardware validation. No new model benchmark, quality score or hardware acceptance is claimed for this guard change.

Additional CPU/GPU placement measurements are recorded in [PLACEMENT_EVALUATION.md](PLACEMENT_EVALUATION.md). GPU synthesis and translation improved diagnostic processing latency, but all four tested placements failed the full-run RAM margin. The older measurements below remain historical evidence; no new default is accepted.

The [staging and precision evaluation](STAGING_EVALUATION.md) adds five fresh-process, 90-observation runs: explicit per-provider initialization, serial reload/close per utterance, CPU recognition with GPU MT/TTS, compact GPU precision, and requested CTranslate2 CUB allocator with no retained cache. All completed without provider/OOM or telemetry errors; all failed the available-RAM margin. Full-run minima were 170.1–429.1 MiB. Serial reloads measured processing p50/p95 5.773/6.445 s, including loading and cleanup. CPU recognition measured 2.365/2.651 s and compact GPU precision 0.495/0.603 s. Neither establishes acoustic response or human quality. An initial initialization harness path error is preserved and excluded from successful model runs.

[CPU quantization/cache experiments](CPU_QUANTIZATION_EVALUATION.md) completed two more 90-observation runs, using the CUDA-enabled and isolated official CPU-only builds of torch 2.7.1. Both succeeded without provider/OOM or telemetry failures and both failed RAM headroom. Their processing p50/p95 was 5.984/7.978 s and 3.857/10.316 s. The CPU-only run spans changing background conditions, including the human closing unnecessary apps; it is not an idle comparison or causal savings measurement. Numerical cache parity is scaffolded but unrun because these resource candidates are unaccepted; human quantization/listening quality remains pending.

The subsequent [idle-desktop follow-up](IDLE_BASELINE_EVALUATION.md) measured model-free available RAM of 1583.2 and 1719.8 MiB before two fresh strongest-loader GPU runs. Both completed 90/90 calls; processing p50/p95 was 0.496/0.602 s and 0.481/0.589 s; dedicated VRAM was 2.339 GiB; sampled full RAM minima were 247.7 and 75.0 MiB. Both RAM gates failed, including measured warm-phase headroom. English/Hindi fingerprints matched the original loader for all 94 ordinary calls in each run. An explicit GPU-ASR / CPU-only-PyTorch cached MT/TTS one-case probe also ran but failed RAM headroom (322.3 MiB minimum); it is not a benchmark or accepted configuration. The [goal review](OPTIMIZATION_REVIEW.md) retains the targets and separates file processing, system baseline, model/native memory and pending human/hardware evidence.

Latest ordinary checks after all model processes exited: `.venv/Scripts/python.exe -m pytest -q` — **32 passed, 3 skipped in 3.55 s**, recorded in `artifacts/option6-unit-tests.txt`; provisioned-model integration checks are skipped by default. `git diff --check` passed (line-ending notices only). A fresh normal-environment import confirmed torch **2.7.1+cu126** still comes from `.venv`, with compiled CUDA 12.6; the CPU wheel remains isolated. Derived weights, runtime caches and benchmark outputs are ignored by Git. No application source/default changes were made during these optimization experiments; earlier capture fixes remain preserved. Cache numerical-parity tooling is present but unrun for rejected CPU resource candidates.

The subsequent [loading and first-inference investigation](LOADING_EVALUATION.md) tested nine fresh-process loader configurations/runs with unchanged all-GPU precision/model choices. All completed 90/90 measured file observations without provider/OOM or telemetry errors; all full-run RAM gates failed. Removing 89 stale Kokoro CPU weight attributes released 214.6 MiB of private commit and 136.0 MiB of RSS in an immediate check. Direct translation loading plus Kokoro mmap/cleanup measured full-run RAM minima 315.4/319.6 MiB and dedicated VRAM 2.339 GiB in two runs. Warm processing p50/p95 was 0.487/0.590 s and 0.480/0.598 s. English/Hindi fingerprints matched the baseline; 30 seeded TTS outputs for the combined path were bit-exact. These numerical diagnostics do not pass human quality, microphone or disconnected-operation gates. Application source/defaults were unchanged during this investigation.

Evidence collected on 2026-10-03. No timing in this report is an estimate. Diagnostic speech is local Windows SAPI synthesis; Hindi reference text is authored draft text awaiting bilingual review. Diagnostic category tags are intended coverage, not evidence of actual accents or noise. These runs do not establish population accuracy or human intelligibility.

## Target environment

- CPU: 12th Gen Intel(R) Core(TM) i5-12500H; 16 logical CPUs.
- OS: Windows-10-10.0.26200-SP0; Python: 3.11.15 (main, Jul 23 2026, 14:42:43) [MSC v.1944 64 bit (AMD64)].
- System RAM: 7.692 GiB; snapshot available: 0.224 GiB.
- GPU: NVIDIA GeForce RTX 3050 Laptop GPU; dedicated memory 4.000 GiB; driver 610.88.
- Exact installed package versions: `requirements/windows-tested.txt`. PyTorch 2.7.1+cu126 reported CUDA available; official IndicProcessor 1.1.1 built and imported on Windows.

Background applications were not stopped and power mode was not controlled. RAM headroom was already marginal and varied during downloads/imports. An earlier CPU ASR probe briefly overlapped exploratory GPU loading and is retained at `artifacts/asr-cpu-int8-float32`; the isolated CPU repeat below supersedes it for comparison. All listed real configurations run in separate fresh processes with no concurrent real-provider inference. These results are limited to the current desktop workload. None is a passed combined residency gate.

## Observed benchmark results

Each completed configuration used 30 cases, 3 warm-up calls, and 3 measured passes (90 observations), plus a separately recorded first call. Percentiles use linear interpolation at `(n-1)*q`, excluding unsuccessful observations while reporting their count. Units are seconds/GiB.

| Diagnostic configuration | Successful / scheduled | Warm p50 / p95 | Cold load / launch-to-ready | Peak RSS / total VRAM | Minimum available RAM |
|---|---:|---:|---:|---:|---:|
| Fake file pipeline | 90 / 90 | 0.000 / 0.001 | 0.003 / unmeasured | 0.035 / 0.124 | 0.990 |
| ASR CPU int8_float32 (isolated repeat) | 90 / 90 | 3.363 / 3.748 | 6.475 / 6.942 | 0.945 / 0.326 | 0.106 |
| ASR GPU FP16 | 90 / 90 | 0.254 / 0.287 | 10.200 / 10.742 | 0.702 / 0.941 | 0.066 |
| ASR GPU INT8/FP16 | 90 / 90 | 0.174 / 0.197 | 6.579 / 8.795 | 1.048 / 0.604 | 0.012 |
| Hindi TTS CPU FP32 | 90 / 90 | 2.430 / 3.289 | 45.401 / 45.892 | 1.104 / 0.204 | 0.013 |
| Translation CPU FP32 | 90 / 90 | 1.021 / 1.413 | 18.506 / 19.010 | 1.151 / 0.163 | 0.273 |
| Translation GPU FP16 | 90 / 90 | 0.485 / 0.639 | 19.332 / 19.740 | 1.581 / 0.653 | 0.014 |
| File ASR GPU / translation CPU / TTS CPU | 90 / 90 | 4.359 / 6.080 | 24.644 / 25.136 | 1.690 / 1.026 | 0.011 |
| File ASR GPU / translation GPU / TTS CPU | 90 / 90 | 3.577 / 4.580 | 31.491 / 31.994 | 1.902 / 1.427 | 0.017 |

File processing timings end at complete audio readiness. They exclude human speech-end/release lag and actual audible onset. They cannot pass the microphone response gate. Fake timing refers to a test tone and is not model latency. RSS includes resident native allocations; the reports additionally record process private/VMS memory where available. GPU measurements are device-wide and include background use; sampled peaks can miss short allocations.

## Verification and remaining gates

- Deterministic tests cover contracts, configuration, Unicode console output, silence/empty input, bounds, resampling, cancellation, cleanup, offline sockets, provisioning integrity, lazy ASR consumption, generation termination, benchmark counts/privacy, and review evidence binding.
- Ordinary tests never download/load real models. Provisioned-model tests require `ARKE_MODEL_CHECKS=1`; final test evidence is listed below. Each real stage is checked in a fresh process with cached assets.
- Real adapters use local checksummed assets and a Python socket/DNS guard. This is not proof of physical network disconnection; repeat real file and microphone flows while disconnected for acceptance.
- PTT hardware listing succeeded. The tool execution shell does not supply Windows console key-release events; `listen` fails with an actionable message. Real warm sessions implement ADR-014: RAM is advisory and VRAM/telemetry checks remain enforced. Human validation still requires a focused Windows console, headphones and 30 turns with measured outcomes, memory trends and latency.
- Bilingual English/Hindi reference approval, meaning adequacy, critical-detail review, Hindi listening scores, a recorded demo, true acoustic onset, and manual release lag remain pending. No subjective scores were fabricated.
- Current goals: clean WER ≤20%; ≥27/30 meaning and intelligibility scores ≥4/5; total dedicated VRAM ≤3.5 GiB; no crashes/OOM across 30 microphone turns with memory/latency trends assessed. Available RAM below 1 GiB is an advisory warning (ADR-014). Speech-end-to-audible targets remain p50 ≤3 s/p95 ≤5 s.

## Setup failures and resolutions

- Sandboxed dependency/model networking failed initially; explicit setup downloads were performed with approved network access. Python/cache/environment and weights remain in ignored local directories.
- CTranslate2 initially failed with missing `pkg_resources`; setuptools 75.8.2 fixes that compatibility issue. CPU generic INT8 resolved to INT8/FP32 and was rejected; the diagnostic configuration now requests the actual supported precision.
- Windows redirected output initially could not encode Hindi; CLI streams now use UTF-8 and a subprocess regression check passes.
- Initial IndicTrans2 setup was denied. The user accepted repository access conditions; cached login is used without copying credentials to project files. Local model/module caches no longer hide that login.
- IndicTrans2 setup now selects safetensors rather than downloading duplicate binary weights and explicitly provisions both SentencePiece model.SRC/model.TGT files. Custom tokenizer/config/model source was inspected at the pinned revision before enabling trust_remote_code; hashes are verified on load.
- The main environment temporarily pointed to an inaccessible Windows Store Python launcher. Its configuration was repaired to use project-local Python 3.11.15 while retaining installed packages.

## Model revisions

- asr: `Systran/faster-whisper-small` at `536b0662742c02347bc0e980a01041f333bce120`; checksums are in its ignored provisioning receipt.
- translation: `ai4bharat/indictrans2-en-indic-dist-200M` at `173b94239f7c38886b2747b8d4a5db771a7e1232`; checksums are in its ignored provisioning receipt.
- tts: `hexgrad/Kokoro-82M` at `f3ff3571791e39611d31c381e3a41a3af07b4987`; checksums are in its ignored provisioning receipt.

## Scope and documented deviations

Implementation remains English → Hindi, batch size one, serial local inference, bounded CLI/file/PTT operation, stock Hindi voice, and no cloud fallback. Optional VAD is omitted. No Rust, service/database/account infrastructure, meeting integration, virtual audio devices, cloning, or V2 behavior was added.

The authorized plan permits finishing code and diagnostic composition while unavailable human evaluation is scaffolded. This does not waive milestone acceptance evidence. Providers and placements remain candidates until quality, offline, stability, and combined memory gates pass. Any exploratory GPU translation configuration is explicit and documented, not an automatic fallback.

### Fake file pipeline

- Local evidence: `artifacts/fake-pipeline/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `10193195-7363-4d1c-8b2f-6e214acb5bbc`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.05816589999994903 / 0.1073745700001382 s. Nominal interval: 0.1 s.
- Diagnostic WER: 97.222%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 0.000 / 0.000.
- tts_rtf p50/p95: 0.000 / 0.001.

### ASR CPU int8_float32 (isolated repeat)

- Local evidence: `artifacts/asr-cpu-int8-isolated/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `9b144bd9-a25e-4f95-89a0-4fa1f71727ea`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.11097375000099419 / 0.11220674999995026 s. Nominal interval: 0.1 s.
- Diagnostic WER: 9.444%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 1.423 / 1.703.

### ASR GPU FP16

- Local evidence: `artifacts/asr-gpu-fp16-isolated/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `4f38e056-22af-4c6d-856e-4a964fdb84be`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.10912004999954661 / 0.1159461950003788 s. Nominal interval: 0.1 s.
- Diagnostic WER: 9.444%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 0.114 / 0.126.

### ASR GPU INT8/FP16

- Local evidence: `artifacts/asr-gpu-int8-isolated/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `45feb973-9951-4d85-a799-3c57a46cf364`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.11010670000086975 / 0.11213894499906019 s. Nominal interval: 0.1 s.
- Diagnostic WER: 9.444%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 0.078 / 0.087.

### Hindi TTS CPU FP32

- Local evidence: `artifacts/tts-cpu-diagnostic/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `c4e5b15a-5b2e-4b9f-8546-3b4a3e51a976`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.10963569999967149 / 0.1129983250006262 s. Nominal interval: 0.1 s.
- tts_rtf p50/p95: 0.749 / 0.792.

### Translation CPU FP32

- Local evidence: `artifacts/translation-cpu-diagnostic/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `7a63dc27-df99-45a2-9a97-048e9115089f`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.10960140000042884 / 0.11424411999869336 s. Nominal interval: 0.1 s.

### Translation GPU FP16

- Local evidence: `artifacts/translation-gpu-diagnostic/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `fbb15133-6b59-4f70-8c5c-51929ed90ae7`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.1096493000004557 / 0.11461366999865276 s. Nominal interval: 0.1 s.

### File ASR GPU / translation CPU / TTS CPU

- Local evidence: `artifacts/pipeline-initial-diagnostic/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `7b7f7e58-1df6-435c-a80d-e1f2f8314be8`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.10995055000057619 / 0.11460194999972373 s. Nominal interval: 0.1 s.
- Diagnostic WER: 9.444%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 0.227 / 0.317.
- tts_rtf p50/p95: 0.779 / 1.380.

### File ASR GPU / translation GPU / TTS CPU

- Local evidence: `artifacts/pipeline-gpu-translation-diagnostic/metadata.json`, `records.jsonl`, `summary.json`, and `behavior.jsonl` when available. Run ID: `b5d8ee84-30e9-4447-a788-1137a21d506e`.
- Outcomes: {'ok': 90}; error codes: {}; fatal error: None.
- Memory gate: **fail**. Sample interval p50/p95: 0.10971320000044216 / 0.11209228499965321 s. Nominal interval: 0.1 s.
- Diagnostic WER: 9.444%; not a human clean/noisy evaluation result.
- asr_rtf p50/p95: 0.206 / 0.258.
- tts_rtf p50/p95: 0.756 / 0.808.

## Final command checks

- `.venv/Scripts/python.exe -m pytest -q`: 31 passed, 3 skipped in 5.20s. Evidence: `artifacts/unit-tests-final.txt`.
- `ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k asr`: 1 passed, 2 deselected, 2 warnings in 7.70s. Evidence: `artifacts/model-check-asr.txt`.
- `ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k translation`: 1 passed, 2 deselected in 14.93s. Evidence: `artifacts/model-check-translation.txt`.
- `ARKE_MODEL_CHECKS=1 .venv/Scripts/python.exe -m pytest -q tests/integration/test_provisioned_models.py -k tts`: 1 passed, 2 deselected, 2 warnings in 19.42s. Evidence: `artifacts/model-check-tts.txt`.
- Real `translate-file --config configs/v1.toml --play` completed with status `ok`, first-call processing 8.444 s, output duration 2.900 s. This single cold-first call is separate from warmed benchmark percentiles. Hindi WAV: `artifacts/example-hi.wav`; structured result: `artifacts/file-real-result.json`.
- Real PortAudio playback completed through the default JLab headphones at 24000 Hz; audio-ready to scheduled-DAC onset proxy 0.571 s. No output resampling was required. Evidence: `artifacts/file-playback.json`. Actual Bluetooth/acoustic onset and human listening quality remain unmeasured.
