import logging
import timeit

from ledfx.effects.utils.get_info import get_info_async
from ledfx.events import VirtualDiagEvent

_LOGGER = logging.getLogger(__name__)

class Phy:
    def __init__(self, f=-1, ver=None, n=-1, name=None, rssi=-1, qual=-1):
        """ 
        ver: Version of the physical device, if applicable.
        n: Number of physical LEDs, -1 if not applicable.
        name: Name of the physical device, if applicable.
        rssi: RSSI of the physical device, -1 if not applicable.
        qual: Signal quality of the physical device, -1 if not applicable."""

        self.f = f
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
        self.phy.f = data.get("leds", {}).get("fps", -1)
        self.phy.ver = data.get("ver", None)
        self.phy.n = data.get("leds", {}).get("count", -1)
        self.phy.name = data.get("name", None)
        self.phy.rssi = data.get("wifi", {}).get("rssi", -1)
        self.phy.qual = data.get("wifi", {}).get("signal", -1)

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

            if self.log:
                r_avg = self.r_total / self.fps if self.fps > 0 else 0.0
                cycle = end - self.last
                sleep = self.current_time - self.last

                _LOGGER.warning(
                    f"{self.effect.name}: FPS {self.fps} Render avg:{r_avg:0.6f} min:{self.r_min:0.6f} max:{self.r_max:0.6f} Cycle: {cycle:0.6f} Sleep: {sleep:0.6f}"
                )
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
