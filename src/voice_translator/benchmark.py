from dataclasses import asdict
from collections import Counter
from pathlib import Path
from time import perf_counter
import hashlib
import json
from .audio.normalize import read_wav, write_wav
from .evaluation import load_manifest, word_errors
from .metrics import environment, MemorySampler, append_jsonl, distribution
from .providers.factory import create_provider, create_pipeline
from .types import utterance_id, AudioBuffer
from .errors import InvalidInput, classify


def summarize(rows):
    successful = [x for x in rows if x["status"] == "ok"]
    names = {name for x in successful for name in x["timings"]}
    wer_rows = [x["word_errors"] for x in successful if x.get("word_errors")]
    words = sum(x["reference_words"] for x in wer_rows)
    return {"attempted": len(rows), "successful": len(successful), "failed_or_skipped": len(rows) - len(successful),
        "outcomes": dict(Counter(x["status"] for x in rows)),
        "failure_codes": dict(Counter(x["error"]["code"] for x in rows if x.get("error"))),
        "timings_seconds": {name: distribution([x["timings"][name] for x in successful if name in x["timings"]]) for name in sorted(names)},
        "asr_rtf": distribution([x["asr_rtf"] for x in successful if x.get("asr_rtf") is not None]),
        "tts_rtf": distribution([x["tts_rtf"] for x in successful if x.get("tts_rtf") is not None]),
        "wer": sum(x["errors"] for x in wer_rows) / words if words else None,
        "wer_reference_words": words, "wer_cases": len(wer_rows),
        "percentile_method": "linear interpolation at (n-1)*q; only successful runs included; failures reported alongside"}


def render_summary(summary):
    def number(value, divisor=1):
        return "unmeasured" if value is None else f"{value/divisor:.3f}"
    measured, memory = summary["measured"], summary["memory"]
    lines = ["# Benchmark report", "", f"Run: `{summary['run_id']}`. Acceptance: **{summary['acceptance_status']}**.", "",
             f"Successful observations: {measured['successful']} / {measured['attempted']}; failed or skipped: {measured['failed_or_skipped']}.", "",
             f"Cold model load: {number(summary.get('cold_load_seconds'))} s; launch to ready: {number(summary.get('cold_startup_seconds'))} s.", "",
             "| Metric (seconds) | First inference | Warm p50 | Warm p95 |", "|---|---:|---:|---:|"]
    first = (summary.get("first_inference") or {}).get("timings", {})
    for name, timing in measured["timings_seconds"].items():
        lines.append(f"| {name} | {number(first.get(name))} | {number(timing['p50'])} | {number(timing['p95'])} |")
    lines.extend(["", "Successful timings only; linear-interpolated percentiles. File processing ends at audio readiness; acoustic response and manual release lag remain unmeasured.", "",
                  f"Outcomes: `{json.dumps(measured['outcomes'])}`. Failure codes: `{json.dumps(measured['failure_codes'])}`. Fatal error: `{json.dumps(summary.get('fatal_error'))}`.", "",
                  "| Memory | GiB |", "|---|---:|"])
    for label, key in (("Peak process RSS", "peak_rss_bytes"), ("Peak private memory", "peak_private_bytes"),
                       ("Total dedicated VRAM peak", "peak_total_dedicated_vram_bytes"), ("Minimum available RAM", "minimum_available_ram_bytes")):
        lines.append(f"| {label} | {number(memory.get(key), 1024**3)} |")
    interval = memory["actual_interval_seconds"]
    lines.extend(["", f"Memory gate: **{memory['memory_gate']}**. Nominal sample interval {memory['requested_interval_seconds']} s; actual p50/p95 {number(interval['p50'])}/{number(interval['p95'])} s.",
                  memory["limitations"], "", f"Quality status: **{summary['quality_status']}**."])
    if memory.get('memory_policy') == 'adr-014-ram-advisory':
        lines.extend(["", f"Memory policy: {memory['memory_policy']}; telemetry: {memory['telemetry_status']}; VRAM gate: {memory['vram_gate']}.",
                      f"RAM advisory: **{memory['ram_advisory']}** (reserve {number(memory['ram_advisory_threshold_bytes'], 1024**3)} GiB). Low RAM alone does not fail the memory gate.",
                      "A passed memory gate is not sustained-session stability or human quality acceptance."])
    if measured.get("wer") is not None:
        lines.append(f"WER: {measured['wer']:.3%}; diagnostic/fake inputs do not establish the human accuracy gate.")
    for key in ("asr_rtf", "tts_rtf"):
        values = measured[key]
        if values["count"]:
            lines.append(f"{key} p50/p95: {number(values['p50'])}/{number(values['p95'])}.")
    primary = "processing" if "processing" in measured["timings_seconds"] else next(iter(measured["timings_seconds"]), "processing")
    lines.extend(["", f"| Category | Successful / observations | {primary} p50 / p95 (s) | WER |", "|---|---:|---:|---:|"])
    for tag, category in summary["categories"].items():
        values = category["timings_seconds"].get(primary, {})
        wer = "unmeasured" if category.get("wer") is None else f"{category['wer']:.3%}"
        lines.append(f"| {tag} | {category['successful']} / {category['attempted']} | {number(values.get('p50'))} / {number(values.get('p95'))} | {wer} |")
    lines.extend(["", "Behavior edge checks are separate from ordinary observations. Full records, errors, configuration/revisions, and telemetry are in `records.jsonl`, `behavior.jsonl`, `metadata.json`, and `summary.json`."])
    return "\n".join(lines) + "\n"


