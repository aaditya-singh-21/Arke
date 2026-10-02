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

**Status: documentation starter; implementation has not begun.**

V1 will capture a short English utterance, recognize its text, translate it into Hindi, synthesize Hindi speech, and play it through headphones. The project is intended to demonstrate sound engineering, reproducible measurements, and honest tradeoffs on an RTX 3050 with 4 GB VRAM and 8 GB system RAM.

“Real-time” in V1 means an interactive response after a completed utterance. The first version uses push-to-talk and sequential processing. It does not promise simultaneous interpretation while the speaker is still talking.

## Scope

| Area | V1 choice |
|---|---|
| Language | English -> Hindi, one direction |
| Runtime | Python; CLI first |
| Input/output | Microphone or WAV input; Hindi WAV and headphone playback |
| ASR candidate | faster-whisper with Whisper `small` |
| Translation candidate | `ai4bharat/indictrans2-en-indic-dist-200M` |
| TTS candidate | Kokoro-82M with a Hindi voice |
| Speech boundaries | Push-to-talk first; simple VAD after baseline |
| Execution | Local inference; batch size 1; one active utterance |
| Measurements | Stage timing, response latency, quality, peak RAM/VRAM, failures |

The architecture and scope are selected. The models, precision settings, and device placement remain candidates until quality and memory measurements pass on the target computer.

V1 excludes Rust, cloud inference, cloud fallback, Zoom/Meet integration, virtual microphones, databases, accounts, multi-user sessions, voice cloning, Hindi -> English, training/fine-tuning, and a production deployment. Provider interfaces leave room for later cloud/hybrid operation without implementing it now.

## Bundle contents and reading order

```text
voice-translator-v1/
├── AGENTS.md
├── README.md
└── docs/
    ├── ARCHITECTURE.md
    ├── ROADMAP.md
    └── DECISIONS.md
```

Read this file for scope, [ARCHITECTURE.md](docs/ARCHITECTURE.md) for contracts and measurements, [ROADMAP.md](docs/ROADMAP.md) for implementation order, and [DECISIONS.md](docs/DECISIONS.md) for reasons and open gates. `AGENTS.md` guides Codex work in the repository.

Extract this folder into a new repository, or copy its five files into an existing project root. The source layout in the architecture doc is a plan; this archive does not contain application code or model weights.

## Start implementation with Codex

Use this first task:

> Read AGENTS.md and the docs. Implement milestone M0 only: Python package scaffold, configuration, typed provider contracts, fake providers, a serial pipeline, and stage timing. Add the planned doctor command with clear unimplemented-provider reporting. Do not download models. Update README with only commands that actually work, and report remaining milestones.

Continue through milestones in order. Introduce one real provider at a time and collect its independent benchmark before composing the full pipeline.

## Setup and run expectations

The first implementation task should record the actual OS, CPU, Python version, NVIDIA driver, free RAM/VRAM, and compatible model runtimes. Start with Python 3.11 as a proposed baseline, subject to dependency compatibility. Windows is the initial setup path for this project; do not claim other platforms are supported until checked.

Provisioning may require internet access to install dependencies, obtain model weights, accept model repository terms, and cache tokenizer, voice, and phonemizer assets. IndicTrans2 access currently requires accepting its repository conditions. These setup steps are distinct from local inference. Normal runtime must use cached assets and must fail clearly if they are absent.

The commands below define the intended CLI. **They are specifications, not runnable commands in this bundle.** The implementation must provide them or update this documented interface before declaring a milestone complete.

```powershell
# After pyproject.toml and a compatible dependency set exist:
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# Planned CLI:
.\.venv\Scripts\python.exe -m voice_translator doctor --config configs/v1.toml
.\.venv\Scripts\python.exe -m voice_translator setup-models --config configs/v1.toml
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage asr --manifest data/eval/manifest.jsonl
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage translation --manifest data/eval/manifest.jsonl
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage tts --manifest data/eval/manifest.jsonl
.\.venv\Scripts\python.exe -m voice_translator translate-file --input data/eval/example.wav --output artifacts/example-hi.wav --config configs/v1.toml
.\.venv\Scripts\python.exe -m voice_translator listen --mode ptt --config configs/v1.toml
```

`doctor` should report environment, audio devices, model-cache readiness, and configured device/precision without downloading or loading full models. `setup-models` should perform explicit provisioning with revision tracking. Every benchmark should emit per-item records and a summary. File translation should expose English transcript and Hindi translation and save playable audio. Push-to-talk should show ready, recording, processing, playing, and error states.

Use headphones. Pause capture during output playback in V1 to prevent the system from transcribing its own synthesized speech.

## What counts as a useful V1

V1 needs an offline file flow and a microphone flow, understandable Hindi speech, inspectable text outputs, bounded resource use, and a reproducible report from the target computer. Evaluate 30 fixed short utterances, covering ordinary conversation, Indian English accents, names, numbers, dates, negation, and some background noise.

The provisional response goal is warm p50 <= 3 seconds from the end of speech to audible Hindi output for 2–6 second utterances. Report p95 even if it misses this target. Use the quality gates and measurement definitions in the architecture doc. Passing a demo once is insufficient evidence that the pipeline is stable.

Aim for total dedicated GPU usage <= 3.5 GiB and at least 1 GiB available system RAM under a documented baseline. These are planning margins, not measured capabilities. If they fail, benchmark another explicit local placement or candidate and record the tradeoff. Do not enable cloud implicitly.

## Portfolio deliverables

- A short English -> Hindi demo with the computer specifications visible.
- A documented setup and actual runnable commands.
- Stage and end-to-end benchmark results, quality review, and representative failures.
- A clear explanation of provider boundaries, memory placement, and deferred features.

No performance claims are established by this starter bundle. Primary implementation references and candidate caveats are in [DECISIONS.md](docs/DECISIONS.md).
