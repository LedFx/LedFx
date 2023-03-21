import logging

import launchpad_py as launchpad
import serial
import voluptuous as vol

from ledfx.devices import LaunchpadDevice

# from ledfx.devices import LaunchpadDevice, packets

_LOGGER = logging.getLogger(__name__)


def dump_methods(lp_instance, device_type):
    # # create an instance
    # lp = launchpad.Launchpad()
    if lp_instance is None:
        lp_instance = launchpad.Launchpad()

    # Clear the buffer because the Launchpad remembers everything
    # self.lp.ButtonFlush()

    # List the class's methods
    print(" - Available methods:")
    for mName in sorted(dir(lp_instance)):
        if mName.find("__") >= 0:
            continue

        if callable(getattr(lp_instance, mName)):
            print("     " + str(mName) + "()")
        device_type = "Launchpad"


def validate_launchpad(lp_instance):
    lp_instance = launchpad.Launchpad()

    # try the first Mk2
    if lp_instance.Check(0, "mk2"):
        lp_instance = launchpad.LaunchpadMk2()
        if lp_instance.Open(0, "mk2"):
            print(" - Launchpad Mk2: OK")
        else:
            print(" - Launchpad Mk2: ERROR")
            return

    # try the first Mini Mk3
    elif lp_instance.Check(1, "minimk3"):
        lp_instance = launchpad.LaunchpadMiniMk3()
        if lp_instance.Open(1, "minimk3"):
            print(" - Launchpad Mini Mk3: OK")
        else:
            print(" - Launchpad Mini Mk3: ERROR")
            return

    # try the first Pro
    elif lp_instance.Check(0, "pad pro"):
        lp_instance = launchpad.LaunchpadPro()
        if lp_instance.Open(0, "pad pro"):
            print(" - Launchpad Pro: OK")
        else:
            print(" - Launchpad Pro: ERROR")
            return

    # try the first Pro Mk3
    elif lp_instance.Check(0, "promk3"):
        lp_instance = launchpad.LaunchpadProMk3()
        if lp_instance.Open(0):
            print(" - Launchpad Pro Mk3: OK")
        else:
            print(" - Launchpad Pro Mk3: ERROR")
            return

    # try the first X
    # Notice that this is already built-in in the LPX class' methods Check() and Open,
    # but we're using the one from above!
    elif lp_instance.Check(1, "Launchpad X") or lp_instance.Check(1, "LPX"):
        lp_instance = launchpad.LaunchpadLPX()
        # Open() includes looking for "LPX" and "Launchpad X"
        if lp_instance.Open(1):
            print(" - Launchpad X: OK")
        else:
            print(" - Launchpad X: ERROR")
            return

    # nope
    else:
        print(" - No Launchpad available")
        return


class LaunchpadDevice(LaunchpadDevice):
    """Launchpad device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=1,
                ): vol.All(int, vol.Range(min=1)),
                vol.Required(
                    "rows",
                    description="Number of individual rows",
                    default=1,
                ): vol.All(int, vol.Range(min=1)),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # try:
        # 	import launchpad_py as launchpad
        # except ImportError:
        # 	try:
        # 		import launchpad
        # 	except ImportError:
        # 		sys.exit("ERROR: loading launchpad.py failed")
        self.lp = launchpad.Launchpad()
        if (self.lp) is not None:
            dump_methods(self.lp, self._device_type)

    def flush(self, data):
        try:
            # yz = packets.build_launchpad_packet(data)
            # print(yz)
            print(" - Testing Launchpad LedCtrlXY()")
            colors = [
                [63, 0, 0],
                [0, 63, 0],
                [0, 0, 63],
                [63, 63, 0],
                [63, 0, 63],
                [0, 63, 63],
                [63, 63, 63],
            ]
            for i in range(4):
                for y in range(i + 1, 8 - i + 1):
                    for x in range(i, 8 - i):
                        self.lp.LedCtrlXY(
                            x, y, colors[i][0], colors[i][1], colors[i][2]
                        )
            # close this instance
            self.lp.Close()
        except serial.SerialException:
            _LOGGER.warning(
                "MIDI Connection Interrupted. Please check connections and ensure your device is functioning correctly."
            )

    def activate(self):
        validate_launchpad(self.lp)

        # Clear the buffer because the Launchpad remembers everything
        self.lp.ButtonFlush()
        super().activate()

    def deactivate(self):
        self.lp.Close()

        super().deactivate()
