import logging
import timeit

import voluptuous as vol

from ledfx.effects import Effect

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
        end = timeit.default_timer()
        r_time = end - self.current_time
        self.r_total += r_time
        if self.log is True:
            if self.fps > 0:
                r_avg = self.r_total / self.fps
            else:
                r_avg = 0.0
            _LOGGER.warning(
                f"{self.name}: FPS {self.fps} Render:{r_avg:0.6f} Cycle: {(end - self.last):0.6f} Sleep: {(self.current_time - self.last):0.6f}"
            )
            self.r_total = 0.0
        self.last = end
        return self.log
