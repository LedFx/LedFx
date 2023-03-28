import logging

import voluptuous as vol
from numpy import zeros

import ledfx.devices.launchpad_lib as launchpad
from ledfx.devices import MidiDevice

# import timeit


_LOGGER = logging.getLogger(__name__)

def dump_methods(instance):

    # List the class's methods
    _LOGGER.debug(" - Available methods:")
    for mName in sorted(dir(instance)):
        if mName.find("__") >= 0:
            continue

        if callable(getattr(instance, mName)):
            _LOGGER.debug(f"     {mName}()")


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
                    default=9,
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(
                    "icon_name",
                    description="Icon for the device*",
                    default="launchpad",
                ): str,
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lp = None
        self.flush_launchpad = None

    def flush(self, data):
        self.flush_launchpad(data)

    def activate(self):
        self.lp = launchpad.Launchpad()
        self.validate_launchpad()
        super().activate()

    def deactivate(self):
        self.flush_launchpad(zeros((self.pixel_count, 3)))
        self.lp.Close()
        super().deactivate()

    # Need a flush variant for each supported Launchpad, and assign in validate
    def flush_launchpadLPX(self, data):
        try:
            # we will use RawWriteSysEx(self, lstMessage, timeStamp=0)
            # this function adds the preamble 240 and post amble 247
            #
            # This message can be sent to Lighting Custom Modes and the Programmer mode
            # to light up LEDs. The LED indices used always correspond to those of
            # Programmer mode, regardless of the layout selected:
            #
            # Host => Launchpad X:
            # Hex: F0h 00h 20h 29h 02h 0Ch 03h <colourspec> [<colourspec> […]] F7h
            # Dec: 240 0   32  41  2   12   3  <colourspec> [<colourspec> […]] 247
            #
            # the <colourspec> is structured as follows:
            # - Lighting type (1 byte)
            # - LED index (1 byte)  ---- WARNING, each row starts at 11, 21, 31 etc
            # - Lighting data (1 – 3 bytes)
            # Lighting types:
            # - 0: Static colour from palette 1 byte specifying palette entry.
            # - 1: Flashing colour, 2 bytes specifying Colour B and Colour A.
            # - 2: Pulsing colour, 1 byte specifying palette entry.
            # - 3: RGB colour, 3 bytes for Red, Green and Blue (127: Max, 0: Min).
            #
            # The message may contain up to 81 <colourspec> entries to light up the entire
            # Launchpad X surface.
            # Example:

            # Host => Launchpad X:
            # Hex: F0h 00h 20h 29h 02h 0Ch 03h 00h 0Bh 0Dh 01h 0Ch 15h 17h 02h 0Dh 25h F7h
            # Dec: 240  0  32  41   2  12   3   0  11  13   1  12  21  23   2  13  37  247
            #
            # Sending this message to the Launchpad X in Programmer layout sets up the
            # bottom left pad to static yellow, the pad next to it to flashing green
            # (between dim and bright green), and the pad next to that pulsing turquoise
            #
            # in summary
            # [ 3 = RGB, Pos = layout BE CAREFUL, R,G, B max 127 ]
            # example of send RED pixel at row 3 pixel 6
            # send_buffer.extend([3, 35, 127, 0, 0])

            #            start = timeit.default_timer()

            # stuff the send buffer with the command preamble
            send_buffer = [0, 32, 41, 2, 12, 3]

            # prebump the programmer mode index up a row and just before
            pgm_mode_pos = 10
            for idx, pixel in enumerate(data):
                # check for row bumps, position is specific to programmer mode
                if idx % 9 == 0:
                    pgm_mode_pos += 1
                send_buffer.extend(
                    [
                        3,
                        pgm_mode_pos,
                        max(min(int(pixel[0] // 2), 127), 0),
                        max(min(int(pixel[1] // 2), 127), 0),
                        max(min(int(pixel[2] // 2), 127), 0),
                    ]
                )
                pgm_mode_pos += 1
            self.lp.myMidi.RawWriteSysEx(send_buffer)
            # took = timeit.default_timer() - start
            # _LOGGER.info(f"Updated Pixels: {took} ")

        except RuntimeError:
            _LOGGER.error("Error in LaunchpadLPX handling")

    def validate_launchpad(self):
        # try the first Mk2
        if self.lp.Check(0, "mk2"):
            self.lp = launchpad.LaunchpadMk2()
            if self.lp.Open(0, "mk2"):
                _LOGGER.info(" - Launchpad Mk2: OK")
            else:
                _LOGGER.error(" - Launchpad Mk2: ERROR")
                return

        # try the first Mini Mk3
        elif self.lp.Check(1, "minimk3"):
            self.lp = launchpad.LaunchpadMiniMk3()
            if self.lp.Open(1, "minimk3"):
                _LOGGER.info(" - Launchpad Mini Mk3: OK")
            else:
                _LOGGER.error(" - Launchpad Mini Mk3: ERROR")
                return

        # try the first Pro
        elif self.lp.Check(0, "pad pro"):
            self.lp = launchpad.LaunchpadPro()
            if self.lp.Open(0, "pad pro"):
                _LOGGER.info(" - Launchpad Pro: OK")
            else:
                _LOGGER.error(" - Launchpad Pro: ERROR")
                return

        # try the first Pro Mk3
        elif self.lp.Check(0, "promk3"):
            self.lp = launchpad.LaunchpadProMk3()
            if self.lp.Open(0):
                _LOGGER.info(" - Launchpad Pro Mk3: OK")
            else:
                _LOGGER.error(" - Launchpad Pro Mk3: ERROR")
                return

        # try the first X
        # Notice that this is already built-in in the LPX class' methods Check() and Open,
        # but we're using the one from above!
        elif self.lp.Check(1, "Launchpad X") or self.lp.Check(1, "LPX"):
            self.lp = launchpad.LaunchpadLPX()
            self.flush_launchpad = self.flush_launchpadLPX
            # Open() includes looking for "LPX" and "Launchpad X"
            if self.lp.Open(1):
                _LOGGER.info(" - Launchpad X: OK")
                dump_methods(self.lp.myMidi.devIn)
                dump_methods(self.lp.myMidi.devOut)
            else:
                _LOGGER.error(" - Launchpad X: ERROR")
                return

        # nope
        else:
            _LOGGER.error(" - No Launchpad available")
            self.flush_launchpad = None
            return
