from random import randint

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.droplets import DROPLET_NAMES, load_droplet


class RainAudioEffect(AudioReactiveEffect):
    NAME = "Rain"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=True,
            ): bool,
            # TODO drops should be controlled by some sort of effectlet class,
            # which will provide a list of available drop names rather than just
            # this static range
            vol.Optional(
                "lows_color",
                description="color for low sounds, ie beats",
                default="white",
            ): validate_color,
            vol.Optional(
                "mids_color",
                description="color for mid sounds, ie vocals",
                default="red",
            ): validate_color,
            vol.Optional(
                "high_color",
                description="color for high sounds, ie hi hat",
                default="blue",
            ): validate_color,
            vol.Optional(
                "lows_sensitivity",
                description="Sensitivity to low sounds",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.03, max=0.3)),
            vol.Optional(
                "mids_sensitivity",
                description="Sensitivity to mid sounds",
                default=0.05,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.03, max=0.3)),
            vol.Optional(
                "high_sensitivity",
                description="Sensitivity to high sounds",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.03, max=0.3)),
            vol.Optional(
                "raindrop_animation",
                description="Droplet animation style",
                default=DROPLET_NAMES[0],
            ): vol.In(DROPLET_NAMES),
        }
    )

    def on_activate(self, pixel_count):
        self.drop_frames = np.zeros(self.pixel_count, dtype=int)
        self.drop_colors = np.zeros((3, self.pixel_count))

    def config_updated(self, config):
        self.drop_animation = load_droplet(config["raindrop_animation"])

        self.n_frames, self.frame_width = np.shape(self.drop_animation)
        self.frame_centre_index = self.frame_width // 2
        self.frame_side_lengths = self.frame_centre_index - 1

        self.intensity_filter = self.create_filter(
            alpha_decay=0.5, alpha_rise=0.99
        )
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
            colored_frame = [
                self.drop_animation[self.drop_frames[index]]
                * self.drop_colors[color, index]
                for color in range(3)
            ]
            overlaid_frames[
                :, index : index + self.frame_width
            ] += colored_frame

        np.clip(overlaid_frames, 0, 255, out=overlaid_frames)
        self.pixels = overlaid_frames[
            :,
            self.frame_side_lengths : self.frame_side_lengths
            + self.pixel_count,
        ].T

    def audio_data_updated(self, data):
        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count
        intensities = np.fromiter(
            (i.max() for i in self.melbank_thirds()), float
        )

        self.update_drop_frames()

        if (
            intensities[0] - self.filtered_intensities[0]
            > self._config["lows_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                parse_color(self._config["lows_color"]),
            )
        if (
            intensities[1] - self.filtered_intensities[1]
            > self._config["mids_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                parse_color(self._config["mids_color"]),
            )
        if (
            intensities[2] - self.filtered_intensities[2]
            > self._config["high_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                parse_color(self._config["high_color"]),
            )

        self.filtered_intensities = self.intensity_filter.update(intensities)
