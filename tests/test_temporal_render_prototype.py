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


@pytest.mark.parametrize(
    "interval,speed,period", [(None, 0.5, 0.2), (2, 5, 0.04), (0, 1, 0.001)]
)
def test_cadence_honors_speed_interval_and_coalesces_late_ticks(
    interval: float | None, speed: float, period: float
):
    now = [10.0]
    calls = []

    class Probe:
        def __init__(self):
            self._virtual = SimpleNamespace(id="benchmark")
            self.config = SimpleNamespace(speed=speed)

        def render(self):
            pass

        def effect_loop(self):
            calls.append(now[0])
            return interval

    restore = install_temporal_render_prototype(
        Probe, cadence=True, clock=lambda: now[0]
    )
    try:
        effect = Probe()
        TemporalEffect.on_activate(cast(TemporalEffect, effect), 50000)
        effect.render()
        now[0] += period * 0.99
        effect.render()
        assert len(calls) == 1
        now[0] += period * 0.02
        effect.render()
        assert len(calls) == 2
        now[0] += 100
        for _ in range(20):
            effect.render()
        assert len(calls) == 3  # No catch-up burst after a stall.
        TemporalEffect.on_activate(cast(TemporalEffect, effect), 50000)
        effect.render()
        assert len(calls) == 4  # Reactivation resets the deadline.
    finally:
        restore()


@pytest.mark.parametrize(
    "module,name",
    [
        ("fade", "FadeEffect"),
        ("rainbow", "RainbowEffect"),
        ("singleColor", "SingleColorEffect"),
        ("pixels", "PixelsEffect"),
        ("random_flash", "RandomFlashEffect"),
        ("gradient", "TemporalGradientEffect"),
    ],
)
def test_real_effect_activation_render_shutdown_and_reactivation(
    module: str, name: str
) -> None:
    import importlib

    import numpy as np

    cls = getattr(importlib.import_module("ledfx.effects." + module), name)
    clock = [1.0]
    restore = install_temporal_render_prototype(
        cls, cadence=True, clock=lambda: clock[0]
    )
    effect = cls(SimpleNamespace(), cls.config_model().model_validate({}))
    virtual = SimpleNamespace(id="benchmark", effective_pixel_count=32)
    try:
        for _ in range(2):
            effect.activate(virtual)
            assert effect._thread is None
            for _ in range(10):
                clock[0] += 0.21
                effect.now = clock[0]
                effect.render()
                assert effect.pixels.shape == (32, 3)
                assert np.isfinite(effect.pixels).all()
            effect.deactivate()
            assert effect._thread is None
            assert not effect._active
    finally:
        if effect._active:
            effect.deactivate()
        restore()


def test_fade_cadence_preserves_phase_and_rainbow_exposes_quantization() -> None:
    """A 500 Hz renderer must not advance Fade 500 times/s; ticks still quantize."""
    from ledfx.effects.fade import FadeEffect
    from ledfx.effects.rainbow import RainbowEffect

    for cls, speed in ((FadeEffect, 0.5), (RainbowEffect, 6)):
        clock = [0.0]
        restore = install_temporal_render_prototype(
            cls, cadence=True, clock=lambda: clock[0]
        )
        effect = cls(
            SimpleNamespace(), cls.config_model().model_validate({"speed": speed})
        )
        try:
            effect.activate(SimpleNamespace(id="benchmark", effective_pixel_count=32))
            for frame in range(1000):
                clock[0] = frame / 500
                effect.render()
            if isinstance(effect, FadeEffect):
                assert effect.idx == pytest.approx(10 * 0.0015)
            else:
                # 1/60-second ticks round to the next 2ms render opportunity:
                # about 112 updates in two seconds, not the ideal 120.
                assert effect._hue == pytest.approx(0.1 + 112 * 0.01)
        finally:
            effect.deactivate()
            restore()
