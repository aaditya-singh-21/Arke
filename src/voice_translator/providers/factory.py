def create_provider(config, stage):
    pc = getattr(config, stage)
    if pc.provider == "fake":
        from .fake import FakeProvider
        return FakeProvider(pc, stage)
    if stage == "asr":
        from .asr_faster_whisper import FasterWhisperRecognizer
        return FasterWhisperRecognizer(pc, config)
    if stage == "translation":
        from .translation_indictrans2 import IndicTransTranslator
        return IndicTransTranslator(pc, config)
    from .tts_kokoro import KokoroSynthesizer
    return KokoroSynthesizer(pc, config)


def create_pipeline(config):
    from ..pipeline import Pipeline
    return Pipeline(config, *(create_provider(config, stage) for stage in ("asr", "translation", "tts")))

