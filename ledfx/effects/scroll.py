import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect


class ScrollAudioEffect(AudioReactiveEffect):
    NAME = "Scroll"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True

    class Config(AudioReactiveEffect.Config):
        blur: CoercedFloat = Field(
            3.0, description="Amount to blur the effect", ge=0.0, le=10
        )
        mirror: bool = Field(True, description="Mirror the effect")
        speed: CoercedInt = Field(3, description="Speed of the effect", ge=1, le=10)
        decay: CoercedFloat = Field(
            0.97, description="Decay rate of the scroll", ge=0.8, le=1.0
        )
        threshold: CoercedFloat = Field(
            0.0,
            description="Cutoff for quiet sounds. Higher -> only loud sounds are detected",
            ge=0,
            le=1,
        )
        color_lows: Color = Field("#FF0000", description="Color of low, bassy sounds")
        color_mids: Color = Field("#00FF00", description="Color of midrange sounds")
        color_high: Color = Field("#0000FF", description="Color of high sounds")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.intensities = np.zeros(3)

    def config_updated(self, config):
        # TODO: Determine how buffers based on the pixels should be
        # allocated. Technically there is no guarantee that the effect
        # is bound to a device while the config gets updated. Might need
        # to move to a model where effects are created for a device and
        # must be destroyed and recreated to be moved to another device.
        self.lows_color = np.array(parse_color(self.config.color_lows), dtype=float)
        self.mids_color = np.array(parse_color(self.config.color_mids), dtype=float)
        self.high_color = np.array(parse_color(self.config.color_high), dtype=float)

        self.lows_cutoff = self.config.threshold / 10
        self.mids_cutoff = self.config.threshold / 8
        self.high_cutoff = self.config.threshold / 7

    def audio_data_updated(self, data):
        # Divide the melbank into lows, mids and highs
        self.intensities = np.fromiter(
            (i.max() ** 2 for i in self.melbank_thirds()), float
        )
        np.clip(self.intensities, 0, 1, out=self.intensities)

        if self.intensities[0] < self.lows_cutoff:
            self.intensities[0] = 0
        if self.intensities[1] < self.mids_cutoff:
            self.intensities[1] = 0
        if self.intensities[2] < self.high_cutoff:
            self.intensities[2] = 0

    def render(self):
        # Roll the effect and apply the decay
        speed = self.config.speed
        self.pixels[speed:, :] = self.pixels[:-speed, :]
        self.pixels *= self.config.decay

        self.pixels[:speed] = (
            self.lows_color * self.intensities[0]
            + self.mids_color * self.intensities[1]
            + self.high_color * self.intensities[2]
        )
