"""Graph and diagnostic producers build payloads only for someone listening."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

import ledfx.effects.melbank as melbank_module
import ledfx.effects.noise2d as noise2d_module
import ledfx.effects.utils.logsec_helper as logsec_module
from ledfx.configuration.models import AudioConfig
from ledfx.effects.melbank import Melbanks
from ledfx.effects.noise2d import Noise2d
from ledfx.effects.utils.logsec_helper import LogSecHelper
from ledfx.events import (
    Event,
    Events,
    GeneralDiagEvent,
    GraphUpdateEvent,
    VirtualDiagEvent,
)
from tests.test_utilities.fake_ledfx import fake_ledfx
from tests.test_utilities.fake_loop import FakeLoop


def make_events() -> tuple[Events, FakeLoop]:
    loop = FakeLoop()
    return Events(SimpleNamespace(loop=loop)), loop


def make_melbanks(events: Events, *, stream_active: bool = True) -> Melbanks:
    ledfx = fake_ledfx()
    ledfx.events = events
    audio = SimpleNamespace(
        _config=AudioConfig(min_volume=0.3), _audio_stream_active=stream_active
    )
    return Melbanks(ledfx, audio, ledfx.config.melbanks.model_dump())


@pytest.fixture
def graph_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    spy = MagicMock(wraps=GraphUpdateEvent)
    monkeypatch.setattr(melbank_module, "GraphUpdateEvent", spy)
    return spy


def test_graph_event_built_only_for_matching_listener(graph_spy: MagicMock):
    events, loop = make_events()
    melbanks = make_melbanks(events)
    assert len(melbanks.melbank_processors) > 1

    for i in range(len(melbanks.melbank_processors)):
        melbanks.send_melbank_event(i)
    graph_spy.assert_not_called()

    received: list[GraphUpdateEvent] = []
    events.add_listener(received.append, Event.GRAPH_UPDATE, {"graph_id": "melbank_1"})
    for i in range(len(melbanks.melbank_processors)):
        melbanks.send_melbank_event(i)
    loop.run_ready()

    assert [call.args[0] for call in graph_spy.call_args_list] == ["melbank_1"]
    assert [event.graph_id for event in received] == ["melbank_1"]


def test_graph_not_published_after_audio_stop(graph_spy: MagicMock):
    events, loop = make_events()
    melbanks = make_melbanks(events, stream_active=False)
    received: list[GraphUpdateEvent] = []
    events.add_listener(received.append, Event.GRAPH_UPDATE)

    melbanks.send_melbank_event(0)
    loop.run_ready()

    graph_spy.assert_not_called()
    assert received == []


def make_logsec(events: Events, virtual_id: str = "strip") -> LogSecHelper:
    effect = SimpleNamespace(
        name="Noise",
        _virtual=SimpleNamespace(id=virtual_id, name=virtual_id, is_device=None),
        _ledfx=SimpleNamespace(events=events),
    )
    helper = LogSecHelper(effect)
    helper.diag = True
    return helper


def emit_diag(helper: LogSecHelper) -> None:
    # Diagnostics fire on the frame that crossed a second boundary.
    helper.log = True
    helper.fps = 60
    helper.try_log()


def test_virtual_diag_gated_and_phy_snapshotted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logsec_module.Teleplot, "send", MagicMock())
    spy = MagicMock(wraps=logsec_module.VirtualDiagEvent)
    monkeypatch.setattr(logsec_module, "VirtualDiagEvent", spy)
    events, loop = make_events()
    helper = make_logsec(events)
    received: list[VirtualDiagEvent] = []

    dispose = events.add_listener(
        received.append, Event.VIRTUAL_DIAG, {"virtual_id": "other"}
    )
    emit_diag(helper)
    loop.run_ready()
    spy.assert_not_called()
    assert received == []

    dispose()
    events.add_listener(received.append, Event.VIRTUAL_DIAG, {"virtual_id": "strip"})
    helper.phy.fps = 42
    emit_diag(helper)
    helper.phy.fps = 7
    loop.run_ready()

    assert len(received) == 1
    assert received[0].virtual_id == "strip"
    assert received[0].phy["fps"] == 42


def test_noise2d_diag_skipped_without_listener(monkeypatch: pytest.MonkeyPatch):
    spy = MagicMock(wraps=noise2d_module.GeneralDiagEvent)
    monkeypatch.setattr(noise2d_module, "GeneralDiagEvent", spy)
    events, loop = make_events()
    effect = Noise2d(
        SimpleNamespace(events=events),
        Noise2d.config_model().model_validate({"test": True}),
    )
    effect._virtual = MagicMock()
    effect._virtual.config.rows = 4
    effect._virtual.config.rotate = 0
    effect.pixels = np.zeros((16, 3))
    effect.on_activate(16)

    effect.render()
    spy.assert_not_called()

    received: list[GeneralDiagEvent] = []
    events.add_listener(received.append, Event.GENERAL_DIAG)
    effect.render()
    loop.run_ready()

    spy.assert_called_once()
    assert len(received) == 1
    assert received[0].debug.startswith("Noise2d: ")
