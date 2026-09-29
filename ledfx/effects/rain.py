from random import randint
from typing import Annotated, Literal

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.droplets import DROPLET_NAMES, load_droplet


class RainAudioEffect(AudioReactiveEffect):
    NAME = "Rain"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True

    class Config(AudioReactiveEffect.Config):
        mirror: bool = Field(True, description="Mirror the effect")
        # TODO drops should be controlled by some sort of effectlet class,
        # which will provide a list of available drop names rather than just
        # this static range
        lows_color: Color = Field("white", description="color for low sounds, ie beats")
        pulse_strip: Literal["Off", "Lows", "Mids", "Highs"] = Field(
            "Off", description="Pulse the entire strip to the beat"
        )
        mids_color: Color = Field("red", description="color for mid sounds, ie vocals")
        high_color: Color = Field(
            "blue", description="color for high sounds, ie hi hat"
        )
        lows_sensitivity: CoercedFloat = Field(
            0.1, description="Sensitivity to low sounds", ge=0.03, le=0.3
        )
        mids_sensitivity: CoercedFloat = Field(
            0.05, description="Sensitivity to mid sounds", ge=0.03, le=0.3
        )
        high_sensitivity: CoercedFloat = Field(
            0.1, description="Sensitivity to high sounds", ge=0.03, le=0.3
        )
        raindrop_animation: Annotated[str, OneOf(DROPLET_NAMES)] = Field(
            "Ripple", description="Droplet animation style"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.drop_frames = np.zeros(self.pixel_count, dtype=int)
        self.drop_colors = np.zeros((3, self.pixel_count))
        self.pulse_pixels = np.zeros((self.pixel_count, 3))

    def config_updated(self, config):
        self.drop_animation = load_droplet(self.config.raindrop_animation)

        self.n_frames, self.frame_width = np.shape(self.drop_animation)
        self.frame_centre_index = self.frame_width // 2
        self.frame_side_lengths = self.frame_centre_index - 1

        self.intensity_filter = self.create_filter(alpha_decay=0.5, alpha_rise=0.99)
        self.filtered_intensities = np.zeros(3)

    def new_drop(self, location, color):
        """
        Add a new drop animation
        TODO (?) this method overwrites a running drop animation in the same location
        would need a significant restructure to fix
        """
        self.drop_frames[location] = 1
        self.drop_colors[:, location] = color

    def update_drop_frames(self):
        # Set any drops at final frame back to 0 and remove color data
        finished_drops = self.drop_frames >= self.n_frames - 1
        self.drop_frames[finished_drops] = 0
        self.drop_colors[:, finished_drops] = 0
        # Add one to any running frames
        self.drop_frames[self.drop_frames > 0] += 1

    def render(self):
        """
        Get colored pixel data of all drops overlaid
        """
        # 2d array containing color intensity data
        overlaid_frames = np.zeros((3, self.pixel_count + self.frame_width))
        # Indexes of active drop animations
        drop_indices = np.flatnonzero(self.drop_frames)
        # TODO vectorize this to remove for loop
        for index in drop_indices:
            if self.drop_frames[index] >= len(self.drop_animation):
                continue
            colored_frame = [
                self.drop_animation[self.drop_frames[index]]
                * self.drop_colors[color, index]
                for color in range(3)
            ]
            overlaid_frames[:, index : index + self.frame_width] += colored_frame

        self.pixels = overlaid_frames[
            :,
            self.frame_side_lengths : self.frame_side_lengths + self.pixel_count,
        ].T
        self.pixels += self.pulse_pixels
        # Decay the pulse pixels
        self.pulse_pixels = (self.pulse_pixels * 9) // 10

    def strip_pulse(self, color):
        """
        Set the pulse pixels to a color
        This color decays over time in render()

        Args:
            color: The color to pulse the strip
        """
        self.pulse_pixels = np.array([color])

    def audio_data_updated(self, data):
        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count
        intensities = np.fromiter((i.max() for i in self.melbank_thirds()), float)

        self.update_drop_frames()

        if intensities[0] - self.filtered_intensities[0] > self.config.lows_sensitivity:
            if self.config.pulse_strip == "Lows":
                self.strip_pulse(parse_color(self.config.lows_color))
            else:
                self.new_drop(
                    randint(0, self.pixel_count - 1),
                    parse_color(self.config.lows_color),
                )
        if intensities[1] - self.filtered_intensities[1] > self.config.mids_sensitivity:
            if self.config.pulse_strip == "Mids":
                self.strip_pulse(parse_color(self.config.mids_color))
            else:
                self.new_drop(
                    randint(0, self.pixel_count - 1),
                    parse_color(self.config.mids_color),
                )
        if intensities[2] - self.filtered_intensities[2] > self.config.high_sensitivity:
            if self.config.pulse_strip == "Highs":
                self.strip_pulse(parse_color(self.config.high_color))
            else:
                self.new_drop(
                    randint(0, self.pixel_count - 1),
                    parse_color(self.config.high_color),
                )

        self.filtered_intensities = self.intensity_filter.update(intensities)
