# Architecture decisions

Created: 2026-10-02. Status terms: **accepted** = V1 design direction; **candidate** = evaluate before selecting a default; **deferred** = outside V1; **proposed gate** = initial evaluation target requiring evidence.

The starter bundle established no measurements. Current implementation evidence and pending gates are recorded in `VALIDATION.md`; earlier illustrative timings must not appear as benchmark results.

## ADR-001 — Portfolio-first local inference

**Accepted.** V1 should prove the pipeline on an RTX 3050 with 4 GB VRAM and 8 GB RAM, produce reproducible evidence, and avoid inference service charges. After explicit provisioning, speech, text, and synthesized audio stay on the computer during inference.

Consequence: quality and speed are limited by actual local resources. Offline capability requires caching every runtime asset. Model/dependency downloads and repository access are setup tasks, not cloud inference. A local failure does not trigger a network request.

## ADR-002 — Python-first V1

**Accepted.** Use Python for capture orchestration, model adapters, CLI, and benchmarking because experimentation and model integration are the immediate goals. Begin with a proposed Python 3.11 environment and confirm dependency support before pinning it.

Consequence: use profiling before introducing a second language. Rust/native application work is deferred until a specific audio, packaging, or performance requirement justifies it.

## ADR-003 — One language direction and completed utterances

**Accepted.** English -> Hindi first; one speaker, one completed utterance, one output at a time. Push-to-talk makes speech boundaries explicit and keeps the first benchmark interpretable. Simple VAD is an optional follow-up within V1.

Consequence: this is interactive utterance translation. Continuous streaming, simultaneous interpretation, bidirectional conversation, diarization (identifying different speakers), and interruption while translated speech plays are deferred. Capture pauses during playback; headphones reduce feedback.

## ADR-004 — faster-whisper small as initial ASR

**Candidate.** Evaluate faster-whisper with Whisper `small` first. Specify English and the transcription task. Compare supported FP16/INT8 execution at batch size 1 on the target hardware before choosing defaults.

The upstream implementation uses CTranslate2 and supports reduced-precision execution. Its published results use other hardware, so they do not establish this laptop's latency or memory. Runtime compatibility must follow the selected faster-whisper/CTranslate2 versions. Returned segments are lazy and must be consumed during timing. [Official repository](https://github.com/SYSTRAN/faster-whisper).

Consequence: `base` is a possible measured fallback if small misses resource targets. Record its recognition tradeoff instead of silently replacing the candidate.

## ADR-005 — IndicTrans2 distilled En-Indic 200M

**Candidate.** Evaluate `ai4bharat/indictrans2-en-indic-dist-200M` for English -> Hindi. “200M” identifies the named variant; it is not a RAM/VRAM budget. Use the adapter to handle `eng_Latn`, `hin_Deva`, and official preprocessing/postprocessing.

