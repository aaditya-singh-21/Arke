## Long-term product direction
The long-term goal is a platform-independent, near-real-time
voice translation layer for natural multilingual communication.

The product is intended to work across communication platforms
rather than becoming a replacement video-conferencing service.

V1 deliberately uses a modular:

speech → ASR → translation → TTS

pipeline because it is easier to benchmark, debug, replace, and
optimize on constrained local hardware.

Future work may evaluate direct speech-to-speech models when they
provide measurable improvements in latency, quality, prosody, or
voice preservation.

The project follows a local-first, cloud-capable philosophy.
Inference should remain local whenever the user's hardware can meet
the required quality and latency targets. Cloud inference may later
be used selectively when local hardware cannot satisfy those targets.

During the portfolio stage, cloud inference is optional and can remain
disabled so recurring inference cost stays effectively zero.

The expected evolution is:

V1
→ local utterance translation

V2
→ streaming/conversational translation

Portfolio extensions
→ desktop/system audio integration
→ voice preservation
→ virtual audio devices/native adapters

Hybrid
→ selective local/cloud inference

Production
→ multi-user reliability, regional inference, scaling,
   observability, privacy, authentication and cost management


# Local Voice Translator — V1

**Status: V1 code and evaluation tooling implemented; local real-model diagnostics ran, but V1 acceptance remains pending.** See [validation evidence](docs/VALIDATION.md) for measured results and remaining gates.

**Current RAM policy:** [ADR-014](docs/DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability) makes the 1 GiB available-RAM reserve advisory. A lower reading does not establish that the app will crash; acceptance depends on measured execution, memory/latency trends and the 30-turn microphone stability test. `listen` now warns and continues on low RAM, checking memory after loading and each utterance. Excess dedicated VRAM, missing telemetry and actual device/OOM failures remain explicit blockers. New reports separate the RAM advisory from VRAM/telemetry status; historical RAM-gate failures retain their original meaning. Models, placements and defaults are unchanged.

The [CPU/GPU placement evaluation](docs/PLACEMENT_EVALUATION.md) records additional fixed-set diagnostics. GPU synthesis and translation improved file processing latency, but every tested placement failed the available-RAM margin. `configs/gpu-tts.toml`, `configs/all-gpu-fp32.toml`, and `configs/all-gpu.toml` are explicit experiment configurations; `configs/v1.toml` remains the provisional default.

The [loading investigation](docs/LOADING_EVALUATION.md) found removable Kokoro CPU tensor storage and tested direct GPU loading/checkpoint mapping. Two combined diagnostic runs completed 90/90 observations each, with warm processing p50/p95 about 0.48/0.60 s and 2.339 GiB peak dedicated VRAM, but first-call available RAM still fell to about 315–320 MiB. These process-local experiments are not applied to the application or accepted as a microphone configuration.

The [staging and precision evaluation](docs/STAGING_EVALUATION.md) tested initialization order, one-provider residency, CPU recognition, compact GPU precision and CTranslate2 allocator settings. All five completed 90/90 diagnostic observations, but none passed the full-run RAM margin. Reloading every stage raised processing p50/p95 to 5.77/6.44 s. These are investigation results; application defaults remain unchanged.

The [CPU quantization investigation](docs/CPU_QUANTIZATION_EVALUATION.md) records explicit derived-weight provisioning, cached loading, and failed probes. The first completed all-CPU quantized/cached benchmark using the CUDA-enabled PyTorch build succeeded on 90/90 calls but measured processing p50/p95 5.98/7.98 s and only 202.5 MiB minimum available RAM. Its experimental loader is not an accepted application configuration.

After the human closed unnecessary apps, [two idle-desktop follow-ups](docs/IDLE_BASELINE_EVALUATION.md) of the strongest GPU loader each completed 90/90 calls at processing p50/p95 about 0.48–0.50/0.59–0.60 s, but both RAM gates failed. The [optimization goal review](docs/OPTIMIZATION_REVIEW.md) retains the documented targets and explains why file timing and synthetic diagnostics cannot establish microphone or quality acceptance. No default or memory guard was changed.

Translate a completed English utterance into Hindi through a local, serial speech → ASR → translation → TTS pipeline. Python CLI, English → Hindi only, one speaker and one utterance at a time. File input and Windows push-to-talk are implemented. The initial candidate placement is Whisper small on GPU, IndicTrans2 distilled 200M on CPU, and Kokoro-82M stock Hindi speech on CPU. Combined diagnostic measurements failed the available-RAM margin; placement and quality remain provisional.

Inference uses cached assets with explicit device/precision and fails clearly when prerequisites are missing. Model downloads are explicit setup actions. Audio capture is bounded to 15 seconds and paused during playback. There is no automatic model/device/cloud fallback.

## Reading order

