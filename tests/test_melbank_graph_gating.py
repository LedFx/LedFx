"""Melbank graph events are only built while something listens for them."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from ledfx.effects.melbank import Melbanks
from ledfx.events import Event, Events, GraphUpdateEvent


def _melbanks(events: Events) -> Melbanks:
    melbanks = Melbanks.__new__(Melbanks)
    melbanks._ledfx = SimpleNamespace(events=events)
    melbanks.melbanks_filtered = (np.zeros(4),)
    melbanks.melbank_processors = [SimpleNamespace(melbank_frequencies=MagicMock())]
    return melbanks


def test_no_listener_builds_nothing():
    events = Events(MagicMock())
    fire = MagicMock()
    events.fire_event = fire
    melbanks = _melbanks(events)
    melbanks.send_melbank_event(0)
    fire.assert_not_called()


def test_a_listener_gets_the_graph():
    events = Events(MagicMock())
    received: list[Event] = []
    events.add_listener(received.append, Event.GRAPH_UPDATE)
    events.fire_event = lambda event: received.append(event)
    melbanks = _melbanks(events)
    melbanks.send_melbank_event(0)
    assert received
    event = received[-1]
    assert isinstance(event, GraphUpdateEvent)
    assert event.graph_id == "melbank_0"
