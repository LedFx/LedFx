import logging
import timeit

import voluptuous as vol

from ledfx.effects import Effect
from ledfx.events import VirtualDiagEvent

_LOGGER = logging.getLogger(__name__)


@Effect.no_registration
class LogSec(Effect):

    ADVANCED_KEYS = ["diag"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "diag",
                description="diagnostic enable",
                default=False,
            ): bool,
            vol.Optional(
                "advanced",
                description="enable advanced options",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        """
        Initializes the LogSec effect, setting up frame counting, timing, and render statistics.

        Initializes internal state for FPS measurement, render time tracking (including min, max, and total times), and timing markers based on the current timer.
        """
        super().__init__(ledfx, config)
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.r_total = 0.0
        self.r_min = 1.0
        self.r_max = 0.0
        self.passed = 0
        self.current_time = timeit.default_timer()
        self.lasttime = int(self.current_time)

    def on_activate(self, pixel_count):
        """
        Resets the internal timer when the effect is activated.

        Args:
            pixel_count: The number of pixels for the effect (unused).
        """
        self.current_time = timeit.default_timer()

    def config_updated(self, config):
        self.diag = self._config["diag"]

    def log_sec(self):
        was = self.current_time
        self.current_time = timeit.default_timer()
        self.passed = self.current_time - was

        result = False
        if self.diag:
            nowint = int(self.current_time)
            # if now just rolled over a second boundary
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                result = True
            else:
                self.frame += 1
            self.lasttime = nowint
        self.log = result

    def try_log(self):
        """
        Logs and reports frame rendering diagnostics if logging is enabled.

        Measures render time for the current frame, updates minimum, maximum, and total render times, and, if logging is flagged, computes and logs FPS and timing statistics. Fires a diagnostic event with the collected metrics and resets render time statistics for the next interval.

        Returns:
            True if diagnostics were logged and reported during this call; otherwise, False.
        """
        end = timeit.default_timer()
        r_time = end - self.current_time
        self.r_total += r_time
        if r_time < self.r_min:
            self.r_min = r_time
        if r_time > self.r_max:
            self.r_max = r_time
        if self.log is True:
            if self.fps > 0:
                r_avg = self.r_total / self.fps
            else:
                r_avg = 0.0
            cycle = end - self.last
            sleep = self.current_time - self.last
            _LOGGER.warning(
                f"{self.name}: FPS {self.fps} Render avg:{r_avg:0.6f} min:{self.r_min:0.06f} max:{self.r_max:0.06f} Cycle: {cycle:0.6f} Sleep: {sleep:0.6f}"
            )
            self._ledfx.events.fire_event(
                VirtualDiagEvent(
                    self.id,
                    self.fps,
                    r_avg,
                    self.r_min,
                    self.r_max,
                    cycle,
                    sleep,
                )
            )
            self.r_min = 1.0
            self.r_max = 0.0
            self.r_total = 0.0
        self.last = end
        return self.log
