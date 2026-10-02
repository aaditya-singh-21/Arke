from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from voice_translator.config import load_config
from voice_translator.errors import InvalidConfig, InvalidInput, ResourceExhausted
from voice_translator.providers.factory import create_pipeline
from voice_translator.types import AudioBuffer, Cancellation, Transcript

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config(ROOT / "configs/fake.toml")


@pytest.fixture
def audio():
    return AudioBuffer(np.full(16000, .1, dtype=np.float32), 16000)


def test_serial_contracts_and_unicode(config, audio):
    pipeline = create_pipeline(config)
    pipeline.load()
    result = pipeline.run(audio)
    assert result.status == "ok"
    assert {x.utterance_id for x in (result, result.transcript, result.translation, result.audio)} == {audio.utterance_id}
    assert "नमस्ते" in result.translation.text
    assert result.audio.sample_rate == 24000
    assert set(result.timings) == {"asr", "translation", "tts", "processing"}
    assert "english" not in result.record()
    pipeline.close()


@pytest.mark.parametrize("count", [0, 16000])
def test_silence_skips_downstream(config, count):
    pipeline = create_pipeline(config)
    assert pipeline.run(AudioBuffer(np.zeros(count, dtype=np.float32), 16000)).status == "skipped_silence"


def test_cancel_before_and_during(config, audio):
    pipeline = create_pipeline(config)
    pipeline.load()
    token = Cancellation()
    token.cancel()
    assert pipeline.run(audio, token).status == "cancelled"
    token = Cancellation()
    original = pipeline.asr.transcribe
    def transcribe(*args):
        token.cancel()
        return original(*args)
    pipeline.asr.transcribe = transcribe
    result = pipeline.run(audio, token)
    assert result.status == "cancelled" and result.translation is None and result.audio is None


def test_stage_failure_and_empty_transcript(config, audio):
    pipeline = create_pipeline(config)
    pipeline.load()
    pipeline.asr.transcribe = lambda *args: Transcript(audio.utterance_id, "")
    assert pipeline.run(audio).status == "skipped_empty_asr"
    def fail(*args):
        raise MemoryError()
    pipeline.asr.transcribe = fail
    result = pipeline.run(audio)
    assert result.status == "failed" and result.error["code"] == "resource_exhausted"
    assert "asr" in result.timings
    assert not pipeline.lock.locked()


def test_id_and_input_bounds(config, audio):
    pipeline = create_pipeline(config)
    pipeline.load()
    pipeline.asr.transcribe = lambda *args: Transcript("wrong", "hello")
    assert pipeline.run(audio).status == "failed"
    assert pipeline.run(replace(audio, sample_rate=8000)).status == "failed"
    pipeline.lock.acquire()
    with pytest.raises(InvalidInput):
        pipeline.run(audio)
    pipeline.lock.release()


@pytest.mark.parametrize("body", ['offline = false', 'target_language = "en"', 'max_audio_seconds = 100', 'max_text_chars = 0', 'retain_content = "yes"'])
def test_invalid_config(tmp_path, body):
    original = (ROOT / "configs/fake.toml").read_text()
    key = body.split("=")[0].strip()
    import re
    original = re.sub(rf"^{key} = .*", body, original, flags=re.M)
    path = tmp_path / "bad.toml"
    path.write_text(original)
    with pytest.raises(InvalidConfig):
        load_config(path)


def test_invalid_samples():
    for data in (np.array([np.nan], dtype=np.float32), np.array([2], dtype=np.float32), np.ones((2, 2), dtype=np.float32)):
        with pytest.raises(InvalidInput):
            AudioBuffer(data, 16000)


def test_load_failure_rolls_back_and_cleanup_errors_are_visible(config):
    pipeline = create_pipeline(config)
    def fail_load():
        pipeline.translator.loaded = True
        raise MemoryError()
    pipeline.translator.load = fail_load
    with pytest.raises(ResourceExhausted):
        pipeline.load()
    assert all(not provider.loaded for _, provider in pipeline.providers())
    def fail_close():
        raise RuntimeError('fixture cleanup error')
    pipeline.tts.close = fail_close
    with pytest.warns(RuntimeWarning, match='Provider cleanup failed'):
        errors = pipeline.close()
    assert errors == [{'stage': 'tts', 'error': 'provider_error'}]

