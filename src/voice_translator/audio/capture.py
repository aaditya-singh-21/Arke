"""Focused Windows console PTT. No global keyboard hook or microphone background capture."""
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
import json
import sys
from ..errors import DeviceError, InvalidInput, Cancelled, classify
from ..types import AudioBuffer, Cancellation, utterance_id
from ..metrics import MemorySampler, append_jsonl, distribution, environment
from ..providers.factory import create_pipeline
from .endpoint import BoundedCapture
from .normalize import normalize
from .playback import play


class ConsoleKeys:
    def __init__(self):
        if sys.platform != "win32":
            raise DeviceError("PTT currently supports a focused Windows console only")
        import ctypes
        from ctypes import wintypes as w
        class Char(ctypes.Union):
            _fields_ = [("UnicodeChar", w.WCHAR), ("AsciiChar", ctypes.c_char)]
        class Key(ctypes.Structure):
            _fields_ = [("down", w.BOOL), ("repeat", w.WORD), ("vk", w.WORD), ("scan", w.WORD), ("char", Char), ("control", w.DWORD)]
        class Payload(ctypes.Union):
            _fields_ = [("key", Key), ("padding", ctypes.c_byte * 16)]
        class Record(ctypes.Structure):
            _fields_ = [("type", w.WORD), ("event", Payload)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [w.DWORD]
        kernel.GetStdHandle.restype = w.HANDLE
        kernel.GetConsoleMode.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        kernel.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
        kernel.GetNumberOfConsoleInputEvents.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        kernel.ReadConsoleInputW.argtypes = [w.HANDLE, ctypes.POINTER(Record), w.DWORD, ctypes.POINTER(w.DWORD)]
        self.ctypes, self.w, self.Record, self.kernel = ctypes, w, Record, kernel
        self.handle = kernel.GetStdHandle(w.DWORD(-10))
        mode = w.DWORD()
        if not kernel.GetConsoleMode(self.handle, ctypes.byref(mode)):
            raise DeviceError("PTT needs a Windows console with key release events; run listen in PowerShell/Windows Terminal")
        self.original_mode = mode.value
        self.space = Event()
        self.quit = Event()
        self.stop = Event()
        self.token = None
        self.error = None
        self.release_time = None

    def __enter__(self):
        # Disable line/echo/quick-edit, preserve processed Ctrl+C behavior.
        if not self.kernel.SetConsoleMode(self.handle, (self.original_mode | 0x80) & ~(0x2 | 0x4 | 0x40)):
            raise DeviceError("Cannot configure Windows console for PTT")
        self.thread = Thread(target=self._run, daemon=True, name="console-keys")
        self.thread.start()
        return self

    def _run(self):
        try:
            count = self.w.DWORD()
            while not self.stop.wait(.01):
                if not self.kernel.GetNumberOfConsoleInputEvents(self.handle, self.ctypes.byref(count)):
                    raise DeviceError("Console input device disconnected")
                if not count.value:
                    continue
                record = self.Record()
                if not self.kernel.ReadConsoleInputW(self.handle, self.ctypes.byref(record), 1, self.ctypes.byref(count)):
                    raise DeviceError("Console input read failed")
                if record.type != 1:
                    continue
                key = record.event.key
                if key.vk == 32:
                    if key.down:
                        self.space.set()
                    else:
                        self.release_time = perf_counter()
                        self.space.clear()
                if key.down and key.vk in (27, 81):
                    if self.token:
                        self.token.cancel()
                    if key.vk == 81:
                        self.quit.set()
        except Exception as exc:
            self.error = classify(exc, "console")
            self.quit.set()

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=1)
        self.kernel.SetConsoleMode(self.handle, self.original_mode)


def capture_once(config, keys, token):
    import sounddevice as sd
    rate = config.audio.sample_rate
    buffer = BoundedCapture(rate, config.max_audio_seconds)
    start = perf_counter()
    def callback(data, frames, timing, status):
        buffer.append(data, status)
    try:
        with sd.InputStream(device=None if config.audio.input_device == -1 else config.audio.input_device,
                            channels=1, samplerate=rate, dtype="float32", callback=callback):
            while keys.space.is_set() and not buffer.limit.wait(.01):
                token.check()
                if keys.error:
                    raise keys.error
                if perf_counter() - start > config.max_audio_seconds + 1:
                    raise DeviceError("Input callbacks stalled; capture discarded")
        token.check()
        end = perf_counter()
        if buffer.limit.is_set():
            print(f"Duration limit {config.max_audio_seconds:g}s reached; finalizing", flush=True)
        samples = buffer.finish()
        return normalize(AudioBuffer(samples, rate, capture_start=start, capture_end=end)), keys.release_time
    except sd.PortAudioError as exc:
        raise DeviceError("Capture failed; check microphone permissions, sample rate, and device ID") from exc


