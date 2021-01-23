import logging

import numpy as np
import voluptuous as vol

from ledfx.effects import Effect

_LOGGER = logging.getLogger(__name__)
_rate = 60


@Effect.no_registration
class ModulateEffect(Effect):
    """
    Extension of TemporalEffect that applies brightness modulation
    over the strip. This is intended to allow more static effects like
    Gradient or singleColor to have some visual movement.
    """

    # _thread_active = False
    # _thread = None

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "modulate",
                description="Brightness modulation",
                default=False,
            ): bool,
            vol.Optional(
                "modulation_effect",
                default="sine",
                description="Choose an animation",
            ): vol.In(list(["sine", "breath"])),
            vol.Optional(
                "modulation_speed",
                default=0.5,
                description="Animation speed",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1)),
        }
    )

    def config_updated(self, config):
        self._counter = 0

        # temporal array for breathing cycle
        self._breath_cycle = np.linspace(0, 9, 9 * _rate)
        self._breath_cycle[: 3 * _rate] = (
            0.4 * np.sin(self._breath_cycle[: 3 * _rate] - (np.pi / 2)) + 0.6
        )
        self._breath_cycle[3 * _rate :] = (
            np.exp(3 - self._breath_cycle[3 * _rate :]) + 0.2
        )

    def modulate(self, pixels):
        """
        Call this function from the effect
        """
        if not self._config["modulate"]:
            return pixels

        if self._config["modulation_effect"] == "sine":
            self._counter += 0.1 * self._config["modulation_speed"] / np.pi
            if self._counter >= 2 * np.pi:
                self._counter = 0
            overlay = np.linspace(
                self._counter + np.pi, self._counter, self.pixel_count
            )
            overlay = np.tile(0.3 * np.sin(overlay) + 0.4, (3, 1)).T
            return pixels * overlay

        elif self._config["modulation_effect"] == "breath":
            self._counter += self._config["modulation_speed"]
            if int(self._counter) >= 9 * _rate - 1:
                self._counter = 0

            pixels[
                int(
                    self._breath_cycle[int(self._counter)] * self.pixel_count
                ) :,
                :,
            ] = 0
            return pixels

        else:
            # LOG that unknown mode selected somehow?
            return pixels
