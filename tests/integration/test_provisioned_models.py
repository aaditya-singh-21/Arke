"""Opt-in checks never provision models. ARKE_MODEL_CHECKS=1 requires local assets."""
import os
from pathlib import Path
import numpy as np
import pytest
from voice_translator.config import load_config
from voice_translator.providers.factory import create_provider
from voice_translator.offline import offline_runtime
from voice_translator.types import AudioBuffer, utterance_id

pytestmark = [pytest.mark.models, pytest.mark.skipif(os.environ.get("ARKE_MODEL_CHECKS") != "1", reason="requires opt-in provisioned model assets")]


@pytest.mark.parametrize("stage", ["asr", "translation", "tts"])
def test_provisioned_provider_offline(stage, monkeypatch):
    config = load_config(os.environ.get("ARKE_MODEL_CONFIG", "configs/v1.toml"))
    cache = Path(__file__).resolve().parents[2]/'.cache'/'huggingface'
    monkeypatch.setenv('HF_HUB_CACHE', str(cache/'hub'))
    monkeypatch.setenv('HF_MODULES_CACHE', str(cache/'modules'))
    with offline_runtime():
        provider = create_provider(config, stage)
        try:
            provider.load()
            if stage == "asr":
                result = provider.transcribe(AudioBuffer(np.zeros(32000, dtype=np.float32), 16000))
                assert result.language == "en"
            elif stage == "translation":
                result = provider.translate("Hello, how are you?", utterance_id())
                assert result.target_language == "hi" and result.text
            else:
                result = provider.synthesize("नमस्ते, आप कैसे हैं?", utterance_id())
                assert result.sample_rate == 24000 and result.samples.size
        finally:
            provider.close()

