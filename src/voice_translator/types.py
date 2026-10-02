from dataclasses import dataclass, field
from threading import Event
from uuid import uuid4
import numpy as np
from numpy.typing import NDArray
from .errors import InvalidInput, Cancelled


def utterance_id() -> str:
    return str(uuid4())


def validate_samples(samples: NDArray[np.float32], sample_rate: int) -> None:
    if not isinstance(samples, np.ndarray) or samples.ndim != 1 or samples.dtype != np.float32:
        raise InvalidInput("Audio must be one-dimensional float32 samples")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise InvalidInput("Audio sample rate must be a positive integer")
    if not np.isfinite(samples).all() or (samples.size and np.max(np.abs(samples)) > 1.0):
        raise InvalidInput("Audio must contain finite samples in [-1, 1]")


@dataclass(frozen=True)
class AudioBuffer:
    samples: NDArray[np.float32]
    sample_rate: int
    utterance_id: str = field(default_factory=utterance_id)
    capture_start: float | None = None
    capture_end: float | None = None
    speech_end: float | None = None

    def __post_init__(self):
        validate_samples(self.samples, self.sample_rate)

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate


@dataclass(frozen=True)
class Transcript:
    utterance_id: str
    text: str
    language: str = "en"
    segments: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Translation:
    utterance_id: str
    text: str
    source_language: str = "en"
    target_language: str = "hi"


@dataclass(frozen=True)
class SynthesizedAudio:
    utterance_id: str
    samples: NDArray[np.float32]
    sample_rate: int

    def __post_init__(self):
        validate_samples(self.samples, self.sample_rate)

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    model_id: str
    revision: str
    device: str
    precision: str
    languages: tuple[str, ...]


@dataclass
class UtteranceResult:
    utterance_id: str
    status: str = "ok"
    transcript: Transcript | None = None
    translation: Translation | None = None
    audio: SynthesizedAudio | None = None
    timings: dict[str, float] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def record(self, retain_content: bool = False) -> dict:
        record = {"utterance_id": self.utterance_id, "status": self.status,
                  "timings": self.timings, "error": self.error,
                  "output_duration": self.audio.duration if self.audio else None}
        if retain_content:
            record["english"] = self.transcript.text if self.transcript else None
            record["hindi"] = self.translation.text if self.translation else None
        return record


class Cancellation:
    def __init__(self):
        self.event = Event()

    def cancel(self):
        self.event.set()

    def check(self):
        if self.event.is_set():
            raise Cancelled("Utterance cancelled; unfinished output discarded")

