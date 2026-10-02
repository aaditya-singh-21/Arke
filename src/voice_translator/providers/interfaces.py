from typing import Protocol
from ..types import AudioBuffer, Transcript, Translation, SynthesizedAudio, ProviderMetadata


class Provider(Protocol):
    metadata: ProviderMetadata
    def load(self) -> None: ...
    def close(self) -> None: ...


class SpeechRecognizer(Provider, Protocol):
    def transcribe(self, audio: AudioBuffer, language: str = "en") -> Transcript: ...


class TextTranslator(Provider, Protocol):
    def translate(self, text: str, utterance_id: str, source: str = "en", target: str = "hi") -> Translation: ...


class SpeechSynthesizer(Provider, Protocol):
    def synthesize(self, text: str, utterance_id: str, language: str = "hi") -> SynthesizedAudio: ...

