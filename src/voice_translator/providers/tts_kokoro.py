import numpy as np
from .base import LocalProvider
from ..types import SynthesizedAudio
from ..errors import InvalidInput, UnsupportedLanguage, classify
from ..offline import offline_call


class KokoroSynthesizer(LocalProvider):
    stage = "tts"

    @offline_call
    def load(self):
        self.assets()
        try:
            torch = self.torch_setup()
            from kokoro import KModel
            from misaki.espeak import EspeakG2P
            self.model = KModel(repo_id=self.pc.model_id, config=str(self.pc.path / "config.json"),
                                model=str(self.pc.path / "kokoro-v1_0.pth")).to(self.pc.device).eval()
            self.verify_torch_placement(torch.float32)
            self.voice = torch.load(self.pc.path / "voices" / f"{self.pc.voice}.pt", weights_only=True, map_location=self.pc.device)
            self.g2p = EspeakG2P(language="hi")
        except Exception as exc:
            self.close()
            raise classify(exc, "load tts") from exc

    @offline_call
    def synthesize(self, text, utterance_id, language="hi"):
        self.require_loaded()
        if language != "hi":
            raise UnsupportedLanguage("TTS supports Hindi only")
        self.validate_text(text)
        import torch
        try:
            phonemes, _ = self.g2p(text)
            if not phonemes or len(phonemes) > self.pc.max_phonemes:
                raise InvalidInput("Hindi phonemes empty or exceed configured limit; no truncation performed")
            unknown = set(phonemes) - set(self.model.vocab)
            if unknown:
                raise InvalidInput("Phonemizer returned symbols absent from Kokoro vocabulary")
            if len(phonemes) + 2 > self.model.context_length or len(phonemes) > len(self.voice):
                raise InvalidInput("Hindi phoneme sequence exceeds model or voice bounds")
            with torch.inference_mode():
                audio = self.model(phonemes, self.voice[len(phonemes)-1], self.pc.speed)
            if self.pc.device == "cuda":
                torch.cuda.synchronize()
            samples = audio.detach().cpu().numpy().astype(np.float32).reshape(-1)
            if not len(samples) or len(samples) / 24000 > self.config.max_output_seconds:
                raise InvalidInput("TTS produced empty or oversized audio")
            return SynthesizedAudio(utterance_id, samples, 24000)
        except Exception as exc:
            raise classify(exc, "tts") from exc

    def close(self):
        self.model = self.voice = self.g2p = None

