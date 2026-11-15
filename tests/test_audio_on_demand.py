"""Result groups are computed only while something reads them.

AudioAnalyzer.set_wanted() skips what is not wanted; AudioAnalysisSource.want()
registers every read and sends the set of recently read groups to the analysis,
in this process or in the audio process.
"""

import time

import numpy as np
import pytest

from ledfx.audio_process.worker import AudioWorker
from ledfx.configuration.models import AudioConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.audio_analyzer import ANALYSIS_GROUPS, AudioAnalyzer
from tests.test_audio_analyzer import (
    FakeClock,
    analyzer_values,
    assert_same,
    make_signal,
    make_source,
)


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(time, "time", c)
    return c


def analyzer(config=None):
    src = make_source(AudioConfig.model_validate(config or {}).model_dump())
    return AudioAnalyzer(*src._analyzer_args())


def feed(an, blocks, clock):
    for block in blocks:
        clock.tick()
        an.process(block)


def loud_blocks():
    # The first second of the test signal: tones, noise and kicks, all above
    # the silence gate once the volume filter has risen.
    return make_signal()[:60]


def test_wanting_every_group_is_the_same_as_the_default(clock):
    blocks = make_signal()
    default = analyzer()
    every = analyzer()
    every.set_wanted(ANALYSIS_GROUPS)
    for i, block in enumerate(blocks):
        clock.tick()
        default.process(block)
        every.process(block)
        assert_same(analyzer_values(default), analyzer_values(every), f"block {i}")


def test_unwanted_groups_are_not_computed(clock):
    an = analyzer()
    feed(an, loud_blocks(), clock)
    assert all(m.any() for m in an.melbanks)
    before = [m.copy() for m in an.melbanks]
    pitch, powers = an.pitch, an.freq_power_raw.copy()

    an.set_wanted(())
    feed(an, make_signal()[60:120], clock)

    for old, now in zip(before, an.melbanks, strict=True):
        np.testing.assert_array_equal(old, now)
    assert an.pitch == pitch
    np.testing.assert_array_equal(an.freq_power_raw, powers)
    assert an.volume_beat_now is False


def test_onset_and_tempo_always_run(clock):
    an = analyzer()
    an.set_wanted(())
    onsets = 0
    for block in make_signal():
        clock.tick()
        an.process(block)
        onsets += an.onset
    assert onsets
    assert an.tempo.get_bpm() > 0


@pytest.mark.parametrize(
    ("group", "computed"),
    [
        ("melbank1", {1}),
        ("volume_beat", {0}),
        ("freq_power", {2}),
    ],
)
def test_a_group_computes_the_melbanks_it_needs(clock, group, computed):
    an = analyzer()
    an.set_wanted((group,))
    feed(an, loud_blocks(), clock)
    assert {i for i, m in enumerate(an.melbanks) if m.any()} == computed


def test_volume_beat_forgets_powers_from_before_a_pause(clock):
    an = analyzer()
    feed(an, loud_blocks(), clock)
    assert len(an.beat_power_history)
    an.set_wanted(())
    an.set_wanted(("volume_beat",))
    assert len(an.beat_power_history) == 0


def test_reads_register_their_groups():
    src = make_source(AudioConfig.model_validate({}).model_dump())
    src.pitch()
    src.volume_beat_now()
    src.lows_power()
    assert set(src._demand) == {"pitch", "volume_beat", "freq_power"}


def test_an_effect_melbank_read_registers_its_melbank():
    src = make_source(AudioConfig.model_validate({}).model_dump())

    class Reader:
        audio = src
        _selected_melbank = 1
        _melbank_min_idx = 0
        _melbank_max_idx = 24
        _input_mel_length = 24
        melbank_no_nan = AudioReactiveEffect.melbank_no_nan

    AudioReactiveEffect.melbank.__wrapped__(Reader())
    assert set(src._demand) == {"melbank1"}


class FakeRemote:
    alive = True

    def __init__(self):
        self.sent = []

    def want(self, groups):
        self.sent.append(frozenset(groups))


def test_the_source_sends_recent_groups_and_only_on_change(clock):
    src = make_source(AudioConfig.model_validate({}).model_dump())
    src._ledfx.events.has_listeners.return_value = False
    remote = src._remote = FakeRemote()
    view = analyzer()
    feed(view, loud_blocks()[:1], clock)

    src.pitch()
    for _ in range(3):
        src._apply_results(view)
    assert remote.sent == [frozenset({"pitch"})]

    for _ in range(src.DEMAND_TTL_BLOCKS + 1):
        src._apply_results(view)
    assert remote.sent == [frozenset({"pitch"}), frozenset()]


def test_graphs_want_their_melbank_only_while_someone_listens(clock):
    src = make_source(AudioConfig.model_validate({}).model_dump())
    view = analyzer()
    feed(view, loud_blocks()[:1], clock)
    last = f"melbank{len(src.melbanks.melbank_processors) - 1}"

    src._ledfx.events.has_listeners.return_value = False
    src._apply_results(view)
    assert last not in src._demand

    src._ledfx.events.has_listeners.return_value = True
    src._apply_results(view)
    assert last in src._demand


def test_the_local_analyzer_gets_the_groups(clock):
    src = make_source(AudioConfig.model_validate({}).model_dump())
    src._ledfx.events.has_listeners.return_value = False
    src.get_freq_power(0)
    for block in loud_blocks()[:5]:
        clock.tick()
        src._audio_sample_callback(block, 1, None, None)
    assert src._analyzer._wanted == frozenset({"freq_power"})


def test_the_worker_keeps_the_groups_across_a_configure():
    src = make_source(AudioConfig.model_validate({}).model_dump())
    audio_config, melbank_configs, coeffs_type = src._analyzer_args()
    worker = AudioWorker(None, None)
    worker.handle({"t": "want", "groups": ["pitch"]})
    worker.handle(
        {
            "t": "configure",
            "audio_config": audio_config,
            "melbank_configs": melbank_configs,
            "coeffs_type": coeffs_type,
        }
    )
    assert worker._analyzer._wanted == frozenset({"pitch"})
    worker.handle({"t": "want", "groups": None})
    assert worker._analyzer._wanted is None
