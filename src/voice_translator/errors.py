class TranslatorError(Exception):
    """Actionable error; messages must not include captured speech or credentials."""
    code = "translator_error"


class InvalidConfig(TranslatorError):
    code = "invalid_config"


class ModelUnavailable(TranslatorError):
    code = "model_unavailable"


class UnsupportedLanguage(TranslatorError):
    code = "unsupported_language"


class InvalidInput(TranslatorError):
    code = "invalid_input"


class ResourceExhausted(TranslatorError):
    code = "resource_exhausted"


class DeviceError(TranslatorError):
    code = "device_error"


class ProviderError(TranslatorError):
    code = "provider_error"


class Cancelled(TranslatorError):
    code = "cancelled"


def classify(exc: Exception, stage: str) -> TranslatorError:
    if isinstance(exc, TranslatorError):
        return exc
    message = str(exc).lower()
    if isinstance(exc, MemoryError) or "out of memory" in message or "bad_alloc" in message:
        return ResourceExhausted(f"{stage}: insufficient memory; choose an explicit measured placement before retrying")
    if "cuda" in message or "cudnn" in message or "cublas" in message:
        return DeviceError(f"{stage}: CUDA runtime/device failure; run doctor and verify configured runtimes")
    return ProviderError(f"{stage}: {type(exc).__name__}; use --debug for the traceback")

