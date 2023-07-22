import logging
import time

# from ledfx.effects.audio import AudioReactiveEffect
from threading import Thread

import voluptuous as vol

from ledfx.effects import Effect

_LOGGER = logging.getLogger(__name__)

# use 10 frames per second as default rate at 1x multiplier
# windows pre 3.11 will cap at 64Hz max for now,
# other OS at 100Hz with speed slider ot 10
DEFAULT_RATE = 1.0 / 10.0


@Effect.no_registration
class TemporalEffect(Effect):
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                default=1.0,
                description="Speed of the effect",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._thread_active = False
        self._thread = None

    def thread_function(self):
        while self._thread_active:
            startTime = time.time()

            # Treat the return value of the effect loop as a speed modifier
            # such that effects that are naturally faster or slower can have
            # a consistent feel.
            sleepInterval = self.effect_loop()
            if sleepInterval is None:
                sleepInterval = 1.0
            sleepInterval = sleepInterval * DEFAULT_RATE

            # Calculate the time to sleep accounting for potential heavy
            # frame assembly operations
            timeToSleep = (sleepInterval / self._config["speed"]) - (
                time.time() - startTime
            )
            if timeToSleep < 0.001:
                timeToSleep = 0.001
            time.sleep(timeToSleep)

    def effect_loop(self):
        """
        Triggered periodically based on the effect speed and
        any additional effect modifiers
        """
        pass

    def on_activate(self, pixel_count):
        self._thread_active = True
        self._thread = Thread(target=self.thread_function)
        self._thread.start()

    def deactivate(self):
        if self._thread_active:
            self._thread_active = False
            self._thread.join()
            self._thread = None

        super().deactivate()
