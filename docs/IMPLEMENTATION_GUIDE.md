# How the V1 implementation works

This is a walkthrough of the application as implemented, from files on disk to an English utterance becoming Hindi audio. It describes the supported application separately from the local optimization experiments. Read it alongside [SETUP.md](SETUP.md) for installation and [VALIDATION.md](VALIDATION.md) for measured evidence.

**Current state:** the V1 application and evaluation tooling exist. That is different from V1 being fully validated. Human-reviewed references, bilingual and listening scores, a real 30-turn microphone session, disconnected operation, and the remaining acceptance evidence are still required. A fast diagnostic benchmark does not complete those steps.

The scope is one speaker, English → Hindi, one completed utterance at a time, local inference, a CLI, WAV files, and Windows push-to-talk through headphones. There is no continuous translation, voice cloning, meeting integration, virtual audio device, database, server, or cloud fallback. Optional VAD is not implemented.

## Contents

1. [The whole system in one picture](#1-the-whole-system-in-one-picture)
2. [Directory structure and what belongs in Git](#2-directory-structure-and-what-belongs-in-git)
3. [Root files and configuration profiles](#3-root-files-and-configuration-profiles)
4. [Entry points and command dispatch](#4-entry-points-and-command-dispatch)
5. [Shared types, configuration, and errors](#5-shared-types-configuration-and-errors)
6. [Provider contracts and the serial pipeline](#6-provider-contracts-and-the-serial-pipeline)
7. [The three real adapters](#7-the-three-real-adapters)
8. [WAV files, microphone capture, and playback](#8-wav-files-microphone-capture-and-playback)
9. [Provisioning, caches, and offline execution](#9-provisioning-caches-and-offline-execution)
10. [Measurement, benchmarks, and human evaluation](#10-measurement-benchmarks-and-human-evaluation)
11. [Scripts and benchmark entry points](#11-scripts-and-benchmark-entry-points)
12. [Tests: what they prove and what they do not](#12-tests-what-they-prove-and-what-they-do-not)
13. [The documentation map](#13-the-documentation-map)
14. [Local experiment files](#14-local-experiment-files)
15. [Tracing a problem and understanding the remaining work](#15-tracing-a-problem-and-understanding-the-remaining-work)

## 1. The whole system in one picture

```text
Explicit setup, with network access             Normal execution, using local assets
───────────────────────────────────            ────────────────────────────────────
bootstrap.ps1 → Python + dependencies           CLI → validated TOML configuration
setup-models → pinned files + receipt                   ↓
                       │                       WAV file OR bounded microphone capture
                       └── local models ──┐             ↓
                                         │     mono floating-point audio at 16 kHz
                                         │             ↓
                                         └──→ SpeechRecognizer → English Transcript
                                              TextTranslator   → Hindi Translation
                                              SpeechSynthesizer → Hindi audio, 24 kHz
                                                        ↓
                                              explicit WAV export / headphone playback
                                                        ↓
                                              timings and optional JSONL records
```

ASR means automatic speech recognition: extracting English words from sound. Translation converts English text into Hindi text. TTS means text-to-speech: synthesizing a Hindi voice from that text. These are separate models; Kokoro does not translate, and Whisper does not synthesize the Hindi output.

An **utterance** is one bounded piece of speech, such as a sentence spoken while holding Space. The system waits for the utterance to finish before processing it. It does not translate words while they are being spoken.

A **sample** is one numeric audio measurement. A sample rate of 16,000 Hz means 16,000 samples per second. A WAV is an audio container holding samples and information such as sample rate and channel count. Renaming an arbitrary file to `.wav` does not turn it into a valid WAV.

A **provider** is an adapter exposing the application's common interface. A **model** is the learned network and its weights. A Python dependency is the library used to run it; installing the library does not install the model weights.

The architecture keeps these responsibilities separate:

| Layer | Responsibility | Main files |
|---|---|---|
| CLI | Parse commands, choose operations, present results and exit codes | `cli.py`, `__main__.py` |
| Configuration and contracts | Define supported inputs, outputs, limits, and explicit placement | `config.py`, `types.py`, `providers/interfaces.py` |
| Pipeline | Run three stages serially, preserve identity, enforce bounds and cancellation | `pipeline.py` |
| Adapters | Load a particular model and perform its vendor-specific processing | The three real provider modules |
| Audio | Decode, resample, capture, play, and export samples | `audio/` |
| Assets and offline controls | Provision and verify model files; prevent ordinary Python network use during inference | `provision.py`, `offline.py` |
| Evidence | Measure runs, validate references, summarize results, and collect human scores | `metrics.py`, `benchmark.py`, `evaluation.py` |

Provider calls run synchronously on the main execution thread. Audio callbacks, keyboard polling, and memory sampling use separate threads where needed. There is no inference worker pool, asynchronous inference queue, or parallel execution of the three models.

## 2. Directory structure and what belongs in Git

This tree lists the authored application, configuration, tests, scripts, and documentation. Installed dependencies and generated artifacts can contain thousands of files; those are described by their role rather than treated as application source.

```text
Arke/
├── AGENTS.md
├── README.md
├── LICENSE
├── .gitignore
├── pyproject.toml
├── requirements/
│   └── windows-tested.txt
├── configs/
│   ├── v1.toml
│   ├── fake.toml
│   ├── asr-cpu.toml
│   ├── asr-gpu-int8.toml
│   ├── gpu-translation.toml
│   ├── gpu-tts.toml
│   ├── all-gpu.toml
│   └── all-gpu-fp32.toml
├── src/voice_translator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── types.py
│   ├── errors.py
│   ├── config.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── doctor.py
│   ├── provision.py
│   ├── offline.py
│   ├── metrics.py
│   ├── benchmark.py
│   ├── evaluation.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── interfaces.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── fake.py
│   │   ├── asr_faster_whisper.py
│   │   ├── translation_indictrans2.py
│   │   └── tts_kokoro.py
│   └── audio/
│       ├── __init__.py
│       ├── normalize.py
│       ├── endpoint.py
│       ├── capture.py
│       └── playback.py
├── scripts/
│   ├── bootstrap.ps1
│   ├── benchmark-process.ps1
│   ├── make-asr-diagnostic.ps1
│   └── report-validation.py
├── benchmarks/
│   ├── runner.py
│   └── evaluation.py
├── tests/
│   ├── unit/
│   │   ├── test_foundation.py
│   │   ├── test_audio_metrics.py
│   │   ├── test_offline_adapters_cli.py
│   │   ├── test_text_adapters.py
│   │   ├── test_playback.py
│   │   ├── test_capture_session.py
│   │   ├── test_memory_policy.py
│   │   └── test_benchmark_review.py
│   └── integration/
│       └── test_provisioned_models.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── DECISIONS.md
│   ├── SETUP.md
│   ├── EVALUATION.md
│   ├── VALIDATION.md
│   ├── PLACEMENT_EVALUATION.md
│   ├── LOADING_EVALUATION.md
│   ├── STAGING_EVALUATION.md
│   ├── CPU_QUANTIZATION_EVALUATION.md
│   ├── OPTIMIZATION_REVIEW.md
│   ├── IDLE_BASELINE_EVALUATION.md
│   └── IMPLEMENTATION_GUIDE.md
│
└── Local/ignored directories, when provisioned or generated:
    ├── .venv/             installed Python packages and executable
    ├── .python/           project-local Python managed by uv
    ├── .cache/            uv, Hugging Face, and experiment caches
    ├── models/            weights, tokenizer assets, pinned model code, receipts
    ├── data/eval/         manifests, recordings, references, human review forms
    └── artifacts/         generated WAVs, logs, benchmark reports, local experiments
```

`src/` is the installable application. `tests/` checks its behavior. `configs/` chooses explicit operating profiles. `scripts/` assists setup and measurement. `docs/` explains decisions and evidence. `data/eval/` is input to evaluation; `artifacts/` is output from runs.

The ignored directories are not a distributable model bundle. A fresh checkout needs dependencies and explicit provisioning. Local experiment scripts under `artifacts/` are also ignored and may not exist on another machine.

Editable installation also generates `src/local_voice_translator.egg-info/`, which is ignored. `PKG-INFO` describes the installed package; `requires.txt` lists its dependencies; `entry_points.txt` records the console command; `top_level.txt` identifies the import package; `SOURCES.txt` lists packaging inputs; `dependency_links.txt` is setuptools metadata. These files are generated from packaging configuration, not separate application modules to edit.

## 3. Root files and configuration profiles

| File | What it does |
|---|---|
| [AGENTS.md](../AGENTS.md) | Defines scope, architecture discipline, evidence requirements, and instructions for coding agents. |
| [README.md](../README.md) | Gives current status, entry commands, reading order, and links to evidence. Its future product direction does not authorize later-stage features in V1. |
| [pyproject.toml](../pyproject.toml) | Defines the Python package, supported Python range, pinned direct dependencies, optional dependency groups, setuptools packaging, CLI entry point, and pytest settings. |
| [requirements/windows-tested.txt](../requirements/windows-tested.txt) | Records the installed Windows dependency snapshot, including transitive packages and the actual PyTorch build. Presence here does not mean every package is used by an application feature. |
| [.gitignore](../.gitignore) | Excludes environments, caches, weights, credentials, recordings, generated media, evaluation data, and benchmark outputs from Git. |
| [LICENSE](../LICENSE) | Licenses the project code under MIT. Model weights and third-party code retain their own licenses and access conditions. |

Python starts with 3.11 for the tested environment. The package declares `>=3.11,<3.13`; that declaration is not evidence that every native dependency has been tested on both versions.

The base dependency group provides NumPy, SciPy, psutil, and SoundFile. Optional groups add audio playback/capture, pytest, faster-whisper/CTranslate2, IndicTrans2 dependencies, and Kokoro dependencies. Translation and TTS use PyTorch. ASR runs through CTranslate2; PyTorch CUDA allocation counters alone therefore cannot describe the application's total GPU memory.

### What TOML configuration controls

`load_config()` reads a TOML file into validated dataclasses. Top-level settings define languages, offline execution, audio/text/output bounds, memory sampling interval, silence threshold, and content retention. Provider sections specify model identity, revision, local path, device, precision, and decoding limits. The audio section selects capture/output devices, capture sample rate, and push-to-talk key.

The project profiles are:

| File | ASR | Translation | TTS | Purpose |
|---|---|---|---|---|
| `v1.toml` | CUDA, float16 | CPU, float32 | CPU, float32 | Provisional application default |
| `fake.toml` | Fake, CPU | Fake, CPU | Fake, CPU | Deterministic plumbing checks |
| `asr-cpu.toml` | CPU, int8_float32 | CPU, float32 | CPU, float32 | Recognition placement comparison |
| `asr-gpu-int8.toml` | CUDA, int8_float16 | CPU, float32 | CPU, float32 | Recognition precision comparison |
| `gpu-translation.toml` | CUDA, float16 | CUDA, float16 | CPU, float32 | Translation placement comparison |
| `gpu-tts.toml` | CUDA, float16 | CPU, float32 | CUDA, float32 | Synthesis placement comparison |
| `all-gpu.toml` | CUDA, float16 | CUDA, float16 | CUDA, float32 | Combined GPU experiment |
| `all-gpu-fp32.toml` | CUDA, float16 | CUDA, float32 | CUDA, float32 | Combined experiment with float32 translation |

`all-gpu-fp32.toml` does **not** make ASR float32. Read the individual provider settings rather than inferring precision from the filename. Fake provider precision is float32.

The supplied V1 profile sets these important limits/options:

| Setting | Value | Meaning |
|---|---:|---|
| `max_audio_seconds` | 15 | Maximum input/capture duration |
| `max_text_chars` | 1000 | Maximum text passed between stages |
| `max_output_seconds` | 30 | Maximum synthesized duration |
| `silence_rms` | 0.0001 | Pipeline's amplitude threshold for skipping quiet input |
| `memory_interval_seconds` | 0.1 | Requested memory sampling interval; actual intervals are reported |
| `retain_content` | false | Persist performance metadata without raw English/Hindi text by default |
| Translation input/new-token limits | 256 / 256 | Reject oversized input and potentially truncated output |
| Beam size | 5 | Explicit recognition/translation search setting |
| CPU threads | 4 | Requested provider runtime thread setting |
| TTS voice/speed/phoneme bound | `hf_alpha` / 1.0 / 500 | Stock Hindi voice, normal speed, bounded phoneme sequence |

Not every provider uses every `ProviderConfig` field: the shared dataclass contains settings used by different adapters. For example, TTS does not use translation beam search, and ASR does not use the Kokoro voice setting. Metadata records configuration separately from the adapter's actual placement.

The real profiles pin these model revisions:

| Stage | Model | Revision |
|---|---|---|
| ASR | `Systran/faster-whisper-small` | `536b0662742c02347bc0e980a01041f333bce120` |
| Translation | `ai4bharat/indictrans2-en-indic-dist-200M` | `173b94239f7c38886b2747b8d4a5db771a7e1232` |
| TTS | `hexgrad/Kokoro-82M` | `f3ff3571791e39611d31c381e3a41a3af07b4987` |

Device `-1` means the operating system's default audio device. The profiles capture at 48 kHz and normalize input to 16 kHz. Model paths are resolved relative to the parent of the configuration file's directory, which is the project root for the supplied `configs/` files. Moving a config to a different directory changes that base; file/audio command paths are interpreted from the command's working directory.

Precision describes model computation/storage choices. Float16 uses fewer bytes per value than float32; quantization represents selected values with smaller integers plus scaling information. These choices can change compatibility, memory, speed, and quality. They are explicit settings, not permission to silently switch after a failure.

## 4. Entry points and command dispatch

### `__init__.py` and `__main__.py`

`src/voice_translator/__init__.py` declares the package version. The provider and audio `__init__.py` files are lightweight package markers. Importing these packages does not provision weights, load a model, or open a microphone.

`python -m voice_translator` runs `__main__.py`, which calls `cli.main()`. Installation also exposes the `voice-translator` console entry point. Both reach the same implementation.

### `cli.py`

`parser()` defines the eight supported commands. `main()` sets UTF-8 console output so Hindi survives Windows redirection, loads configuration, sets project-local Hugging Face cache locations, and enters the offline context for every command except `setup-models`. Imports of command-specific modules happen in the relevant branch.

| Command | Main implementation | What it actually does |
|---|---|---|
| `doctor` | `doctor.doctor()` | Inspect hardware, packages, audio devices, paths, and asset readiness without model inference |
| `setup-models --stage …` | `provision.setup_models()` | Explicitly download the selected stage's pinned assets and write an integrity receipt |
| `translate-file` | `read_wav()` → factory → pipeline → `write_wav()` / `play()` | Process one WAV, export Hindi WAV, optionally play it |
| `listen --mode ptt` | `audio.capture.listen()` | Run the Windows press/release microphone session |
| `benchmark --stage …` | `benchmark.run_benchmark()` | Run a fixed-set stage or composed benchmark and write reports |
| `eval-init` | Evaluation initialization | Create draft cases and blank human review tooling |
| `eval-validate` | `evaluation.load_manifest()` | Check references, categories, IDs, and, where needed, recordings |
| `evaluate` | `evaluation.score_review()` | Validate submitted human scores and their associated run evidence |

All commands accept `--config`; the default is `configs/v1.toml`. `--debug` enables tracebacks. Errors normally appear as structured JSON with a code and actionable message. A command-level exception returns exit code 2; unsuccessful utterance processing returns 1; cancellation uses 130 where handled that way. Benchmark exit status reports failed/skipped execution or a fatal error; it does not certify every acceptance gate.

Run `python -m voice_translator <command> --help` to inspect flags without loading models. `emit()` preserves Unicode and rejects non-finite JSON numbers.

### A complete file request

```text
parse arguments → validate config → enter offline context
    → decode WAV and reject invalid/oversized input
    → create adapters without loading models
    → load ASR, translation, TTS
    → pipeline.run(audio)
    → print result; optionally append metrics
    → on success, write Hindi WAV; optionally play
    → finally close all providers
```

Input decoding happens before model loading. Therefore `Cannot decode WAV: LibsndfileError` is an input decoding problem, not a translation failure. Missing/unreadable files, invalid contents, or an unsupported container can produce it.

`translate-file` prints English/Hindi text to the console. Its optional `--metrics` stores an utterance record, respecting `retain_content`. It does **not** run the microphone session's resident-memory guard or continuously sample memory. Use `benchmark` for sampled memory evidence; do not interpret a successful file command as a sustained-session test.

## 5. Shared types, configuration, and errors

### `types.py`: data crossing layer boundaries

| Type/helper | Purpose |
|---|---|
| `utterance_id()` | Generate a unique UUID for a new input utterance |
| `validate_samples()` | Require one-dimensional float32 samples, a positive sample rate, finite values, and samples within `[-1,1]` |
| `AudioBuffer` | Store input samples, rate, identity, and optional capture/speech timestamps; expose duration |
| `Transcript` | Store recognized English text, identity, language, and optional segment diagnostics |
| `Translation` | Store Hindi text, the same identity, and source/target languages |
| `SynthesizedAudio` | Store validated output samples, actual sample rate, identity, and duration |
| `ProviderMetadata` | Describe model/provider identity, revision, actual device, precision, and languages |
| `UtteranceResult` | Hold status, stage outputs, elapsed times, and a structured error; create a JSON-safe record |
| `Cancellation` | Wrap an event that can be set by another thread and checked between synchronous operations |

The stage data classes are frozen, so their fields cannot be reassigned. Their NumPy arrays remain mutable objects; freezing the dataclass is not a deep copy or a guarantee that array contents cannot change.

Every stage must return the original utterance ID. This connects capture, transcription, translation, synthesis, playback, and metrics without relying on text matching. A provider returning a different ID is an explicit failure.

`UtteranceResult.record()` normally exports performance metadata without English/Hindi content. Content is included only when requested. It does not serialize audio arrays into JSON.

Audio arrays and stage text exist in memory during processing. Normal microphone operation does not automatically save recordings or output WAVs. File export is an explicit command action; benchmark WAV/text retention is opt-in. Console transcripts are visible even when persisted metrics omit them, so redirecting the console to a file also retains that displayed content.

### `config.py`: reject unsupported combinations early

`ProviderConfig`, `AudioConfig`, and `Config` define the configuration shape. `load_config()` parses TOML, rejects unknown keys, resolves paths, and validates values. `Config.metadata()` produces a serializable account of the requested setup.

Validation enforces English → Hindi, offline execution, supported provider names and device/precision combinations, supported stock voices, positive finite settings, bounded token counts, and supported audio rates/devices. Capture is capped at 15 seconds. The input/output text and synthesized-audio duration limits remain bounded even if someone edits a config.

Configuration validation cannot prove that a native library supports the machine's CUDA runtime or that assets match their receipt. Those checks happen during provisioning or adapter loading.

### `errors.py`: failures retain their meaning

Typed failures include `InvalidConfig`, `ModelUnavailable`, `UnsupportedLanguage`, `InvalidInput`, `ResourceExhausted`, `DeviceError`, `ProviderError`, and `Cancelled`.

`classify()` preserves already typed errors. Memory/OOM exceptions become resource failures; CUDA/cuBLAS/cuDNN failures become device errors; other vendor exceptions become provider failures. Debug mode exposes a traceback for diagnosis. Ordinary messages avoid dumping raw speech or credentials.

The failure policy is explicit: no model substitution, automatic CPU fallback, silent truncation, or cloud request. A deprecation warning such as PyTorch's `weight_norm` warning is different from an application error. It concerns a dependency API and does not itself establish that inference failed.

## 6. Provider contracts and the serial pipeline

### `providers/interfaces.py`

The three Python protocols define common methods:

```text
SpeechRecognizer: load(), close(), metadata, transcribe(AudioBuffer) → Transcript
TextTranslator:   load(), close(), metadata, translate(text, utterance_id, source, target) → Translation
SpeechSynthesizer:load(), close(), metadata, synthesize(text, utterance_id, language) → SynthesizedAudio
```

The recognizer's optional language argument defaults to `en`; translation defaults to `en`/`hi`, and synthesis to `hi`. The common `Provider` protocol supplies lifecycle and metadata. The pipeline extracts `.text` from the previous result and passes that string and the original ID to translation/synthesis; those methods do not accept the whole preceding dataclass.

The pipeline sees these application types and ordinary strings, not PyTorch tensors, Hugging Face tokenizers, vendor language tags, or Kokoro phonemes. This is the provider boundary that permits a future measured replacement without rewriting capture, logging, or orchestration. It does not mean such a replacement is already implemented.

### `providers/factory.py`, `base.py`, and `fake.py`

`factory.py` selects adapters from explicit config names and imports only the required implementation. `create_pipeline()` connects the chosen instances. There is no plugin discovery or automatic provider selection.

`base.py` provides shared asset validation, loaded-state checks, text bounds, Torch setup, and representative parameter device/dtype checks. Torch setup applies configured CPU threads and rejects an unavailable requested CUDA device. These checks help catch mismatches; a representative parameter check is not a complete audit of every tensor allocation.

`fake.py` provides deterministic test implementations. They return fixed English/Hindi text and a short 440 Hz tone, tracking whether they are loaded. That tone is not Hindi speech. Fakes let tests exercise contracts and failure handling without downloads or expensive inference.

### `pipeline.py`

`Pipeline.load()` loads ASR, translation, and TTS serially and records load durations. If one load fails, it closes already constructed providers. `close()` runs in reverse order, reports cleanup errors, and releases provider references. Releasing Python references does not guarantee that every native runtime immediately returns all memory to Windows.

`run()` follows this sequence:

1. Acquire a nonblocking lock. If another utterance is active, reject the request; do not queue it.
2. Check cancellation, sample rate, and maximum input duration.
3. Skip empty or sufficiently quiet input before calling models.
4. Run ASR and validate identity, language, nonempty text, and bounds.
5. Check cancellation; run translation and validate its result.
6. Check cancellation; synthesize and validate output identity and duration.
7. Record stage and total processing times, release the lock, and return a result.

Empty recognition or translation results are recorded as skipped outcomes rather than passed through to the next model. A failed stage records its failure and elapsed time; later stages do not run. Cancelled results discard synthesized audio, preventing stale playback.

Cancellation is **cooperative**. Pressing Escape cannot interrupt a synchronous vendor kernel in its middle. The token is checked before and after stage calls; once the current call returns, the pipeline discards the cancelled result and does not continue to later stages or playback.

The pipeline does not capture audio, save files, or play sound. Those are the caller's responsibilities. The normal composed path keeps all three models loaded between utterances; loading and unloading a model for every stage is an experimental strategy, not current pipeline behavior.

For an illustrative utterance, the data path looks like this. The text is an explanation, not a claimed measured model output:

```text
AudioBuffer(id=A, rate=16000, samples=English speech)
    → asr.transcribe(audio, "en")
Transcript(id=A, text="Please wait a moment.", language="en")
    → translator.translate(transcript.text, A, "en", "hi")
Translation(id=A, text="कृपया एक क्षण रुकिए।", source="en", target="hi")
    → tts.synthesize(translation.text, A, "hi")
SynthesizedAudio(id=A, rate=24000, samples=Hindi speech)
    → UtteranceResult → caller exports/plays
```

`perf_counter()` provides monotonic elapsed timing. `timings["asr"]`, `timings["translation"]`, and `timings["tts"]` cover their complete calls and immediate result checks; `timings["processing"]` covers the pipeline run, including checks between stages. It excludes model loading, initial WAV decoding, microphone recording, and playback. This is why a fast processing percentile is not the same as quick audible response from the moment the speaker stops talking.

## 7. The three real adapters

### `providers/asr_faster_whisper.py`

`load()` verifies local assets, prepares the configured Windows DLL directory when CUDA is requested, imports CTranslate2/faster-whisper, checks supported compute types, and constructs `WhisperModel` with local files only. It validates the resulting device and compute type. The supplied CUDA profile points native library lookup at `.venv/Lib/site-packages/torch/lib`; a visible NVIDIA driver alone is insufficient.

`transcribe()` accepts bounded mono 16 kHz audio and English only. It specifies language/task, configured beam size, temperature zero, disabled previous-text conditioning, disabled VAD, and a generation limit. Faster-whisper yields segments lazily: the adapter consumes that generator inside the measured call, joins text, and collects segment diagnostics. Reaching the generation bound is rejected rather than assumed to be a complete transcript.

Segment values such as average log probability and no-speech probability are diagnostics. The application does not interpret them as calibrated accuracy guarantees.

`close()` drops the model and restores DLL/path resources. The adapter runs native CTranslate2 inference; its memory is included through process/system telemetry rather than Torch counters alone.

### `providers/translation_indictrans2.py`

`load()` requires a valid receipt and reviewed pinned custom model code. It loads the local tokenizer, official `IndicProcessor`, and sequence-to-sequence model with the explicit Torch dtype/device. `trust_remote_code=True` here permits the pinned **local** model implementation; it does not authorize a network inference request. The standard adapter constructs the model and then moves it to the requested device.

`translate()` performs:

```text
English Transcript
    → IndicProcessor.preprocess_batch([text], eng_Latn, hin_Deva)
    → tokenize without truncation
    → reject input exceeding configured token limit
    → move batch of one to configured device
    → deterministic beam generation within output bound
    → reject incomplete/bound-limited output
    → decode and official Hindi postprocessing
    → Hindi Translation with original ID
```

Tokens are the model's internal text pieces; one token is not necessarily one word or one character. Beam search examines a bounded set of possible sequences; increasing beams can increase work. The adapter keeps these vendor details internal.

Generation runs in inference mode, with sampling disabled. CUDA work is synchronized before returning so stage timing includes completed GPU work. `close()` releases model, tokenizer, and processor references.

### `providers/tts_kokoro.py`

`load()` verifies Kokoro configuration, checkpoint, and selected stock voice. It creates `KModel`, loads checkpoint data, moves the model to the configured device, loads the voice tensor, and creates the Hindi Misaki/eSpeak grapheme-to-phoneme component. The normal constructor can allocate CPU tensors even for a GPU target; this is one reason loading experiments investigated more than final GPU placement.

`synthesize()` converts Hindi writing into phonemes, validates nonempty phonemes and the 500-phoneme bound, rejects unsupported symbols or model-context/voice-index overflow, and invokes the model with the configured voice/speed. It returns mono float32 samples at **24,000 Hz**, preserving the utterance ID. Output duration and sample validity are checked.

Phonemes represent speech sounds. The voice tensor selects a provided voice; it is not a recording of the user's voice. This application does not clone voices. `close()` releases the model, voice, and phonemizer references.

Numerical or waveform comparisons in experiments are useful for detecting changed computation. They cannot replace a Hindi speaker judging pronunciation and intelligibility.

## 8. WAV files, microphone capture, and playback

### `audio/normalize.py`

`read_wav()` uses SoundFile/libsndfile to check the container, channels, sample rate, and duration before reading the complete file. It supports mono or stereo WAV/WAVEX input, checks finite sample values, converts stereo to mono, constructs `AudioBuffer`, and normalizes to 16 kHz.

`normalize()` uses SciPy `resample_poly()` with a rational rate ratio, not a sample-rate label change. It preserves identity/timestamps and clips filter overshoot into the valid sample range. If the rate already matches, it can return the existing buffer.

`write_wav()` creates parent directories and writes PCM16 WAV at the synthesized audio's reported sample rate. Exporting Kokoro output therefore normally produces 24 kHz audio. Input and output rates serve different models; they need not match.

### `audio/endpoint.py`

`BoundedCapture` allocates a fixed maximum-size float32 buffer. Audio callbacks append into the remaining capacity under a lock. An event marks reaching the limit. Device overflow/status errors are saved and raised explicitly; `finish()` returns the captured portion or reports the failure.

Despite the filename, this is manual capture bounding, not a speech endpoint detector or VAD. Very quiet captured audio is filtered later by the pipeline's RMS silence check.

### `audio/capture.py`

`ConsoleKeys` uses Windows console key events to distinguish Space press and release. It temporarily configures console mode, polls keys on a thread, and restores mode on exit. This requires a real interactive Windows console; a headless process or unsupported platform is not silently converted to another input method.

`capture_once()` opens a SoundDevice input stream only while recording. Its callback copies audio into `BoundedCapture`; it does not run a model. Release, the 15-second bound, cancellation, console failure, or device failure ends recording. The input stream closes before processing begins. The resulting buffer is resampled to 16 kHz and retains capture timing and identity.

`listen()` loads the pipeline once, starts memory sampling and keyboard handling, and presents states:

```text
ready → recording → processing → playing → ready
                  ↘ cancelled/error → record outcome and recover or end session
```

Hold Space to capture; release it to process. Escape cancels the current utterance; Q requests exit. The application does not capture during playback or maintain pending utterances. Holding the key past the bound finalizes capture; the key must be released before another utterance begins.

The session records each attempt and returns to readiness where recovery is supported. Resource/device failures end further attempts. `finally` cleanup closes providers and audio/key resources, including cancellation and interruption paths.

### Session memory policy: ADR-014

For real providers, `listen()` checks telemetry after loading and after each utterance. The checks are cumulative session observations, not a proof that every instant was sampled.

| Condition | Current response |
|---|---|
| Available system RAM below 1 GiB | Warn once and continue; reserve is advisory |
| Total dedicated GPU usage above 3.5 GiB | Explicit residency failure; do not continue capture |
| Missing or failed memory telemetry | Residency remains unverified and blocks real capture |
| Actual OOM/device failure | Record failure and end further attempts |

There is no replacement lower RAM crash threshold. Passing with less than 1 GiB is evidence of that run's execution, not proof that every sustained session will be stable. Acceptance requires memory/latency trend review and real microphone evidence. Fake sessions cannot pass the real hardware acceptance gates.

### `audio/playback.py`

`play()` validates the selected device and attempts playback at the synthesized rate. If the device cannot use that rate, it explicitly resamples to a supported preferred device rate and records the conversion. This is audio format adaptation on the chosen device, not a hidden model/device fallback.

The output callback writes chunks, zero-fills unused output, and handles cancellation/completion. Underflow/status failures become explicit errors. The caller waits for completion and closes the stream.

Timing uses the first callback and PortAudio's scheduled DAC information as an onset **proxy**. It does not measure actual acoustic onset at the headphones or Bluetooth transport delay. Microphone logs distinguish release-to-finalization, release-to-onset proxy, and completion. Acoustic onset, speech-end response, and manual release lag remain unmeasured without appropriate annotations or hardware measurements.

## 9. Provisioning, caches, and offline execution

### `provision.py`

`setup_models()` is an explicit network-enabled setup operation for one stage. It resolves an immutable revision, records a setup plan for repeatability/resumption, downloads the required subset, computes SHA-256 hashes, and writes `provisioned.json`. A receipt records stage, model identity, resolved revision, file hashes, timestamp, and custom-code review status where applicable.

Typical local assets are:

| Stage | Required asset families |
|---|---|
| ASR | CTranslate2 `model.bin`, model configuration, tokenizer, and applicable vocabulary/preprocessing files |
| Translation | Model weights, configuration, tokenizer metadata, source/target dictionaries and tokenization assets, plus pinned custom Python model/tokenizer code |
| TTS | `config.json`, `kokoro-v1_0.pth`, and configured stock voice such as `voices/hf_alpha.pt` |

Hindi phonemization also needs its installed runtime/dependency assets; a Kokoro checkpoint alone is insufficient. Native CUDA libraries are a separate runtime prerequisite.

IndicTrans2 access acceptance and an authorized locally configured Hugging Face token are user prerequisites. Tokens are not source code or benchmark content. `--accept-reviewed-code` attests that the pinned custom implementation has been reviewed; it should not be treated as an automatic quality approval.

`validate_assets()` checks receipt identity/revision, safe paths, required files, file hashes, and the translation custom-code review flag before loading. Hashing files contributes to cold loading cost. A valid receipt proves asset consistency, not inference compatibility or translation quality. Changing model/revision requires an explicit matching provisioning setup, not silently reusing another model's files.

### `offline.py`

`offline_runtime()` sets Hugging Face/Transformers offline flags and temporarily blocks ordinary Python socket connections and DNS helpers. It restores the previous state when leaving the context. `offline_call` wraps real adapter loading/inference so direct adapter use also receives the guard.

This is application-level protection. It is not a Windows firewall rule or a complete sandbox for all native libraries and subprocesses. A physically disconnected real file/microphone run remains separate acceptance evidence. No inference path intentionally sends audio or text to a remote model.

### `doctor.py`

`doctor()` combines environment inventory with dependency availability, model receipt/path inspection, native library paths, and SoundDevice device enumeration. It does not load all models or open a recording stream. Its asset-ready result is runtime-unverified; it does not perform the adapter's full file-hash validation or prove CUDA readiness.

Use it to answer “what prerequisite is missing?” rather than “has the entire application passed?” A driver, a package import path, a model receipt, and a successful actual inference call are four different levels of evidence.

## 10. Measurement, benchmarks, and human evaluation

### `metrics.py`

`environment()` records platform, CPU, Python/package versions, system memory, disk, and GPU inventory. `gpu_inventory()` queries `nvidia-smi` and reports dedicated memory usage for the device, including other processes. It is not just this Python process's Torch allocations.

On this single-GPU target, the sampler's peak uses the GPU's reported usage. If there are several GPUs, the current implementation takes the maximum device reading rather than summing every card; it is not a general multi-GPU accounting system.

`MemorySampler` periodically samples process RSS, available system RAM, Windows private/virtual memory where exposed, and device-wide GPU usage. The configured default interval is 100 ms. It records actual interval behavior and sampling failures. Short-lived peaks between samples can be missed; the report cannot claim continuous observation.

The sampler keeps observations in memory for the run. Standard reports save the aggregate summary; microphone JSONL also saves cumulative residency summaries at check points. Some investigation wrappers additionally export individual samples and phase traces. The microphone turn limit counts attempted utterances, not seconds spent idle, and ordinary execution does not establish unlimited-session resource behavior.

RSS is resident process memory, available RAM is the system's immediately available physical memory, and private bytes concern committed private allocations. They are related but not interchangeable. Device-wide GPU usage includes display/background use; native allocations and workspaces can be larger than model tensors alone.

`percentile()` uses linear interpolation on sorted values at position `(n−1)×q`. `distribution()` returns count/p50/p95. `append_jsonl()` appends one UTF-8 JSON object per line, creating parent directories. JSONL lets an interrupted run preserve completed observations.

New summaries expose separate `telemetry_status`, `ram_advisory`, `vram_gate`, and `memory_gate` fields under `memory_policy: adr-014-ram-advisory`. A passed memory gate means the applicable VRAM/telemetry conditions passed. It does not mean human quality or sustained-session stability passed.

### `benchmark.py`

`run_benchmark()` selects a single provider or composed pipeline, validates the fixed 30-case manifest, requires an empty output directory, captures run identity/configuration/environment, and measures:

1. Cold model loading and the first inference separately.
2. Three warm-up calls, excluded from warm percentiles.
3. Three measured passes over all 30 cases: 90 observations.
4. Separate boundary/behavior checks where applicable.
5. Memory sampling during the measured process lifetime covered by the sampler.

The process wrapper also records a launch clock for startup measurements. Initial interpreter/import/environment work outside a particular timer or sampling window should not be inferred from that timer alone. The output identifies measured boundaries.

For ASR, input is audio plus a reference English transcript. For translation, input is the correct English reference, bypassing recognition. For TTS, input is reference Hindi, bypassing translation. The composed stage uses audio and all three models. These separations help distinguish recognition mistakes from translation mistakes and pronunciation problems.

`summarize()` aggregates successful timings, reports failures/skips alongside them, and groups results by categories. Cases can have several categories, so category counts are not necessarily disjoint. Failed timings do not improve or worsen latency percentiles by being included as successful samples; they remain visible failures. Fatal device/OOM conditions prevent further model attempts, and remaining observations are reported accordingly.

ASR real-time factor is recognition time divided by source-audio duration. TTS real-time factor is synthesis time divided by output-audio duration. WER is total word edits divided by total reference words, not the arithmetic average of case percentages. `render_summary()` produces a readable Markdown report from the summary.

Typical run output includes metadata, JSONL observations, JSON summary, and Markdown summary. `--retain-content` explicitly includes text and exports measured synthesized WAVs; otherwise benchmark records avoid speech content. Use a new output directory for each run so old evidence is preserved.

`--allow-unreviewed` permits diagnostic execution. It does not turn draft references or synthetic speech into accepted evaluation data. Synthetic Windows SAPI audio is especially unsuitable for proving Indian-English or noisy human recording performance.

### `evaluation.py`

`DRAFTS` supplies 30 starting cases across the documented categories, including clean/noisy speech, Indian English, names, dates/numbers, and negations. These are draft prompts and Hindi references, not human-approved ground truth.

Evaluation initialization writes a manifest and blank review template and refuses to overwrite existing files. `--synthetic` creates test tones for fake-provider plumbing only. A real evaluation set needs human recordings and reviewed English/Hindi references.

`read_jsonl()` parses structured rows with useful line errors. `load_manifest()` verifies exactly 30 unique safe IDs, categories, text, review flags, recording kind, and, for audio stages, actual WAV durations of 2–6 seconds matching declarations. Relaxing review requirements is an explicit diagnostic option.

`word_errors()` normalizes text and calculates edit distance over words. That can measure recognition disagreement with a reviewed transcript. It cannot judge whether Hindi preserves meaning.

`score_review()` validates 30 review rows, integer scores from 1 to 5, reviewer information, critical-detail checks, run IDs, stage evidence, manifest hashes, and appropriate completed real-provider reports. Fake or unreviewed diagnostic runs cannot pass these quality gates. It counts how many reviewed cases meet the score threshold; absent scores remain pending.

A bilingual reviewer supplies adequacy and critical-detail judgments. A Hindi listener supplies intelligibility/pronunciation judgments. The software checks the form and evidence linkage; it does not manufacture scores or certify reviewer competence. Listening to isolated reference-Hindi TTS and listening to composed output answer different questions.

### How to interpret the current evidence

The provisional latency goals remain processing p50 ≤3 s and p95 ≤5 s, with clean WER ≤20% and at least 90% of adequacy/intelligibility scores ≥4/5. The dedicated VRAM ceiling remains 3.5 GiB. The 1 GiB available-RAM reserve is now advisory under ADR-014. Real 30-turn execution, trends, and absence of crashes/OOM must still be evaluated.

The strongest local loader diagnostics recorded roughly 0.48/0.60 s warm processing and 2.339 GiB peak dedicated VRAM. Those experiments are not integrated into the standard adapter path and do not establish acoustic microphone response or reviewed quality. Read the evidence reports for exact runs and limitations.

Older reports that failed the former mandatory RAM margin retain that historical result. They must be interpreted with the ADR-014 banner/current policy; they are not retrospectively rewritten as accepted V1 runs. Microphone summaries likewise separate an execution gate from pending memory/latency trend review.

## 11. Scripts and benchmark entry points

| File | Role and important behavior |
|---|---|
| [scripts/bootstrap.ps1](../scripts/bootstrap.ps1) | Uses `uv`, local Python/cache paths, and a project environment. Installs base/test/audio dependencies; `-Asr`, `-Translation`, and `-Tts` add stage dependencies. Translation/TTS setup selects the tested CUDA-enabled Torch build. Checks failures and runs doctor. Does not download model weights. |
| [scripts/benchmark-process.ps1](../scripts/benchmark-process.ps1) | Starts one fresh Python benchmark process with a launch-clock marker and forwards stage/config/manifest/output and diagnostic/content flags. Removes the marker afterward. Fresh processes reduce contamination from a preceding model configuration. |
| [scripts/make-asr-diagnostic.ps1](../scripts/make-asr-diagnostic.ps1) | Uses a Windows English SAPI voice to produce diagnostic 16 kHz WAVs for draft prompts in a new directory. Pads short recordings to 2 seconds, rejects oversized ones, and marks references unreviewed/synthetic. This is tooling validation data, not a human quality set. |
| [scripts/report-validation.py](../scripts/report-validation.py) | Historical report generator using specific local artifact filenames and embedded narrative. Can rewrite `docs/VALIDATION.md` and older summary Markdown. It is not fully synchronized with later curated ADR-014 updates; do not run it casually to regenerate current acceptance status. |
| [benchmarks/runner.py](../benchmarks/runner.py) | Convenience wrapper that calls the same CLI benchmark implementation. It does not implement a second benchmark engine. |
| [benchmarks/evaluation.py](../benchmarks/evaluation.py) | Re-exports evaluation helpers for convenience; it does not contain another scoring algorithm. |

The normal setup and run sequence is documented in [SETUP.md](SETUP.md). The central commands look like this from the project root:

```powershell
# Install dependencies; stage flags do not provision weights.
.\scripts\bootstrap.ps1 -Asr -Translation -Tts

# Inspect readiness without loading models.
.\.venv\Scripts\python.exe -m voice_translator doctor --config configs/v1.toml

# Explicit provisioning. IndicTrans2 requires authorized access and code review.
.\.venv\Scripts\python.exe -m voice_translator setup-models --config configs/v1.toml --stage asr
.\.venv\Scripts\python.exe -m voice_translator setup-models --config configs/v1.toml --stage translation --accept-reviewed-code
.\.venv\Scripts\python.exe -m voice_translator setup-models --config configs/v1.toml --stage tts

# Process your own valid WAV, or use an interactive Windows console for PTT.
.\.venv\Scripts\python.exe -m voice_translator translate-file --config configs/v1.toml --input english.wav --output artifacts/hindi.wav --play
.\.venv\Scripts\python.exe -m voice_translator listen --config configs/v1.toml --mode ptt --turns 30 --metrics artifacts/microphone.jsonl
```

The model setup commands require network access; normal inference uses cached files. Read the setup prerequisites before using the review flag. `english.wav` is a file you must provide, not a guaranteed bundled recording. The microphone command uses the provisional profile; availability of the command is not acceptance of that profile.

The evaluation commands connect as follows. These examples require an existing, completed, reviewed set; see [EVALUATION.md](EVALUATION.md) to prepare it. Choose unused output directories:

```powershell
# Check references and recordings before running models.
.\.venv\Scripts\python.exe -m voice_translator eval-validate --manifest data/eval/manifest.jsonl

# Run separately, in fresh processes. ASR and pipeline are additional stage choices.
.\scripts\benchmark-process.ps1 -Stage translation -Manifest data/eval/manifest.jsonl -Output artifacts/reviewed-translation -RetainContent
.\scripts\benchmark-process.ps1 -Stage tts -Manifest data/eval/manifest.jsonl -Output artifacts/reviewed-tts -RetainContent

# A human fills review.jsonl with scores and matching run IDs before evaluation.
.\.venv\Scripts\python.exe -m voice_translator evaluate --manifest data/eval/manifest.jsonl --review data/eval/review.jsonl --translation-report artifacts/reviewed-translation/summary.json --tts-report artifacts/reviewed-tts/summary.json
```

For a new set, `eval-init --manifest <new-directory>/manifest.jsonl` creates draft tooling; it intentionally refuses to overwrite the current set. Review scores belong to the generated output being judged. Filling in run IDs and marking reference flags must follow actual recording/review, not simply editing values to satisfy validation.

## 12. Tests: what they prove and what they do not

| Test file | Main coverage |
|---|---|
| `unit/test_foundation.py` | Contracts, Unicode, identity propagation, serial execution, silence/empty results, input/configuration bounds, stage failures, cancellation, load rollback, and cleanup reporting |
| `unit/test_audio_metrics.py` | Actual resampling behavior, duration/identity preservation, percentiles, failed-sample exclusion, WER, and unreviewed draft creation |
| `unit/test_offline_adapters_cli.py` | Network guard/restoration, receipt integrity, custom-code review requirements, bounded capture/overflow, mocked lazy ASR output, inert imports, and UTF-8 CLI behavior |
| `unit/test_text_adapters.py` | Mocked official IndicTrans2 preprocessing/generation bounds and Kokoro phoneme/vocabulary/context/output bounds |
| `unit/test_playback.py` | Mocked device-rate adaptation, timing proxy, cancellation, and stream cleanup |
| `unit/test_capture_session.py` | Mocked capture limit/identity, stream closure, cancelled playback suppression, session cleanup, advisory RAM behavior, telemetry/VRAM failures, and OOM/device stop behavior |
| `unit/test_memory_policy.py` | ADR-014 RAM warning boundaries, unchanged VRAM ceiling, missing telemetry, gaps/errors, and policy reporting |
| `unit/test_benchmark_review.py` | Fixed-set fake benchmark structure/counts, privacy, separate first/warm-up calls, and rejection of fake evidence for human quality acceptance |
| `integration/test_provisioned_models.py` | Three opt-in cached-asset checks: real ASR, translation, and TTS load/inference under offline controls |

The recorded post-ADR-014 deterministic result is **45 passed, 3 skipped**; see [VALIDATION.md](VALIDATION.md). This guide did not initiate another model benchmark.

The three skips are the real-provider integration cases. They require `ARKE_MODEL_CHECKS=1`, installed runtimes, and already provisioned assets. Ordinary tests intentionally neither download models nor load all real providers. Their pass result proves tested software behavior, not Hindi quality or physical microphone reliability.

```powershell
# Fast checks; provisioned-model tests remain skipped unless explicitly enabled.
.\.venv\Scripts\python.exe -m pytest -q

# Opt-in examples: separate processes let each provider release residency on exit.
$env:ARKE_MODEL_CHECKS = "1"
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_provisioned_models.py -k asr
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_provisioned_models.py -k translation
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_provisioned_models.py -k tts
Remove-Item Env:ARKE_MODEL_CHECKS
```

Even those integration cases are small smoke checks. They do not replace the 30-case benchmark, human review, disconnected execution, or real 30-turn microphone validation. Mocked 30-turn session tests verify logic under controlled conditions, not actual hardware stability.

## 13. The documentation map

| Document | Question it answers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | What are the boundaries, provider contracts, data flow, resource limits, measurement protocol, and provisional targets? |
| [ROADMAP.md](ROADMAP.md) | What belongs to M0–M7, what code exists, and what acceptance remains pending? |
| [DECISIONS.md](DECISIONS.md) | Why were implementation, model, placement, measurement, and RAM-policy decisions made? ADR-014 controls the current reserve policy. |
| [SETUP.md](SETUP.md) | How do dependencies, native libraries, access acceptance, asset provisioning, and run commands fit together on Windows? |
| [EVALUATION.md](EVALUATION.md) | How do you record cases, review references, run benchmarks, score Hindi output, and collect microphone evidence? |
| [VALIDATION.md](VALIDATION.md) | What actually ran, what was measured, what failed, and what remains unverified? |
| [PLACEMENT_EVALUATION.md](PLACEMENT_EVALUATION.md) | What happened when individual stages moved between CPU/GPU? |
| [LOADING_EVALUATION.md](LOADING_EVALUATION.md) | What allocations/loading paths were investigated and what did the strongest loader diagnostics show? |
| [STAGING_EVALUATION.md](STAGING_EVALUATION.md) | What happened with initialization ordering, stage residency, precision, and allocator experiments? |
| [CPU_QUANTIZATION_EVALUATION.md](CPU_QUANTIZATION_EVALUATION.md) | What happened with CPU quantization, derived cached weights, and isolated CPU runtime trials? |
| [OPTIMIZATION_REVIEW.md](OPTIMIZATION_REVIEW.md) | Are the optimization targets appropriate, and what does diagnostic evidence actually establish? |
| [IDLE_BASELINE_EVALUATION.md](IDLE_BASELINE_EVALUATION.md) | What changed after unnecessary applications were closed for controlled follow-ups? |
| [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) | How do the current files and functions cooperate internally? |

When a historical experiment's conclusion differs from current policy, consult the current decision and the report's date/policy note. Do not interpret an old report generator or an experiment configuration as a new default.

## 14. Local experiment files

The ignored `artifacts/` directory currently contains small diagnostic programs as well as generated data. They help explain the optimization history but are **not supported application entry points**. Many use process-local hooks, hard-coded paths, or specific earlier output names. Running a report writer may overwrite curated documentation with historical assumptions.

The following inventory describes their roles, not a recommendation to execute every script:

| Local file(s) | Role |
|---|---|
| `memory-probe.py` | One-call composed memory diagnostic with before/after loading and inference snapshots; not the full benchmark protocol |
| `profile_memory_v1.py` | Provider-boundary allocation investigation, tensor-storage inventory, and optional Kokoro checkpoint mapping; uses one pass over draft cases after warm-up, not the three-pass acceptance protocol |
| `report_option1.py` | Summarizes the early memory attribution investigation |
| `placement_benchmark.py` | Adds phase tracing/memory sampling around explicit placement benchmarks |
| `run-placement-benchmark.ps1` | Fresh-process wrapper for placement investigation |
| `report_placement.py` | Produces the corresponding placement comparison report |
| `investigation_hooks.py` | Installs process-local experimental loading changes and tensor/storage diagnostics without editing the application adapters |
| `investigation_benchmark.py` | Runs loading, initialization/residency, allocator, and cached-loading trials around the benchmark machinery, recording phases and actual experimental choices |
| `run-loading-benchmark.ps1` | Fresh-process wrapper for loader/staging investigations |
| `loading_numerical_check.py` | Seeded numerical/state comparisons for loading changes; numerical evidence does not supply listening scores |
| `summarize_loading.py`, `write_loading_report.py` | Summarize loading trial outputs and write their report |
| `write_staging_report.py` | Writes the staging/precision investigation report |
| `prepare_compact_placement.py`, `prepare_cpu_placement.py`, `prepare_cpu_quant.py` | Prepare explicit local experiment profiles; do not automatically change `configs/v1.toml` |
| `cpu_quant_hooks.py` | Process-local CPU quantization and related preparation, with explicit quantized-module choices |
| `cpu_quant_probe.py` | Small CPU quantization/cached-loading probes; a completed probe is not a 90-observation benchmark |
| `build_cpu_optimized_assets.py` | Explicitly derives local cached CPU weights and integrity metadata; the derived assets are ignored and distinct from upstream provisioning |
| `cached_cpu_hooks.py` | Experimental loading of those derived assets with receipt/hash/runtime checks, empty/meta construction, and required buffer handling |
| `cpu_cache_numerics.py` | Numerical comparison tooling for CPU conversion/caching; tooling existence does not mean a complete comparison ran |
| `run-cached-cpu-benchmark.ps1` | Fresh-process wrapper for the explicit CPU cache trial |
| `write_cpu_quant_report.py` | Writes CPU quantization/caching evidence and failures |
| `system_memory_inventory.py` | Read-only Windows memory/process inventory, including system commit/kernel observations; does not close programs or alter Windows settings |
| `live_progress.py` | Observes benchmark progress and process data; the observer itself consumes some memory |
| `verify_environment.py` | Checks which Python/Torch runtime a trial is using |
| `write_idle_report.py` | Writes idle-desktop follow-up evidence |

Additional generated files fall into these families:

- **Run directories:** metadata, observations, summaries, phase events, sampled memory, and optional output WAVs. Run IDs and manifest hashes establish which inputs/settings produced a report.
- **Console logs:** test and model-check output, failure traces, setup/runtime observations. Logs preserve evidence; they are not automatically current status.
- **Model directories:** original weights, tokenizers, voice assets, pinned vendor code, `setup-plan.json`, and `provisioned.json`. Experimental derived CPU assets have separate provenance and are not standard provider defaults.
- **Evaluation directories:** draft manifests, synthetic diagnostic recordings, later human recordings, reference-review flags, and listening/adequacy forms. A file being present does not establish review completion.
- **Caches/environments:** downloaded package archives, Hugging Face/module caches, installed third-party source and DLLs, and isolated runtimes used in experiments. Application files inside `src/` remain the place to inspect project behavior.

The strongest experimental GPU loader is not selected by merely passing `configs/all-gpu.toml` to the normal CLI. That config changes placement/precision; the experimental hooks additionally change loading behavior. Integration of an accepted loader would require a separate reviewable code change and evidence. It has not happened merely because a local experiment succeeded.

## 15. Tracing a problem and understanding the remaining work

| Symptom/question | Start reading here |
|---|---|
| “Why does the command choose these models/devices?” | Config file → `config.py` → `providers/factory.py` |
| “Why can't my WAV be opened?” | `cli.py` file branch → `audio/normalize.py` |
| “Why is input rejected or skipped?” | `types.py`, config bounds, `pipeline.py` input/RMS checks |
| “Why are weights missing or rejected?” | `provision.py` receipt validation → provider `load()` |
| “Why does CUDA fail despite an NVIDIA driver?” | ASR DLL/compute-type checks, Torch setup, then `SETUP.md` |
| “Where do English words become Hindi?” | `translation_indictrans2.py`, especially preprocessing → generation → postprocessing |
| “Where does Hindi become sound?” | `tts_kokoro.py`, phonemes → model → 24 kHz samples |
| “Why does Space/Escape/Q behave this way?” | `audio/capture.py`, then `Cancellation` and pipeline checks |
| “Why does playback use a different rate?” | `audio/playback.py` device validation/resampling |
| “Why is low RAM a warning, or why does VRAM/telemetry stop capture?” | `metrics.py` → `audio/capture.py` → ADR-014 |
| “Why can all tests pass while acceptance is pending?” | Test inventory → `EVALUATION.md` and `VALIDATION.md` |
| “Why is the experiment faster than my CLI run?” | Experiment hook/profile distinction → loading/placement reports |

For a first code-reading pass, use this order: `types.py` → `interfaces.py` → `config.py` → `fake.py` → `pipeline.py` → `factory.py` → `cli.py`. You can understand that path without learning every vendor library. Then read `normalize.py`, `capture.py`, and `playback.py`; then the real adapters, provisioning/offline controls, and measurement/evaluation modules.

The remaining validation follows the same separation of concerns: review the reference set, measure recognition against reviewed English, review translation from correct English, listen to TTS from reviewed Hindi, check composed results, and run real sustained microphone/disconnected operation. Record failures and subjective findings rather than substituting synthetic scores.

This guide describes the current implementation; it does not claim those pending steps passed, adopt an experimental default, or extend V1 scope.
