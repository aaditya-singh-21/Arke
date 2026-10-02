from time import perf_counter
from threading import Lock
import warnings
import numpy as np
from .types import AudioBuffer, UtteranceResult, Cancellation
from .errors import InvalidInput, Cancelled, classify
from .providers.interfaces import SpeechRecognizer, TextTranslator, SpeechSynthesizer


class Pipeline:
    def __init__(self, config, asr: SpeechRecognizer, translator: TextTranslator, tts: SpeechSynthesizer):
        self.config, self.asr, self.translator, self.tts = config, asr, translator, tts
        self.lock = Lock()
        self.load_timings = {}

    def load(self):
        try:
            for stage, provider in self.providers():
                start = perf_counter()
                provider.load()
                self.load_timings[stage] = perf_counter() - start
        except Exception as exc:
            self.close()
            raise classify(exc, f"load {stage}") from exc

    def providers(self):
        return (("asr", self.asr), ("translation", self.translator), ("tts", self.tts))

    def close(self):
        errors = []
        for stage, provider in reversed(self.providers()):
            try:
                provider.close()
            except Exception as exc:
                errors.append({"stage": stage, "error": classify(exc, stage).code})
        if errors:
            warnings.warn(f"Provider cleanup failed: {errors}", RuntimeWarning, stacklevel=2)
        return errors

    def run(self, audio: AudioBuffer, cancellation: Cancellation | None = None) -> UtteranceResult:
        if not self.lock.acquire(blocking=False):
            raise InvalidInput("One utterance is already active; no queue is supported")
        result = UtteranceResult(audio.utterance_id)
        token = cancellation or Cancellation()
        start = perf_counter()
        stage = "input"
        try:
            token.check()
            if audio.sample_rate != 16000 or audio.duration > self.config.max_audio_seconds:
                raise InvalidInput("ASR input must be mono 16 kHz and within the duration limit")
            if not audio.samples.size or np.sqrt(np.mean(audio.samples.astype(np.float64) ** 2)) <= self.config.silence_rms:
                result.status = "skipped_silence"
                return result
            for stage, provider in self.providers():
                token.check()
                stage_start = perf_counter()
                try:
                    if stage == "asr":
                        value = provider.transcribe(audio, "en")
                        result.transcript = value
                        if value.language != "en":
                            raise InvalidInput("ASR returned an unsupported language")
                    elif stage == "translation":
                        value = provider.translate(result.transcript.text, audio.utterance_id, "en", "hi")
                        result.translation = value
                        if (value.source_language, value.target_language) != ("en", "hi"):
                            raise InvalidInput("Translation returned unsupported languages")
                    else:
                        value = provider.synthesize(result.translation.text, audio.utterance_id, "hi")
                        if not value.samples.size or value.duration > self.config.max_output_seconds:
                            raise InvalidInput("Synthesis produced empty or oversized output")
                        result.audio = value
                    if value.utterance_id != audio.utterance_id:
                        raise InvalidInput("Provider returned a mismatched utterance ID")
                finally:
                    result.timings[stage] = perf_counter() - stage_start
                token.check()
                if stage != "tts":
                    if not value.text.strip():
                        result.status = f"skipped_empty_{stage}"
                        return result
                    if len(value.text) > self.config.max_text_chars:
                        raise InvalidInput(f"{stage} text exceeds configured character limit")
            return result
        except Exception as exc:
            error = classify(exc, stage)
            result.status = "cancelled" if isinstance(error, Cancelled) else "failed"
            result.error = {"stage": stage, "code": error.code, "message": str(error)}
            result.audio = None
            return result
        finally:
            result.timings["processing"] = perf_counter() - start
            self.lock.release()

