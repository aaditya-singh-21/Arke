# Instructions for coding agents

## Purpose and current state

Build a portfolio-first, local-first voice translator for an RTX 3050 with 4 GB VRAM and a computer with 8 GB RAM. V1 translates one speaker's short English utterance into Hindi speech through headphones.

This starter bundle contains documentation only. Source code, dependencies, model downloads, commands, and benchmark results still need to be implemented. Never describe planned functionality as working functionality.

Read `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and `docs/DECISIONS.md` before implementing. Follow the current human request when it changes these plans, and update the affected docs.

## V1 boundaries

- Use Python for the application and model adapters. Begin with a CLI.
- Support English -> Hindi only, one utterance at a time.
- Start with push-to-talk. Add simple voice activity detection (VAD: identifying speech versus silence) only after the manual flow works.
- Run inference locally after explicit model provisioning. No cloud fallback or outbound inference requests.
- Evaluate faster-whisper with Whisper `small`, IndicTrans2 En-Indic distilled `200M`, and lightweight Hindi TTS with Kokoro-82M as the initial candidates.
- Keep model-specific code behind provider interfaces. Candidate selection is provisional until measured on the target computer.
- Defer Rust, Zoom/Meet integration, virtual audio devices, databases, accounts, servers, multi-user support, voice cloning, and continuous simultaneous translation.

## Implementation discipline

1. Implement the next incomplete milestone in `docs/ROADMAP.md`; keep each change reviewable.
2. Begin with types, configuration, fake providers, and measurement plumbing. Avoid downloading every model in the first task.
3. Benchmark ASR, translation, and TTS separately before connecting real providers. Test translation with correct English text and TTS with reviewed Hindi text to isolate quality problems.
4. Start with batch size 1 and serial processing. Keep audio buffers and generated tokens bounded.
5. Make device, precision, model path/revision, and decoding options explicit. Record the actual choices; do not silently switch models or devices.
6. Inspect available CPU, driver/runtime compatibility, Python support, and free RAM/VRAM before selecting package versions. Pin the combination that actually runs. Do not install arbitrary latest versions and claim compatibility.
7. Keep vendor preprocessing, language tags, tokenization, and output normalization inside adapters.
8. Importing the package must not load models, capture audio, or download assets. Separate model setup from offline execution.
9. Fail clearly on missing assets, unsupported language, invalid configuration, device errors, and out-of-memory errors. A CPU fallback must be explicitly configured and logged.
10. Update the README whenever a command becomes available. Label unimplemented commands as planned until then.

## Code organization

Use the proposed `src/voice_translator/` layout in the architecture doc. Keep pipeline orchestration independent from provider libraries. Use typed data classes and Python protocols or abstract classes for the three provider contracts. Prefer simple functions and a small number of modules over frameworks and plugin discovery.

Use monotonic clocks for elapsed time. Every utterance needs a unique ID across capture, ASR, translation, synthesis, playback, and metrics. Preserve Unicode Hindi text. Do not treat ASR confidence as a calibrated probability.

Keep model caches, virtual environments, credentials, recordings, generated audio, and benchmark artifacts out of Git. Commit only small, intentionally selected fixtures with permission to share them. Logging raw audio and text is opt-in; performance metadata may be recorded without content.

## Validation and handoff

When implementation validation is requested, use fast deterministic checks for contracts, configuration, empty/silent input, cancellation, bounds, and stage failures. Real model checks are separate, require provisioned assets, and must never trigger downloads during ordinary unit checks. Use a fixed evaluation set and the protocol in the architecture doc for hardware benchmarks.

Do not invent timing, quality, or memory results. Distinguish measured values, provisional targets, and estimates. Include CTranslate2/native allocations in memory measurement; PyTorch counters alone are insufficient.

At each milestone, report what works, exact commands available, checks performed, measured evidence if any, and remaining limitations. If a candidate fails the quality or memory gate, document the result in `docs/DECISIONS.md` before changing the default. Continue reversible work within scope; ask the user only when a decision changes scope, requires their credentials or external terms acceptance, or introduces spending.
