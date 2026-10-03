# V1 evaluation and human review

Create a local draft set:

```powershell
.\.venv\Scripts\python.exe -m voice_translator eval-init --manifest data/eval/manifest.jsonl
```

The command authors 30 draft English/Hindi pairs and a review template. It does not assert that Hindi references are correct. The whole evaluation directory is ignored. Obtain permission before sharing recordings or selecting any fixture for Git.

## Prepare human reference data

Record each prompt as a 2–6 second mono/stereo WAV at a real recorded sample rate. Save it at the case's relative `audio_path`. Capture ordinary/Indian English speech and mild noise according to tags. Record the actual WAV duration in `source_duration`; use `audio_kind="human_recording"`. A reviewer must verify the spoken English transcript and approve/correct Hindi, then set `english_reviewed=true` and `hindi_reviewed=true`. Preserve case IDs across comparisons. Fix the set before measuring; do not tune on and silently replace failing cases.

```powershell
.\.venv\Scripts\python.exe -m voice_translator eval-validate --manifest data/eval/manifest.jsonl --stage pipeline
```

The validator requires exactly 30 unique cases, references, review declarations, category tags, and matching 2–6 second audio durations for ASR/composed runs. Translation and TTS do not require audio files, so their independent reference-text measurements can proceed first. `--allow-unreviewed` permits diagnostic runs and explicitly prevents acceptance claims. It never fabricates review scores.

The optional local SAPI script prepares synthetic English speech solely to diagnose ASR loading/timing. It does not produce accent/noise validation data:

```powershell
.\scripts\make-asr-diagnostic.ps1 -OutputDirectory data/eval/asr-diagnostic
```

## Run the fixed protocol

Each invocation is a new Python process. Use an empty output directory. Keep power mode, background apps, generation options, devices, and model placement fixed; describe them with `--baseline-note` and retain the doctor inventory.

For measured launch-to-ready startup on Windows, invoke `scripts/benchmark-process.ps1` with `-Stage`, `-Config`, `-Manifest`, and `-Output`; add `-AllowUnreviewed` only for diagnostics. It launches one benchmark Python process and adds the parent monotonic launch boundary. Example: `.\scripts\benchmark-process.ps1 -Stage asr -Config configs/v1.toml -Manifest data/eval/manifest.jsonl -Output artifacts/asr-startup`.

```powershell
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage asr --config configs/v1.toml --manifest data/eval/manifest.jsonl --output artifacts/asr-fp16 --baseline-note 'Describe power/background/audio baseline'
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage translation --config configs/v1.toml --manifest data/eval/manifest.jsonl --output artifacts/translation-cpu
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage tts --config configs/v1.toml --manifest data/eval/manifest.jsonl --output artifacts/tts-cpu --retain-content
.\.venv\Scripts\python.exe -m voice_translator benchmark --stage pipeline --config configs/v1.toml --manifest data/eval/manifest.jsonl --output artifacts/composed --retain-content
```

Translation receives reference English, TTS receives reviewed Hindi, and the composed flow receives audio. Every run records cold load, first inference, three warm-ups, and three measured passes (90 observations). GPU stage calls complete before returning. JSONL contains every outcome; summaries exclude unsuccessful timings from linear-interpolated percentiles and show failure counts alongside them. A device/OOM failure stops further inference attempts and marks remaining scheduled cases as not run. Separate behavior records cover silence/empty/bounds and are excluded from ordinary aggregates.

WER uses NFKC normalization, case folding, punctuation replaced by spaces except apostrophes, and word edit distance. Report clean/noisy categories separately. Diagnostic synthetic/fake WER is not a human accuracy claim. Record critical detail errors regardless of average WER.

The memory sampler records RSS including native allocations, private commit, system available RAM, and total dedicated GPU memory. Its nominal interval is 100 ms; actual intervals and sampling limitations are reported. Under [ADR-014](DECISIONS.md#adr-014--advisory-ram-reserve-and-measured-session-stability), RAM below 1 GiB is an advisory warning, not an automatic acceptance failure or predicted crash. Keep full-run and phase minima, baseline notes and warning status visible. Missing telemetry leaves memory evidence unverified. New reports identify `memory_policy: adr-014-ram-advisory` and expose `ram_advisory`, `vram_gate` and `telemetry_status` separately; `memory_gate` covers VRAM/telemetry only. Historical artifacts without that policy field retain the old mandatory RAM threshold and must not be rewritten as passes. Real sessions record checks after loading and each utterance; `execution_gate` can report 30 successful turns while `stability_gate` remains pending review of memory/latency trends. `scripts/benchmark-process.ps1` records a parent Windows monotonic timestamp just before launching one Python child and measures launch-to-models-ready startup using the same Windows performance counter. Direct CLI runs measure cold load only. True acoustic response latency remains unmeasured unless external measurement is supplied; file processing timings have a separate name.

## Human quality review

Run benchmarks with `--retain-content` to explicitly save generated text/audio for review. Copy the review template into a local review file. Fill each case's `reviewer`, `translation_run_id`, `tts_run_id`, meaning score (1 incorrect to 5 complete), TTS intelligibility score (1 unintelligible to 5 easily understood), `critical_details_reviewed`, and every critical-detail error. Use TTS generated from approved Hindi for the TTS score; use independently generated translations for meaning scores. Keep a separate review for composed output to expose accumulated errors. Supply matching benchmark reports to bind scores to measured output; fake/unreviewed/incomplete runs cannot pass the review gate.

```powershell
.\.venv\Scripts\python.exe -m voice_translator evaluate --manifest data/eval/manifest.jsonl --review data/eval/review.jsonl --translation-report artifacts/translation-cpu/summary.json --tts-report artifacts/tts-cpu/summary.json
```

Incomplete references/reviews remain pending. At least 27 of the 30 cases must score ≥4 for each proposed quality gate. A reviewed report must identify the relevant benchmark run; preserve critical-detail error lists. The tool validates declarations and arithmetic, not reviewer competence or whether listening actually took place.

## Microphone and portfolio evidence

Run 30 sequential PTT utterances through headphones. Record every skip/failure, inspect English/Hindi, and ask a Hindi listener to review the actual output. Session JSONL records capture duration, finalization timing, stage times, release-to-playback onset/completion proxies, configuration, and sampled memory. A PortAudio scheduled DAC timestamp is a software proxy; Bluetooth/acoustic onset is not assumed. Manual speech-end-to-release lag needs human annotation or an external measurement. Do not present release-based proxies as measured speech-end-to-audible response.

Keep the provisional p50 ≤3 s/p95 ≤5 s goals visible, along with clean WER ≤20%, ≥90% adequacy/intelligibility ≥4/5, ≤3.5 GiB dedicated VRAM, and no crashes/OOM in 30 microphone turns. Record RAM below 1 GiB as an advisory warning. Inspect memory and latency over the session, including loading/first-call peaks, early/late turns and unexplained sustained growth; investigate actual allocation failures, hangs or material latency degradation before claiming stability. Do not replace the reserve with another arbitrary mandatory RAM cutoff. Unit tests and fast file percentiles alone do not establish microphone reliability. Disconnected real execution, human quality, combined memory telemetry, and stability are required for validated V1. Record a demo with hardware/configuration visible only after the flow is validated.

