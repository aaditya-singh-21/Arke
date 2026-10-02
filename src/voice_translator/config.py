from dataclasses import dataclass, fields, asdict
from pathlib import Path
import math
import tomllib
from .errors import InvalidConfig


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model_id: str
    revision: str
    path: Path
    device: str
    precision: str
    beam_size: int = 5
    cpu_threads: int = 4
    max_input_tokens: int = 256
    max_new_tokens: int = 256
    voice: str = "hf_alpha"
    speed: float = 1.0
    max_phonemes: int = 500
    native_library_path: Path | None = None


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 48000
    input_device: int = -1
    output_device: int = -1
    ptt_key: str = "space"


@dataclass(frozen=True)
class Config:
    asr: ProviderConfig
    translation: ProviderConfig
    tts: ProviderConfig
    audio: AudioConfig
    source_language: str = "en"
    target_language: str = "hi"
    offline: bool = True
    max_audio_seconds: float = 15.0
    max_text_chars: int = 1000
    max_output_seconds: float = 30.0
    silence_rms: float = 0.0001
    memory_interval_seconds: float = 0.1
    retain_content: bool = False

    def metadata(self) -> dict:
        data = asdict(self)
        for stage in ("asr", "translation", "tts"):
            data[stage]["path"] = str(data[stage]["path"])
            native = data[stage]["native_library_path"]
            data[stage]["native_library_path"] = str(native) if native else None
        return data


def _keys(data: dict, cls):
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise InvalidConfig(f"Unknown {cls.__name__} keys: {', '.join(sorted(unknown))}")


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        _keys(data, Config)
        providers = {}
        for stage, allowed in (("asr", "faster-whisper"), ("translation", "indictrans2"), ("tts", "kokoro")):
            raw = dict(data.pop(stage))
            _keys(raw, ProviderConfig)
            # Paths are relative to project root (parent of configs/).
            raw["path"] = (path.parent.parent / raw["path"]).resolve()
            if raw.get("native_library_path") is not None:
                raw["native_library_path"] = (path.parent.parent / raw["native_library_path"]).resolve()
            pc = ProviderConfig(**raw)
            if pc.provider not in (allowed, "fake") or pc.device not in ("cpu", "cuda"):
                raise InvalidConfig(f"{stage}: unsupported local provider/device")
            if pc.provider == "fake" and (pc.device != "cpu" or pc.precision != "float32"):
                raise InvalidConfig("Fake providers require explicit CPU/float32 placement")
            if not pc.model_id or not pc.revision:
                raise InvalidConfig(f"{stage}: model ID and setup revision are required")
            precisions = ("float32", "float16", "int8", "int8_float16", "int8_float32") if stage == "asr" else ("float32", "float16")
            if pc.precision not in precisions or (pc.device == "cpu" and pc.precision in ("float16", "int8_float16")):
                raise InvalidConfig(f"{stage}: unsupported precision for configured device")
            if stage == "tts" and pc.precision != "float32":
                raise InvalidConfig("Kokoro adapter requires explicit float32 precision")
            for name in ("beam_size", "cpu_threads", "max_input_tokens", "max_new_tokens", "max_phonemes"):
                value = getattr(pc, name)
                if type(value) is not int or value < 1 or value > 4096:
                    raise InvalidConfig(f"{stage}: {name} must be an integer in [1, 4096]")
            if pc.max_phonemes > 500 or not 0.5 <= pc.speed <= 2.0 or not math.isfinite(pc.speed):
                raise InvalidConfig(f"{stage}: unsupported phoneme limit or speed")
            if stage == "tts" and pc.voice not in ("hf_alpha", "hf_beta", "hm_omega", "hm_psi"):
                raise InvalidConfig("V1 requires a supported stock Hindi voice")
            providers[stage] = pc
        audio_raw = data.pop("audio", {})
        _keys(audio_raw, AudioConfig)
        audio = AudioConfig(**audio_raw)
        config = Config(**providers, audio=audio, **data)
        if config.source_language != "en" or config.target_language != "hi" or config.offline is not True:
            raise InvalidConfig("V1 requires offline English -> Hindi")
        for name, low, high in (("max_audio_seconds", 0.1, 15), ("max_output_seconds", 0.1, 60),
                                ("memory_interval_seconds", 0.01, 10), ("silence_rms", 0, 0.1)):
            value = getattr(config, name)
            if isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
                raise InvalidConfig(f"{name} must be finite in [{low}, {high}]")
        if type(config.max_text_chars) is not int or not 1 <= config.max_text_chars <= 4000:
            raise InvalidConfig("max_text_chars must be in [1, 4000]")
        if type(config.retain_content) is not bool:
            raise InvalidConfig("retain_content must be boolean")
        if type(audio.sample_rate) is not int or audio.sample_rate not in (16000, 22050, 24000, 44100, 48000):
            raise InvalidConfig("Unsupported capture sample rate")
        if audio.ptt_key != "space" or any(type(v) is not int or v < -1 for v in (audio.input_device, audio.output_device)):
            raise InvalidConfig("Use space for PTT and numeric audio device IDs (-1 for default)")
        return config
    except InvalidConfig:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InvalidConfig(f"Cannot read valid configuration at {path}: {type(exc).__name__}") from exc

