# Architecture decisions

Created: 2026-10-02. Status terms: **accepted** = V1 design direction; **candidate** = evaluate before selecting a default; **deferred** = outside V1; **proposed gate** = initial evaluation target requiring evidence.

The starter bundle established no measurements. Current implementation evidence and pending gates are recorded in `VALIDATION.md`; earlier illustrative timings must not appear as benchmark results. ADR-014 supersedes the earlier mandatory 1 GiB RAM gate; dated experiment notes retain their original policy and results.

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

Aim for total dedicated VRAM <= 3.5 GiB; require a 30-turn session without crashes/OOM. Under ADR-014, >= 1 GiB available system RAM is an advisory reserve rather than an acceptance gate or predicted crash threshold. Record memory throughout startup and the session and assess observed stability, memory growth and latency degradation under a documented baseline. The architecture doc defines timing boundaries and the evaluation protocol.

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

## 2026-10-03 microphone startup diagnosis — ADR-010, ADR-012

The user reported only Codex was running. Latest microphone evidence (`artifacts/microphone.jsonl`, session `13d454d9-bd14-4dc4-80d3-fe28df7cc29d`) started with 1.914 GiB available RAM; loading the initial placement reduced sampled available RAM to 303.2 MiB. Peak dedicated VRAM was 639.0 MiB and telemetry had no errors. This was the application's proactive RAM-margin rejection, not an observed CUDA/OOM crash. The gate aggregates samples during model loading; it is not solely an instantaneous post-load check.

A fresh single-utterance GPU-translation diagnostic (`artifacts/memory-probe-gpu-translation.json`) measured 1343.7 MiB available immediately after loading and 844.0 MiB after inference, with a 7.9 MiB sampled minimum during the entire probe. Inference succeeded, but this is not a passed memory/stability/quality benchmark. Moving translation alone did not establish sufficient headroom under the current baseline. Windows, Codex, and model/runtime allocations contribute even when other user applications are closed. The error now reports exact RAM/VRAM readings and telemetry errors instead of implying other open applications are the only cause. Defaults and targets remain unchanged; lower-memory placement/loading still requires measurement.

## 2026-10-03 CPU/GPU placement evaluation — ADR-006, ADR-009, ADR-010, ADR-012

The human requested placement evaluation before adopting changes. Four fresh, serial process runs used the same 30-case unreviewed SAPI/draft manifest, three warm-ups and three measured passes. Each completed 90/90 observations without provider failures/OOM or telemetry errors. Original loaders and candidate model revisions were retained; no application source, default or gate changed during this evaluation. Explicit experiment configurations are `gpu-tts.toml`, `all-gpu-fp32.toml` and `all-gpu.toml`.

ASR GPU FP16 / translation CPU FP32 / synthesis CPU FP32 measured processing p50/p95 1.988/2.609 s. Moving synthesis to GPU FP32 measured 0.846/1.131 s. Moving translation to GPU FP32 as well measured 0.478/0.592 s, with 2.398 GiB peak dedicated VRAM. All-GPU FP16 translation measured 0.480/0.598 s and 1.982 GiB peak dedicated VRAM: less VRAM, without a meaningful warm latency advantage in this diagnostic. Standalone GPU FP32 synthesis also completed 90/90 cases, p50/p95 0.116/0.178 s. These are file processing/stage timings, not microphone-to-audible response measurements.

Every full-run RAM gate failed. All-GPU FP32 measured a warm minimum of 1021.7 MiB, slightly below the unchanged 1024 MiB margin, and a first-inference minimum of 80.3 MiB. Its loading minimum was 338.0 MiB. All-GPU FP16 warm minimum was 564.7 MiB. Baseline available RAM differed substantially between processes; these observations do not establish a controlled causal amount of RAM saved by placement or precision. Sampling interval p50/p95 was approximately 110–111/112–113 ms despite a requested 100 ms; short peaks may be missed.

All-GPU FP32 is a promising subsequent host-memory/loading experiment, not an accepted default. GPU placement did not remove CPU model construction/loading or first-call runtime allocations. No candidate replacement or target relaxation is justified by these results alone. Human Hindi/translation review, real recordings, acoustic response timing, disconnected operation and 30 microphone turns remain pending. Full evidence, configurations, phase summaries and reproduction commands are in `PLACEMENT_EVALUATION.md`; earlier measurements remain historical evidence in `VALIDATION.md`.

## 2026-10-03 loading/first-inference investigation — ADR-009, ADR-010, ADR-012

The human requested investigation while retaining the discussion-before-adoption boundary. Nine fresh-process runs kept Whisper small GPU FP16, IndicTrans2 distilled 200M GPU FP32 and Kokoro GPU FP32, using the fixed 30-case SAPI/draft diagnostic set, three warm-ups and three passes. Each completed 90/90 measured observations without provider failures/OOM or telemetry errors; every full-run available-RAM gate failed. No application source, default configuration, model asset or acceptance target changed during this investigation.

