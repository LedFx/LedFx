"""AudioAnalyzer and the AudioAnalysisSource getters that expose it.

Every value an effect can read must come straight from the analyzer's results
for the latest block, through the same getters effects always used.
"""

import time

import numpy as np
import pytest

from ledfx.configuration.models import AudioConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.audio_analyzer import AudioAnalyzer
from tests.test_utilities.fake_ledfx import fake_ledfx

STREAM_RATE = 48000
FPS = 60
SECONDS = 10


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def tick(self):
        self.now += 1 / FPS


def make_signal():
    """Tones, noise, a kick every half second and a silent stretch."""
    rng = np.random.default_rng(1234)
    n = STREAM_RATE * SECONDS
    t = np.arange(n) / STREAM_RATE
    signal = 0.15 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.sin(2 * np.pi * 1760 * t)
    signal += 0.03 * rng.standard_normal(n)
    kick_len = int(0.15 * STREAM_RATE)
    kick = np.exp(-np.arange(kick_len) / 3000.0) * np.sin(
        2 * np.pi * 50 * np.arange(kick_len) / STREAM_RATE
    )
    for start in range(0, n - kick_len, STREAM_RATE // 2):
        signal[start : start + kick_len] += kick
    signal[4 * STREAM_RATE : 5 * STREAM_RATE] = 0.0
    signal = np.clip(signal, -1, 1).astype(np.float32)
    block = STREAM_RATE // FPS
    return [signal[i : i + block] for i in range(0, n - block + 1, block)]


def make_source(audio_config):
    """AudioAnalysisSource set up as activation leaves it, without a device."""
    src = object.__new__(AudioAnalysisSource)
    src._ledfx = fake_ledfx({"audio": audio_config})
    src._config = AudioConfig.model_validate(audio_config)
    src._callbacks = []
    src.initialise_analysis()
    src._analyzer = src._create_analyzer()
    src._callbacks = [src._publish_results]
    return src


def source_values(src):
    """Everything an effect can read, through the effect-facing API."""
    return {
        "volume_raw": src.volume(filtered=False),
        "volume_filtered": src.volume(filtered=True),
        "melbanks": [m.copy() for m in src.melbanks.melbanks],
        "melbanks_filtered": [m.copy() for m in src.melbanks.melbanks_filtered],
        "pitch": src.pitch(),
        "onset": src.onset(),
        "bpm_beat_now": src.bpm_beat_now(),
        "bar_oscillator": src.bar_oscillator(),
        "beat_oscillator": src.beat_oscillator(),
        "volume_beat_now": src.volume_beat_now(),
        "beat_counter": src.beat_counter,
        "tempo_bpm": src._tempo.get_bpm(),
        "tempo_confidence": src._tempo.get_confidence(),
        "powers": [
            src.beat_power(),
            src.bass_power(),
            src.lows_power(),
            src.mids_power(),
            src.high_power(),
            src.beat_power(filtered=False),
            src.lows_power(filtered=False),
        ],
    }


def analyzer_values(an):
    def power(i, filtered=True):
        value = an.freq_power_filtered[i] if filtered else an.freq_power_raw[i]
        return value if not np.isnan(value) else 0.0

    return {
        "volume_raw": an.volume_raw,
        "volume_filtered": an.volume_filtered,
        "melbanks": [m.copy() for m in an.melbanks],
        "melbanks_filtered": [m.copy() for m in an.melbanks_filtered],
        "pitch": an.pitch,
        "onset": an.onset,
        "bpm_beat_now": an.bpm_beat_now,
        "bar_oscillator": an.bar_oscillator,
        "beat_oscillator": an.bar_oscillator % 1,
        "volume_beat_now": an.volume_beat_now,
        "beat_counter": an.beat_counter,
        "tempo_bpm": an.tempo.get_bpm(),
        "tempo_confidence": an.tempo.get_confidence(),
        "powers": [
            power(0),
            power(1),
            (power(0) + power(1)) * 0.5,
            power(2),
            power(3),
            power(0, False),
            (power(0, False) + power(1, False)) * 0.5,
        ],
    }


def assert_same(expected, got, where):
    for key, value in expected.items():
        other = got[key]
        if isinstance(value, list) and value and isinstance(value[0], np.ndarray):
            for a, b in zip(value, other, strict=True):
                np.testing.assert_array_equal(a, b, err_msg=f"{where} {key}")
        else:
            assert value == other, f"{where} {key}: {value!r} != {other!r}"


def run(feed, values, blocks, clock):
    rows = []
    for block in blocks:
        clock.tick()
        feed(block)
        rows.append(values())
    return rows


@pytest.mark.parametrize("delay_ms", [0, 50])
def test_source_exposes_exactly_the_analyzer_results(monkeypatch, delay_ms):
    audio_config = AudioConfig.model_validate({"delay_ms": delay_ms}).model_dump()
    blocks = make_signal()
    clock = FakeClock()
    monkeypatch.setattr(time, "time", clock)

    src = make_source(audio_config)
    from_source = run(
        lambda b: src._audio_sample_callback(b, 1, None, None),
        lambda: source_values(src),
        blocks,
        clock,
    )

    clock.now = 1_000_000.0
    melbank_configs = [entry["config"] for entry in src.melbanks.melbank_collection]
    an = AudioAnalyzer(
        audio_config, melbank_configs, src._ledfx.config.melbanks.coeffs_type
    )
    from_analyzer = run(an.process, lambda: analyzer_values(an), blocks, clock)

    started = False
    for i, (expected, got) in enumerate(zip(from_analyzer, from_source, strict=True)):
        started = started or an.has_volume_measurement
        if not src._has_volume_measurement:
            continue
        assert_same(expected, got, f"block {i}")
    assert started


def test_signal_exercises_every_detector(monkeypatch):
    """Equality only means something if the detectors actually fire."""
    clock = FakeClock()
    monkeypatch.setattr(time, "time", clock)
    src = make_source(AudioConfig.model_validate({}).model_dump())
    seen = {"onset": 0, "volume_beat_now": 0, "bpm_beat_now": 0, "silent": 0}
    for block in make_signal():
        clock.tick()
        src._audio_sample_callback(block, 1, None, None)
        seen["onset"] += bool(src.onset())
        seen["volume_beat_now"] += bool(src.volume_beat_now())
        seen["bpm_beat_now"] += bool(src.bpm_beat_now())
        seen["silent"] += not src.melbanks.melbanks[0].any()
    assert all(seen.values()), seen


def test_getters_before_any_audio():
    src = make_source(AudioConfig.model_validate({}).model_dump())
    assert src.volume() == -90
    assert src.pitch() == 0
    assert src.onset() is False
    assert src.beat_power() == 0.0
    assert src.bar_oscillator() == 0.0
    assert src._tempo.get_bpm() == 0.0
    assert src._has_volume_measurement is False
