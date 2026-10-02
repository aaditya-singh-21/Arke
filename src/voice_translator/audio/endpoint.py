from threading import Event, Lock
import numpy as np
from ..errors import DeviceError


class BoundedCapture:
    def __init__(self, rate, max_seconds):
        self.samples = np.zeros(int(rate * max_seconds), dtype=np.float32)
        self.count = 0
        self.limit = Event()
        self.error = None
        self.lock = Lock()

    def append(self, data, status=None):
        with self.lock:
            if status:
                self.error = DeviceError("Capture overflow/device error; utterance discarded")
                self.limit.set()
                return
            count = min(len(data), len(self.samples) - self.count)
            if count:
                self.samples[self.count:self.count+count] = data[:count, 0]
                self.count += count
            if self.count == len(self.samples):
                self.limit.set()

    def finish(self):
        with self.lock:
            if self.error:
                raise self.error
            return self.samples[:self.count].copy()

