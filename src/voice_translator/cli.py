import argparse
import json
import sys
from pathlib import Path
from contextlib import ExitStack
from .config import load_config
from .errors import TranslatorError, classify


def parser():
    root = argparse.ArgumentParser(description="Offline English -> Hindi utterance translator")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "setup-models", "benchmark", "translate-file", "listen", "eval-init", "eval-validate", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", default="configs/v1.toml")
        sub.add_argument("--debug", action="store_true")
        if name == "doctor":
            sub.add_argument("--output", type=Path)
        if name == "setup-models":
            sub.add_argument("--stage", choices=("asr", "translation", "tts"), required=True)
            sub.add_argument("--accept-reviewed-code", action="store_true", help="After reviewing pinned IndicTrans2 model code")
        if name == "translate-file":
            sub.add_argument("--input", type=Path, required=True)
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--play", action="store_true")
            sub.add_argument("--metrics", type=Path)
        if name == "listen":
            sub.add_argument("--mode", choices=("ptt",), default="ptt")
            sub.add_argument("--metrics", type=Path, default=Path("artifacts/microphone.jsonl"))
            sub.add_argument("--turns", type=int, default=30)
        if name == "benchmark":
            sub.add_argument("--stage", choices=("asr", "translation", "tts", "pipeline"), required=True)
            sub.add_argument("--manifest", type=Path, required=True)
            sub.add_argument("--output", type=Path, default=Path("artifacts/benchmark"))
            sub.add_argument("--allow-unreviewed", action="store_true")
            sub.add_argument("--retain-content", action="store_true")
            sub.add_argument("--baseline-note", default="unspecified")
        if name in ("eval-init", "eval-validate", "evaluate"):
            sub.add_argument("--manifest", type=Path, default=Path("data/eval/manifest.jsonl"))
        if name == "eval-init":
            sub.add_argument("--synthetic", action="store_true", help="Create test tones for fake-provider checks only")
        if name == "eval-validate":
            sub.add_argument("--stage", choices=("asr", "translation", "tts", "pipeline"), default="pipeline")
            sub.add_argument("--allow-unreviewed", action="store_true")
        if name == "evaluate":
            sub.add_argument("--review", type=Path, required=True)
            sub.add_argument("--translation-report", type=Path)
            sub.add_argument("--tts-report", type=Path)
    return root


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def main(argv=None):
    # Windows redirected consoles otherwise default to a codepage that cannot encode Hindi.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    stack = ExitStack()
    try:
        config = load_config(args.config)
        import os
        cache_root = Path(args.config).resolve().parent.parent / ".cache"
        # Keep model/module caches local without hiding the user's existing HF login token.
        os.environ["HF_HUB_CACHE"] = str(cache_root / "huggingface" / "hub")
        os.environ["HF_MODULES_CACHE"] = str(cache_root / "huggingface" / "modules")
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        if args.command != "setup-models":
            from .offline import offline_runtime
            stack.enter_context(offline_runtime())
        if args.command == "doctor":
            from .doctor import doctor
            report = doctor(config)
            emit(report)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        elif args.command == "translate-file":
            from .audio.normalize import read_wav, write_wav
            from .providers.factory import create_pipeline
            from .metrics import append_jsonl
            audio = read_wav(args.input, config.max_audio_seconds)
            pipeline = create_pipeline(config)
            try:
                pipeline.load()
                result = pipeline.run(audio)
                emit(result.record(True))
                if args.metrics:
                    append_jsonl(args.metrics, result.record(config.retain_content))
                if result.status == "cancelled":
                    return 130
                if result.status != "ok":
                    return 1
                if result.audio:
                    write_wav(args.output, result.audio)
                    if args.play:
                        from .audio.playback import play
                        emit(play(result.audio, config.audio.output_device))
            finally:
                pipeline.close()
        elif args.command == "setup-models":
            from .provision import setup_models
            emit(setup_models(config, args.stage, args.accept_reviewed_code))
        elif args.command == "listen":
            from .audio.capture import listen
            return listen(config, args.metrics, args.turns)
        elif args.command == "benchmark":
            from .benchmark import run_benchmark
            summary = run_benchmark(config, args)
            emit(summary)
            if summary.get("fatal_error") and summary["fatal_error"].get("code") == "cancelled":
                return 130
            if summary["fatal_error"] or summary["measured"]["failed_or_skipped"]:
                return 1
        else:
            from .evaluation import init_evaluation, load_manifest, score_review
            if args.command == "eval-init":
                emit(init_evaluation(args.manifest, args.synthetic))
            elif args.command == "eval-validate":
                cases = load_manifest(args.manifest, args.stage, args.allow_unreviewed)
                emit({"case_count": len(cases), "valid": True})
            else:
                emit(score_review(args.manifest, args.review, args.translation_report, args.tts_report))
        return 0
    except KeyboardInterrupt:
        print("Cancelled; audio and providers cleaned up", file=sys.stderr)
        return 130
    except Exception as exc:
        error = classify(exc, args.command)
        print(json.dumps({"error": error.code, "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 2
    finally:
        stack.close()


