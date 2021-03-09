import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect


class EnergyAudioEffect(AudioReactiveEffect):

    NAME = "Energy"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=4.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=True,
            ): bool,
            vol.Optional(
                "color_cycler",
                description="Change colors in time with the beat",
                default=False,
            ): bool,
            vol.Optional(
                "color_lows",
                description="Color of low, bassy sounds",
                default="red",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "color_mids",
                description="Color of midrange sounds",
                default="green",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "color_high",
                description="Color of high sounds",
                default="blue",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "sensitivity",
                description="Responsiveness to changes in sound",
                default=0.85,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.3, max=0.99)),
            vol.Optional(
                "mixing_mode",
                description="Mode of combining each frequencies' colours",
                default="overlap",
            ): vol.In(["additive", "overlap"]),
        }
    )

    def config_updated(self, config):
        # scale decay value between 0.1 and 0.2
        decay_sensitivity = (self._config["sensitivity"] - 0.2) * 0.25
        self._p_filter = self.create_filter(
            alpha_decay=decay_sensitivity,
            alpha_rise=self._config["sensitivity"],
        )

        self.color_cycler = 0

        self.lows_colour = np.array(
            COLORS[self._config["color_lows"]], dtype=float
        )
        self.mids_colour = np.array(
            COLORS[self._config["color_mids"]], dtype=float
        )
        self.high_colour = np.array(
            COLORS[self._config["color_high"]], dtype=float
        )

    def audio_data_updated(self, data):

        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count
        lows_idx = int(np.mean(self.pixel_count * data.melbank_lows()))
        mids_idx = int(np.mean(self.pixel_count * data.melbank_mids()))
        highs_idx = int(np.mean(self.pixel_count * data.melbank_highs()))

        if self._config["color_cycler"]:
            beat_now = data.oscillator()
            if beat_now:
                # Cycle between 0,1,2 for lows, mids and highs
                self.color_cycler = (self.color_cycler + 1) % 3
                color = np.random.choice(list(COLORS.keys()))

                if self.color_cycler == 0:
                    self.lows_colour = COLORS[color]
                elif self.color_cycler == 1:
                    self.mids_colour = COLORS[color]
                elif self.color_cycler == 2:
                    self.high_colour = COLORS[color]

        # Build the new energy profile based on the mids, highs and lows setting
        # the colors as red, green, and blue channel respectively
        p = np.zeros(np.shape(self.pixels))
        if self._config["mixing_mode"] == "additive":
            p[:lows_idx] = self.lows_colour
            p[:mids_idx] += self.mids_colour
            p[:highs_idx] += self.high_colour
        elif self._config["mixing_mode"] == "overlap":
            p[:lows_idx] = self.lows_colour
            p[:mids_idx] = self.mids_colour
            p[:highs_idx] = self.high_colour

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(p)
