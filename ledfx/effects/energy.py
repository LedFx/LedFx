from typing import Literal

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect


class EnergyAudioEffect(AudioReactiveEffect):
    NAME = "Energy"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True

    class Config(AudioReactiveEffect.Config):
        blur: CoercedFloat = Field(
            4.0, description="Amount to blur the effect", ge=0.0, le=10
        )
        mirror: bool = Field(True, description="Mirror the effect")
        color_cycler: bool = Field(
            False, description="Change colors in time with the beat"
        )
        color_lows: Color = Field("#FF0000", description="Color of low, bassy sounds")
        color_mids: Color = Field("#00FF00", description="Color of midrange sounds")
        color_high: Color = Field("#0000FF", description="Color of high sounds")
        sensitivity: CoercedFloat = Field(
            0.6, description="Responsiveness to changes in sound", ge=0.3, le=0.99
        )
        mixing_mode: Literal["additive", "overlap"] = Field(
            "additive", description="Mode of combining each frequencies' colors"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.p = np.zeros((pixel_count, 3))
        self.beat_now = False
        self.lows_idx = 0
        self.mids_idx = 0
        self.highs_idx = 0

        # make sure the p_filter is flushed from prior lifecycles
        # prevent crashes from segment edit / led count changes
        if self._p_filter is not None:
            self._p_filter.value = None

    def config_updated(self, config):
        # scale decay value between 0.1 and 0.2
        decay_sensitivity = (self.config.sensitivity - 0.1) * 0.7
        self._p_filter = self.create_filter(
            alpha_decay=decay_sensitivity,
            alpha_rise=self.config.sensitivity,
        )

        self.color_cycler = 0

        self.lows_color = np.array(parse_color(self.config.color_lows), dtype=float)
        self.mids_color = np.array(parse_color(self.config.color_mids), dtype=float)
        self.high_color = np.array(parse_color(self.config.color_high), dtype=float)

        self._multiplier = 1.6 - self.config.blur / 17

    def audio_data_updated(self, data):
        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count

        self.lows_idx, self.mids_idx, self.highs_idx = (
            int(self._multiplier * self.pixel_count * np.mean(i))
            for i in self.melbank_thirds(filtered=False)
        )
        self.beat_now = data.volume_beat_now()

    def render(self):
        if self.config.color_cycler and self.beat_now:
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
        if self.config.mixing_mode == "additive":
            self.p[: self.lows_idx] = self.lows_color
            self.p[: self.mids_idx] += self.mids_color
            self.p[: self.highs_idx] += self.high_color
        elif self.config.mixing_mode == "overlap":
            self.p[: self.lows_idx] = self.lows_color
            self.p[: self.mids_idx] = self.mids_color
            self.p[: self.highs_idx] = self.high_color

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(self.p)
