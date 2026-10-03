# V1 architecture

## Flow and execution model

```text
Microphone / WAV
       |
Capture + endpoint (push-to-talk release; later simple VAD)
       |
Mono audio normalized for ASR
       |
SpeechRecognizer -> English transcript
       |
TextTranslator -> Hindi text
       |
SpeechSynthesizer -> Hindi audio + sample rate
       |
Headphone playback / WAV export

Configuration selects adapters; metrics observe every boundary.
```

ASR means automatic speech recognition; TTS means text-to-speech. An endpoint is the moment an utterance is considered complete. A provider is a replaceable implementation of a stage contract.

Use one Python process and serial orchestration initially. An audio callback may copy input into a bounded buffer, but must never perform model inference. A worker handles the finalized utterance, then playback. Model execution should not overlap until profiling justifies it. Avoid a general event bus, HTTP services, and background model workers in V1.

States: `READY -> RECORDING -> PROCESSING -> PLAYING -> READY`. Failure returns to `READY` after cleanup and an actionable error. Cancellation discards unfinished work and suppresses stale audio using the utterance ID. Shutdown stops capture/playback and closes providers.

Default capture limits should be explicit: propose 15 seconds maximum per utterance, one active job, and no pending-job queue. Show the duration limit when reached and finalize the captured audio. For long input files, reject unsupported length until deliberate segmentation is implemented. Never silently truncate text tokens or audio.

## Provider contracts

Implement these as typed synchronous Python protocols or abstract classes; exact code names may change together with callers and docs.

| Contract | Input | Output | Required behavior |
|---|---|---|---|
| `SpeechRecognizer.transcribe` | `AudioBuffer`, source language `en` | `Transcript` | English text and optional segments; transcription task, not Whisper translation |
| `TextTranslator.translate` | English text, `en`, `hi` | `Translation` | Hindi Unicode text; preserve meaning and entities |
| `SpeechSynthesizer.synthesize` | Hindi text, `hi`, configured stock voice | `SynthesizedAudio` | Finite mono samples and actual output sample rate |

Each provider also supplies explicit `load()`, `close()`, and metadata: provider ID, model ID/revision, device, precision, and supported languages. Loading is outside warm inference timing. Keep vendor tensors out of contracts; use ordinary text and an agreed audio representation such as one-dimensional float32 samples.

Data objects:

- `AudioBuffer`: samples, sample rate, utterance ID, capture start/end, and speech-end estimate if available.
- `Transcript`: utterance ID, source text/language, optional segments and diagnostic scores.
- `Translation`: utterance ID, source and target languages, translated text.
- `SynthesizedAudio`: utterance ID, samples, sample rate, duration.
- `UtteranceResult`: these results, timings, status, and structured error metadata.

The orchestrator skips downstream stages for silence/empty input, empty transcripts, or empty translation. Providers raise identifiable errors such as `ModelUnavailable`, `UnsupportedLanguage`, `InvalidInput`, and `ResourceExhausted`. No raw traceback should be the only user-visible explanation.

Cloud providers can implement the same contracts later. V1 configuration accepts local providers only. Future routing, consent, credentials, network timeouts, and billing policy belong outside the core pipeline. Voice cloning can later extend synthesis options with a speaker profile; V1 uses a stock voice and contains no speaker-reference collection.

## Adapter responsibilities

| Adapter | Initial evaluation configuration | What must be validated |
|---|---|---|
| faster-whisper | `small`, language `en`, batch size 1; compare GPU FP16 and supported INT8 mode | Fully consume returned segments inside timing; accuracy versus precision; CUDA runtime compatibility |
| IndicTrans2 | En-Indic distilled 200M; `eng_Latn` -> `hin_Deva` internally | Official preprocessing/postprocessing, CPU/GPU dtype compatibility, token limits, meaning and entities |
| Kokoro | Hindi language/voice; CPU first, then GPU only if useful | Phonemizer assets, Hindi intelligibility, names/numbers, synthesis time and memory |

Application language codes remain `en` and `hi`; adapters convert to vendor codes. ASR expects normalized mono 16 kHz audio. Preserve the original rate at capture, resample once with a documented method, and do not relabel samples without resampling. Playback and WAV writing use the TTS result's actual sample rate. Resample for an output device only if required.

GPU placement is an experiment. Start by benchmarking each stage alone. Evaluate ASR on GPU with translation and TTS on CPU as one composition candidate; evaluate GPU translation separately if CPU latency is excessive. Measure all resident models together before selecting defaults. Low parameter counts do not establish total runtime memory.

