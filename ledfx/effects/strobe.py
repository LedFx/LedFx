import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class Strobe(AudioReactiveEffect, GradientEffect):
    MAPPINGS = {
        "1/1 (.,. )": 1,
        "1/2 (.-. )": 2,
        "1/4 (.o. )": 4,
        "1/8 (◉◡◉ )": 8,
        "1/16 (◉﹏◉ )": 16,
        "1/32 (⊙▃⊙ )": 32,
    }

    NAME = "BPM Strobe"
    CATEGORY = "BPM"
    HIDDEN_KEYS = ["gradient_roll"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "strobe_frequency",
                description="How many strobes per beat",
                default=list(MAPPINGS.keys())[1],
            ): vol.In(list(MAPPINGS.keys())),
            vol.Optional(
                "strobe_decay",
                description="How rapidly a single strobe hit fades. Higher -> faster fade",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=10)),
            vol.Optional(
                "beat_decay",
                description="How much the strobes fade across the beat. Higher -> less bright strobes towards end of beat",
                default=2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
            vol.Optional(
                "strobe_pattern",
                description="When to fire (*) or skip (.) the strobe (Note that beat 1 is arbitrary)",
                default="****",
            ): vol.In(list(["****", "*.*.", ".*.*", "*...", "...*"])),
        }
    )

    def on_activate(self, pixel_count):
        self.color = self.get_gradient_color(0)
        self.strobe_brightness = 0

    def config_updated(self, config):
        self.freq = self.MAPPINGS[self._config["strobe_frequency"]]
        self.strobe_decay = self._config["strobe_decay"]
        self.beat_decay = self._config["beat_decay"]
        self.strobe_pattern = self._config["strobe_pattern"]

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
        self.pixels[:] = (
            self.color * self.strobe_brightness * self.strobe_brightness
        )
