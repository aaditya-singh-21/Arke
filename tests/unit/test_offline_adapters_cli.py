from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import os
import socket
import subprocess
import sys
import numpy as np
import pytest
from voice_translator.config import load_config
from voice_translator.offline import offline_runtime
from voice_translator.provision import validate_assets, sha256
from voice_translator.errors import ModelUnavailable, InvalidInput
from voice_translator.types import AudioBuffer
from voice_translator.audio.endpoint import BoundedCapture
from voice_translator.providers.asr_faster_whisper import FasterWhisperRecognizer
from voice_translator.providers.translation_indictrans2 import IndicTransTranslator

ROOT = Path(__file__).resolve().parents[2]


def test_network_guard_restores_environment():
    original = socket.create_connection
    env = os.environ.get("HF_HUB_OFFLINE")
    with offline_runtime():
        with pytest.raises(ModelUnavailable):
            socket.create_connection(("example.com", 443))
        assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert socket.create_connection is original
    assert os.environ.get("HF_HUB_OFFLINE") == env


def test_provision_receipt_integrity_and_review(tmp_path):
    cfg = load_config(ROOT / "configs/v1.toml")
    pc = replace(cfg.translation, path=tmp_path)
    file = tmp_path / "model.bin"
    file.write_bytes(b"fixture")
    receipt = {"stage": "translation", "model_id": pc.model_id, "revision": "a" * 40,
               "custom_code_reviewed": False, "files": {"model.bin": sha256(file)}}
    path = tmp_path / "provisioned.json"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ModelUnavailable):
        validate_assets(pc, "translation")
    receipt["custom_code_reviewed"] = True
    path.write_text(json.dumps(receipt))
    assert validate_assets(pc, "translation")["revision"] == "a" * 40
    file.write_bytes(b"changed")
    with pytest.raises(ModelUnavailable):
        validate_assets(pc, "translation")


def test_capture_buffer_limit_and_overflow():
    buffer = BoundedCapture(16000, .1)
    buffer.append(np.ones((1700, 1), dtype=np.float32) * .1)
    assert buffer.limit.is_set() and len(buffer.finish()) == 1600
    buffer = BoundedCapture(16000, .1)
    buffer.append(np.zeros((10, 1), dtype=np.float32), "input overflow")
    with pytest.raises(Exception, match="Capture overflow"):
        buffer.finish()


def test_asr_consumes_lazy_segments_and_generation_bound():
    cfg = load_config(ROOT / "configs/v1.toml")
    provider = FasterWhisperRecognizer(cfg.asr, cfg)
    consumed = []
    def segments():
        for i in range(2):
            consumed.append(i)
            yield SimpleNamespace(start=i, end=i+1, text=" hello", tokens=[1], avg_logprob=-.4, no_speech_prob=.01)
    provider.model = SimpleNamespace(transcribe=lambda *args, **kwargs: (segments(), None))
    result = provider.transcribe(AudioBuffer(np.full(16000, .1, dtype=np.float32), 16000))
    assert consumed == [0, 1] and result.text == "hello hello"
    provider.pc = replace(cfg.asr, max_new_tokens=1)
    with pytest.raises(InvalidInput, match="token limit"):
        provider.transcribe(AudioBuffer(np.full(16000, .1, dtype=np.float32), 16000))


def test_package_import_is_inert_and_cli_unicode(tmp_path):
    env = dict(os.environ, PYTHONUTF8="0")
    probe = subprocess.run([sys.executable, "-c", "import sys; import voice_translator; assert 'torch' not in sys.modules; assert 'sounddevice' not in sys.modules; assert 'faster_whisper' not in sys.modules"], env=env, capture_output=True)
    assert probe.returncode == 0
    from voice_translator.audio.normalize import write_wav
    input_path = tmp_path / "input.wav"
    output = tmp_path / "hindi.wav"
    write_wav(input_path, AudioBuffer(np.full(16000, .1, dtype=np.float32), 16000))
    run = subprocess.run([sys.executable, "-m", "voice_translator", "translate-file", "--config", str(ROOT / "configs/fake.toml"), "--input", str(input_path), "--output", str(output)], capture_output=True, env=env)
    assert run.returncode == 0, run.stderr.decode("utf-8")
    report = json.loads(run.stdout.decode("utf-8"))
    assert "नमस्ते" in report["hindi"] and output.is_file()

