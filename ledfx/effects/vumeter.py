from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect


class VuMeterAudioEffect(AudioReactiveEffect):
    NAME = "VuMeter"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS: ClassVar[list[str]] = [
        "background_color",
        "background_brightness",
        "blur",
    ]

    class Config(AudioReactiveEffect.Config):
        peak_decay: CoercedFloat = Field(
            0.1,
            description="Decay filter applied to raw volume to track peak, 0 is None",
            ge=0.01,
            le=0.3,
        )
        color_min: Color = Field("#0000FF", description="Color of min volume cutoff")
        color_max: Color = Field("#FF0000", description="Color of max volume warning")
        color_mid: Color = Field("#00FF00", description="Color of heathy volume range")
        color_peak: Color = Field("#FFFFFF", description="Color of peak inidicator")
        peak_percent: CoercedInt = Field(
            1,
            description="% size of peak indicator that follows the filtered volume",
            ge=0,
            le=5,
        )
        max_volume: CoercedFloat = Field(
            0.8, description="Cut off limit for max volume warning", ge=0, le=1
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        pass

    def config_updated(self, config):
        self.volume_peak_filter = self.create_filter(
            alpha_decay=self.config.peak_decay, alpha_rise=0.99
        )
        self.volume_min_peak_filter = self.create_filter(
            alpha_decay=self.config.peak_decay, alpha_rise=0.99
        )

        self.color_peak = parse_color(self.config.color_peak)
        self.color_min = parse_color(self.config.color_min)
        self.color_max = parse_color(self.config.color_max)
        self.color_mid = parse_color(self.config.color_mid)
        self.peak_percent = self.config.peak_percent
        self.vol_max = self.config.max_volume
        self.volume = 0
        self.volume_peak = 0
        self.volume_min_peak = 0
        self.volume_min = 0

    def audio_data_updated(self, data):
        # grab the raw volume from the audio driver
        self.volume = max(0, min(1, self.audio.volume(filtered=False)))
        self.volume_peak = self.volume_peak_filter.update(self.volume)
        self.volume_min_peak = self.volume_min_peak_filter.update(1 - self.volume)
        self.volume_min = self.audio._config["min_volume"]

    def render(self):
        self.pixels = np.zeros(np.shape(self.pixels))

        volume = int(self.pixel_count * self.volume)
        volume_min = min(int(self.pixel_count * self.volume_min), self.pixel_count)
        volume_max = min(int(self.pixel_count * self.vol_max), self.pixel_count)

        self.pixels[0 : min(volume_min, volume)] = self.color_min
        if volume > volume_min:
            self.pixels[volume_min : min(volume, volume_max)] = self.color_mid
        if volume > volume_max:
            self.pixels[volume_max:volume] = self.color_max
        if self.peak_percent > 0:
            peak_start = min(int(self.pixel_count * self.volume_peak), self.pixel_count)
            peak_end = min(
                peak_start + int(self.peak_percent * (self.pixel_count / 100.0)),
                self.pixel_count,
            )
            self.pixels[peak_start:peak_end] = self.color_peak
            min_peak_start = max(
                0,
                min(
                    int(self.pixel_count * (1 - self.volume_min_peak)),
                    self.pixel_count,
                ),
            )
            min_peak_end = max(
                0,
                min(
                    min_peak_start
                    - int(self.peak_percent * (self.pixel_count / 100.0)),
                    self.pixel_count,
                ),
            )
            self.pixels[min_peak_end:min_peak_start] = self.color_peak
