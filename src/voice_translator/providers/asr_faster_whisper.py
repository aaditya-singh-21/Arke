from .base import LocalProvider
from ..types import Transcript
from ..errors import InvalidInput, UnsupportedLanguage, DeviceError, classify


class FasterWhisperRecognizer(LocalProvider):
    stage = "asr"

    def load(self):
        self.assets()
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
            supported = ctranslate2.get_supported_compute_types(self.pc.device)
            if self.pc.precision not in supported:
                raise DeviceError("ASR precision is not supported on the configured device")
            self.model = WhisperModel(str(self.pc.path), device=self.pc.device, compute_type=self.pc.precision,
                                     cpu_threads=self.pc.cpu_threads, num_workers=1, local_files_only=True)
            # Record actual native model placement/precision; fail on implicit conversion.
            actual = self.model.model
            if actual.device != self.pc.device or actual.compute_type != self.pc.precision:
                self.close()
                raise DeviceError("ASR runtime changed device or precision; select a supported explicit configuration")
        except Exception as exc:
            self.close()
            raise classify(exc, "load asr") from exc

    def transcribe(self, audio, language="en"):
        self.require_loaded()
        if language != "en":
            raise UnsupportedLanguage("ASR supports English transcription only")
        if audio.sample_rate != 16000 or not audio.samples.size or audio.duration > self.config.max_audio_seconds:
            raise InvalidInput("ASR requires nonempty bounded mono 16 kHz audio")
        try:
            segments, info = self.model.transcribe(audio.samples, language="en", task="transcribe", beam_size=self.pc.beam_size,
                temperature=0.0, condition_on_previous_text=False, vad_filter=False,
                max_new_tokens=self.pc.max_new_tokens)
            rows = []
            text = []
            for segment in segments:  # Consume all lazy inference before returning/stopping timer.
                rows.append({"start": segment.start, "end": segment.end,
                             "avg_logprob": segment.avg_logprob, "no_speech_prob": segment.no_speech_prob})
                text.append(segment.text)
                if len(segment.tokens) >= self.pc.max_new_tokens:
                    raise InvalidInput("ASR generation reached token limit; output may be truncated")
            transcript = "".join(text).strip()
            if len(transcript) > self.config.max_text_chars:
                raise InvalidInput("ASR output exceeds character limit")
            return Transcript(audio.utterance_id, transcript, "en", tuple(rows))
        except Exception as exc:
            raise classify(exc, "asr") from exc

