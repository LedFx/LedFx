"""Benchmark-only temporal backpressure experiment, not production timing.

Compute one temporal frame on demand in the target virtual's render thread.
This intentionally ignores effect_loop's timing multiplier and speed pacing;
it demonstrates compute/output capacity, not equivalent animation timing.
With cadence=True, retain speed/returned interval and the 1ms minimum yield.
Updates are quantized to render opportunities; slow renderers lose ticks, so
this still is not a general elapsed-time animation solution.
Fixtures and other virtuals retain their normal threads. Call restore on exit
when used outside the short-lived benchmark worker.
"""

import time


def install_temporal_render_prototype(
    effect_class, *, cadence=False, clock=time.monotonic
):
    from ledfx.effects.temporal import DEFAULT_RATE, TemporalEffect

    original_activate = TemporalEffect.on_activate
    original_render = effect_class.render
    owned_render = effect_class.__dict__.get("render")

    def is_target(effect):
        return (
            isinstance(effect, effect_class)
            and getattr(effect._virtual, "id", None) == "benchmark"
        )

    def activate(effect, pixel_count):
        if not is_target(effect):
            original_activate(effect, pixel_count)
        else:
            effect._benchmark_due = clock()

    def render(effect):
        if is_target(effect):
            start = clock()
            if cadence and start < effect._benchmark_due:
                return
            interval = effect.effect_loop()
            if cadence:
                period = (
                    DEFAULT_RATE
                    * (1.0 if interval is None else interval)
                    / effect.config.speed
                )
                # Match the original start-relative interval and minimum yield.
                # Late ticks are coalesced, never replayed in a catch-up burst.
                effect._benchmark_due = max(start + period, clock() + 0.001)
        else:
            original_render(effect)

    TemporalEffect.on_activate = activate
    effect_class.render = render

    def restore():
        TemporalEffect.on_activate = original_activate
        if owned_render is None:
            delattr(effect_class, "render")
        else:
            effect_class.render = owned_render

    return restore
