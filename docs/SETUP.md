# Windows V1 setup

The application code and deterministic harness are implemented. Real-model and human acceptance status is recorded in [VALIDATION.md](VALIDATION.md). Candidate dependencies are not a claim that every adapter has passed on Windows.

## Python and basic checks

Run PowerShell in the project root. `uv` is required for the bootstrap script. It places Python 3.11, its cache, and the virtual environment inside ignored project directories.

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m voice_translator doctor --config configs/v1.toml --output artifacts/doctor.json
```

The doctor inventories CPU, Windows, Python/packages, system RAM, disk, GPU/driver, audio devices, configuration, and provisioning receipts. It does not load models or verify native runtime compatibility. Device IDs can change after reconnecting headphones; select current IDs in the TOML. Use headphones and choose a compatible capture rate. Runtime never switches provider/device implicitly.

`requirements/windows-tested.txt` records every installed package version from this Windows validation environment, including the explicit CUDA wheel. To recreate its Python package combination after making a 3.11 environment:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements/windows-tested.txt --extra-index-url https://download.pytorch.org/whl/cu126
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
```

This records exact versions, not wheel hashes or system compiler/driver installations. The baseline uses Python 3.11.15 and toolkit source compilation; models are provisioned separately. The incremental bootstrap installs only each requested adapter.

## Verify the plumbing without models

```powershell
.\.venv\Scripts\python.exe -m voice_translator eval-init --config configs/fake.toml --manifest data/eval/synthetic/manifest.jsonl --synthetic
.\.venv\Scripts\python.exe -m voice_translator benchmark --config configs/fake.toml --stage pipeline --manifest data/eval/synthetic/manifest.jsonl --allow-unreviewed --output artifacts/fake-run
.\.venv\Scripts\python.exe -m voice_translator translate-file --config configs/fake.toml --input data/eval/synthetic/audio/case-01.wav --output artifacts/fake-hi.wav
```

Use a new manifest/output directory for each run; the commands refuse to overwrite evaluation references or benchmark evidence. Fake TTS produces a 440 Hz test tone. It is not Hindi speech. Fake outputs and synthetic input cannot pass quality gates.

## Install and provision one provider at a time

All network use belongs to these explicit installation/setup steps. No model weight enters Git. `setup-models --stage` downloads just one configured model, resolves the requested setup revision to an immutable commit, and writes local checksums to `models/<stage>/provisioned.json`. Reusing that path keeps its pinned revision; changing models requires a new path. Runtime verifies the receipt and hashes before loading.

### ASR

```powershell
.\scripts\bootstrap.ps1 -Asr
.\.venv\Scripts\python.exe -m voice_translator setup-models --stage asr --config configs/v1.toml
```

