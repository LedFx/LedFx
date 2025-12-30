import logging
import timeit

from ledfx.effects.utils.get_info import get_info_async
from ledfx.events import VirtualDiagEvent
from ledfx.utils import Teleplot

_LOGGER = logging.getLogger(__name__)


class Phy:
    def __init__(
        self, fps=None, ver=None, n=None, name=None, rssi=None, qual=None
    ):
        """
        fps: fps of physical device
        ver: Version of the physical device
        n: Number of physical LEDs
        name: Name of the physical device
        rssi: RSSI of the physical device
        qual: Signal quality of the physical device
        """
        self.fps = fps
        self.ver = ver
        self.n = n
        self.name = name
        self.rssi = rssi
        self.qual = qual

    def __repr__(self):
        return repr(self.__dict__)


class LogSecHelper:
    def __init__(self, effect):
        self.effect = effect
        self.reset()

    def reset(self):
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.r_total = 0.0
        self.r_min = 1.0
        self.r_max = 0.0
        self.phy = Phy()
        self.log = False
        self.diag = False
        self.current_time = timeit.default_timer()
        self.lasttime = int(self.current_time)

    def handle_info_response(self, data):
        self.phy.fps = data.get("leds", {}).get("fps")
        self.phy.ver = data.get("ver")
        self.phy.n = data.get("leds", {}).get("count")
        self.phy.name = data.get("name")
        self.phy.rssi = data.get("wifi", {}).get("rssi")
        self.phy.qual = data.get("wifi", {}).get("signal")

        _LOGGER.info(
            f"{self.effect._virtual.name}:{self.effect.name} wled info: {self.phy}"
        )

    def log_sec(self, current_time):
        self.current_time = current_time

        result = False
        if self.diag:
            nowint = int(self.current_time)
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                if self.effect._virtual and self.effect._virtual.is_device:
                    device_id = self.effect._virtual.is_device
                    device = self.effect._ledfx.devices.get(device_id)
                    if device and device.type == "wled":
                        get_info_async(
                            self.effect._ledfx.loop,
                            device._destination,
                            self.handle_info_response,
                        )
                result = True
            else:
                self.frame += 1
            self.lasttime = nowint
        self.log = result

    def try_log(self):

        if self.diag:
            end = timeit.default_timer()
            r_time = end - self.current_time
            self.r_total += r_time
            self.r_min = min(self.r_min, r_time)
            self.r_max = max(self.r_max, r_time)

            if self.log and self.effect._virtual:
                r_avg = (self.r_total / self.fps * 1000) if self.fps > 0 else 0.0
                r_min_ms = self.r_min * 1000
                r_max_ms = self.r_max * 1000
                cycle = (end - self.last) * 1000
                sleep = (self.current_time - self.last) * 1000

                _LOGGER.warning(
                    f"{self.effect.name}: FPS {self.fps} Render avg:{r_avg:0.3f} min:{r_min_ms:0.3f} max:{r_max_ms:0.3f} Cycle: {cycle:0.3f} Sleep: {sleep:0.3f} (ms)"
                )
                Teleplot.send(f"{self.effect._virtual.id}_avg_ms:{r_avg}")

                self.effect._ledfx.events.fire_event(
                    VirtualDiagEvent(
                        self.effect._virtual.id,
                        self.fps,
                        r_avg,
                        self.r_min,
                        self.r_max,
                        cycle,
                        sleep,
                        self.phy.__dict__,
                    )
                )
                self.r_min = 1.0
                self.r_max = 0.0
                self.r_total = 0.0
            self.last = end
        return self.log