Keep chosen models loaded for a warm interactive session while evaluating measured stability and the dedicated-VRAM ceiling. Under [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), available system RAM below 1 GiB is advisory and alone must not prevent the session. Record warnings and memory/latency trends; require the 30-turn microphone stability evidence before acceptance. If explicit CPU placement, smaller ASR such as `base`, or staged loading is needed, record its quality and latency cost. Staged loading adds model load time to each affected response and must appear in end-to-end timing. Catch out-of-memory errors cleanly; do not repeatedly retry an impossible allocation.

The CLI implements ADR-014: after loading and each utterance, `listen` records a memory check and emits one low-RAM warning without blocking solely on available RAM below 1 GiB. Excess dedicated VRAM or incomplete telemetry closes providers and prevents another capture/allocation attempt. Actual device/OOM errors remain explicit without fallback. File/stage/composed diagnostic commands remain available; no bypass option is needed.

## Proposed implementation layout

The implementation follows this layout. Evaluation inputs, models, and generated artifacts remain ignored local data; setup and evaluation instructions are in `docs/SETUP.md` and `docs/EVALUATION.md`.

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .gitignore
├── configs/
│   └── v1.toml
├── src/voice_translator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── types.py
│   ├── pipeline.py
│   ├── metrics.py
│   ├── audio/
│   │   ├── capture.py
│   │   ├── normalize.py
│   │   ├── endpoint.py
│   │   └── playback.py
│   └── providers/
│       ├── interfaces.py
│       ├── fake.py
│       ├── asr_faster_whisper.py
│       ├── translation_indictrans2.py
│       └── tts_kokoro.py
├── benchmarks/
│   ├── runner.py
│   └── evaluation.py
├── tests/
│   ├── unit/
│   └── integration/
├── data/eval/               # local evaluation media and manifest
├── models/                  # ignored local caches, or explicit external cache
├── artifacts/               # ignored audio, metrics, reports
└── docs/
    ├── ARCHITECTURE.md
    ├── ROADMAP.md
    └── DECISIONS.md
