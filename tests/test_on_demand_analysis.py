"""Melbanks, band powers, pitch and volume beat are computed only on demand."""

from collections import deque
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import numpy as np
import pytest

from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.melbank import Melbanks


def _no_listeners(event_type: str) -> bool:
    return False


def _loud(filtered: bool = True) -> float:
    return 1.0


def _melbanks():
    m = Melbanks.__new__(Melbanks)
    m._ledfx = SimpleNamespace(events=SimpleNamespace(has_listeners=_no_listeners))
    m._audio = SimpleNamespace(_frequency_domain=None, volume=_loud)
    m.dev_enabled = False
    m.minimum_volume = 0.0
    m.melbank_processors = [MagicMock() for _ in range(3)]
    m.melbanks = tuple(np.zeros(4) for _ in range(3))
    m.melbanks_filtered = tuple(np.zeros(4) for _ in range(3))
    m._wanted = {}
    m._frame = 0
    return m


def test_unread_melbanks_are_skipped():
    m = _melbanks()
    m()
    assert not any(p.called for p in m.melbank_processors)
    m.want(1)
    m()
    assert [p.called for p in m.melbank_processors] == [False, True, False]


def test_demand_expires_after_the_ttl():
    m = _melbanks()
    m.want(0)
    m._frame += Melbanks.WANT_TTL_FRAMES + 1
    m()
    assert not m.melbank_processors[0].called


def _source():
    s = AudioAnalysisSource.__new__(AudioAnalysisSource)
    s._freq_power_frame = 0
    s._freq_power_wanted = -(AudioAnalysisSource.FREQ_POWER_TTL_FRAMES + 1)
    s._pitch_frame = 0
    s._pitch_wanted = -(AudioAnalysisSource.PITCH_TTL_FRAMES + 1)
    s._volume_beat_frame = 0
    s._volume_beat_wanted = -(AudioAnalysisSource.VOLUME_BEAT_TTL_FRAMES + 1)
    s.melbanks = MagicMock()
    s.melbanks.melbanks = [np.ones(24)] * 3
    s.freq_mel_indexes = [2, 5, 17, 23]
    s.freq_power_raw = np.zeros(4)
    s.freq_power_filter = MagicMock(value=np.zeros(4))
    return s


def test_freq_power_runs_only_after_a_read():
    s = _source()
    want = cast(MagicMock, s.melbanks).want
    s.freq_power()
    want.assert_not_called()
    s.get_freq_power(0)
    s.freq_power()
    want.assert_called_once_with(2)


def test_pitch_runs_only_while_read():
    s = _source()
    s._pitch = MagicMock(return_value=[60.0])
    s.audio_sample = lambda raw=False: np.zeros(4, dtype=np.float32)
    s._pitch_tick()
    assert s._pitch.call_count == 0
    assert s.pitch() == 60.0
    AudioAnalysisSource.pitch.cache_clear()
    AudioAnalysisSource._pitch_compute.cache_clear()
    s._pitch_tick()
    assert s._pitch.call_count == 2


def _beat(self: AudioAnalysisSource) -> bool:
    return True


def test_volume_beat_drops_stale_history(monkeypatch: pytest.MonkeyPatch):
    s = _source()
    monkeypatch.setattr(AudioAnalysisSource, "_volume_beat_compute", _beat)
    s.beat_power_history = deque([1.0, 2.0])
    s._volume_beat_frame = 1000
    s._volume_beat_wanted = 0
    assert s.volume_beat_now() is True
    assert len(s.beat_power_history) == 0
    AudioAnalysisSource.volume_beat_now.cache_clear()
