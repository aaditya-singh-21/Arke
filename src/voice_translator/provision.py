from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from .errors import InvalidConfig, ModelUnavailable


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_assets(pc, stage):
    try:
        receipt = json.loads((pc.path / "provisioned.json").read_text(encoding="utf-8"))
        if receipt["model_id"] != pc.model_id or receipt["stage"] != stage:
            raise ValueError()
        if not re.fullmatch(r"[a-f0-9]{40}", receipt["revision"]):
            raise ValueError()
        if re.fullmatch(r"[a-f0-9]{40}", pc.revision) and pc.revision != receipt["revision"]:
            raise ValueError()
        if stage == "translation" and receipt.get("custom_code_reviewed") is not True:
            raise ModelUnavailable("IndicTrans2 custom code must be reviewed at its pinned revision before loading")
        if not receipt["files"]:
            raise ValueError()
        for relative, expected in receipt["files"].items():
            path = (pc.path / relative).resolve()
            if not path.is_relative_to(pc.path.resolve()) or not path.is_file() or sha256(path) != expected:
                raise ModelUnavailable(f"{stage}: missing or changed provisioned asset: {Path(relative).name}")
        return receipt
    except ModelUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ModelUnavailable(f"{stage}: assets not provisioned; run setup-models --stage {stage}") from exc


def setup_models(config, stage, accept_reviewed_code=False):
    pc = getattr(config, stage)
    if pc.provider == "fake":
        return {"stage": stage, "fake": True, "downloads": 0}
    try:
        from huggingface_hub import HfApi, snapshot_download
        from huggingface_hub.errors import GatedRepoError
    except ImportError as exc:
        raise ModelUnavailable(f"Install the {stage} optional dependencies before provisioning") from exc
    pc.path.mkdir(parents=True, exist_ok=True)
    # Resume interrupted setup at the same revision; never silently replace a pinned receipt.
    receipt_path = pc.path / "provisioned.json"
    previous = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
    if previous:
        if previous["model_id"] != pc.model_id or (re.fullmatch(r"[a-f0-9]{40}", pc.revision) and pc.revision != previous["revision"]):
            raise InvalidConfig("Provision into a new model path when changing model ID or revision")
        revision = previous["revision"]
    else:
        try:
            revision = HfApi().model_info(pc.model_id, revision=pc.revision).sha
        except GatedRepoError as exc:
            raise ModelUnavailable("Accept IndicTrans2 repository conditions using your own Hugging Face account, then set HF_TOKEN outside Git") from exc
    if not revision or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ModelUnavailable("Could not resolve an immutable model revision")
    patterns = {"asr": ["model.bin", "config.json", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"],
        "translation": ["*.json", "*.py", "*.spm", "*.model", "*.txt", "*.safetensors", "pytorch_model*.bin"],
        "tts": ["config.json", "kokoro-v1_0.pth", f"voices/{pc.voice}.pt"]}[stage]
    try:
        snapshot_download(pc.model_id, revision=revision, local_dir=str(pc.path), allow_patterns=patterns,
                          max_workers=1)
    except GatedRepoError as exc:
        raise ModelUnavailable("Model access denied: accept repository conditions and supply HF_TOKEN for setup only") from exc
    files = {str(p.relative_to(pc.path)).replace("\\", "/"): sha256(p)
             for p in pc.path.rglob("*") if p.is_file() and ".cache" not in p.parts and p.name != "provisioned.json"}
    reviewed = stage != "translation" or accept_reviewed_code or bool(previous and previous.get("custom_code_reviewed"))
    receipt = {"stage": stage, "model_id": pc.model_id, "revision": revision, "requested_revision": pc.revision,
               "files": files, "custom_code_reviewed": reviewed,
               "provisioned_utc": datetime.now(timezone.utc).isoformat()}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"stage": stage, "revision": revision, "files": len(files), "path": str(pc.path),
            "custom_code_reviewed": reviewed, "ready": reviewed,
            "next_step": "Install/verify native runtimes and benchmark in isolation" if reviewed else
            "Review downloaded *.py at this revision; rerun setup-models --accept-reviewed-code after review"}