```

Configuration covers languages, model IDs/revisions/paths, devices, precision, ASR decoding, translation generation limits, TTS voice/speed, capture/output devices, endpoint limits, offline mode, and artifact retention. Keep credentials outside configuration committed to Git.

## Implemented interface details

The package uses synchronous Python protocols and float32 NumPy mono buffers. Translation/synthesis calls take the utterance ID alongside text. Native adapter calls are explicitly offline; setup is a separate stage-selected command. Runtime model revisions come from checksummed local provisioning receipts, not the setup branch name. Windows ASR may use an explicitly configured native DLL directory; no provider/device/precision substitution is automatic.

The CLI implements `doctor`, `setup-models --stage`, `benchmark --stage asr|translation|tts|pipeline`, `translate-file`, `listen --mode ptt`, `eval-init`, `eval-validate`, and `evaluate`. Config/model paths are resolved against the project root (parent of `configs/`); evaluation audio paths resolve against the manifest directory. Unknown configuration keys fail. Candidate TOMLs have not been accepted as a combined production configuration.

PTT reads press/release events from a focused Windows console. Esc requests cooperative cancellation and Q exits; native model calls finish before cancellation can be checked. Capture callbacks only copy into preallocated bounded memory. The input stream closes before processing/playback; a held key during processing cannot enqueue another utterance. File audio uses polyphase resampling, with explicit clipping of possible filtering overshoot. Output is resampled only when the configured output device rejects the actual TTS rate; the original/device rates are recorded.

Benchmarks keep edge behavior separate, retain all failures, and stop repeated inference after device/OOM failure. File timing is processing-start to complete synthesized audio; PTT reports release-to-scheduled-DAC onset/completion proxies. The Windows benchmark launcher supplies a monotonic process-launch timestamp for cold startup; direct CLI calls measure cold load only. Manual release lag and true acoustic onset remain unmeasured rather than being inferred. VAD remains optional and omitted from this implementation.

## Benchmark protocol

Build a fixed set of 30 utterances of 2–6 seconds, with hand-checked English transcripts and reviewed Hindi translations. Include clean speech, Indian English accents, mild noise, short phrases, names, numbers/dates, questions, and negation. Track categories and case IDs. Report this as a small project evaluation set, not a population-level accuracy claim.

Use the same manifest for all configurations: case ID, audio path, source duration, English reference, Hindi reference, and tags. Add separate silence, empty text, invalid audio, and maximum-duration cases for behavior checks. Do not mix these into latency/quality aggregates for ordinary speech; report their outcomes separately.

For each configuration, start a fresh process, record cold load/first-run costs, then perform 3 warm-up runs and 3 measured passes over the 30 cases. Report 90 measured observations, distinct-case count, p50/p95, failure count, and per-category results. Use a stated percentile method. Do not discard failures or slow cases; state how failed cases are excluded from timing percentiles and include their rate beside those percentiles.

Keep power mode, background applications, audio-device settings, and model generation settings fixed. Record CPU, OS, driver, Python/library versions, model revisions, device placement, precision, input durations, warm-up count, and memory sampling interval. Stage-only measurements run one provider at a time; composed measurements run the exact resident model arrangement intended for the demo.

Translation benchmarks use reference English text. TTS benchmarks use reviewed Hindi text. End-to-end benchmarks use ASR and translation outputs, exposing accumulated errors. Store per-case timing JSONL and a human-readable summary locally. Content retention is opt-in.

## Metrics and provisional gates

All elapsed measurements use monotonic time. GPU work must finish before stopping a stage timer. Fully consume lazy outputs. Native CTranslate2 allocations are outside PyTorch's allocator counters, so sample total dedicated VRAM and process/system RAM through an appropriate OS or GPU tool; allocator counters are supplementary. State sampling limitations because brief peaks may be missed.

| Metric | Definition | Initial target or interpretation |
|---|---|---|
| Cold startup | Launch to ready with all chosen models loaded | Report separately; no fixed gate yet |
| First inference | First stage call after loading | Report separately from warm runs |
| Endpoint delay | Speech end to finalized utterance | Includes trailing silence and VAD hangover; manual release lag is reported for PTT |
| ASR latency | Final audio -> complete transcript | Report p50/p95 and seconds per input-audio second (RTF) |
| Translation latency | English text -> complete Hindi text | Include preprocessing/tokenization/postprocessing |
| TTS latency | Hindi text -> complete synthesized buffer | Include phonemization; report synthesis seconds / output-audio seconds |
| Playback delay | Audio ready -> output-device playback start | Label software callback timing as a proxy unless audible onset is measured |
| Response latency | Speech end -> audible Hindi onset | Warm p50 <= 3 s is provisional; report p95, aim <= 5 s |
| Completion latency | Speech end -> translated playback end | Includes target speech duration; report separately |
| WER | (substitutions + deletions + insertions) / reference English words | Propose clean-set WER <= 20%; define normalization and report noisy cases separately |
| Meaning adequacy | Bilingual reviewer score, 1 incorrect to 5 complete meaning | Propose >= 90% of cases scoring >= 4 |
| TTS intelligibility | Hindi listener score, 1 unintelligible to 5 easily understood | Propose >= 90% of cases scoring >= 4 using reviewed Hindi inputs |
| Critical details | Preservation of negation, numbers, dates, and named entities | Review every applicable case; list every error rather than hiding it in averages |
| Memory | Peak process RSS/private commit, total RAM/available RAM, total dedicated VRAM | <= 3.5 GiB total dedicated VRAM; available RAM <1 GiB is an advisory warning, not an automatic rejection (ADR-014) |
| Reliability | Successful utterances / attempted utterances; categorized failures | No crash/OOM in 30 sequential microphone turns; report all skipped/failed cases |

RTF is real-time factor: 0.5 means processing took half the duration of the audio. A fast stage alone does not guarantee a fast conversation. Response latency includes endpoint and playback delays and any model swapping. For file benchmarks use processing-start -> audio-ready timing; do not present it as measured microphone-to-audible latency.

These numerical gates are proposed starting criteria, not prior experimental results. Revise them only through a documented decision with evidence. Stable local execution and adequate Hindi quality are required to call V1 complete; unmet latency goals must remain visible in the portfolio report.

Assess session stability using crashes/OOM, all utterance outcomes, memory trends and latency across 30 sequential microphone turns. Keep startup/first-call and warm measurements separate and retain low-RAM warnings. Investigate sustained unexplained growth, allocation failures, hangs or material latency degradation before claiming stability. Passing unit tests or file p50/p95 does not complete this gate. Missing telemetry leaves evidence unverified. New reports identify `memory_policy: adr-014-ram-advisory` and separate `ram_advisory`, `vram_gate` and `telemetry_status`; their `memory_gate` covers VRAM/telemetry, not RAM reserve or session stability. Session `execution_gate` reports successful turns, while `stability_gate` remains pending memory/latency review. Historical reports without this policy field retain the legacy gate semantics.

## Audio behavior and validation

Start with push-to-talk and headphone playback. Do not record during playback. Provide clear capture-device selection, empty-input feedback, cancellation, duration limits, and shutdown cleanup. Avoid overlapping speech outputs.

After the baseline, simple VAD may use configurable speech threshold, minimum speech duration, pre-roll, and silence hangover. Measure clipped starts/ends, false triggers, and endpoint delay. The ASR library's silence filter alone does not provide a live microphone endpoint controller.

Validation layers: fake-provider pipeline checks; deterministic contract/audio/configuration checks; optional provisioned-model integration checks; independent provider benchmarks; composed offline benchmarks; microphone walkthrough and a 30-turn stability session. Model access and downloading remain explicit setup actions. A disconnected run with cached assets must complete file and microphone flows without network inference.
