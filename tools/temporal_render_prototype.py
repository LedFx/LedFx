"""Benchmark-only temporal backpressure experiment, not production timing.

Compute one temporal frame on demand in the target virtual's render thread.
This intentionally ignores effect_loop's timing multiplier and speed pacing;
it demonstrates compute/output capacity, not equivalent animation timing.
Fixtures and other virtuals retain their normal threads. Call restore on exit
when used outside the short-lived benchmark worker.
"""


def install_temporal_render_prototype(effect_class):
    from ledfx.effects.temporal import TemporalEffect

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

    def render(effect):
        if is_target(effect):
            effect.effect_loop()
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