def run_benchmark(config, args):
    cases = load_manifest(args.manifest, args.stage, args.allow_unreviewed)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise InvalidInput("Benchmark output directory must be empty; preserve earlier evidence")
    run_id = utterance_id()
    retain = config.retain_content or args.retain_content
    stage = args.stage
    stages = ("asr", "translation", "tts") if stage == "pipeline" else (stage,)
    fake = any(getattr(config, s).provider == "fake" for s in stages)
    if any(c.get("audio_kind") == "synthetic_tone" for c in cases) and not fake:
        raise InvalidInput("Synthetic tone manifests are for fake-provider benchmarks only")
    metadata = {"run_id": run_id, "stage": stage, "pid": __import__("os").getpid(), "environment": environment(),
        "configuration": config.metadata(), "baseline_note": args.baseline_note,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "warmup_count": 3, "passes": 3, "distinct_case_count": 30, "fake": fake,
        "diagnostic_unreviewed": args.allow_unreviewed, "content_retained": retain,
        "quality_status": "not_applicable_fake" if fake else "human_review_pending",
        "timing_boundary": "processing start -> audio ready" if stage == "pipeline" else "complete stage call",
        "audible_response_latency": None, "manual_release_lag": None,
        "wer_normalization": "NFKC, casefold, punctuation to spaces except apostrophes; word edit distance"}
    (args.output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    load_start = perf_counter()
    provider = None
    rows = []
    cold = None
    load_seconds = None
    fatal = None
    with MemorySampler(config.memory_interval_seconds) as memory:
        try:
            provider = create_pipeline(config) if stage == "pipeline" else create_provider(config, stage)
            provider.load()
            load_seconds = perf_counter() - load_start
            launch_clock = __import__("os").environ.get("ARKE_BENCHMARK_LAUNCH_CLOCK")
            cold_startup_seconds = perf_counter() - float(launch_clock) if launch_clock else None
            metadata["actual_providers"] = ([asdict(p.metadata) for _, p in provider.providers()] if stage == "pipeline" else [asdict(provider.metadata)])
            def one(case, pass_number, phase):
                uid = utterance_id()
                row = {"run_id": run_id, "utterance_id": uid, "case_id": case["case_id"], "pass": pass_number,
                       "phase": phase, "tags": case["tags"], "status": "ok", "error": None, "timings": {},
                       "source_duration": case.get("source_duration")}
                text = None
                synthesized = None
                clock = perf_counter()
                if fatal is not None:
                    row["status"] = "not_run_after_device_failure"
                    row["error"] = fatal
                    return row
                try:
                    if stage in ("asr", "pipeline"):
                        audio = read_wav(case["resolved_audio_path"], config.max_audio_seconds)
                        uid = audio.utterance_id
                        row["utterance_id"] = uid
                        # Decode/resample outside ASR stage timer.
                        clock = perf_counter()
                        if stage == "pipeline":
                            value = provider.run(audio)
                            row.update(value.record(retain))
                            row["timings"] = value.timings
                            text = value.transcript.text if value.transcript else None
                            synthesized = value.audio
                        else:
                            value = provider.transcribe(audio, "en")
                            text = value.text
                            row["timings"][stage] = perf_counter() - clock
                    elif stage == "translation":
                        value = provider.translate(case["english_reference"], uid, "en", "hi")
                        text = value.text
                        row["timings"][stage] = perf_counter() - clock
                    else:
                        synthesized = provider.synthesize(case["hindi_reference"], uid, "hi")
                        row["timings"][stage] = perf_counter() - clock
                    if stage != "pipeline" and (not text.strip() if text is not None else synthesized is None or not synthesized.samples.size):
                        row["status"] = "skipped_empty_output"
                    if synthesized:
                        if synthesized.duration > config.max_output_seconds:
                            raise InvalidInput("Synthesized output exceeds configured duration")
                        row["output_duration"] = synthesized.duration
                        row["tts_rtf"] = row["timings"].get("tts", 0) / synthesized.duration
                        if retain and phase == "measured":
                            output = args.output / "audio" / f"{case['case_id']}-pass-{pass_number}.wav"
                            write_wav(output, synthesized)
                            row["generated_audio_path"] = str(output)
                    if stage in ("asr", "pipeline") and text is not None:
                        row["word_errors"] = word_errors(case["english_reference"], text)
                        row["asr_rtf"] = row["timings"].get("asr", 0) / case["source_duration"]
                    if retain and text is not None and stage != "pipeline":
                        row["text"] = text
                except Exception as exc:
                    error = classify(exc, stage)
                    row["status"] = "failed"
                    row["error"] = {"code": error.code, "stage": stage, "message": str(error)}
                    row["timings"][stage] = perf_counter() - clock
                return row
            cold = one(cases[0], 0, "first_inference")
            append_jsonl(args.output / "records.jsonl", cold)
            if cold.get("error") and cold["error"]["code"] in ("resource_exhausted", "device_error"):
                fatal = cold["error"]
            for i in range(3):
                warmup = one(cases[i], 0, "warmup")
                append_jsonl(args.output / "records.jsonl", warmup)
                if warmup.get("error") and warmup["error"]["code"] in ("resource_exhausted", "device_error"):
                    fatal = warmup["error"]
            for pass_number in range(1, 4):
                for case in cases:
                    row = one(case, pass_number, "measured")
                    rows.append(row)
                    append_jsonl(args.output / "records.jsonl", row)
                    if row.get("error") and row["error"]["code"] in ("resource_exhausted", "device_error"):
                        fatal = row["error"]
            if fatal is None:
                behavior = behavior_checks(config, stage, provider)
                for row in behavior:
                    append_jsonl(args.output / "behavior.jsonl", row)
            # Sample even when fake inference finishes before another scheduled tick.
            memory.sample()
        except Exception as exc:
            error = classify(exc, f"load {stage}")
            fatal = {"code": error.code, "message": str(error)}
        except KeyboardInterrupt:
            fatal = {"code": "cancelled", "message": "Benchmark interrupted; partial measured records preserved"}
        finally:
            if provider:
                provider.close()
    summary = {"run_id": run_id, "fake": fake, "diagnostic_unreviewed": args.allow_unreviewed,
        "cold_load_seconds": load_seconds, "cold_startup_seconds": locals().get("cold_startup_seconds"),
        "cold_startup_note": "Use scripts/benchmark-process.ps1 for parent launch -> models-ready timing; ordinary direct calls measure load only",
        "first_inference": cold, "fatal_error": fatal, "measured": summarize(rows), "memory": memory.summary(),
        "distinct_case_count": len({x["case_id"] for x in rows}),
        "categories": {tag: summarize([x for x in rows if tag in x["tags"]]) for tag in sorted({t for c in cases for t in c["tags"]})},
        "quality_status": metadata["quality_status"], "response_latency_gate": "unmeasured; file timing is not audible response"}
    summary["behavior_results"] = locals().get("behavior", [])
    if fake or args.allow_unreviewed:
        summary["acceptance_status"] = "diagnostic_only"
    else:
        summary["acceptance_status"] = "pending_human_quality_and_microphone_validation"
    (args.output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text(render_summary(summary), encoding="utf-8")
    return summary


def behavior_checks(config, stage, provider):
    """Separate deterministic edge outcomes from ordinary speech timing aggregates."""
    import numpy as np
    rows = []
    if stage in ("asr", "pipeline"):
        items = [("empty_audio", 0), ("silence", 16000),
                 ("maximum_duration", int(config.max_audio_seconds * 16000)),
                 ("over_duration", int(config.max_audio_seconds * 16000) + 1)]
    else:
        items = [("empty_text", ""), ("over_character_bound", "x" * (config.max_text_chars + 1))]
    for name, input_value in items:
        row = {"case_id": name, "stage": stage, "utterance_id": utterance_id(), "error": None}
        try:
            if stage in ("asr", "pipeline"):
                data = np.zeros(input_value, dtype=np.float32)
                audio = AudioBuffer(data, 16000, row["utterance_id"])
                result = provider.run(audio) if stage == "pipeline" else provider.transcribe(audio)
                row["outcome"] = result.status if stage == "pipeline" else ("empty_transcript" if not result.text.strip() else "nonempty_transcript_on_silence")
                if stage == "pipeline":
                    row["error"] = result.error
            elif stage == "translation":
                provider.translate(input_value, row["utterance_id"])
                row["outcome"] = "accepted"
            else:
                provider.synthesize(input_value, row["utterance_id"])
                row["outcome"] = "accepted"
        except Exception as exc:
            error = classify(exc, stage)
            row["outcome"] = "rejected"
            row["error"] = {"code": error.code, "message": str(error)}
        rows.append(row)
        if row.get("error") and row["error"]["code"] in ("resource_exhausted", "device_error"):
            break
    return rows
