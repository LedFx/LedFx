import logging

import launchpad_py as launchpad
import voluptuous as vol
import timeit

from ledfx.devices import MidiDevice, fps_validator
from ledfx.utils import AVAILABLE_FPS

_LOGGER = logging.getLogger(__name__)


def dump_methods(lp_instance, device_type):
    # create an instance
    if lp_instance is None:
        lp_instance = launchpad.Launchpad()

    # List the class's methods
    _LOGGER.debug(" - Available methods:")
    for mName in sorted(dir(lp_instance)):
        if mName.find("__") >= 0:
            continue

        if callable(getattr(lp_instance, mName)):
            _LOGGER.debug(f"     {mName}()")

def validate_launchpad(lp_instance):
    if lp_instance is None:
        lp_instance = launchpad.Launchpad()

    # try the first Mk2
    if lp_instance.Check(0, "mk2"):
        lp_instance = launchpad.LaunchpadMk2()
        if lp_instance.Open(0, "mk2"):
            _LOGGER.info(" - Launchpad Mk2: OK")
        else:
            _LOGGER.error(" - Launchpad Mk2: ERROR")
            return

    # try the first Mini Mk3
    elif lp_instance.Check(1, "minimk3"):
        lp_instance = launchpad.LaunchpadMiniMk3()
        if lp_instance.Open(1, "minimk3"):
            _LOGGER.info(" - Launchpad Mini Mk3: OK")
        else:
            _LOGGER.error(" - Launchpad Mini Mk3: ERROR")
            return

    # try the first Pro
    elif lp_instance.Check(0, "pad pro"):
        lp_instance = launchpad.LaunchpadPro()
        if lp_instance.Open(0, "pad pro"):
            _LOGGER.info(" - Launchpad Pro: OK")
        else:
            _LOGGER.error(" - Launchpad Pro: ERROR")
            return

    # try the first Pro Mk3
    elif lp_instance.Check(0, "promk3"):
        lp_instance = launchpad.LaunchpadProMk3()
        if lp_instance.Open(0):
            _LOGGER.info(" - Launchpad Pro Mk3: OK")
        else:
            _LOGGER.error(" - Launchpad Pro Mk3: ERROR")
            return

    # try the first X
    # Notice that this is already built-in in the LPX class' methods Check() and Open,
    # but we're using the one from above!
    elif lp_instance.Check(1, "Launchpad X") or lp_instance.Check(1, "LPX"):
        lp_instance = launchpad.LaunchpadLPX()
        # Open() includes looking for "LPX" and "Launchpad X"
        if lp_instance.Open(1):
            _LOGGER.info(" - Launchpad X: OK")
        else:
            _LOGGER.error(" - Launchpad X: ERROR")
            return

    # nope
    else:
        _LOGGER.error(" - No Launchpad available")
        return
    return lp_instance


class LaunchpadDevice(MidiDevice):
    """Launchpad device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=81,
                ): vol.All(int, vol.Range(min=1)),
                vol.Required(
                    "rows",
                    description="Number of individual rows",
                    default=8,
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(
                    "refresh_rate",
                    description="Target rate that pixels are sent to the device",
                    default=next(
                        (f for f in AVAILABLE_FPS if f >= 20),
                        list(AVAILABLE_FPS)[-1],
                    ),
                ): fps_validator,
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def flush(self, data):
        try:
            start = timeit.default_timer()
            count = 0
            tooks = []
            for idx, pixel in enumerate(data):
                count += 1
                pixel = pixel.astype(int)
                x, y = divmod(idx, 9)
                r, g, b = pixel[:] // 4
                begin = timeit.default_timer()
                self.lp.LedCtrlXY(x, y, r, g, b)
                one_took = timeit.default_timer() - begin
                tooks.append(one_took)
            took = timeit.default_timer() - start
#            _LOGGER.info(f"Updated Pixels: {count} took: {took} each: {sum(tooks) / len(tooks)} ")

        except RuntimeError:
            _LOGGER.error("Error in Launchpad handling")

    def activate(self):
        self.lp = launchpad.Launchpad()
        self.lp = validate_launchpad(self.lp)
        super().activate()

    def deactivate(self):
        self.lp.Reset()
        self.lp.Close()
        super().deactivate()
