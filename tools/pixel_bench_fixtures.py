"""Local inputs for pixel profiling; replaces hardware, never effect algorithms."""

import math
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def catalog():
    from ledfx.effects import Effects
    from ledfx.effects.audio import AudioReactiveEffect
    from ledfx.effects.temporal import TemporalEffect
    from ledfx.effects.twod import Twod

    registry = Effects(SimpleNamespace(audio=None))
    return {
        name: {
            "name": cls.NAME,
            "matrix": issubclass(cls, Twod) or cls.CATEGORY == "Matrix",
            "audio": issubclass(cls, AudioReactiveEffect),
            "temporal": issubclass(cls, TemporalEffect),
        }
        for name, cls in sorted(registry.classes().items())
    }


def matrix_rows(pixels: int) -> int:
    rows = math.isqrt(pixels)
    while pixels % rows:
        rows -= 1
    return rows


def audio_signal(sample_rate: int = 30000, seconds: int = 8) -> np.ndarray:
    """Seeded 120 BPM drum pulses, changing chords, a sweep and broadband noise."""
    t = np.arange(sample_rate * seconds) / sample_rate
    beat = t % 0.5
    rng = np.random.default_rng(42)
    notes = np.array([220, 277.18, 329.63, 440])[(t.astype(int) // 2) % 4]
    signal = (
        0.40 * np.sin(2 * np.pi * 65 * t) * np.exp(-beat * 35)
        + 0.16 * np.sin(2 * np.pi * notes * t)
        + 0.10 * np.sin(2 * np.pi * notes * 1.5 * t)
        + 0.08 * np.sin(2 * np.pi * (1000 * t + 160 * t * t))
        + 0.10 * rng.standard_normal(len(t)) * np.exp(-(t % 0.25) * 80)
    )
    return np.clip(signal, -1, 1).astype(np.float32)


def install_audio():
    """Let normal AudioInputSource activation construct its real DSP pipeline."""
    from ledfx.effects.audio import AudioInputSource

    class InputStream:
        def __init__(self, *, callback, samplerate, blocksize, **kwargs):
            self.callback = callback
            self.samplerate = samplerate
            self.blocksize = blocksize
            self.signal = audio_signal(samplerate)
            self.stopped = threading.Event()
            self.thread = None

        def start(self):
            # Start only after AudioAnalysisSource and the effect finish setup.
            pass

        def begin(self):
            def feed():
                offset = 0
                deadline = time.perf_counter()
                while not self.stopped.is_set():
                    frame = self.signal[offset : offset + self.blocksize].copy()
                    offset = (offset + self.blocksize) % len(self.signal)
                    if len(frame) != self.blocksize:
                        offset = 0
                        continue
                    self.callback(frame, self.blocksize, None, None)
                    deadline = max(
                        deadline + self.blocksize / self.samplerate, time.perf_counter()
                    )
                    self.stopped.wait(max(0, deadline - time.perf_counter()))

            self.thread = threading.Thread(
                target=feed, name="Benchmark PCM", daemon=True
            )
            self.thread.start()

        def stop(self):
            self.stopped.set()
            if self.thread and self.thread is not threading.current_thread():
                self.thread.join(5)

        close = stop

    AudioInputSource.query_devices = staticmethod(
        lambda: (
            {
                "name": "Benchmark PCM",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 30000,
            },
        )
    )
    AudioInputSource.query_hostapis = staticmethod(
        lambda: ({"name": "Benchmark", "default_input_device": 0},)
    )
    AudioInputSource.default_device_index = staticmethod(lambda: 0)
    AudioInputSource._audio = SimpleNamespace(InputStream=InputStream)


def local_config(effect: str, directory: str) -> dict:
    from PIL import Image, ImageDraw

    if effect == "random_flash":
        # Default flashes can remain idle for the entire short screening run.
        return {"hit_probability_per_sec": 1.0}
    if effect in {"gifplayer", "keybeat2d", "imagespin"}:
        path = Path(directory, "fixture.gif")
        frames = []
        for n in range(16):
            frame = Image.new("RGB", (128, 128), (n * 15, 40, 255 - n * 15))
            ImageDraw.Draw(frame).rectangle(
                (n * 6, 16, n * 6 + 24, 110), fill=(255, 200, 20)
            )
            frames.append(frame)
        frames[0].save(
            path, save_all=True, append_images=frames[1:], duration=50, loop=0
        )
        if effect == "imagespin":
            path = Path(directory, "fixture.png")
            frames[0].resize((1024, 1024)).save(path)
            return {"image_source": str(path), "spin": True}
        return {
            "image_source" if effect == "imagespin" else "image_location": str(path)
        }
    if effect == "clone":
        from ledfx.effects import clone

        class Screen:
            monitors = [{"top": 0, "left": 0}] * 5

            def grab(self, area):
                width, height = area["width"], area["height"]
                color = int(time.perf_counter() * 60) % 256
                frame = Image.new("RGB", (width, height), (color, 80, 255 - color))
                return SimpleNamespace(
                    size=frame.size, bgra=frame.tobytes("raw", "BGRX")
                )

        clone.mss.mss = Screen
    return {}
