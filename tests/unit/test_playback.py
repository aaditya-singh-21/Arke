from types import SimpleNamespace
import sys
import numpy as np
import pytest
from voice_translator.audio.playback import play
from voice_translator.types import SynthesizedAudio, Cancellation
from voice_translator.errors import Cancelled


def test_playback_resampling_onset_and_cleanup(monkeypatch):
    class Stop(Exception): pass
    class Abort(Exception): pass
    closed = []
    rates = []
    def check_output_settings(**kwargs):
        if kwargs['samplerate'] != 48000:
            raise ValueError('unsupported rate')
    class Stream:
        def __init__(self, **kwargs):
            self.options = kwargs
            rates.append(kwargs['samplerate'])
        def __enter__(self):
            callback = self.options['callback']
            timing = SimpleNamespace(outputBufferDacTime=1.05, currentTime=1)
            with pytest.raises(Stop):
                callback(np.zeros((48000, 1), dtype=np.float32), 48000, timing, False)
            self.options['finished_callback']()
            return self
        def __exit__(self, *args):
            closed.append(True)
    stub = SimpleNamespace(check_output_settings=check_output_settings, query_devices=lambda *args: {'default_samplerate': 48000},
        OutputStream=Stream, CallbackStop=Stop, CallbackAbort=Abort, PortAudioError=RuntimeError)
    monkeypatch.setitem(sys.modules, 'sounddevice', stub)
    audio = SynthesizedAudio('id', np.zeros(24000, dtype=np.float32), 24000)
    result = play(audio)
    assert rates == [48000] and closed == [True]
    assert result['resampled_for_output'] is True and result['playback_delay_proxy_seconds'] >= .05
    token = Cancellation()
    token.cancel()
    with pytest.raises(Cancelled):
        play(audio, cancellation=token)

