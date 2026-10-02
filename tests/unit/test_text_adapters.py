from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pytest
from voice_translator.config import load_config
from voice_translator.errors import InvalidInput, UnsupportedLanguage
from voice_translator.providers.translation_indictrans2 import IndicTransTranslator
from voice_translator.providers.tts_kokoro import KokoroSynthesizer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg():
    return load_config(ROOT / "configs/v1.toml")


@pytest.fixture
def torch_stub(monkeypatch):
    stub = SimpleNamespace(inference_mode=nullcontext)
    monkeypatch.setitem(sys.modules, "torch", stub)
    return stub


class Encoding(dict):
    def to(self, device):
        self.device = device
        return self


def test_translation_vendor_tags_no_truncation_and_eos(cfg, torch_stub):
    provider = IndicTransTranslator(cfg.translation, cfg)
    calls = []
    def preprocess(text, **kwargs):
        calls.append(kwargs)
        return text
    provider.processor = SimpleNamespace(preprocess_batch=preprocess,
        postprocess_batch=lambda values, lang: ["नमस्ते"])
    length = [3]
    def tokenize(batch, **kwargs):
        assert kwargs["truncation"] is False
        return Encoding(input_ids=SimpleNamespace(shape=(1, length[0])))
    provider.tokenizer = SimpleNamespace(__call__=tokenize)
    class Tokenizer:
        __call__ = staticmethod(tokenize)
        batch_decode = staticmethod(lambda *args, **kwargs: ["नमस्ते"])
    provider.tokenizer = Tokenizer()
    generated = [0, 7, 2]
    provider.model = SimpleNamespace(generate=lambda **kwargs: [SimpleNamespace(tolist=lambda: generated)],
                                     generation_config=SimpleNamespace(eos_token_id=2))
    result = provider.translate("Hello", "test-id")
    assert calls == [{"src_lang": "eng_Latn", "tgt_lang": "hin_Deva"}]
    assert result.utterance_id == "test-id" and result.text == "नमस्ते"
    length[0] = cfg.translation.max_input_tokens + 1
    with pytest.raises(InvalidInput, match="token limit"):
        provider.translate("Hello", "test-id")
    length[0] = 3
    generated[:] = [0, 7, 7]
    with pytest.raises(InvalidInput, match="EOS"):
        provider.translate("Hello", "test-id")
    with pytest.raises(UnsupportedLanguage):
        provider.translate("Hello", "test-id", "hi", "en")


def test_tts_phoneme_and_output_bounds(cfg, torch_stub):
    provider = KokoroSynthesizer(cfg.tts, cfg)
    phonemes = ["abc"]
    provider.g2p = lambda text: (phonemes[0], None)
    provider.voice = [np.zeros(256)] * 510
    class Model:
        vocab = {c: i for i, c in enumerate("abc")}
        context_length = 512
        def __call__(self, *args):
            class Samples:
                def detach(self): return self
                def cpu(self): return self
                def numpy(self): return np.zeros(24000, dtype=np.float32)
            return Samples()
    provider.model = Model()
    result = provider.synthesize("नमस्ते", "test-id")
    assert result.duration == 1 and result.utterance_id == "test-id"
    phonemes[0] = "a" * 501
    with pytest.raises(InvalidInput, match="limit"):
        provider.synthesize("नमस्ते", "test-id")
    phonemes[0] = "z"
    with pytest.raises(InvalidInput, match="vocabulary"):
        provider.synthesize("नमस्ते", "test-id")
    with pytest.raises(InvalidInput):
        provider.synthesize("", "test-id")

