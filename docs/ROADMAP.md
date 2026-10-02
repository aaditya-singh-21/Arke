# Roadmap and implementation gates

Implement milestones in order. Complete the listed evidence before adding the next layer. V1 is the first portfolio milestone; later stages are direction, not promises of delivery dates or guaranteed performance.

## Implementation status (2026-10-03)

The human request authorizes completing V1 code while unavailable human references/listening remain pending. The implementation proceeds through the layers in order; code existence does not complete a milestone's acceptance evidence. See `VALIDATION.md` for measured results and prerequisites.

| Milestone | Code/tooling | Acceptance evidence |
|---|---|---|
| M0 | Implemented; Python 3.11 foundation and fake CLI exercised | Deterministic checks pass; full native adapter compatibility assessed separately |
| M1 | Implemented; 30 draft cases, review forms, benchmark/memory harness | Fake 90-observation run exercised; human recordings/references pending |
| M2 | Implemented; faster-whisper adapter and pinned provisioning | Stage measurements recorded as diagnostics when synthetic speech is used; human WER pending |
| M3 | Implemented; official processor boundary and reviewed-code gate | Access resolved; processor runs on Windows; CPU/GPU diagnostics recorded; bilingual review pending |
| M4 | Implemented; bounded stock Hindi Kokoro adapter | Real CPU synthesis benchmark recorded; human listening pending |
| M5 | Implemented; file orchestration and offline asset checks | Real composition runs with cached assets and network guard; available-RAM margin failed; physical disconnection pending |
| M6 | Implemented; bounded Windows PTT, cancellation, playback proxies | Human microphone/listening and 30-turn stability session pending |
| M7 | Setup/evaluation/validation documentation implemented | Demo and final accepted placement/quality decisions pending; optional VAD omitted |

V1 is not yet declared validated. No V2 or portfolio-extension features are implemented.

## M0 — Scaffold and execution contracts

Create the Python package, `pyproject.toml`, `.gitignore`, configuration, typed provider interfaces/data objects, fake providers, serial pipeline, structured errors, and utterance timing. Implement a lightweight `doctor` command. Record the target environment and decide a compatible Python/runtime dependency baseline.

Done when a fake utterance produces inspectable English/Hindi outputs and an audio-result object, every stage has timing, invalid configuration fails clearly, and imports have no audio/model/download side effects. Update the README with actual working commands. Heavy dependencies should enter only with their adapter.

## M1 — Evaluation assets and measurement harness

Prepare the 30-case evaluation manifest, reference transcripts, reviewed Hindi text, and edge cases described in the architecture doc. Implement per-stage benchmark selection, metadata capture, warm-up handling, JSONL results, summaries, and RAM/VRAM sampling. Keep evaluation content local unless intentionally selected for sharing.

Done when fake-provider runs create reproducible reports with correct durations, p50/p95, error counts, and configuration metadata. Real hardware/model measurements are still pending at this milestone.

## M2 — ASR candidate in isolation

Provision only the initial ASR assets. Implement faster-whisper `small` with explicit English transcription. Benchmark batch size 1 and supported GPU precision options; include CPU as a diagnostic option. Fully consume segments before stopping timing. Measure WER, silence behavior, cold/warm timing, and memory.

Done when saved audio yields understandable English transcripts and a report from the RTX 3050 machine. If small fails resource gates, evaluate base as a documented fallback; preserve the comparison and quality cost.

## M3 — Translation candidate in isolation

Handle IndicTrans2 access/setup explicitly. Implement the En-Indic distilled 200M adapter using the official processor and language tags. Feed reference English text, not ASR output. Benchmark CPU and a GPU configuration if appropriate; verify dtype compatibility and bounded generation without silent truncation.

Done when a bilingual review scores the evaluation cases, Hindi text retains important details, and latency/memory are recorded. Record the chosen placement and failures before integration.

## M4 — Lightweight Hindi TTS in isolation

Provision Kokoro-82M, a Hindi stock voice, and its required text/phonemizer assets. Begin with CPU inference. Feed reviewed Hindi text and inspect pronunciation, short phrases, names, dates, numbers, output sample rate, audio validity, and playback. Compare GPU only if CPU timing justifies the memory cost.

Done when a Hindi listener can understand the output, the TTS quality gate is reviewed, and cold/warm synthesis and memory measurements exist. If Kokoro misses the quality/resource gate, evaluate another lightweight local Hindi TTS provider through the same interface. Record that choice; do not jump to XTTS or cloud as an implicit V1 fallback.

## M5 — Composed file pipeline

Connect the accepted adapters: WAV -> English transcript -> Hindi text -> Hindi WAV. Expose intermediate text and per-stage metrics. Run the fixed set through the real pipeline with the intended resident model arrangement. Verify cached execution while disconnected and graceful failures on absent assets.

Done when output is playable, all three outputs share an utterance ID, quality errors can be traced to a stage, and combined peak memory stays within the chosen headroom. Stage-only success does not prove that combined residency fits.

If combined memory fails, benchmark explicit CPU placement, smaller ASR, supported lower precision, or staged loading. Record the changed end-to-end latency and quality. Select a stable local configuration before microphone integration.

## M6 — Push-to-talk microphone demo

Implement microphone capture, finalization on button/key release, resampling, bounded duration, headphone playback, user states, cancellation, and cleanup. Pause capture during playback. Measure endpoint/release lag and playback-start timing with its stated measurement accuracy.

Done when 30 sequential utterances run without crashes/OOM, normal conversation produces understandable Hindi, every failure is counted, and response/completion timing is reported. Use 2–6 second utterances for the provisional 3-second median response target. Publish misses honestly rather than claiming the target was achieved.

## M7 — Optional simple VAD and V1 portfolio package

VAD is optional for V1 completion; push-to-talk is the baseline. Add VAD only after M6, with configurable pre-roll, silence hangover, minimum speech, and maximum duration. Compare endpoint delay and clipped/false-trigger cases against push-to-talk.

Finish the portfolio package: actual setup guide, dependency/model revisions, reproducible benchmark commands, target-machine report, demo recording, architecture explanation, and known limitations. Update candidate decisions to accepted or rejected based on evidence.

V1 is complete when the local file and microphone flows work, Hindi quality and stability gates pass, combined memory is measured, offline operation is demonstrated, and the latency results are documented. A latency miss may require a follow-up optimization milestone; it must not disappear from the report.

## After V1

| Stage | Purpose and likely work | Gate before expanding |
|---|---|---|
| V2: local latency and conversation | Profile the bottleneck; improve endpoints, segmentation, first-audio delivery; consider Hindi -> English and a simple UI | Measured improvement against V1 without unacceptable quality/memory regression |
| Portfolio extension: voice preservation | Evaluate XTTS-v2 behind synthesis interface with a consenting speaker's reference audio | Compare intelligibility, similarity, startup, response latency, and memory; review model terms |
| Portfolio extension: audio integration | Evaluate virtual device and meeting-app routing; consider native/Rust pieces only for demonstrated needs | Stable audio routing, feedback control, and measured benefit |
| Hybrid experiment | Add an explicit user-selected cloud provider or routing policy | Separate local/cloud quality results; consent, credentials, costs, network failure behavior |
| Production investigation | Address deployment, privacy/retention, authentication, concurrency, monitoring, support, and possibly persistent storage | Product requirements, operating budget, scale and reliability targets agreed first |

Cloud/hybrid can provide different quality and latency tradeoffs; architecture flexibility does not guarantee equivalent results. Retain a local path and benchmark each mode independently. Production decisions should follow actual requirements rather than bringing infrastructure into V1.