Kokoro retained approximately 219.9 MiB of derived, unregistered CPU tensor storage after GPU loading because its legacy WeightNorm hooks replace it only on forward. Clearing 89 such attributes with their recomputation hooks intact released 214.6 MiB of process private commit and 136.0 MiB of RSS in an immediate before/after check. Registered model parameters/buffers were unchanged. A seeded 30-case TTS comparison was bit-exact for mmap, stale-attribute cleanup, no_grad construction and the combined mmap/cleanup path. GPU construction retained identical registered parameter/buffer hashes but produced waveform differences beyond the stated numerical tolerance; their audibility/cause was not established, so that path is unadopted.

Direct translation GPU loading used an explicit root `device_map` to CUDA 0 with Accelerate 1.6.0 installed only into an ignored isolated cache directory. It added no application dependency or automatic placement/offload. Combining this with Kokoro mmap and CPU-attribute cleanup completed two fresh runs: processing p50/p95 0.487/0.590 s and 0.480/0.598 s, total dedicated VRAM 2.339 GiB, full-run available-RAM minima 315.4/319.6 MiB. Warm-phase minima were 921.8/932.0 MiB. English/Hindi text fingerprints matched the original loader for all calls. Stage checkpoints show further RAM loss during first ASR and translation calls before synthesis; coarse telemetry does not isolate exact native allocation ownership.

Baselines varied substantially, including an original-loader baseline already below the 1 GiB margin. Cross-run minimum differences are not a controlled causal amount of RAM saved. Early DLL mapping field names were misleading and are annotated as region inventory, not physical RSS or native-library ownership. Full-run gate telemetry itself is unaffected. Diagnostic callbacks add timing overhead; file processing is not acoustic response latency.

No loader/default is accepted and no margin is relaxed. Further first-call host/runtime attribution or explicit staged initialization/residency is a reasonable next experiment before selecting a replacement model; neither is claimed implemented or successful here. Staged residency must include reload costs and quality checks. All human quality, disconnected real-flow and 30-turn microphone gates remain pending. Evidence, reproduction steps, isolated dependency details and limitations are in `LOADING_EVALUATION.md`.

## 2026-10-03 staging and precision evaluation — ADR-009, ADR-010, ADR-012

Five subsequent fresh-process comparisons each completed the fixed 30-case diagnostic set three times, without provider/OOM failures or telemetry errors. Explicit initialization order, per-stage reload/close, CPU ASR with GPU MT/TTS, compact GPU precision and requested CTranslate2 zero-cache CUB settings all failed the full-run RAM margin (170.1–429.1 MiB minimum available). Serial reloads included their costs and measured processing p50/p95 5.773/6.445 s; provider close did not establish release of all native allocations. CPU ASR measured 2.365/2.651 s; compact GPU precision 0.495/0.603 s. Reduced VRAM alone does not solve the host RAM gate. No application default, source, acceptance target or model candidate changes on this evidence. The human has deferred listening/reference review and microphone validation until optimization; those gates remain pending. See `STAGING_EVALUATION.md` for measured placement, phase memory, failure accounting and limitations.

## 2026-10-03 CPU quantization/cache investigation — ADR-009, ADR-010, ADR-012

Explicit ignored diagnostic loaders evaluate the same models with CPU ASR INT8/FP32, CPU FBGEMM quantized translation linear/embedding weights (remaining tensors FP32), and CPU FP32 Kokoro with fused WeightNorm weights. A separate offline conversion writes checksummed derived weights into the ignored local model directory; original provisioned receipts/revisions and application source/defaults remain unchanged. Cache startup performs strict weight assignment, not runtime conversion or fallback. Failed contiguous-index, meta-construction and generation-metadata probes are preserved and resolved explicitly. Conversion itself failed the RAM margin and is not presented as runtime validation.

The first completed 90-observation cached CPU benchmark using torch 2.7.1+cu126 had no provider/OOM or telemetry failures, but processing p50/p95 was 5.984/7.978 s and full-run available RAM reached 202.5 MiB. It is not accepted. A same-release official CPU-only torch wheel is provisioned in an isolated cache for a separate explicit runtime comparison, without replacing the environment or model. Background load is not controlled; process inventory showed browser and substantial kernel memory during the comparison. Cross-run changes cannot establish causal memory savings. Numerical cache checks and human quantization/listening acceptance must remain separate. Full evidence and limitations are in `CPU_QUANTIZATION_EVALUATION.md`.

The CPU-only comparison subsequently completed 90/90 calls without provider/OOM/telemetry failures, measuring processing p50/p95 3.857/10.316 s and 3.3 MiB minimum available RAM. The human closed unnecessary apps during it, so it spans changing background load rather than a controlled CPU/CUDA build comparison. It remains unaccepted; cache numerical parity tooling is scaffolded but unrun after the failed resource gate.

## 2026-10-03 goal review and idle-desktop follow-up — ADR-009, ADR-010, ADR-012

