import voluptuous as vol

from ledfx.effects import fill_rainbow
from ledfx.effects.temporal import TemporalEffect


class RainbowEffect(TemporalEffect):
    NAME = "Rainbow"
    CATEGORY = "Non-Reactive"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency",
                description="Frequency of the effect curve",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
        }
    )

    _hue = 0.1

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        hue_delta = self._config["frequency"] / self.pixel_count
        self.pixels = fill_rainbow(self.pixels, self._hue, hue_delta)

        self._hue = self._hue + 0.01
