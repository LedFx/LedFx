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
        super().__init__(ledfx, config)
        self.lasttime = 0
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.r_total = 0.0
        self.passed = 0
        self.current_time = timeit.default_timer()

    def on_activate(self, pixel_count):
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
        Logs frame rate and timing diagnostics if a new second boundary has been reached.

        Calculates and logs frames per second, average render time, cycle time, and sleep time when diagnostics are enabled and a new second has elapsed. Fires a `VirtualDiagEvent` with the collected metrics. Returns whether a new second boundary was crossed.

        Returns:
            True if a new second boundary was crossed and diagnostics were logged; otherwise, False.
        """
        end = timeit.default_timer()
        r_time = end - self.current_time
        self.r_total += r_time
        if self.log is True:
            if self.fps > 0:
                r_avg = self.r_total / self.fps
            else:
                r_avg = 0.0
            cycle = end - self.last
            sleep = self.current_time - self.last
            _LOGGER.warning(
                f"{self.name}: FPS {self.fps} Render:{r_avg:0.6f} Cycle: {cycle:0.6f} Sleep: {sleep:0.6f}"
            )
            self._ledfx.events.fire_event(
                VirtualDiagEvent(self.id, self.fps, r_avg, cycle, sleep)
            )
            self.r_total = 0.0
        self.last = end
        return self.log
