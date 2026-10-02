"""A process-scoped network guard for explicit inference, including vendor custom code."""
from contextlib import contextmanager
import os
import socket
from .errors import ModelUnavailable


@contextmanager
def offline_runtime():
    keys = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")
    old = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ[key] = "1"
    def blocked(*args, **kwargs):
        raise ModelUnavailable("Network access blocked during local inference; provision assets explicitly")
    originals = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo = originals
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

