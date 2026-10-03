"""The throughput experiment must leave fixture and normal timing paths alone."""

from types import SimpleNamespace
from typing import cast

import pytest

from ledfx.effects.temporal import TemporalEffect
from tools.temporal_render_prototype import install_temporal_render_prototype


def test_temporal_experiment_is_targeted_and_restorable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Probe:
        def __init__(self, virtual_id: str) -> None:
            self._virtual = SimpleNamespace(id=virtual_id)

        def render(self) -> None:
            calls.append("normal-render")

        def effect_loop(self) -> None:
            calls.append("effect")

    def original_activate(effect: TemporalEffect, count: int) -> None:
        calls.append("normal-activate")

    monkeypatch.setattr(TemporalEffect, "on_activate", original_activate)
    original_render = Probe.render
    restore = install_temporal_render_prototype(Probe)
    try:
        target, fixture = Probe("benchmark"), Probe("fixture")
        TemporalEffect.on_activate(cast(TemporalEffect, target), 50)
        target.render()
        TemporalEffect.on_activate(cast(TemporalEffect, fixture), 50)
        fixture.render()
        assert calls == ["effect", "normal-activate", "normal-render"]
    finally:
        restore()
    assert TemporalEffect.on_activate is original_activate
    assert Probe.render is original_render
