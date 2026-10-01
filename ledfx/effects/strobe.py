from typing import Annotated, ClassVar, Literal

from pydantic import Field

from ledfx.configuration.fields import CoercedFloat, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect

STROBE_MAPPINGS: dict[str, int] = {
    "1/1 (.,. )": 1,
    "1/2 (.-. )": 2,
    "1/4 (.o. )": 4,
    "1/8 (◉◡◉ )": 8,
    "1/16 (◉﹏◉ )": 16,
    "1/32 (⊙▃⊙ )": 32,
}


class Strobe(AudioReactiveEffect, GradientEffect):
    MAPPINGS: ClassVar[dict[str, int]] = STROBE_MAPPINGS

    NAME = "BPM Strobe"
    CATEGORY = "BPM"
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]

    class Config(GradientEffect.Config):
        strobe_frequency: Annotated[str, OneOf(list(STROBE_MAPPINGS.keys()))] = Field(
            list(STROBE_MAPPINGS.keys())[1], description="How many strobes per beat"
        )
        strobe_decay: CoercedFloat = Field(
            1.5,
            description="How rapidly a single strobe hit fades. Higher -> faster fade",
            ge=1,
            le=10,
        )
        beat_decay: CoercedFloat = Field(
            2,
            description="How much the strobes fade across the beat. Higher -> less bright strobes towards end of beat",
            ge=0,
            le=10,
        )
        strobe_pattern: Literal["****", "*.*.", ".*.*", "*...", "...*"] = Field(
            "****",
            description="When to fire (*) or skip (.) the strobe (Note that beat 1 is arbitrary)",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.color = self.get_gradient_color(0)
        self.strobe_brightness = 0

    def config_updated(self, config):
        self.freq = self.MAPPINGS[self.config.strobe_frequency]
        self.strobe_decay = self.config.strobe_decay
        self.beat_decay = self.config.beat_decay
        self.strobe_pattern = self.config.strobe_pattern

    def audio_data_updated(self, data):
        o = data.beat_oscillator()
        bar = data.bar_oscillator()
        self.color = self.get_gradient_color(bar / 4)

        self.strobe_brightness = (
            ((-o % (1 / self.freq)) * self.freq) ** self.strobe_decay
        ) * (1 - o) ** self.beat_decay

        bar_idx = int(bar)
        strobe_mask = int(self.strobe_pattern[bar_idx] == "*")
        self.strobe_brightness *= strobe_mask

    def render(self):
        # brightness is now locally calculated and applied, as the original
        # implementation overrode self.brightness which then was used in the
        # get_pixels method of the base class, it was effectively applied twice
        # To get the same effect, now with self.brightness at 1, we have to apply
        # strobe_brightness here twice.
        self.pixels[:] = self.color * self.strobe_brightness * self.strobe_brightness
