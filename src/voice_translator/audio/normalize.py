from dataclasses import replace
from math import gcd
from pathlib import Path
import numpy as np
from ..types import AudioBuffer, validate_samples
from ..errors import InvalidInput


def normalize(audio: AudioBuffer, target_rate: int = 16000) -> AudioBuffer:
    if audio.sample_rate == target_rate:
        return audio
    from scipy.signal import resample_poly
    divisor = gcd(audio.sample_rate, target_rate)
    samples = resample_poly(audio.samples, target_rate // divisor, audio.sample_rate // divisor)
    # Polyphase filtering may overshoot full scale; explicit output clipping.
    samples = np.clip(samples, -1, 1).astype(np.float32)
    return replace(audio, samples=samples, sample_rate=target_rate)


def read_wav(path: str | Path, max_seconds: float = 15) -> AudioBuffer:
    import soundfile as sf
    try:
        with sf.SoundFile(path) as stream:
            if stream.format not in ("WAV", "WAVEX"):
                raise InvalidInput("Only WAV input is supported")
            if stream.samplerate <= 0 or stream.channels not in (1, 2):
                raise InvalidInput("WAV must have one or two channels and a valid rate")
            if stream.frames / stream.samplerate > max_seconds:
                raise InvalidInput(f"WAV exceeds {max_seconds:g} seconds; segmentation is not implemented")
            rate = stream.samplerate
            data = stream.read(dtype="float32", always_2d=True)
        if not np.isfinite(data).all() or (data.size and np.max(np.abs(data)) > 1):
            raise InvalidInput("WAV contains nonfinite or out-of-range samples")
        mono = data.mean(axis=1).astype(np.float32)
        return normalize(AudioBuffer(mono, rate))
    except InvalidInput:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise InvalidInput(f"Cannot decode WAV: {type(exc).__name__}") from exc


def write_wav(path: str | Path, audio) -> None:
    import soundfile as sf
    validate_samples(audio.samples, audio.sample_rate)
    path = Path(path)
    if path.suffix.lower() != ".wav":
        raise InvalidInput("Output path must end with .wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio.samples, audio.sample_rate, subtype="PCM_16")

