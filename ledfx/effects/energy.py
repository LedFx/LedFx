import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect


class EnergyAudioEffect(AudioReactiveEffect):
    NAME = "Energy"
    CATEGORY = "Classic"

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
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "color_mids",
                description="Color of midrange sounds",
                default="#00FF00",
            ): validate_color,
            vol.Optional(
                "color_high",
                description="Color of high sounds",
                default="#0000FF",
            ): validate_color,
            vol.Optional(
                "sensitivity",
                description="Responsiveness to changes in sound",
                default=0.6,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.3, max=0.99)),
            vol.Optional(
                "mixing_mode",
                description="Mode of combining each frequencies' colors",
                default="additive",
            ): vol.In(["additive", "overlap"]),
        }
    )

    def on_activate(self, pixel_count):
        self.p = np.zeros((pixel_count, 3))
        self.beat_now = False
        self.lows_idx = 0
        self.mids_idx = 0
        self.highs_idx = 0

    def config_updated(self, config):
        # scale decay value between 0.1 and 0.2
        decay_sensitivity = (self._config["sensitivity"] - 0.1) * 0.7
        self._p_filter = self.create_filter(
            alpha_decay=decay_sensitivity,
            alpha_rise=self._config["sensitivity"],
        )

        self.color_cycler = 0

        self.lows_color = np.array(
            parse_color(self._config["color_lows"]), dtype=float
        )
        self.mids_color = np.array(
            parse_color(self._config["color_mids"]), dtype=float
        )
        self.high_color = np.array(
            parse_color(self._config["color_high"]), dtype=float
        )

        self._multiplier = 1.6 - self._config["blur"] / 17

    def audio_data_updated(self, data):
        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count

        self.lows_idx, self.mids_idx, self.highs_idx = (
            int(self._multiplier * self.pixel_count * np.mean(i))
            for i in self.melbank_thirds(filtered=False)
        )
        self.beat_now = data.volume_beat_now()

    def render(self):
        if self._config["color_cycler"]:
            if self.beat_now:
                # Cycle between 0,1,2 for lows, mids and highs
                self.color_cycler = (self.color_cycler + 1) % 3

                color_raw = self._ledfx.colors.get_all(merged=False)
                if len(color_raw[1]) > 0:  # if there are user colors, use them
                    color_list = list(color_raw[1].values())
                else:
                    color_list = list(color_raw[0].values())
                color = parse_color(np.random.choice(color_list))

                if self.color_cycler == 0:
                    self.lows_color = color
                elif self.color_cycler == 1:
                    self.mids_color = color
                elif self.color_cycler == 2:
                    self.high_color = color

        # Build the new energy profile based on the mids, highs and lows setting
        # the colors as red, green, and blue channel respectively
        self.p[:, :] = 0
        if self._config["mixing_mode"] == "additive":
            self.p[: self.lows_idx] = self.lows_color
            self.p[: self.mids_idx] += self.mids_color
            self.p[: self.highs_idx] += self.high_color
        elif self._config["mixing_mode"] == "overlap":
            self.p[: self.lows_idx] = self.lows_color
            self.p[: self.mids_idx] = self.mids_color
            self.p[: self.highs_idx] = self.high_color

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(self.p)
