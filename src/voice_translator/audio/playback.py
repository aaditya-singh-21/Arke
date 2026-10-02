from threading import Event
from time import perf_counter
from dataclasses import replace
import numpy as np
from ..errors import DeviceError, InvalidInput
from ..types import AudioBuffer, Cancellation
from .normalize import normalize


def play(audio, device=-1, cancellation=None):
    import sounddevice as sd
    token = cancellation or Cancellation()
    token.check()
    if not audio.samples.size:
        raise InvalidInput("Cannot play empty audio")
    ready = perf_counter()
    selected = None if device == -1 else device
    output_rate = audio.sample_rate
    try:
        sd.check_output_settings(device=selected, channels=1, dtype="float32", samplerate=output_rate)
    except Exception:
        info = sd.query_devices(selected, "output")
        output_rate = int(info["default_samplerate"])
        try:
            sd.check_output_settings(device=selected, channels=1, dtype="float32", samplerate=output_rate)
        except Exception as exc:
            raise DeviceError("Output device cannot play mono audio; select a supported output device") from exc
    samples = audio.samples if output_rate == audio.sample_rate else normalize(AudioBuffer(audio.samples, audio.sample_rate, audio.utterance_id), output_rate).samples
    finished = Event()
    position = 0
    onset = None
    callback_error = None
    def callback(outdata, frames, timing, status):
        nonlocal position, onset, callback_error
        outdata.fill(0)
        if token.event.is_set():
            raise sd.CallbackAbort
        if status:
            callback_error = DeviceError("Playback underflow/device error; output incomplete")
            raise sd.CallbackAbort
        if onset is None:
            onset = perf_counter() + max(0, timing.outputBufferDacTime - timing.currentTime)
        count = min(frames, len(samples) - position)
        outdata[:count, 0] = samples[position:position+count]
        position += count
        if position >= len(samples):
            raise sd.CallbackStop
    try:
        with sd.OutputStream(device=selected, channels=1, dtype="float32", samplerate=output_rate,
                             callback=callback, finished_callback=finished.set):
            while not finished.wait(.02):
                token.check()
        token.check()
        if callback_error:
            raise callback_error
        end = perf_counter()
        return {"utterance_id": audio.utterance_id, "playback_onset_proxy": onset,
                "audio_ready": ready, "playback_end_proxy": end,
                "playback_delay_proxy_seconds": onset - ready if onset is not None else None,
                "original_sample_rate": audio.sample_rate, "device_sample_rate": output_rate,
                "resampled_for_output": output_rate != audio.sample_rate,
                "measurement": "PortAudio scheduled DAC time proxy; acoustic/Bluetooth audible onset unmeasured"}
    except (sd.PortAudioError, OSError) as exc:
        raise DeviceError("Playback failed; check headphones and configured output device") from exc

