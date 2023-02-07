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
        }
    )

    def on_activate(self, pixel_count):
        self.color = self.get_gradient_color(0)
        self.brightness = 0

    def config_updated(self, config):
        self.freq = self.MAPPINGS[self._config["strobe_frequency"]]
        self.strobe_decay = self._config["strobe_decay"]
        self.beat_decay = self._config["beat_decay"]

    def audio_data_updated(self, data):
        o = data.beat_oscillator()
        self.color = self.get_gradient_color(data.bar_oscillator() / 4)

        self.brightness = (
            ((-o % (1 / self.freq)) * self.freq) ** self.strobe_decay
        ) * (1 - o) ** self.beat_decay

    def render(self):
        self.pixels[:] = self.color * self.brightness
