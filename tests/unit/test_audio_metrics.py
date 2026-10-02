from pathlib import Path
import numpy as np
import pytest
from voice_translator.audio.normalize import normalize, read_wav, write_wav
from voice_translator.types import AudioBuffer
from voice_translator.errors import InvalidInput
from voice_translator.metrics import percentile
from voice_translator.evaluation import init_evaluation, load_manifest, word_errors, score_review
from voice_translator.benchmark import summarize


def test_resample_preserves_duration_id_and_frequency(tmp_path):
    original = AudioBuffer((.2 * np.sin(2 * np.pi * 440 * np.arange(48000) / 48000)).astype(np.float32), 48000)
    result = normalize(original)
    assert result.sample_rate == 16000 and result.duration == original.duration
    assert result.utterance_id == original.utterance_id
    frequency = np.fft.rfftfreq(len(result.samples), 1 / 16000)[np.argmax(np.abs(np.fft.rfft(result.samples)))]
    assert frequency == 440
    path = tmp_path / "out.wav"
    write_wav(path, original)
    assert read_wav(path).duration == 1
    with pytest.raises(InvalidInput):
        read_wav(path, max_seconds=.5)
    path.write_text("invalid")
    with pytest.raises(InvalidInput):
        read_wav(path)


def test_percentiles_failures_and_wer():
    assert percentile([1, 2, 3, 4], .95) == pytest.approx(3.85)
    assert percentile([], .5) is None
    report = summarize([{"status": "ok", "timings": {"asr": 1}}, {"status": "failed", "timings": {"asr": 99}, "error": {"code": "oom"}}])
    assert report["attempted"] == 2 and report["timings_seconds"]["asr"]["p95"] == 1
    assert word_errors("Hello, World!", "hello world")["wer"] == 0
    assert word_errors("one two three", "one four")["errors"] == 2


def test_evaluation_never_claims_reviewed(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    init_evaluation(manifest, synthetic=True)
    assert len(load_manifest(manifest, "pipeline", True)) == 30
    with pytest.raises(InvalidInput):
        load_manifest(manifest, "pipeline")
    assert score_review(manifest, tmp_path / "review-template.jsonl")["status"] == "human_review_pending"
    with pytest.raises(InvalidInput):
        init_evaluation(manifest)

