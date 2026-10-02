from .base import LocalProvider
from ..types import Translation
from ..errors import InvalidInput, ModelUnavailable, UnsupportedLanguage, classify
from ..offline import offline_call


class IndicTransTranslator(LocalProvider):
    stage = "translation"

    @offline_call
    def load(self):
        self.assets()
        try:
            torch = self.torch_setup()
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            try:
                from IndicTransToolkit import IndicProcessor
            except ImportError as exc:
                raise ModelUnavailable("Official IndicTransToolkit processor is missing; see Windows setup limitations") from exc
            self.processor = IndicProcessor(inference=True)
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.pc.path), trust_remote_code=True, local_files_only=True)
            dtype = torch.float32 if self.pc.precision == "float32" else torch.float16
            self.model = AutoModelForSeq2SeqLM.from_pretrained(str(self.pc.path), trust_remote_code=True,
                local_files_only=True, torch_dtype=dtype, attn_implementation="eager").to(self.pc.device).eval()
            self.verify_torch_placement(dtype)
        except Exception as exc:
            self.close()
            raise classify(exc, "load translation") from exc

    @offline_call
    def translate(self, text, utterance_id, source="en", target="hi"):
        self.require_loaded()
        if (source, target) != ("en", "hi"):
            raise UnsupportedLanguage("Translation supports English -> Hindi only")
        self.validate_text(text)
        import torch
        try:
            batch = self.processor.preprocess_batch([text], src_lang="eng_Latn", tgt_lang="hin_Deva")
            inputs = self.tokenizer(batch, truncation=False, padding=False, return_tensors="pt", return_attention_mask=True)
            if inputs["input_ids"].shape[-1] > self.pc.max_input_tokens:
                raise InvalidInput("Translation input exceeds configured token limit; no truncation performed")
            inputs = inputs.to(self.pc.device)
            with torch.inference_mode():
                output = self.model.generate(**inputs, use_cache=True, do_sample=False, num_beams=self.pc.beam_size,
                    num_return_sequences=1, max_new_tokens=self.pc.max_new_tokens)
            if self.pc.device == "cuda":
                torch.cuda.synchronize()
            ids = output[0].tolist()
            if len(ids) - 1 >= self.pc.max_new_tokens:
                raise InvalidInput("Translation reached generation bound; refusing potentially truncated output")
            eos = self.model.generation_config.eos_token_id
            eos = eos if isinstance(eos, list) else [eos]
            if not any(i in eos for i in ids[1:]):
                raise InvalidInput("Translation generation ended without EOS; token limit may have truncated output")
            decoded = self.tokenizer.batch_decode(output, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            hindi = self.processor.postprocess_batch(decoded, lang="hin_Deva")[0].strip()
            if len(hindi) > self.config.max_text_chars:
                raise InvalidInput("Translation output exceeds configured character bound")
            return Translation(utterance_id, hindi)
        except Exception as exc:
            raise classify(exc, "translation") from exc

    def close(self):
        self.model = self.tokenizer = self.processor = None

