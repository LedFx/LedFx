import os.path
from random import randint

import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.effectlets import EFFECTLET_LIST


class RainAudioEffect(AudioReactiveEffect):

    NAME = "Rain"
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
                "lows_colour",
                description="Colour for low sounds, ie beats",
                default="white",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "mids_colour",
                description="Colour for mid sounds, ie vocals",
                default="red",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "high_colour",
                description="Colour for high sounds, ie hi hat",
                default="blue",
            ): vol.In(list(COLORS.keys())),
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
                default=EFFECTLET_LIST[0],
            ): vol.In(list(EFFECTLET_LIST)),
        }
    )

    def config_updated(self, config):
        # this could be cleaner but it's temporary, until an effectlet class is
        # made to handle this stuff
        self.drop_animation = np.load(
            os.path.join(
                os.path.dirname(__file__),
                "effectlets/" + config["raindrop_animation"],
            )
        )

        self.n_frames, self.frame_width = np.shape(self.drop_animation)
        self.frame_centre_index = self.frame_width // 2
        self.frame_side_lengths = self.frame_centre_index - 1

        self.intensity_filter = self.create_filter(
            alpha_decay=0.5, alpha_rise=0.99
        )
        self.filtered_intensities = np.zeros(3)

        self.first_call = True

    def new_drop(self, location, colour):
        """
        Add a new drop animation
        TODO (?) this method overwrites a running drop animation in the same location
        would need a significant restructure to fix
        """
        self.drop_frames[location] = 1
        self.drop_colours[:, location] = colour

    def update_drop_frames(self):
        # TODO these should be made in config_updated or __init__ when pixel
        # count is available there
        if self.first_call:
            self.drop_frames = np.zeros(self.pixel_count, dtype=int)
            self.drop_colours = np.zeros((3, self.pixel_count))
            self.first_call = False

        # Set any drops at final frame back to 0 and remove colour data
        finished_drops = self.drop_frames >= self.n_frames - 1
        self.drop_frames[finished_drops] = 0
        self.drop_colours[:, finished_drops] = 0
        # Add one to any running frames
        self.drop_frames[self.drop_frames > 0] += 1

    def get_drops(self):
        """
        Get coloured pixel data of all drops overlaid
        """
        # 2d array containing colour intensity data
        overlaid_frames = np.zeros((3, self.pixel_count + self.frame_width))
        # Indexes of active drop animations
        drop_indices = np.flatnonzero(self.drop_frames)
        # TODO vectorize this to remove for loop
        for index in drop_indices:
            coloured_frame = [
                self.drop_animation[self.drop_frames[index]]
                * self.drop_colours[colour, index]
                for colour in range(3)
            ]
            overlaid_frames[
                :, index : index + self.frame_width
            ] += coloured_frame

        np.clip(overlaid_frames, 0, 255, out=overlaid_frames)
        return overlaid_frames[
            :,
            self.frame_side_lengths : self.frame_side_lengths
            + self.pixel_count,
        ].T

    def audio_data_updated(self, data):

        # Calculate the low, mids, and high indexes scaling based on the pixel
        # count
        intensities = np.array(
            [
                np.mean(data.melbank_lows()),
                np.mean(data.melbank_mids()),
                np.mean(data.melbank_highs()),
            ]
        )

        self.update_drop_frames()

        if (
            intensities[0] - self.filtered_intensities[0]
            > self._config["lows_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                COLORS.get(self._config["lows_colour"]),
            )
        if (
            intensities[1] - self.filtered_intensities[1]
            > self._config["mids_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                COLORS.get(self._config["mids_colour"]),
            )
        if (
            intensities[2] - self.filtered_intensities[2]
            > self._config["high_sensitivity"]
        ):
            self.new_drop(
                randint(0, self.pixel_count - 1),
                COLORS.get(self._config["high_colour"]),
            )

        self.filtered_intensities = self.intensity_filter.update(intensities)

        self.pixels = self.get_drops()