def listen(config, metrics: Path, turns=30):
    if turns < 1:
        raise InvalidInput("--turns must be positive")
    pipeline = create_pipeline(config)
    records = []
    session_id = utterance_id()
    metadata = {"type": "session", "session_id": session_id, "environment": environment(),
                "configuration": config.metadata(), "fake": any(getattr(config, s).provider == "fake" for s in ("asr", "translation", "tts")),
                "manual_release_lag": None, "acoustic_onset": None}
    append_jsonl(metrics, metadata)
    try:
        with ConsoleKeys() as keys, MemorySampler(config.memory_interval_seconds) as memory:
            pipeline.load()
            print("Use headphones. Hold Space to speak; release to translate. Esc cancels; Q quits.\nREADY", flush=True)
            while len(records) < turns and not keys.quit.is_set():
                # Require a release before accepting another press (no queued utterance).
                while keys.space.is_set() and not keys.quit.wait(.01):
                    pass
                while not keys.space.wait(.02) and not keys.quit.is_set():
                    if keys.error:
                        raise keys.error
                if keys.quit.is_set():
                    break
                token = Cancellation()
                keys.token = token
                record = {"type": "utterance", "session_id": session_id, "utterance_id": utterance_id(), "status": "failed"}
                try:
                    print("RECORDING", flush=True)
                    audio, release_time = capture_once(config, keys, token)
                    record["utterance_id"] = audio.utterance_id
                    print("PROCESSING", flush=True)
                    result = pipeline.run(audio, token)
                    record.update(result.record(config.retain_content))
                    record["capture_duration"] = audio.duration
                    record["release_to_finalize_seconds"] = audio.capture_end - release_time if release_time and release_time >= audio.capture_start else None
                    if result.transcript:
                        print("English:", result.transcript.text)
                    if result.translation:
                        print("Hindi:", result.translation.text)
                    token.check()
                    if result.audio:
                        print("PLAYING", flush=True)
                        timing = play(result.audio, config.audio.output_device, token)
                        record["playback"] = timing
                        endpoint = release_time if release_time and release_time >= audio.capture_start else audio.capture_end
                        record["release_to_onset_proxy_seconds"] = timing["playback_onset_proxy"] - endpoint
                        record["release_to_completion_proxy_seconds"] = timing["playback_end_proxy"] - endpoint
                        record["speech_end_to_audible_seconds"] = None
                        record["manual_release_lag_seconds"] = None
                    if result.error:
                        print("ERROR:", result.error["message"], flush=True)
                    elif result.status != "ok":
                        print(result.status, flush=True)
                except Exception as exc:
                    error = classify(exc, "microphone")
                    record["status"] = "cancelled" if isinstance(error, Cancelled) else "failed"
                    record["error"] = {"code": error.code, "message": str(error)}
                    print("ERROR:", str(error), flush=True)
                finally:
                    keys.token = None
                    records.append(record)
                    append_jsonl(metrics, record)
                    print("READY", flush=True)
            if keys.error:
                raise keys.error
        summary = {"type": "summary", "session_id": session_id, "attempted": len(records),
                   "successful": sum(x["status"] == "ok" for x in records), "memory": memory.summary(),
                   "release_to_onset_proxy_seconds": distribution([x["release_to_onset_proxy_seconds"] for x in records if x.get("release_to_onset_proxy_seconds") is not None]),
                   "release_to_completion_proxy_seconds": distribution([x["release_to_completion_proxy_seconds"] for x in records if x.get("release_to_completion_proxy_seconds") is not None]),
                   "quality_status": "human_listening_pending", "audible_response_gate": "unmeasured",
                   "stability_gate": "pass" if len(records) >= 30 and all(x["status"] == "ok" for x in records) else "pending_or_failed"}
        append_jsonl(metrics, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if all(x["status"] == "ok" for x in records) else 1
    finally:
        pipeline.close()

