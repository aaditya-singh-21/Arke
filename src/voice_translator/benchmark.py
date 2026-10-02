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
from .types import utterance_id
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
            metadata["actual_providers"] = ([asdict(p.metadata) for _, p in provider.providers()] if stage == "pipeline" else [asdict(provider.metadata)])
            def one(case, pass_number, phase):
                uid = utterance_id()
                row = {"run_id": run_id, "utterance_id": uid, "case_id": case["case_id"], "pass": pass_number,
                       "phase": phase, "tags": case["tags"], "status": "ok", "error": None, "timings": {},
                       "source_duration": case.get("source_duration")}
                text = None
                synthesized = None
                clock = perf_counter()
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
            for i in range(3):
                append_jsonl(args.output / "records.jsonl", one(cases[i], 0, "warmup"))
            for pass_number in range(1, 4):
                for case in cases:
                    row = one(case, pass_number, "measured")
                    rows.append(row)
                    append_jsonl(args.output / "records.jsonl", row)
            # Sample even when fake inference finishes before another scheduled tick.
            memory.sample()
        except Exception as exc:
            error = classify(exc, f"load {stage}")
            fatal = {"code": error.code, "message": str(error)}
        finally:
            if provider:
                provider.close()
    summary = {"run_id": run_id, "fake": fake, "diagnostic_unreviewed": args.allow_unreviewed,
        "cold_load_seconds": load_seconds, "cold_startup_seconds": None,
        "cold_startup_note": "Cold load measured; full interpreter launch-to-ready is not instrumented",
        "first_inference": cold, "fatal_error": fatal, "measured": summarize(rows), "memory": memory.summary(),
        "distinct_case_count": len({x["case_id"] for x in rows}),
        "categories": {tag: summarize([x for x in rows if tag in x["tags"]]) for tag in sorted({t for c in cases for t in c["tags"]})},
        "quality_status": metadata["quality_status"], "response_latency_gate": "unmeasured; file timing is not audible response"}
    if fake or args.allow_unreviewed:
        summary["acceptance_status"] = "diagnostic_only"
    else:
        summary["acceptance_status"] = "pending_human_quality_and_microphone_validation"
    (args.output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text("# Benchmark report\n\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    return summary

