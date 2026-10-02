from dataclasses import asdict
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
import json
import platform
import subprocess
import sys


def gpu_inventory() -> dict:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0)
        devices = []
        for line in completed.stdout.strip().splitlines():
            index, name, driver, total, used = [x.strip() for x in line.split(",")]
            devices.append({"index": int(index), "name": name, "driver": driver,
                            "total_bytes": int(total) * 1048576, "used_bytes": int(used) * 1048576})
        return {"devices": devices, "error": None}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"devices": [], "error": type(exc).__name__}


def environment() -> dict:
    import psutil
    cpu = platform.processor()
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        except OSError:
            pass
    packages = {}
    for name in ("numpy", "scipy", "psutil", "soundfile", "sounddevice", "pytest", "faster-whisper",
                 "ctranslate2", "torch", "transformers", "kokoro", "misaki", "huggingface-hub", "IndicTransToolkit"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"os": platform.platform(), "cpu": cpu, "logical_cpus": psutil.cpu_count(),
            "python": sys.version, "executable": sys.executable, "packages": packages,
            "ram": psutil.virtual_memory()._asdict(), "disk": psutil.disk_usage(str(Path.cwd()))._asdict(),
            "gpu": gpu_inventory()}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    low = int(position)
    fraction = position - low
    return values[low] + fraction * (values[min(low + 1, len(values) - 1)] - values[low])


def distribution(values: list[float]) -> dict:
    return {"count": len(values), "p50": percentile(values, .5), "p95": percentile(values, .95)}


def append_jsonl(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


class MemorySampler:
    """Process RSS includes native allocations; GPU use is total device use, not torch allocator use."""
    def __init__(self, interval=.1):
        self.interval = interval
        self.stop_event = Event()
        self.thread = None
        self.samples = []
        self.errors = set()

    def sample(self):
        import psutil
        stamp = perf_counter()
        ram = psutil.virtual_memory()
        gpu = gpu_inventory()
        if gpu["error"]:
            self.errors.add(gpu["error"])
        process_memory = psutil.Process().memory_info()
        self.samples.append({"time": stamp, "rss": process_memory.rss,
                             "private": getattr(process_memory, "private", None), "vms": process_memory.vms,
                             "ram_total": ram.total, "ram_available": ram.available,
                             "gpu_used": max((x["used_bytes"] for x in gpu["devices"]), default=None)})

    def _run(self):
        while not self.stop_event.is_set():
            start = perf_counter()
            try:
                self.sample()
            except Exception as exc:
                self.errors.add(type(exc).__name__)
            self.stop_event.wait(max(0, self.interval - (perf_counter() - start)))

    def __enter__(self):
        self.thread = Thread(target=self._run, name="memory-sampler", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.errors.add("sampler_shutdown_timeout")

    def summary(self) -> dict:
        samples = sorted(self.samples, key=lambda sample: sample["time"])
        def peak(name):
            return max((s[name] for s in samples if s[name] is not None), default=None)
        available = min((s["ram_available"] for s in samples), default=None)
        gpu_peak = peak("gpu_used")
        intervals = [b["time"] - a["time"] for a, b in zip(samples, samples[1:])]
        complete = bool(self.samples) and gpu_peak is not None and not self.errors
        return {"sample_count": len(self.samples), "requested_interval_seconds": self.interval,
                "actual_interval_seconds": distribution(intervals), "peak_rss_bytes": peak("rss"),
                "peak_private_bytes": peak("private"), "peak_vms_bytes": peak("vms"),
                "total_ram_bytes": peak("ram_total"), "minimum_available_ram_bytes": available,
                "peak_total_dedicated_vram_bytes": gpu_peak, "errors": sorted(self.errors),
                "memory_gate": ("pass" if gpu_peak <= 3.5 * 1024**3 and available >= 1024**3 else "fail") if complete else "unverified",
                "limitations": "Sampled peaks may miss brief allocations; device-wide VRAM includes background applications. WDDM process GPU accounting is not assumed."}

