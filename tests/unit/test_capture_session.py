from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import sys
import numpy as np
import pytest
from voice_translator.audio import capture
from voice_translator.config import load_config
from voice_translator.errors import Cancelled, DeviceError
from voice_translator.evaluation import read_jsonl
from voice_translator.providers.factory import create_pipeline
from voice_translator.types import AudioBuffer, Cancellation

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('cancel', [False, True])
def test_capture_limit_id_and_cancel_close_stream(monkeypatch, cancel):
    cfg = load_config(ROOT/'configs/fake.toml')
    cfg = replace(cfg, max_audio_seconds=.1, audio=replace(cfg.audio, sample_rate=16000))
    token = Cancellation()
    keys = SimpleNamespace(space=Event(), error=None, release_time=None)
    keys.space.set()
    closed = []
    class Stream:
        def __init__(self, **options):
            self.callback = options['callback']
        def __enter__(self):
            if cancel:
                token.cancel()
            else:
                self.callback(np.full((1700, 1), .1, dtype=np.float32), 1700, None, None)
            return self
        def __exit__(self, *args):
            closed.append(True)
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(InputStream=Stream, PortAudioError=OSError))
    if cancel:
        with pytest.raises(Cancelled):
            capture.capture_once(cfg, keys, token, 'capture-id')
    else:
        audio, _ = capture.capture_once(cfg, keys, token, 'capture-id')
        assert audio.duration == .1 and audio.utterance_id == 'capture-id'
        assert audio.sample_rate == 16000
    assert closed == [True]


def test_session_discards_cancelled_inference_and_closes_providers(monkeypatch, tmp_path):
    cfg = load_config(ROOT/'configs/fake.toml')
    pipeline = create_pipeline(cfg)
    class Keys:
        def __init__(self):
            self.space = SimpleNamespace(is_set=lambda: False, wait=lambda timeout: True)
            self.quit = Event()
            self.error = None
            self.token = None
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    keys = Keys()
    transcribe = pipeline.asr.transcribe
    def cancelling_asr(*args):
        result = transcribe(*args)
        keys.token.cancel()
        return result
    pipeline.asr.transcribe = cancelling_asr
    class Memory:
        def __init__(self, interval):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def summary(self):
            return {'memory_gate': 'unverified'}
    captured_ids = []
    def input_audio(config, keys, token, uid):
        captured_ids.append(uid)
        return AudioBuffer(np.full(16000, .1, dtype=np.float32), 16000, uid, 1., 2.), 2.
    monkeypatch.setattr(capture, 'ConsoleKeys', lambda: keys)
    monkeypatch.setattr(capture, 'MemorySampler', Memory)
    monkeypatch.setattr(capture, 'environment', lambda: {})
    monkeypatch.setattr(capture, 'create_pipeline', lambda config: pipeline)
    monkeypatch.setattr(capture, 'capture_once', input_audio)
    monkeypatch.setattr(capture, 'play', lambda *args: pytest.fail('Cancelled audio must never play'))
    path = tmp_path/'microphone.jsonl'
    assert capture.listen(cfg, path, turns=1) == 1
    rows = read_jsonl(path)
    assert rows[1]['status'] == 'cancelled'
    assert rows[1]['utterance_id'] == captured_ids[0]
    assert rows[-1]['stability_gate'] == 'not_applicable_fake'
    assert all(not provider.loaded for _, provider in pipeline.providers())


@pytest.mark.parametrize('gate', ['fail', 'unverified'])
def test_real_session_rejects_failed_or_missing_memory_gate(monkeypatch, tmp_path, gate):
    cfg = load_config(ROOT/'configs/fake.toml')
    pipeline = create_pipeline(cfg)
    # Mark a real configuration while injecting model-free providers for this check.
    cfg = replace(cfg, asr=replace(cfg.asr, provider='faster-whisper'))
    class Keys:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    class Memory:
        def __init__(self, interval):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def sample(self):
            pass
        def summary(self):
            return {'memory_gate': gate}
    monkeypatch.setattr(capture, 'ConsoleKeys', Keys)
    monkeypatch.setattr(capture, 'MemorySampler', Memory)
    monkeypatch.setattr(capture, 'environment', lambda: {})
    monkeypatch.setattr(capture, 'create_pipeline', lambda config: pipeline)
    monkeypatch.setattr(capture, 'capture_once', lambda *args: pytest.fail('Memory gate must precede capture'))
    path = tmp_path/'memory-session.jsonl'
    with pytest.raises(DeviceError, match='Resident-model memory gate'):
        capture.listen(cfg, path, turns=30)
    rows = read_jsonl(path)
    assert rows[1]['type'] == 'resident_memory_check'
    assert rows[1]['memory']['memory_gate'] == gate
    assert rows[-1]['type'] == 'session_error' and rows[-1]['attempted'] == 0
    assert all(not provider.loaded for _, provider in pipeline.providers())
