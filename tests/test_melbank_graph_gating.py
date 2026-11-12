"""Melbank graph events are only built while something listens for them."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ledfx.effects.melbank import Melbanks
from ledfx.events import Event, Events


def _melbanks(events):
    melbanks = Melbanks.__new__(Melbanks)
    melbanks._ledfx = SimpleNamespace(events=events)
    melbanks.melbanks_filtered = [MagicMock()]
    melbanks.melbank_processors = [SimpleNamespace(melbank_frequencies=MagicMock())]
    melbanks._wanted = {}
    melbanks._frame = 0
    return melbanks


def test_no_listener_builds_nothing():
    events = Events(MagicMock())
    melbanks = _melbanks(events)
    melbanks.send_melbank_event(0)
    melbanks.melbanks_filtered[0].tolist.assert_not_called()


def test_a_listener_gets_the_graph():
    events = Events(MagicMock())
    received = []
    events.add_listener(received.append, Event.GRAPH_UPDATE)
    events.fire_event = lambda event: received.append(event)
    melbanks = _melbanks(events)
    melbanks.send_melbank_event(0)
    assert received and received[-1].graph_id == "melbank_0"