Read [AGENTS.md](AGENTS.md), this README, [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [decisions](docs/DECISIONS.md). [SETUP.md](docs/SETUP.md) contains Windows dependency/model steps; [EVALUATION.md](docs/EVALUATION.md) defines references, benchmarks, and human review; [VALIDATION.md](docs/VALIDATION.md) distinguishes measured results from pending work.

For a complete code walkthrough, read [the implementation guide](docs/IMPLEMENTATION_GUIDE.md). It maps the directory structure, every application/configuration/test/script file, command flows, model adapters, audio lifecycle, offline controls, measurement policy, and local experiment boundaries.

## Setup and deterministic checks

Run PowerShell from the project root. The script uses `uv`, project-local Python 3.11, and ignored caches/environment.

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m voice_translator doctor --config configs/v1.toml --output artifacts/doctor.json
```

`doctor` reports hardware/packages, free RAM/VRAM, audio devices, and configured model readiness without loading models. A driver inventory does not prove CUDA library compatibility. Tests use generated fixtures and fake/mocked providers; model checks are opt-in and never download weights.

## Runnable interfaces

These commands exist. Real providers require installed dependencies, provisioned assets, and native runtime compatibility; code existence is not a passed V1 acceptance gate.

```powershell
# Add each adapter and benchmark it alone before composition:
.\scripts\bootstrap.ps1 -Asr
.\.venv\Scripts\python.exe -m voice_translator setup-models --stage asr --config configs/v1.toml

# Prepare drafts; human recordings and reference review are required:
.\.venv\Scripts\python.exe -m voice_translator eval-init --manifest data/eval/manifest.jsonl
.\.venv\Scripts\python.exe -m voice_translator eval-validate --manifest data/eval/manifest.jsonl

.\.venv\Scripts\python.exe -m voice_translator benchmark --stage asr --manifest data/eval/manifest.jsonl --output artifacts/asr-run
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage translation --manifest data/eval/manifest.jsonl --output artifacts/translation-run
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage tts --manifest data/eval/manifest.jsonl --output artifacts/tts-run --retain-content
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage pipeline --manifest data/eval/manifest.jsonl --output artifacts/composed-run

.\.venv\Scripts\python.exe -m voice_translator translate-file --input data/eval/audio/case-01.wav --output artifacts/example-hi.wav --config configs/v1.toml
.\.venv\Scripts\python.exe -m voice_translator listen --mode ptt --config configs/v1.toml --turns 30
```

Translation setup requires accepting the IndicTrans2 repository conditions, authorized access, the official IndicProcessor, and review of the pinned custom model code. TTS requires cached Kokoro weights, a Hindi stock voice, and its Hindi phonemizer assets. Follow [setup instructions](docs/SETUP.md) rather than assuming the commands above install all providers.

For a model-free smoke test:

```powershell
.\.venv\Scripts\python.exe -m voice_translator eval-init --config configs/fake.toml --manifest data/eval/synthetic/manifest.jsonl --synthetic
.\.venv\Scripts\python.exe -m voice_translator translate-file --config configs/fake.toml --input data/eval/synthetic/audio/case-01.wav --output artifacts/test-tone.wav
```

The fake provider outputs fixed English/Hindi text and a test tone, not translated speech. Existing evaluation manifests are preserved; benchmark directories must be empty. If a manifest already exists, reuse it rather than rerunning initialization.

PTT requires a focused Windows console with key release events. Hold Space, release to translate, Esc to cancel, Q to quit. Use headphones. File output uses the actual synthesis sample rate; device resampling is explicit and recorded. Hindi console output is UTF-8. Performance metrics omit raw text/audio unless retention is enabled; console text and explicitly requested WAV export remain visible.

## Acceptance and limits

Use 30 fixed 2–6 second utterances with checked English and reviewed Hindi. Each configuration records cold load, first inference, three warm-ups, and 90 measured observations. Reports contain p50/p95, failures, categories, WER, real-time factors, sampled process/system/native GPU memory, and review status. Human adequacy/listening scores, critical details, a disconnected real file/microphone run, combined memory, and a 30-turn microphone session are required before calling V1 validated.

Provisional goals remain p50 ≤3 s/p95 ≤5 s speech-end-to-audible response, clean WER ≤20%, ≥90% meaning/intelligibility ≥4/5, dedicated VRAM ≤3.5 GiB, and no crashes/OOM across 30 microphone turns. Available RAM below 1 GiB is an advisory warning; continue recording it and examining session memory/latency trends. File processing timings and PortAudio playback proxies do not establish true audible response latency. Missing or failed gates stay visible in [VALIDATION.md](docs/VALIDATION.md).

V1 includes no Rust, cloud inference, servers, accounts, databases, virtual devices, Zoom/Meet integration, voice cloning, continuous interpretation, Hindi → English, training, or deployment. Optional VAD is omitted. Model weights, recordings, credentials, environments, and generated artifacts are ignored by Git. No unreviewed model or hardware result is described as accepted.
