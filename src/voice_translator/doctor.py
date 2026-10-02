from dataclasses import asdict
from importlib.util import find_spec
import json
import shutil
from .metrics import environment


def doctor(config):
    report = environment()
    report["configuration"] = config.metadata()
    report["providers"] = {}
    for stage, module in (("asr", "faster_whisper"), ("translation", "transformers"), ("tts", "kokoro")):
        pc = getattr(config, stage)
        assets = {"status": "missing", "revision": None, "missing_files": [], "checksums": "checked only at provider load"}
        try:
            receipt = json.loads((pc.path / "provisioned.json").read_text(encoding="utf-8"))
            missing = [name for name in receipt["files"] if not (pc.path / name).is_file()]
            reviewed = stage != "translation" or receipt.get("custom_code_reviewed") is True
            matches = receipt.get("model_id") == pc.model_id and receipt.get("stage") == stage
            assets.update(status="present_runtime_unverified" if not missing and reviewed and matches else "incomplete_or_unreviewed",
                          revision=receipt.get("revision"), missing_files=missing)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        dependencies = {name: find_spec(name) is not None for name in
                        ((module, "ctranslate2") if stage == "asr" else (module, "torch", "IndicTransToolkit") if stage == "translation" else (module, "torch", "espeakng_loader"))}
        report["providers"][stage] = {"implemented": True, "fake": pc.provider == "fake",
            "dependency_installed": pc.provider == "fake" or all(dependencies.values()), "dependencies": dependencies,
            "provisioning_receipt": (pc.path / "provisioned.json").is_file(),
            "path": str(pc.path), "device": pc.device, "precision": pc.precision,
            "readiness": "fake_only" if pc.provider == "fake" else assets,
            "native_library_path_exists": pc.native_library_path.is_dir() if pc.native_library_path else None}
    report["espeak_ng_executable"] = shutil.which("espeak-ng")
    report["cuda_runtime"] = "Driver inventory only; provider load is required to verify native runtime compatibility"
    try:
        import sounddevice as sd
        report["audio_devices"] = list(sd.query_devices())
        report["default_audio_devices"] = list(sd.default.device)
    except Exception as exc:
        report["audio_devices"] = []
        report["audio_error"] = type(exc).__name__
    return report

