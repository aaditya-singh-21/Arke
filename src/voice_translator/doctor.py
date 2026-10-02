from dataclasses import asdict
from importlib.util import find_spec
import shutil
from .metrics import environment


def doctor(config):
    report = environment()
    report["configuration"] = config.metadata()
    report["providers"] = {}
    for stage, module in (("asr", "faster_whisper"), ("translation", "transformers"), ("tts", "kokoro")):
        pc = getattr(config, stage)
        report["providers"][stage] = {"implemented": True, "fake": pc.provider == "fake",
            "dependency_installed": pc.provider == "fake" or find_spec(module) is not None,
            "provisioning_receipt": (pc.path / "provisioned.json").is_file(),
            "path": str(pc.path), "device": pc.device, "precision": pc.precision,
            "readiness": "fake_only" if pc.provider == "fake" else "not_loaded; use provisioned-model checks"}
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