Candidate packages are faster-whisper 1.2.1, CTranslate2 4.6.0, and setuptools 75.8.2. The latter supplies `pkg_resources` required by this CTranslate2 release. GPU inference requires CUDA 12 cuBLAS and cuDNN 9 compatible native libraries; `nvidia-smi` reports driver capability, not installed runtime readiness. Follow [faster-whisper requirements](https://github.com/SYSTRAN/faster-whisper#requirements).

The bootstrap for translation/TTS installs an explicit PyTorch 2.7.1 CUDA 12.6 wheel. Its `torch/lib` native libraries can be selected through `asr.native_library_path` in configuration once verified. The adapter adds only that configured directory to Windows DLL search. Do not copy arbitrary DLLs into Windows system directories.

For GPU ASR without installing translation/TTS packages, install the explicit native runtime wheel:

```powershell
uv pip install --python .venv/Scripts/python.exe 'torch==2.7.1' --index-url https://download.pytorch.org/whl/cu126
```

This wheel is large (approximately 2.5 GiB download in this setup). Alternatively provide a verified CUDA 12/cuDNN 9 runtime directory explicitly; that alternative was not tested here.

Compare `configs/v1.toml` (GPU FP16), `configs/asr-gpu-int8.toml` (GPU INT8/FP16), and `configs/asr-cpu.toml` (CPU `int8_float32`). The generic `int8` request resolved to `int8_float32` during the CPU load probe, so the comparison config now specifies that actual compute type. CPU execution is an explicit diagnostic, not an automatic fallback.

### Translation

```powershell
.\scripts\bootstrap.ps1 -Translation
# Official processor compatibility probe; upstream does not advertise Windows support:
uv pip install --python .venv/Scripts/python.exe 'indictranstoolkit==1.1.1'
```

Candidate runtime: torch 2.7.1 CUDA 12.6, transformers 4.51.3, sentencepiece 0.2.0, sacremoses 0.1.1, and official IndicTransToolkit 1.1.1. The adapter uses eager attention, explicit CPU FP32 by default, `eng_Latn` → `hin_Deva`, and bounded generation with no truncation. The official toolkit documents Linux/macOS prerequisites; its Cython extension built successfully on this Windows machine. Other Windows machines need a compatible C++ build toolchain when no wheel is available. The translation extra now includes the tested version. See the [official toolkit](https://github.com/VarunGumma/IndicTransToolkit); a failed install must remain a reported prerequisite, not a replacement hand-written processor.

Accept the conditions at the [IndicTrans2 model repository](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M) using your own account. Set an authorized `HF_TOKEN` in the provisioning shell only; never paste it into a report, config, or Git.

```powershell
.\.venv\Scripts\python.exe -m voice_translator setup-models --stage translation --config configs/v1.toml
# Review the downloaded Python model/tokenizer code at the receipt's pinned revision.
# After review:
.\.venv\Scripts\python.exe -m voice_translator setup-models --stage translation --config configs/v1.toml --accept-reviewed-code
```

The adapter refuses unreviewed custom code and uses local paths plus `local_files_only=True`. Access acceptance is a human action. A missing processor, denied model access, or absent weights prevents translation validation.

### Hindi TTS

```powershell
.\scripts\bootstrap.ps1 -Tts
.\.venv\Scripts\python.exe -m voice_translator setup-models --stage tts --config configs/v1.toml
```

Candidate Kokoro 0.9.4 uses local Kokoro-82M weights/config and the configured stock Hindi voice (`hf_alpha` initially). Hindi phonemization uses Misaki's espeak-ng path. Its `espeakng-loader` dependency bundles the library/data; the standalone `espeak-ng` executable being absent does not by itself prove the phonemizer is missing. Verify phonemization during provider load. Hindi synthesis exports mono 24 kHz. Long phoneme strings and unknown model symbols fail rather than being dropped or truncated.

## Run with provisioned assets

```powershell
.\.venv\Scripts\python.exe -m voice_translator translate-file --input data/eval/audio/case-01.wav --output artifacts/example-hi.wav --config configs/v1.toml --metrics artifacts/file.jsonl
.\.venv\Scripts\python.exe -m voice_translator listen --mode ptt --config configs/v1.toml --turns 30 --metrics artifacts/microphone.jsonl
```

File translation prints English/Hindi to the console and saves the requested WAV. `--play` also plays it. Transcript/audio retention in metrics is opt-in via `retain_content=true`; benchmark retention also has `--retain-content`. Requested file output is itself explicit audio retention.

PTT requires a focused Windows console that supplies key release events, such as PowerShell in Windows Terminal. Hold Space to record, release to translate, Esc to cancel, and Q to quit. Capture finalizes at 15 seconds; there is no queued utterance. Capture is closed before inference/playback. Cancellation cannot preempt a running native model call, but checks between stages suppress stale audio; playback cancellation stops the output stream. Close the program with Ctrl+C to clean up.

`listen` implements [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability). It checks memory after model loading and each utterance; RAM below the advisory 1 GiB reserve produces one visible warning and does not by itself block capture. Dedicated VRAM above 3.5 GiB or incomplete telemetry ends the session and closes providers. Actual device/OOM failures remain explicit and stop further attempts; no model/device fallback occurs. No new option or bypass is required: use the existing `listen --mode ptt` command with an explicit configuration. Session metrics identify the policy, record memory checks and separate successful execution from pending memory/latency trend review. Fake sessions cannot pass the real stability gate. Human quality, microphone and disconnected-operation validation remain pending.

Exit codes: 0 success, 1 completed flow/benchmark with failed or skipped measured cases, 2 setup/configuration/runtime command error, 130 interruption. `--debug` exposes diagnostic tracebacks only when requested.

## Offline verification

After provisioning, run the opt-in provider checks in separate fresh processes:

```powershell
$env:ARKE_MODEL_CHECKS = '1'
foreach ($stage in @('asr', 'translation', 'tts')) {
    .\.venv\Scripts\python.exe -m pytest -q tests/integration/test_provisioned_models.py -k $stage
    if ($LASTEXITCODE -ne 0) { throw "Local provider check failed: $stage" }
}
Remove-Item Env:ARKE_MODEL_CHECKS
```

These checks use local model/module caches and never provision missing assets. Each stage closes its provider before exiting.

Inference enables Hugging Face offline flags and blocks Python socket connection/DNS APIs, including calls made through custom model code. Explicit local asset paths are used for weights, tokenizer, and voice. This guard helps expose accidental downloads; it is not an OS firewall. Disconnect networking after provisioning and run both file and microphone flows for the final offline gate. Do not count fake-provider runs as proof that all real model assets are complete.

Benchmark/review commands and the baseline controls are in [EVALUATION.md](EVALUATION.md). Tested versions and current failures belong in [VALIDATION.md](VALIDATION.md). No cloud inference, VAD, or later-stage integration is included.