The human asked to reassess benchmark targets and confirmed an idle desktop for follow-up. Targets are retained: the response/memory margins remain reasonable provisional goals for this hardware, while synthetic/file benchmarks cannot replace human/microphone acceptance. Model-free available RAM was 1583.2/1719.8 MiB before two fresh runs of the strongest same-model GPU loader. Both completed 90/90 calls with original-loader English/Hindi fingerprints matching all 94 ordinary calls, processing p50/p95 0.496/0.602 s and 0.481/0.589 s, and dedicated VRAM 2.339 GiB. Both full-run RAM gates failed (247.7/75.0 MiB sampled minima), as did warm-phase RAM headroom. An explicit native GPU-ASR plus CPU-only-PyTorch cached MT/TTS one-case probe also failed the RAM margin. Fast computation and adequate VRAM therefore do not establish a sustainable accepted session.

No app, service or OS working set was forcibly closed/trimmed by the agent. Baseline snapshots include substantial and varying Windows service/kernel memory, but establish no leak or exact native owner. A model replacement is neither required nor proven sufficient by these observations alone. Keep the current explicit failure and provisional defaults; further runtime/representation or smaller-candidate investigation needs measured full-run headroom and appropriate numerical/human validation. See `OPTIMIZATION_REVIEW.md` and `IDLE_BASELINE_EVALUATION.md`. All human quality, disconnected hardware and 30-turn microphone gates remain deferred/pending.

## ADR-014 — Advisory RAM reserve and measured session stability

**Accepted by the human, 2026-10-03; runtime/reporting implemented on 2026-10-03.** Supersedes the mandatory available-RAM portion of ADR-012 and earlier experiment conclusions that rejected a configuration solely for falling below 1 GiB. This decision changes the acceptance policy; it does not change models, placement, precision, scope or historical measurements.

The human requested a revision after repeated diagnostic file runs completed without crashes/OOM despite available RAM below 1 GiB. In the two idle-desktop GPU follow-ups, each completed 90/90 measured calls with processing p50/p95 0.496/0.602 s and 0.481/0.589 s, dedicated VRAM 2.339 GiB, and sampled available-RAM minima 247.7/75.0 MiB. Evidence is in `IDLE_BASELINE_EVALUATION.md`. This demonstrates successful execution under those observed conditions, not universal safety at low RAM or sustained microphone stability. The original 1 GiB reserve was conservative and was not an empirically measured crash threshold.

Decision:

- Retain 1 GiB available physical system RAM as an advisory warning threshold. A lower reading alone must not reject a candidate, block capture, predict a crash or trigger a model/device fallback. Do not replace it with another arbitrary mandatory RAM cutoff.
- Continue sampling available RAM, process RSS/private commit and total dedicated VRAM throughout loading, first inference, warm processing and cleanup. Preserve minima, phase results, actual intervals, telemetry errors and all observed failures. Low-RAM warnings must remain visible even when latency and execution outcomes pass.
- Assess stability through actual outcomes: require no crashes/OOM across 30 sequential microphone turns, report every skip/failure, and examine memory trends and latency across the session. Sustained unexplained memory growth, observed allocation failures, hangs or material latency degradation require investigation before claiming stability. A short successful run or percentile alone does not establish sustained reliability. Missing telemetry leaves memory/stability evidence unverified.
- Keep the 3.5 GiB total dedicated-VRAM ceiling, p50 <=3 s / p95 <=5 s response goals, quality requirements, bounded serial processing and local/offline requirements unchanged. File processing remains a diagnostic proxy for microphone-to-audible response. Actual OOM/device errors must still fail explicitly without silent retry or fallback.
- The strongest tested GPU loader may proceed as a file-performance-qualified candidate toward human quality and microphone validation. Its loading changes remain diagnostic hooks, not integrated application behavior or an accepted default. Human reference/listening review, acoustic response, physical disconnected operation and 30 microphone turns remain pending; V1 is not yet validated.

Consequences and implementation status:

The subsequent authorized runtime change implements this policy. `MemorySampler.summary()` records `memory_policy: adr-014-ram-advisory`, `ram_advisory`, `vram_gate` and `telemetry_status`; `memory_gate` passes only when telemetry is complete and dedicated VRAM is within the ceiling, regardless of RAM reserve. Missing/gapped telemetry remains unverified. New readable benchmark reports show the RAM advisory separately and do not equate a passed memory check with validated stability.

`listen` checks after model loading and each utterance, records cumulative memory observations for session trend review, and emits one visible low-RAM warning without rejecting capture solely on RAM. Excess VRAM or incomplete telemetry still ends the session and closes providers; actual device/OOM failures stop further attempts. Session reports separate `execution_gate` (30 successful real turns) from `stability_gate: pending_memory_latency_review`; fake runs cannot establish either real gate. Focused model-free tests cover low-RAM execution, threshold boundaries, missing/gapped telemetry, later VRAM failure, actual OOM handling and cleanup. Models, placements, default configuration and diagnostic loading hooks are unchanged; no bypass command is introduced.

Historical benchmark artifacts and dated reports remain unchanged: their `memory_gate: fail` values describe the previous acceptance policy. They must not be relabeled passed retrospectively. Reassessing a candidate under this decision requires reporting those warnings alongside actual execution, latency and remaining validation evidence; it does not fabricate a stability or quality pass.