The model card currently requires repository access conditions to be accepted and points to the official inference processor. Confirm compatible library versions; use a supported basic attention path before adding optional acceleration dependencies. Pin any downloaded custom model code to a reviewed revision. [Model card](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M), [official repository](https://github.com/AI4Bharat/IndicTrans2).

Consequence: benchmark with reference text to isolate translation quality. Preserve Devanagari output and evaluate numbers, names, and negation. Hindi -> English would require a separate direction/model decision later.

## ADR-006 — Lightweight stock-voice TTS first

**Accepted approach; Kokoro-82M is a candidate.** First prove understandable Hindi speech using a stock voice. Evaluate CPU placement first to preserve GPU headroom for ASR/translation.

Kokoro's official assets include Hindi voices and a Hindi language path (`h`) with espeak-ng Hindi phonemization. Language availability is not proof of adequate pronunciation. Evaluate short utterances, names, numbers, and dates on reviewed Hindi text before accepting it. Cache phonemizer/voice assets for offline use. [Voice documentation](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md), [implementation](https://github.com/hexgrad/kokoro).

Consequence: another lightweight local Hindi provider may replace Kokoro if evidence supports it. The core pipeline retains the same synthesis contract. Do not preserve speaker identity in V1.

## ADR-007 — XTTS-v2 later for voice preservation

**Deferred.** Evaluate XTTS-v2 when the local baseline is measured and stable. Its model card lists cross-language voice cloning and Hindi support, and uses the Coqui Public Model License. Adoption requires a new resource/quality benchmark and review of applicable use terms. [XTTS-v2 model card](https://huggingface.co/coqui/XTTS-v2).

Consequence: provider separation should allow replacing synthesis without rewriting ASR/translation. Voice preservation is approximate and must be evaluated, not guaranteed. Collect speaker references only with the speaker's agreement during that future stage. No XTTS dependency or speaker-profile storage enters V1.

## ADR-008 — Small provider interfaces

**Accepted.** Separate `SpeechRecognizer`, `TextTranslator`, and `SpeechSynthesizer` from orchestration. Keep vendor models, tensors, preprocessing, and language codes within adapters. Use explicit provider selection and shared typed results.

Consequence: future local/cloud/hybrid adapters can reuse the pipeline. V1 does not implement automatic routing, service abstractions, a plugin marketplace, or cloud credentials. Quality differences between providers remain visible.

## ADR-009 — Benchmark stages before composition

**Accepted.** Benchmark ASR on audio, translation on correct English text, and TTS on reviewed Hindi text. Then benchmark the composed file and microphone flows with all intended resident models.

Consequence: an end-to-end error can be traced to recognition, translation, or synthesis. Report cold/warm p50/p95, response/completion timing, quality review, peak memory, and failures. Native memory sampling must complement framework counters.

## ADR-010 — Bounded serial processing and explicit memory placement

**Accepted.** Batch size 1, one active utterance, bounded audio/text, no unbounded queue. Decide placement through hardware measurements. Initial composition experiment: ASR GPU, translation CPU, TTS CPU. This is a hypothesis, not a selected or measured configuration.

Consequence: CPU execution may increase latency; staged loading may add repeated startup costs. Concurrent inference and all-GPU residency require evidence before adoption. Use explicit fallback configuration and report changes to quality, latency, and memory.

## ADR-011 — CLI, local files, no application infrastructure

**Accepted.** Use a CLI plus JSONL benchmark artifacts, local model caches, and optional WAV export. V1 needs no database, server, account system, Zoom integration, or cloud deployment.

Consequence: setup/run commands remain planned until code exists. Ignore caches and private recordings in Git. Persist raw content only when enabled; performance metadata is sufficient for routine measurement.

## ADR-012 — Initial success criteria

**Proposed gates.** For 2–6 second utterances, aim for warm median speech-end -> audible-output latency <= 3 seconds; report p95 with an initial <= 5 second aim. Propose clean WER <= 20%, >= 90% meaning scores >= 4/5, and >= 90% Hindi intelligibility scores >= 4/5. List critical-detail errors separately.

Aim for total dedicated VRAM <= 3.5 GiB and >= 1 GiB available system RAM under a documented baseline; require a 30-turn session without crashes/OOM. These margins depend on the computer's background workload. The architecture doc defines timing boundaries and the evaluation protocol.

Consequence: do not call targets achieved until measured. Adjust provisional targets through a dated evidence-backed decision. A portfolio report may explain a latency miss, while adequate quality, local operation, and stability remain required for V1 completion.

## ADR-013 — Modular pipeline before end-to-end speech models
Accepted.

Begin with separate ASR, translation, and TTS stages because they
allow independent evaluation, clearer error attribution, model
replacement, and better control under constrained local hardware.

Direct speech-to-speech models are deferred but remain a future
candidate. Evaluate them only when the local modular baseline exists
and compare latency, semantic accuracy, prosody preservation, memory,
and voice quality against that baseline.

## Open gates before selecting defaults

| Gate | Evidence needed | Resolve by |
|---|---|---|
| Dependency compatibility | OS/CPU/driver/runtime inventory and a working pinned environment | M0, then each adapter |
| Model access and offline assets | Explicit access setup, recorded revisions, disconnected inference | M2–M5 |
| ASR precision and size | WER, latency and memory comparison on target laptop | M2 |
| Translation placement | Reviewed outputs, CPU/GPU latency and memory | M3 |
| Hindi TTS voice and suitability | Listening scores and synthesis timing | M4 |
| Combined residency | All chosen models loaded; sampled RAM/VRAM and failures | M5 |
| Response timing | Endpoint/release lag, processing and output-device measurements | M6 |
| VAD usefulness | Delay, clipped speech and false-trigger comparison | Optional M7 |

## How to change a decision

Append a dated entry with the decision ID, new status, evidence artifact/configuration, alternatives measured, reason, and effect on scope/quality/latency/memory. Keep earlier context readable. Update README, architecture, and roadmap wherever behavior changes.

Example template:

```text
Date:
Decision ID:
Old choice -> new choice:
Evidence and hardware/configuration:
Quality effect:
Latency effect (cold/warm, p50/p95):
RAM/VRAM effect:
Reason and remaining limitations:
Docs updated:
```

Primary references were checked on 2026-10-02. Recheck setup instructions when implementing; upstream dependencies, model access, and runtime requirements can change.

## 2026-10-03 implementation entry — ADR-002, ADR-009, ADR-010, ADR-011

Python 3.11.15 is installed in an ignored project-local environment. The deterministic foundation is exercised on Windows build 26200 / Intel i5-12500H / RTX 3050 Laptop GPU 4 GiB / 8,259,358,720 bytes system RAM. Exact tested package versions and measurements are in `VALIDATION.md` and local environment artifacts. CTranslate2 4.6.0 requires a setuptools release retaining `pkg_resources`; setuptools 75.8.2 is explicitly pinned instead of allowing an incompatible latest release.

The baseline desktop has approximately 1 GiB free RAM and can fall below the provisional margin even during fake checks. No combined placement is accepted without the documented memory measurement. The initial ASR-GPU/translation-CPU/TTS-CPU candidate remains provisional. Latency/quality claims from fake or SAPI-generated diagnostic speech are not acceptance evidence.

The official IndicTransToolkit documents Linux/macOS prerequisites rather than Windows support. Model access was denied during IndicTrans2 provisioning. Translation keeps the official processing boundary and the access/review gate; it does not silently substitute another translator or cloud inference. Windows compatibility, user repository acceptance, bilingual references, Hindi listening, disconnected real flows, and microphone stability remain separate requirements.

The human approved implementing the rest of V1 tooling while unavailable evaluation data/review is scaffolded and marked pending. This changes the roadmap's coding order gate only where external human evidence is absent; it does not waive acceptance gates. Optional VAD is omitted as selected in the implementation plan. The runtime adds a Python socket guard and explicit cached paths; final disconnected verification is still required. Setup, architecture, roadmap, and evaluation docs are updated together.

CPU ASR requested generic `int8` during its initial load probe, but CTranslate2 reported actual `int8_float32`. The adapter rejected the mismatch instead of silently accepting conversion. `configs/asr-cpu.toml` now explicitly selects supported `int8_float32`; the initial failed probe remains in local artifacts. This is a diagnostic precision correction, not acceptance of CPU placement or a model replacement.

The user subsequently accepted IndicTrans2 access conditions and configured a cached login. Provisioning succeeded after keeping authentication separate from local model/module cache overrides. Official IndicTransToolkit 1.1.1 built and imported on this Windows machine. Kokoro's Misaki/espeakng-loader path also executed locally; a standalone espeak-ng executable was not required. These observations resolve installation/access prerequisites on this machine only; they do not pass human quality gates.

Model configuration revisions are now pinned to the actual provisioned commits recorded in `VALIDATION.md`. IndicTrans2 uses one safetensors weight representation, both SentencePiece assets, and reviewed/checksummed custom code. PyTorch 2.7.1+cu126 provides the explicitly configured ASR native DLL directory. GPU ASR FP16 and INT8/FP16 diagnostic comparisons are recorded, while the named candidate and initial placement remain provisional. An explicit GPU-FP16 translation comparison is included because CPU translation plus CPU synthesis can exceed the provisional response budget; no runtime routing/fallback was added.

## 2026-10-03 measured residency entry — ADR-009, ADR-010, ADR-012

Both composed configurations completed 90/90 diagnostic file observations with no provider failures. Initial ASR GPU FP16 / translation CPU FP32 / TTS CPU FP32 processing p50/p95 was 4.359/6.080 s; peak RSS 1.690 GiB, dedicated VRAM 1.026 GiB, minimum available RAM 0.011 GiB. Explicit GPU FP16 translation reduced processing p50/p95 to 3.577/4.580 s; peak RSS 1.902 GiB, dedicated VRAM 1.427 GiB, minimum available RAM 0.017 GiB. Cold launch-to-ready was 25.136 s and 31.994 s respectively. Full evidence is in `artifacts/pipeline-initial-diagnostic` and `artifacts/pipeline-gpu-translation-diagnostic`, summarized in `VALIDATION.md`.

These experiments used SAPI diagnostic English and unreviewed draft references under the current desktop workload. Both failed the ≥1 GiB available-RAM gate, although sampled VRAM remained below 3.5 GiB. Private process memory peaked above 6 GiB in both runs; low resident RSS alone does not establish adequate system headroom. File timing is not microphone-to-audible timing, and human quality/stability/offline gates remain pending. No placement is accepted and no target is relaxed.

Warm microphone sessions now explicitly check sampled resident-memory margins after loading real providers and close them before capture if telemetry fails or the margins are not met, as required by the architecture. Stage/file/composed diagnostics remain available to assess candidates. The current desktop must free sufficient background RAM or measure another explicit V1 placement before microphone acceptance. This does not silently change a model, device, or precision.
