import numpy as np
from ..types import Transcript, Translation, SynthesizedAudio, ProviderMetadata
from ..errors import ModelUnavailable, UnsupportedLanguage


class FakeProvider:
    def __init__(self, config, stage):
        self.metadata = ProviderMetadata("fake", config.model_id, "1", "cpu", "float32", ("en", "hi"))
        self.loaded = False

    def load(self):
        self.loaded = True

    def close(self):
        self.loaded = False

    def check(self):
        if not self.loaded:
            raise ModelUnavailable("Fake provider must be loaded explicitly")

    def transcribe(self, audio, language="en"):
        self.check()
        if language != "en":
            raise UnsupportedLanguage("Fake ASR accepts English only")
        return Transcript(audio.utterance_id, "Hello, how are you?")

    def translate(self, text, utterance_id, source="en", target="hi"):
        self.check()
        if (source, target) != ("en", "hi"):
            raise UnsupportedLanguage("Fake translation accepts English -> Hindi only")
        return Translation(utterance_id, "नमस्ते, आप कैसे हैं?" if text.strip() else "")

    def synthesize(self, text, utterance_id, language="hi"):
        self.check()
        if language != "hi":
            raise UnsupportedLanguage("Fake TTS accepts Hindi only")
        # An intentionally obvious test tone, never represented as Hindi speech.
        samples = (0.1 * np.sin(2 * np.pi * 440 * np.arange(12000) / 24000)).astype(np.float32)
        return SynthesizedAudio(utterance_id, samples, 24000)

