import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.color import parse_color, validate_color


class VuMeterAudioEffect(AudioReactiveEffect):
    NAME = "VuMeter"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS = ["background_color", "background_brightness","blur"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "peak_decay",
                description="Decay filter applied to raw volume to track peak, 0 is None",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "color_min",
                description="Color of min volume cutoff",
                default="#0000FF",
            ): validate_color,
            vol.Optional(
                "color_max",
                description="Color of max volume warning",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "color_mid",
                description="Color of heathy volume range",
                default="#00FF00",
            ): validate_color,
            vol.Optional(
                "color_peak",
                description="Color of peak inidicator",
                default="#FFFFFF",
            ): validate_color,
            vol.Optional(
                "peak_percent",
                description="% size of peak indicator that follows the filtered volume",
                default=1.0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
            vol.Optional(
                "max_volume",
                description="Cut off limit for max volume warning",
                default=0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        }
    )

    def on_activate(self, pixel_count):
        pass

    def config_updated(self, config):
        self.volume_peak_filter = self.create_filter(
            alpha_decay=self._config["peak_decay"], alpha_rise=0.99
        )

        self.color_peak = parse_color(self._config["color_peak"])
        self.color_min = parse_color(self._config["color_min"])
        self.color_max = parse_color(self._config["color_max"])
        self.color_mid = parse_color(self._config["color_mid"])
        self.peak_percent = self._config["peak_percent"]
        self.vol_max = self._config["max_volume"]
        self.volume = 0
        self.volume_peak = 0
        self.volume_min = 0

    def audio_data_updated(self, data):
        # grab the raw volume from the audio driver
        self.volume = self.audio.volume(filtered=False)
        self.volume_peak = self.volume_peak_filter.update(self.volume)
        self.volume_min = self.audio._config["min_volume"]

    def render(self):
        self.pixels = np.zeros(np.shape(self.pixels))

        volume = int(self.pixel_count * self.volume)
        volume_min = min(int(self.pixel_count * self.volume_min), self.pixel_count)
        volume_max = min(int(self.pixel_count * self.vol_max), self.pixel_count)

        self.pixels[0:min(volume_min, volume)] = self.color_min
        if volume > volume_min:
            self.pixels[volume_min:min(volume, volume_max)] = self.color_mid
        if volume > volume_max:
            self.pixels[volume_max:volume] = self.color_max
        if self.peak_percent > 0:
            peak_start = min(int(self.pixel_count * self.volume_peak), self.pixel_count)
            peak_end = min(peak_start + int(self.peak_percent * (self.pixel_count / 100.0)), self.pixel_count)
            self.pixels[peak_start:peak_end] = self.color_peak