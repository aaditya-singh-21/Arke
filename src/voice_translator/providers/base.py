from ..errors import ModelUnavailable, InvalidInput, DeviceError, classify
from ..types import ProviderMetadata
from ..provision import validate_assets


class LocalProvider:
    stage = ""
    def __init__(self, pc, config):
        self.pc, self.config = pc, config
        self.model = None
        self.metadata = ProviderMetadata(pc.provider, pc.model_id, "not-provisioned", pc.device, pc.precision, ("en", "hi"))

    def assets(self):
        receipt = validate_assets(self.pc, self.stage)
        self.metadata = ProviderMetadata(self.pc.provider, self.pc.model_id, receipt["revision"], self.pc.device, self.pc.precision,
                                        ("en",) if self.stage == "asr" else ("hi",) if self.stage == "tts" else ("en", "hi"))
        return receipt

    def require_loaded(self):
        if self.model is None:
            raise ModelUnavailable(f"{self.stage}: load the provider explicitly first")

    def validate_text(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > self.config.max_text_chars:
            raise InvalidInput(f"{self.stage}: nonempty text within configured character bound required")

    def torch_setup(self):
        import torch
        torch.set_num_threads(self.pc.cpu_threads)
        if self.pc.device == "cuda" and not torch.cuda.is_available():
            raise DeviceError(f"{self.stage}: CUDA explicitly requested but unavailable; no fallback enabled")
        return torch

    def verify_torch_placement(self, dtype):
        parameter = next(self.model.parameters())
        if parameter.device.type != self.pc.device or parameter.dtype != dtype:
            raise DeviceError(f"{self.stage}: runtime parameter device/dtype differs from configuration")

    def close(self):
        self.model = None

