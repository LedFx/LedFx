#!/usr/bin/env python
#
# Hack and slashed down from, to remove pygame
# remove all LED manipulations as LEDFX does this in single message
# generally remove lint problems
#
# A Novation Launchpad control suite for Python.
#
# https://github.com/FMMT666/launchpad.py
#
# FMMT666(ASkr) 01/2013..09/2019..08/2020..01/2021
# www.askrprojects.net
#

import array
import logging
import sys
import time

from pygame import midi

_LOGGER = logging.getLogger(__name__)


# ==========================================================================
# CLASS Midi
# Midi singleton wrapper
# ==========================================================================


class Midi:
    # instance created
    instanceMidi = None

    # ---------------------------------------------------------------------------------------
    # -- init
    # -- Allow only one instance to be created
    # ---------------------------------------------------------------------------------------
    def __init__(self):
        if Midi.instanceMidi is None:
            try:
                Midi.instanceMidi = Midi.__Midi()
            except:
                # TODO: maybe sth like sys.exit()?
                _LOGGER.info("unable to initialize MIDI")
                Midi.instanceMidi = None

        self.devIn = None
        self.devOut = None

    # ---------------------------------------------------------------------------------------
    # -- getattr
    # -- Pass all unknown method calls to the inner Midi class __Midi()
    # ---------------------------------------------------------------------------------------
    def __getattr__(self, name):
        return getattr(self.instanceMidi, name)

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def OpenOutput(self, midi_id):
        if self.devOut is None:
            try:
                # PyGame's default size of the buffer is 4096.
                # Removed code to tune that...
                self.devOut = midi.Output(midi_id, 0)
            except:
                self.devOut = None
                return False
        return True

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def CloseOutput(self):
        if self.devOut is not None:
            # self.devOut.close()
            del self.devOut
            self.devOut = None

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def OpenInput(self, midi_id, bufferSize=None):
        if self.devIn is None:
            try:
                # PyGame's default size of the buffer is 4096.
                if bufferSize is None:
                    self.devIn = midi.Input(midi_id)
                else:
                    # for experiments...
                    self.devIn = midi.Input(midi_id, bufferSize)
            except:
                self.devIn = None
                return False
        return True

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def CloseInput(self):
        if self.devIn is not None:
            # self.devIn.close()
            del self.devIn
            self.devIn = None

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def ReadCheck(self):
        return self.devIn.poll()

    # -------------------------------------------------------------------------------------
    # --
    # -------------------------------------------------------------------------------------
    def ReadRaw(self):
        return self.devIn.read(1)

    # -------------------------------------------------------------------------------------
    # -- sends a single, short message
    # -------------------------------------------------------------------------------------
    def RawWrite(self, stat, dat1, dat2):
        self.devOut.write_short(stat, dat1, dat2)

    # -------------------------------------------------------------------------------------
    # -- Sends a list of messages. If timestamp is 0, it is ignored.
    # -- Amount of <dat> bytes is arbitrary.
    # -- [ [ [stat, <dat1>, <dat2>, <dat3>], timestamp ],  [...], ... ]
    # -- <datN> fields are optional
    # -------------------------------------------------------------------------------------
    def RawWriteMulti(self, lstMessages):
        self.devOut.write(lstMessages)

    # -------------------------------------------------------------------------------------
    # -- Sends a single system-exclusive message, given by list <lstMessage>
    # -- The start (0xF0) and end bytes (0xF7) are added automatically.
    # -- [ <dat1>, <dat2>, ..., <datN> ]
    # -- Timestamp is not supported and will be sent as '0' (for now)
    # -------------------------------------------------------------------------------------
    def RawWriteSysEx(self, lstMessage, timeStamp=0):
        # There's a bug in PyGame's (Python 3) list-type message handling, so as a workaround,
        # we'll use the string-type message instead...
        # self.devOut.write_sys_ex( timeStamp, [0xf0] + lstMessage + [0xf7] ) # old Python 2

        # array.tostring() deprecated in 3.9; quickfix ahead
        try:
            self.devOut.write_sys_ex(
                timeStamp,
                array.array("B", [0xF0] + lstMessage + [0xF7]).tostring(),
            )
        except:
            self.devOut.write_sys_ex(
                timeStamp,
                array.array("B", [0xF0] + lstMessage + [0xF7]).tobytes(),
            )

    # ==========================================================================
    # CLASS __Midi
    # The rest of the Midi class, non Midi-device specific.
    # ==========================================================================

    class __Midi:
        # -------------------------------------------------------------------------------------
        # -- init
        # -------------------------------------------------------------------------------------
        def __init__(self):
            # exception handling moved up to Midi()
            midi.init()
            # but I can't remember why I put this one in here...
            midi.get_count()

        # -------------------------------------------------------------------------------------
        # -- del
        # -- This will never be executed, because no one knows, how many Launchpad instances
        # -- exist(ed) until we start to count them...
        # -------------------------------------------------------------------------------------
        def __del__(self):
            # midi.quit()
            pass

        # -------------------------------------------------------------------------------------
        # -- Returns a list of devices that matches the string 'name' and has in- or outputs.
        # -------------------------------------------------------------------------------------
        def SearchDevices(self, name, output=True, input=True, quiet=True):
            ret = []
            i = 0

            for n in range(midi.get_count()):
                md = midi.get_device_info(n)
                if str(md[1].lower()).find(name.lower()) >= 0:
                    if quiet == False:
                        _LOGGER.info("%2d" % (i), md)
                        sys.stdout.flush()
                    if output == True and md[3] > 0:
                        ret.append(i)
                    if input == True and md[2] > 0:
                        ret.append(i)
                i += 1

            return ret

        # -------------------------------------------------------------------------------------
        # -- Returns the first device that matches the string 'name'.
        # -- NEW2015/02: added number argument to pick from several devices (if available)
        # -------------------------------------------------------------------------------------
        def SearchDevice(self, name, output=True, input=True, number=0):
            ret = self.SearchDevices(name, output, input)

            if number < 0 or number >= len(ret):
                return None

            return ret[number]

        # -------------------------------------------------------------------------------------
        # -- Return MIDI time
        # -------------------------------------------------------------------------------------
        def GetTime(self):
            return midi.time()


# ==========================================================================
# CLASS LaunchpadBase
#
# ==========================================================================
class LaunchpadBase:
    def __init__(self):
        self.midi = Midi()  # midi interface instance (singleton)
        self.idOut = None  # midi id for output
        self.idIn = None  # midi id for input

        # scroll directions
        self.SCROLL_NONE = 0
        self.SCROLL_LEFT = -1
        self.SCROLL_RIGHT = 1

    def __del__(self):
        self.Close()

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -------------------------------------------------------------------------------------
    def Open(self, number=0, name="Launchpad"):
        self.idOut = self.midi.SearchDevice(name, True, False, number=number)
        self.idIn = self.midi.SearchDevice(name, False, True, number=number)

        if self.idOut is None or self.idIn is None:
            return False

        if self.midi.OpenOutput(self.idOut) == False:
            return False

        return self.midi.OpenInput(self.idIn)

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -------------------------------------------------------------------------------------
    def Check(self, number=0, name="Launchpad"):
        self.idOut = self.midi.SearchDevice(name, True, False, number=number)
        self.idIn = self.midi.SearchDevice(name, False, True, number=number)

        if self.idOut is None or self.idIn is None:
            return False

        return True

    # -------------------------------------------------------------------------------------
    # -- Closes this device
    # -------------------------------------------------------------------------------------
    def Close(self):
        self.midi.CloseInput()
        self.midi.CloseOutput()

    # -------------------------------------------------------------------------------------
    # -- _LOGGER.info's a list of all devices to the console (for debug)
    # -------------------------------------------------------------------------------------
    def ListAll(self, searchString=""):
        self.midi.SearchDevices(searchString, True, True, False)

    # -------------------------------------------------------------------------------------
    # -- Clears the button buffer (The Launchpads remember everything...)
    # -- Because of empty reads (timeouts), there's nothing more we can do here, but
    # -- repeat the polls and wait a little...
    # -------------------------------------------------------------------------------------
    def ButtonFlush(self):
        doReads = 0
        # wait for that amount of consecutive read fails to exit
        while doReads < 3:
            if self.midi.ReadCheck():
                doReads = 0
                self.midi.ReadRaw()
            else:
                doReads += 1
                time.sleep(0.005)

    # -------------------------------------------------------------------------------------
    # -- Returns a list of all MIDI events, empty list if nothing happened.
    # -- Useful for debugging or checking new devices.
    # -------------------------------------------------------------------------------------
    def EventRaw(self):
        if self.midi.ReadCheck():
            return self.midi.ReadRaw()
        else:
            return []


# ==========================================================================
# CLASS Launchpad
#
# For 2-color Launchpads with 8x8 matrix and 2x8 top/right rows
# ==========================================================================
class Launchpad(LaunchpadBase):
    # LED AND BUTTON NUMBERS IN RAW MODE (DEC):
    #
    # +---+---+---+---+---+---+---+---+
    # |200|201|202|203|204|205|206|207| < AUTOMAP BUTTON CODES;
    # +---+---+---+---+---+---+---+---+   Or use LedCtrlAutomap() for LEDs (alt. args)
    #
    # +---+---+---+---+---+---+---+---+  +---+
    # |  0|...|   |   |   |   |   |  7|  |  8|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 16|...|   |   |   |   |   | 23|  | 24|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 32|...|   |   |   |   |   | 39|  | 40|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 48|...|   |   |   |   |   | 55|  | 56|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 64|...|   |   |   |   |   | 71|  | 72|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 80|...|   |   |   |   |   | 87|  | 88|
    # +---+---+---+---+---+---+---+---+  +---+
    # | 96|...|   |   |   |   |   |103|  |104|
    # +---+---+---+---+---+---+---+---+  +---+
    # |112|...|   |   |   |   |   |119|  |120|
    # +---+---+---+---+---+---+---+---+  +---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY MODE (X/Y)
    #
    #   0   1   2   3   4   5   6   7      8
    # +---+---+---+---+---+---+---+---+
    # |   |1/0|   |   |   |   |   |   |         0
    # +---+---+---+---+---+---+---+---+
    #
    # +---+---+---+---+---+---+---+---+  +---+
    # |0/1|   |   |   |   |   |   |   |  |   |  1
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |   |   |   |  |   |  2
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |5/3|   |   |  |   |  3
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |   |   |   |  |   |  4
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |   |   |   |  |   |  5
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |4/6|   |   |   |  |   |  6
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |   |   |   |  |   |  7
    # +---+---+---+---+---+---+---+---+  +---+
    # |   |   |   |   |   |   |   |   |  |8/8|  8
    # +---+---+---+---+---+---+---+---+  +---+
    #

    # -------------------------------------------------------------------------------------
    # -- Returns True if a button event was received.
    # -------------------------------------------------------------------------------------
    def ButtonChanged(self):
        return self.midi.ReadCheck()

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change as a list:
    # -- [ <button>, <True/False> ]
    # -------------------------------------------------------------------------------------
    def ButtonStateRaw(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()
            return [
                a[0][0][1] if a[0][0][0] == 144 else a[0][0][1] + 96,
                True if a[0][0][2] > 0 else False,
            ]
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Returns an x/y value of the last button change as a list:
    # -- [ <x>, <y>, <True/False> ]
    # -------------------------------------------------------------------------------------
    def ButtonStateXY(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            if a[0][0][0] == 144:
                x = a[0][0][1] & 0x0F
                y = (a[0][0][1] & 0xF0) >> 4

                return [x, y + 1, True if a[0][0][2] > 0 else False]

            elif a[0][0][0] == 176:
                return [a[0][0][1] - 104, 0, True if a[0][0][2] > 0 else False]

        return []


# ==========================================================================
# CLASS LaunchpadPro
#
# For 3-color "Pro" Launchpads with 8x8 matrix and 4x8 left/right/top/bottom rows
# ==========================================================================
class LaunchpadPro(LaunchpadBase):
    # LED AND BUTTON NUMBERS IN RAW MODE (DEC)
    # WITH LAUNCHPAD IN "LIVE MODE" (PRESS SETUP, top-left GREEN).
    #
    # Notice that the fine manual doesn't know that mode.
    # According to what's written there, the numbering used
    # refers to the "PROGRAMMING MODE", which actually does
    # not react to any of those notes (or numbers).
    #
    #        +---+---+---+---+---+---+---+---+
    #        | 91|   |   |   |   |   |   | 98|
    #        +---+---+---+---+---+---+---+---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 80|  | 81|   |   |   |   |   |   |   |  | 89|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 70|  |   |   |   |   |   |   |   |   |  | 79|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 60|  |   |   |   |   |   |   | 67|   |  | 69|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 50|  |   |   |   |   |   |   |   |   |  | 59|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 40|  |   |   |   |   |   |   |   |   |  | 49|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 30|  |   |   |   |   |   |   |   |   |  | 39|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 20|  |   |   | 23|   |   |   |   |   |  | 29|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 10|  |   |   |   |   |   |   |   |   |  | 19|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |  1|  2|   |   |   |   |   |  8|
    #        +---+---+---+---+---+---+---+---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY CLASSIC MODE (X/Y)
    #
    #   9      0   1   2   3   4   5   6   7      8
    #        +---+---+---+---+---+---+---+---+
    #        |0/0|   |2/0|   |   |   |   |   |         0
    #        +---+---+---+---+---+---+---+---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |0/1|   |   |   |   |   |   |   |  |   |  1
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |9/2|  |   |   |   |   |   |   |   |   |  |   |  2
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |5/3|   |   |  |   |  3
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  4
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  5
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |4/6|   |   |   |  |   |  6
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  7
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |9/8|  |   |   |   |   |   |   |   |   |  |8/8|  8
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |   |1/9|   |   |   |   |   |   |         9
    #        +---+---+---+---+---+---+---+---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY PRO MODE (X/Y)
    #
    #   0      1   2   3   4   5   6   7   8      9
    #        +---+---+---+---+---+---+---+---+
    #        |1/0|   |3/0|   |   |   |   |   |         0
    #        +---+---+---+---+---+---+---+---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |1/1|   |   |   |   |   |   |   |  |   |  1
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |0/2|  |   |   |   |   |   |   |   |   |  |   |  2
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |6/3|   |   |  |   |  3
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  4
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  5
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |5/6|   |   |   |  |   |  6
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  7
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |0/8|  |   |   |   |   |   |   |   |   |  |9/8|  8
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |   |2/9|   |   |   |   |   |   |         9
    #        +---+---+---+---+---+---+---+---+
    #

    COLORS = {"black": 0, "off": 0, "white": 3, "red": 5, "green": 17}

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- Uses search string "Pro", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Open(self, number=0, name="Pro"):
        retval = super().Open(number=number, name=name)
        if retval == True:
            # avoid sending this to an Mk2
            if name.lower() == "pro":
                self.LedSetMode(0)

        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "Launchpad Pro", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="Launchpad Pro"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Sets the button layout (and codes) to the set, specified by <mode>.
    # -- Valid options:
    # --  00 - Session, 01 - Drum Rack, 02 - Chromatic Note, 03 - User (Drum)
    # --  04 - Audio, 05 -Fader, 06 - Record Arm, 07 - Track Select, 08 - Mute
    # --  09 - Solo, 0A - Volume
    # -- Until now, we'll need the "Session" (0x00) settings.
    # -------------------------------------------------------------------------------------
    # TODO: ASkr, Undocumented!
    # TODO: return value
    def LedSetLayout(self, mode):
        if mode < 0 or mode > 0x0D:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 16, 34, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Selects the Pro's mode.
    # -- <mode> -> 0 -> "Ableton Live mode"  (what we need)
    # --           1 -> "Standalone mode"    (power up default)
    # -------------------------------------------------------------------------------------
    def LedSetMode(self, mode):
        if mode < 0 or mode > 1:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 16, 33, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <button>, <value> ], in which <button> is the raw number of the button and
    # -- <value> an intensity value from 0..127.
    # -- >0 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -- Pressure events are returned if enabled via "returnPressure".
    # -- To distinguish pressure events from buttons, a fake button code of "255" is used,
    # -- so the list looks like [ 255, <value> ].
    # -------------------------------------------------------------------------------------
    def ButtonStateRaw(self, returnPressure=False):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # Note:
            #  Beside "144" (Note On, grid buttons), "208" (Pressure Value, grid buttons) and
            #  "176" (Control Change, outer buttons), random (broken) SysEx messages
            #  can appear here:
            #   ('###', [[[240, 0, 32, 41], 4]])
            #   ('-->', [])
            #   ('###', [[[2, 16, 45, 0], 4]])
            #   ('###', [[[247, 0, 0, 0], 4]])
            #  ---
            #   ('###', [[[240, 0, 32, 41], 4]])
            #   ('-->', [])
            #  1st one is a SysEx Message (240, 0, 32, 41, 2, 16 ), with command Mode Status (45)
            #  in "Ableton Mode" (0) [would be 1 for Standalone Mode). "247" is the SysEx termination.
            #  Additionally, it's interrupted by a read failure.
            #  The 2nd one is simply cut. Notice that that these are commands usually send TO the
            #  Launchpad...
            #
            # Reminder for the "pressure event issue":
            # The pressure events do not send any button codes, it's really just the pressure,
            # everytime a value changes:
            #   [[[144, 55, 5, 0], 654185]]    button hit ("NoteOn with vel > 0")
            #   [[[208, 24, 0, 0], 654275]]    button hold
            #   [[[208, 127, 0, 0], 654390]]    ...
            #   [[[208, 122, 0, 0], 654506]     ...
            #   [[[208, 65, 0, 0], 654562]]     ...
            #   [[[208, 40, 0, 0], 654567]]     ...
            #   [[[208, 0, 0, 0], 654573]]      ...
            #   [[[144, 55, 0, 0], 654614]]    button released ("NoteOn with vel == 0")
            # When multiple buttons are pressed (hold), the biggest number will be returned.
            #
            # Copied over from the XY method.
            # Try to avoid getting flooded with pressure events
            if returnPressure == False:
                while a[0][0][0] == 208:
                    a = self.midi.ReadRaw()
                    if a == []:
                        return []

            if a[0][0][0] == 144 or a[0][0][0] == 176:
                return [a[0][0][1], a[0][0][2]]
            else:
                if returnPressure:
                    if a[0][0][0] == 208:
                        return [255, a[0][0][1]]
                    else:
                        return []
                else:
                    return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
    # -- <value> is the intensity from 0..127.
    # -- >0 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -------------------------------------------------------------------------------------
    def ButtonStateXY(self, mode="classic", returnPressure=False):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            if returnPressure == False:
                while a[0][0][0] == 208:
                    a = self.midi.ReadRaw()
                    if a == []:
                        return []

            if a[0][0][0] == 144 or a[0][0][0] == 176:
                if mode.lower() != "pro":
                    x = (a[0][0][1] - 1) % 10
                else:
                    x = a[0][0][1] % 10
                y = (99 - a[0][0][1]) // 10

                return [x, y, a[0][0][2]]
            else:
                if a[0][0][0] == 208:
                    return [255, 255, a[0][0][1]]
                else:
                    return []
        else:
            return []


# ==========================================================================
# CLASS LaunchpadMk2
#
# For 3-color "Mk2" Launchpads with 8x8 matrix and 2x8 right/top rows
# ==========================================================================
class LaunchpadMk2(LaunchpadPro):
    # LED AND BUTTON NUMBERS IN RAW MODE (DEC)
    #
    # Notice that the fine manual doesn't know that mode.
    # According to what's written there, the numbering used
    # refers to the "PROGRAMMING MODE", which actually does
    # not react to any of those notes (or numbers).
    #
    #        +---+---+---+---+---+---+---+---+
    #        |104|   |106|   |   |   |   |111|
    #        +---+---+---+---+---+---+---+---+
    #
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 81|   |   |   |   |   |   |   |  | 89|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 71|   |   |   |   |   |   |   |  | 79|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 61|   |   |   |   |   | 67|   |  | 69|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 51|   |   |   |   |   |   |   |  | 59|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 41|   |   |   |   |   |   |   |  | 49|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 31|   |   |   |   |   |   |   |  | 39|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 21|   | 23|   |   |   |   |   |  | 29|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 11|   |   |   |   |   |   |   |  | 19|
    #        +---+---+---+---+---+---+---+---+  +---+
    #
    #
    #
    # LED AND BUTTON NUMBERS IN XY MODE (X/Y)
    #
    #          0   1   2   3   4   5   6   7      8
    #        +---+---+---+---+---+---+---+---+
    #        |0/0|   |2/0|   |   |   |   |   |         0
    #        +---+---+---+---+---+---+---+---+
    #
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |0/1|   |   |   |   |   |   |   |  |   |  1
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  2
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |5/3|   |   |  |   |  3
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  4
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  5
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |4/6|   |   |   |  |   |  6
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  7
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |8/8|  8
    #        +---+---+---+---+---+---+---+---+  +---+
    #

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- Uses search string "Mk2", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Open(self, number=0, name="Mk2"):
        return super().Open(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "Mk2", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Check(self, number=0, name="Mk2"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
    # -- <svalue> the intensity. Because the Mk2 does not come with full analog capabilities,
    # -- unlike the "Pro", the intensity values for the "Mk2" are either 0 or 127.
    # -- 127 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def ButtonStateXY(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            if a[0][0][0] == 144 or a[0][0][0] == 176:
                if a[0][0][1] >= 104:
                    x = a[0][0][1] - 104
                    y = 0
                else:
                    x = (a[0][0][1] - 1) % 10
                    y = (99 - a[0][0][1]) // 10

                return [x, y, a[0][0][2]]
            else:
                return []
        else:
            return []


# ==========================================================================
# CLASS LaunchControlXL
#
# For 2-color Launch Control XL
# ==========================================================================
class LaunchControlXL(LaunchpadBase):
    # LED, BUTTON AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
    #
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     | 13| 29| 45| 61| 77| 93|109|125|  |NOP||NOP|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     | 14| 30| 46| 62| 78| 94|110|126|  |104||105|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     | 15| 31| 47| 63| 79| 95|111|127|  |106||107|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #
    #     +---+---+---+---+---+---+---+---+     +---+
    #     |   |   |   |   |   |   |   |   |     |105|
    #     |   |   |   |   |   |   |   |   |     +---+
    #     |   |   |   |   |   |   |   |   |     |106|
    #     | 77| 78| 79| 80| 81| 82| 83| 84|     +---+
    #     |   |   |   |   |   |   |   |   |     |107|
    #     |   |   |   |   |   |   |   |   |     +---+
    #     |   |   |   |   |   |   |   |   |     |108|
    #     +---+---+---+---+---+---+---+---+     +---+
    #
    #     +---+---+---+---+---+---+---+---+
    #     | 41| 42| 43| 44| 57| 58| 59| 60|
    #     +---+---+---+---+---+---+---+---+
    #     | 73| 74| 75| 76| 89| 90| 91| 92|
    #     +---+---+---+---+---+---+---+---+
    #
    #
    # LED NUMBERS IN X/Y MODE (DEC)
    #
    #       0   1   2   3   4   5   6   7      8    9
    #
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  0  |0/1|   |   |   |   |   |   |   |  |NOP||NOP|  0
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  1  |   |   |   |   |   |   |   |   |  |   ||   |  1
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  2  |   |   |   |   |   |5/2|   |   |  |   ||   |  2
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #                                            8/9
    #     +---+---+---+---+---+---+---+---+     +---+
    #     |   |   |   |   |   |   |   |   |     |   |    3(!)
    #     |   |   |   |   |   |   |   |   |     +---+
    #     |   |   |   |   |   |   |   |   |     |   |    4(!)
    #  3  |   |   |2/3|   |   |   |   |   |     +---+
    #     |   |   |   |   |   |   |   |   |     |   |    5(!)
    #     |   |   |   |   |   |   |   |   |     +---+
    #     |   |   |   |   |   |   |   |   |     |   |    6
    #     +---+---+---+---+---+---+---+---+     +---+
    #
    #     +---+---+---+---+---+---+---+---+
    #  4  |   |   |   |   |   |   |   |   |              4(!)
    #     +---+---+---+---+---+---+---+---+
    #  5  |   |   |   |3/4|   |   |   |   |              5(!)
    #     +---+---+---+---+---+---+---+---+
    #
    #

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Control XL MIDI devices.
    # -- Uses search string "Control XL", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Open(self, number=0, name="Control XL", template=1):
        # The user template number adds to the MIDI commands.
        # Make sure that the Control XL is set to the corresponding mode by
        # holding down one of the template buttons and selecting the template
        # with the lowest button row 1..8
        # By default, user template 1 is enabled. Notice that the Launch Control
        # actually uses 0..15, but as the pad buttons are labeled 1..8 it probably
        # make sense to use these human readable ones instead.

        template = min(int(template), 16)  # make int and limit to <=8
        template = max(template, 1)  # no negative numbers

        self.UserTemplate = template

        retval = super().Open(number=number, name=name)
        if retval == True:
            self.TemplateSet(self.UserTemplate)

        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "Pro", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="Control XL"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Sets the layout template.
    # -- 1..8 selects the user and 9..16 the factory setups.
    # -------------------------------------------------------------------------------------
    def TemplateSet(self, templateNum):
        if templateNum < 1 or templateNum > 16:
            return
        else:
            self.UserTemplate = templateNum
            self.midi.RawWriteSysEx([0, 32, 41, 2, 17, 119, templateNum - 1])

    # -------------------------------------------------------------------------------------
    # -- Clears the input buffer (The Launchpads remember everything...)
    # -------------------------------------------------------------------------------------
    def InputFlush(self):
        return self.ButtonFlush()

    # -------------------------------------------------------------------------------------
    # -- Returns True if an event occured.
    # -------------------------------------------------------------------------------------
    def InputChanged(self):
        return self.midi.ReadCheck()

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button or potentiometer change as a list:
    # -- potentiometers/sliders:  <pot.number>, <value>     , 0 ]
    # -- buttons:                 <pot.number>, <True/False>, 0 ]
    # -------------------------------------------------------------------------------------
    def InputStateRaw(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # --- pressed
            if a[0][0][0] == 144:
                return [a[0][0][1], True, 127]
            # --- released
            elif a[0][0][0] == 128:
                return [a[0][0][1], False, 0]
            # --- potentiometers and the four cursor buttons
            elif a[0][0][0] == 176:
                # --- cursor buttons
                if a[0][0][1] >= 104 and a[0][0][1] <= 107:
                    if a[0][0][2] > 0:
                        return [a[0][0][1], True, a[0][0][2]]
                    else:
                        return [a[0][0][1], False, 0]
                # --- potentiometers
                else:
                    return [a[0][0][1], a[0][0][2], 0]
            else:
                return []
        else:
            return []


# ==========================================================================
# CLASS LaunchControl
#
# For 2-color Launch Control
# ==========================================================================
class LaunchControl(LaunchControlXL):
    # LED, BUTTON AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
    #
    #       0   1   2   3   4   5   6   7      8    9
    #
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  0  | 21| 22| 23| 24| 25| 26| 27| 28|  |NOP||NOP|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  1  | 41| 42| 43| 44| 45| 46| 47| 48|  |114||115|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  2  |  9| 10| 11| 12| 25| 26| 27| 28|  |116||117|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #
    #
    # LED NUMBERS IN X/Y MODE (DEC)
    #
    #       0   1   2   3   4   5   6   7      8    9
    #
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     | - | - | - | - | - | - | - | - |  |NOP||NOP|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  1  | - | - | - | - | - | - | - | - |  |8/1||9/1|
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #     +---+---+---+---+---+---+---+---+  +---++---+
    #  0  |0/0|   |   |   |   |   |   |7/0|  |8/0||9/0|
    #     +---+---+---+---+---+---+---+---+  +---++---+

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Control MIDI devices.
    # -- Uses search string "Control MIDI", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchControlXL" method
    def Open(self, number=0, name="Control MIDI", template=1):
        # The user template number adds to the MIDI commands.
        # Make sure that the Control is set to the corresponding mode by
        # holding down one of the template buttons and selecting the template
        # with the lowest button row 1..8 (variable here stores that as 0..7 for
        # user or 8..15 for the factory templates).
        # By default, user template 0 is enabled
        self.UserTemplate = template

        retval = super().Open(number=number, name=name)
        if retval == True:
            self.TemplateSet(self.UserTemplate)

        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "Control MIDI", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="Control MIDI"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Sets the layout template.
    # -- 1..8 selects the user and 9..16 the factory setups.
    # -------------------------------------------------------------------------------------
    def TemplateSet(self, templateNum):
        if templateNum < 1 or templateNum > 16:
            return
        else:
            self.midi.RawWriteSysEx([0, 32, 41, 2, 10, 119, templateNum - 1])


# ==========================================================================
# CLASS LaunchKey
#
# For 2-color LaunchKey Keyboards
# ==========================================================================
class LaunchKeyMini(LaunchpadBase):
    # LED, BUTTON, KEY AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
    # NOTICE THAT THE OCTAVE BUTTONS SHIFT THE KEYS UP OR DOWN BY 12.
    #
    # LAUNCHKEY MINI:
    #
    #                   +---+---+---+---+---+---+---+---+
    #                   | 21| 22|...|   |   |   |   | 28|
    #     +---+---+---+ +---+---+---+---+---+---+---+---+ +---+  +---+
    #     |106|107|NOP| | 40| 41| 42| 43| 48| 49| 50| 51| |108|  |104|
    #     +---+---+---+ +---+---+---+---+---+---+---+---+ +---+  +---+
    #     |NOP|NOP|     | 36| 37| 38| 39| 44| 45| 46| 47| |109|  |105|
    #     +---+---+     +---+---+---+---+---+---+---+---+ +---+  +---+
    #
    #     +--+-+-+-+--+--+-+-+-+-+-+--+--+-+-+-+--+--+-+-+-+-+-+--+---+
    #     |  | | | |  |  | | | | | |  |  | | | |  |  | | | | | |  |   |
    #     |  |4| |5|  |  | | | | | |  |  |6| | |  |  | | | | |7|  |   |
    #     |  |9| |1|  |  | | | | | |  |  |1| | |  |  | | | | |0|  |   |
    #     |  +-+ +-+  |  +-+ +-+ +-+  |  +-+ +-+  |  +-+ +-+ +-+  |   |
    #     | 48| 50| 52|   |   |   |   | 60|   |   |   |   |   | 71| 72|
    #     |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
    #     | C | D | E |...|   |   |   | C2| D2|...|   |   |   |   | C3|
    #     +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
    #
    #
    # LAUNCHKEY 25/49/61:
    #
    #    SLIDERS:           41..48
    #    SLIDER (MASTER):   7
    #

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached LaunchKey devices.
    # -- Uses search string "LaunchKey", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Open(self, number=0, name="LaunchKey"):
        retval = super().Open(number=number, name=name)
        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "LaunchKey", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="LaunchKey"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button, key or potentiometer change as a list:
    # -- potentiometers:   <pot.number>, <value>     , 0          ]
    # -- buttons:          <but.number>, <True/False>, <velocity> ]
    # -- keys:             <but.number>, <True/False>, <velocity> ]
    # -- If a button does not provide an analog value, 0 or 127 are returned as velocity values.
    # -- Because of the octave settings cover the complete note range, the button and potentiometer
    # -- numbers collide with the note numbers in the lower octaves.
    # -------------------------------------------------------------------------------------
    def InputStateRaw(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # --- pressed key
            if a[0][0][0] == 144:
                return [a[0][0][1], True, a[0][0][2]]
            # --- released key
            elif a[0][0][0] == 128:
                return [a[0][0][1], False, 0]
            # --- pressed button
            elif a[0][0][0] == 153:
                return [a[0][0][1], True, a[0][0][2]]
            # --- released button
            elif a[0][0][0] == 137:
                return [a[0][0][1], False, 0]
            # --- potentiometers and the four cursor buttons
            elif a[0][0][0] == 176:
                # --- cursor, track and scene buttons
                if a[0][0][1] >= 104 and a[0][0][1] <= 109:
                    if a[0][0][2] > 0:
                        return [a[0][0][1], True, 127]
                    else:
                        return [a[0][0][1], False, 0]
                # --- potentiometers
                else:
                    return [a[0][0][1], a[0][0][2], 0]
            else:
                return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Clears the input buffer (The Launchpads remember everything...)
    # -------------------------------------------------------------------------------------
    def InputFlush(self):
        return self.ButtonFlush()

    # -------------------------------------------------------------------------------------
    # -- Returns True if an event occured.
    # -------------------------------------------------------------------------------------
    def InputChanged(self):
        return self.midi.ReadCheck()


# ==========================================================================
# CLASS Dicer
#
# For that Dicer thingy...
# ==========================================================================
class Dicer(LaunchpadBase):
    # LED, BUTTON, KEY AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
    # NOTICE THAT THE OCTAVE BUTTONS SHIFT THE KEYS UP OR DOWN BY 10.
    #
    # FOR SHIFT MODE (HOLD ONE OF THE 3 MODE BUTTONS): ADD "5".
    #     +-----+  +-----+  +-----+             +-----+  +-----+  +-----+
    #     |#    |  |#    |  |     |             |#   #|  |#   #|  |    #|
    #     |  #  |  |     |  |  #  |             |  #  |  |     |  |  #  |
    #     |    #|  |    #|  |     |             |#   #|  |#   #|  |#    |
    #     +-----+  +-----+  +-----+             +-----+  +-----+  +-----+
    #
    #     +-----+            +---+               +----+           +-----+
    #     |#   #|            | +0|               |+120|           |    #|
    #     |     |            +---+               +----+           |     |
    #     |#   #|       +---+                         +----+      |#    |
    #     +-----+       |+10|                         |+110|      +-----+
    #                   +---+                         +----+
    #     +-----+  +---+                                  +----+  +-----+
    #     |#   #|  |+20|                                  |+100|  |     |
    #     |  #  |  +---+                                  +----+  |  #  |
    #     |#   #|                                                 |     |
    #     +-----+                                                 +-----+
    #
    #

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Dicer devices.
    # -- Uses search string "dicer", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Open(self, number=0, name="Dicer"):
        retval = super().Open(number=number, name=name)
        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "dicer", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="Dicer"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Returns (an already nicely mapped and not raw :) value of the last button change as a list:
    # -- buttons: <number>, <True/False>, <velocity> ]
    # -- If a button does not provide an analog value, 0 or 127 are returned as velocity values.
    # -- Small buttons select either 154, 155, 156 cmd for master or 157, 158, 159 for slave.
    # -- Button numbers (1 to 5): 60, 61 .. 64; always
    # -- Guess it's best to return: 1..5, 11..15, 21..25 for Master and 101..105, ... etc for slave
    # -- Actually, as you can see, it's not "raw", but I guess those decade modifiers really
    # -- make sense here (less brain calculations for you :)
    # -------------------------------------------------------------------------------------
    def ButtonStateRaw(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # --- button on master
            if a[0][0][0] >= 154 and a[0][0][0] <= 156:
                butNum = a[0][0][1]
                if butNum >= 60 and butNum <= 69:
                    butNum -= 59
                    butNum += 10 * (a[0][0][0] - 154)
                    if a[0][0][2] == 127:
                        return [butNum, True, 127]
                    else:
                        return [butNum, False, 0]
                else:
                    return []
            # --- button on master
            elif a[0][0][0] >= 157 and a[0][0][0] <= 159:
                butNum = a[0][0][1]
                if butNum >= 60 and butNum <= 69:
                    butNum -= 59
                    butNum += 100 + 10 * (a[0][0][0] - 157)
                    if a[0][0][2] == 127:
                        return [butNum, True, 127]
                    else:
                        return [butNum, False, 0]
                else:
                    return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Sets the Dicer <device> (0=master, 1=slave) to one of its six modes,
    # -- as specified by <mode>:
    # --  0 - "cue"
    # --  1 - "cue, shift lock"
    # --  2 - "loop"
    # --  3 - "loop, shift lock"
    # --  4 - "auto loop"
    # --  5 - "auto loop, shift lock"
    # --  6 - "one page"
    # -------------------------------------------------------------------------------------
    def ModeSet(self, device, mode):
        if device < 0 or device > 1:
            return

        if mode < 0 or mode > 6:
            return

        self.midi.RawWrite(186 if device == 0 else 189, 17, mode)


# ==========================================================================
# CLASS LaunchpadMiniMk3
#
# For 3-color "Mk3" Launchpads; Mini and Pro
# ==========================================================================
class LaunchpadMiniMk3(LaunchpadPro):
    # LED AND BUTTON NUMBERS IN RAW MODE (DEC)
    #
    #
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |104|   |106|   |   |   |   |111|  |112|
    #        +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 81|   |   |   |   |   |   |   |  | 89|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 71|   |   |   |   |   |   |   |  | 79|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 61|   |   |   |   |   | 67|   |  | 69|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 51|   |   |   |   |   |   |   |  | 59|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 41|   |   |   |   |   |   |   |  | 49|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 31|   |   |   |   |   |   |   |  | 39|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 21|   | 23|   |   |   |   |   |  | 29|
    #        +---+---+---+---+---+---+---+---+  +---+
    #        | 11|   |   |   |   |   |   |   |  | 19|
    #        +---+---+---+---+---+---+---+---+  +---+
    #
    #
    #
    # LED AND BUTTON NUMBERS IN XY MODE (X/Y)
    #
    #          0   1   2   3   4   5   6   7      8
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |0/0|   |2/0|   |   |   |   |   |  |8/0|  0
    #        +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |0/1|   |   |   |   |   |   |   |  |   |  1
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  2
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |5/3|   |   |  |   |  3
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  4
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  5
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |4/6|   |   |   |  |   |  6
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |   |  7
    #        +---+---+---+---+---+---+---+---+  +---+
    #        |   |   |   |   |   |   |   |   |  |8/8|  8
    #        +---+---+---+---+---+---+---+---+  +---+
    #

    # 	COLORS = {'black':0, 'off':0, 'white':3, 'red':5, 'green':17 }

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- Uses search string "MiniMk3", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Open(self, number=0, name="MiniMK3"):
        retval = super().Open(number=number, name=name)
        if retval == True:
            self.LedSetMode(1)

        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "MiniMk3", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="MiniMK3"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Sets the button layout (and codes) to the set, specified by <mode>.
    # -- Valid options:
    # --  00 - Session, 04 - Drums, 05 - Keys, 06 - User (Drum)
    # --  0D - DAW Faders (available if Session enabled), 7F - Programmer
    # -- Until now, we'll need the "Session" (0x00) settings.
    # -------------------------------------------------------------------------------------
    # TODO: ASkr, Undocumented!
    # TODO: return value
    def LedSetLayout(self, mode):
        ValidModes = [0x00, 0x04, 0x05, 0x06, 0x0D, 0x7F]
        if mode not in ValidModes:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 13, 0, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Selects the Mk3's mode.
    # -- <mode> -> 0 -> "Ableton Live mode"
    # --           1 -> "Programmer mode"	(what we need)
    # -------------------------------------------------------------------------------------
    def LedSetMode(self, mode):
        if mode < 0 or mode > 1:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 13, 14, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Sets the button layout to "Session" mode.
    # -------------------------------------------------------------------------------------
    # TODO: ASkr, Undocumented!
    def LedSetButtonLayoutSession(self):
        self.LedSetLayout(0)

    # -------------------------------------------------------------------------------------
    # -- Go back to custom modes before closing connection
    # -- Otherwise Launchpad will stuck in programmer mode
    # -------------------------------------------------------------------------------------
    def Close(self):
        # removed for now (LEDs would light up again; should be in the user's code)
        # 		self.LedSetLayout( 0x05 )

        # TODO: redundant (but needs fix for Py2 embedded anyway)
        self.midi.CloseInput()
        self.midi.CloseOutput()


# ==========================================================================
# CLASS LaunchpadLPX
#
# For 3-color "X" Launchpads
# ==========================================================================
class LaunchpadLPX(LaunchpadPro):
    # 	COLORS = {'black':0, 'off':0, 'white':3, 'red':5, 'green':17 }

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- This is one of the few devices that has different names in different OSs:
    # --
    # --   Windoze
    # --     (b'MMSystem', b'LPX MIDI', 1, 0, 0)
    # --     (b'MMSystem', b'MIDIIN2 (LPX MIDI)', 1, 0, 0)
    # --     (b'MMSystem', b'LPX MIDI', 0, 1, 0)
    # --     (b'MMSystem', b'MIDIOUT2 (LPX MIDI)', 0, 1, 0)
    # --
    # --   macOS
    # --     (b'CoreMIDI', b'Launchpad X LPX DAW Out', 1, 0, 0)
    # --     (b'CoreMIDI', b'Launchpad X LPX MIDI Out', 1, 0, 0)
    # --     (b'CoreMIDI', b'Launchpad X LPX DAW In', 0, 1, 0)
    # --     (b'CoreMIDI', b'Launchpad X LPX MIDI In', 0, 1, 0)
    # --
    # --   Linux [tm]
    # --     ('ALSA', 'Launchpad X MIDI 1', 0, 1, 0)
    # --     ('ALSA', 'Launchpad X MIDI 1', 1, 0, 0)
    # --     ('ALSA', 'Launchpad X MIDI 2', 0, 1, 0)
    # --     ('ALSA', 'Launchpad X MIDI 2', 1, 0, 0)
    # --
    # -- So the old strategy of simply looking for "LPX" will not work.
    # -- Workaround: If the user doesn't request a specific name, we'll just
    # -- search for "Launchpad X" and "LPX"...

    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Open(self, number=0, name="AUTO"):
        nameList = ["Launchpad X", "LPX"]
        if name != "AUTO":
            # mhh, better not this way
            # nameList.insert( 0, name )
            nameList = [name]
        for name in nameList:
            rval = super().Open(number=number, name=name)
            if rval:
                self.LedSetMode(1)
                return rval
        return False

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- See notes in "Open()" above.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="AUTO"):
        nameList = ["Launchpad X", "LPX"]
        if name != "AUTO":
            # mhh, better not this way
            # nameList.insert( 0, name )
            nameList = [name]
        for name in nameList:
            rval = super().Check(number=number, name=name)
            if rval:
                return rval
        return False

    # -------------------------------------------------------------------------------------
    # -- Sets the button layout (and codes) to the set, specified by <mode>.
    # -- Valid options:
    # --  00 - Session, 01 - Note Mode, 04 - Custom 1, 05 - Custom 2, 06 - Custom 3
    # --  07 - Custom 4, 0D - DAW Faders (available if Session enabled), 7F - Programmer
    # -------------------------------------------------------------------------------------
    # TODO: ASkr, Undocumented!
    # TODO: return value
    def LedSetLayout(self, mode):
        ValidModes = [0x00, 0x01, 0x04, 0x05, 0x06, 0x07, 0x0D, 0x7F]
        if mode not in ValidModes:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 12, 0, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Selects the LPX's mode.
    # -- <mode> -> 0 -> "Ableton Live mode"
    # --           1 -> "Programmer mode"	(what we need)
    # -------------------------------------------------------------------------------------
    def LedSetMode(self, mode):
        if mode < 0 or mode > 1:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 12, 14, mode])
        time.sleep(0.010)

    # -------------------------------------------------------------------------------------
    # -- Sets the button layout to "Session" mode.
    # -------------------------------------------------------------------------------------
    # TODO: ASkr, Undocumented!
    def LedSetButtonLayoutSession(self):
        self.LedSetLayout(0)

    # -------------------------------------------------------------------------------------
    # -- Go back to custom modes before closing connection
    # -- Otherwise Launchpad will stuck in programmer mode
    # -------------------------------------------------------------------------------------
    def Close(self):
        # TODO: redundant (but needs fix for Py2 embedded anyway)
        self.midi.CloseInput()
        self.midi.CloseOutput()

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <button>, <value> ], in which <button> is the raw number of the button and
    # -- <value> an intensity value from 0..127.
    # -- >0 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -- Pressure events are returned if enabled via "returnPressure".
    # -- Unlike the Launchpad Pro, the X does indeed return the button number AND the
    # -- pressure value. To provide visibility whether or not a button was pressed or is
    # -- hold, a value of 255 is added to the button number.
    # -- [ <button> + 255, <value> ].
    # -- In contrast to the Pro, which only has one pressure value for all, the X does
    # -- this per button. Nice.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def ButtonStateRaw(self, returnPressure=False):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # Copied over from the Pro's method.
            # Try to avoid getting flooded with pressure events
            if returnPressure == False:
                while a[0][0][0] == 160:
                    a = self.midi.ReadRaw()
                    if a == []:
                        return []

            if a[0][0][0] == 144 or a[0][0][0] == 176:
                return [a[0][0][1], a[0][0][2]]
            else:
                if returnPressure:
                    if a[0][0][0] == 160:
                        # the X returns button number AND pressure value
                        # adding 255 to make it possible to distinguish "pressed" from "pressure"
                        return [255 + a[0][0][1], a[0][0][2]]
                    else:
                        return []
                else:
                    return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
    # -- <value> is the intensity from 0..127.
    # -- >0 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def ButtonStateXY(self, mode="classic", returnPressure=False):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # 8/2020: Copied from the Pro.
            # 9/2020: now also _with_ pressure :)
            if returnPressure == False:
                while a[0][0][0] == 160:
                    a = self.midi.ReadRaw()
                    if a == []:
                        return []

            if a[0][0][0] == 144 or a[0][0][0] == 176 or a[0][0][0] == 160:
                if mode.lower() != "pro":
                    x = (a[0][0][1] - 1) % 10
                else:
                    x = a[0][0][1] % 10
                y = (99 - a[0][0][1]) // 10

                # now with pressure events (9/2020)
                if a[0][0][0] == 160 and returnPressure == True:
                    return [x + 255, y + 255, a[0][0][2]]
                else:
                    return [x, y, a[0][0][2]]
            else:
                return []
        else:
            return []


# ==========================================================================
# CLASS MidiFighter64
#
# For Midi Fighter 64 Gedöns
# ==========================================================================
class MidiFighter64(LaunchpadBase):
    #
    # LED AND BUTTON NUMBERS IN RAW MODE
    #
    #        +---+---+---+---+---+---+---+---+
    #        | 64|   |   | 67| 96|   |   | 99|
    #        +---+---+---+---+---+---+---+---+
    #        | 60|   |   | 63| 92|   |   | 95|
    #        +---+---+---+---+---+---+---+---+
    #        | 56|   |   | 59| 88|   |   | 91|
    #        +---+---+---+---+---+---+---+---+
    #        | 52|   |   | 55| 84|   |   | 87|
    #        +---+---+---+---+---+---+---+---+
    #        | 48|   |   | 51| 80|   |   | 83|
    #        +---+---+---+---+---+---+---+---+
    #        | 44|   |   | 47| 76|   |   | 79|
    #        +---+---+---+---+---+---+---+---+
    #        | 40|   |   | 43| 72|   |   | 75|
    #        +---+---+---+---+---+---+---+---+
    #        | 36|   |   | 39| 68|   |   | 71|
    #        +---+---+---+---+---+---+---+---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY MODE (X/Y)
    #
    #          0   1   2   3   4   5   6   7
    #        +---+---+---+---+---+---+---+---+
    #        |0/0|   |   |   |   |   |   |   | 0
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |   | 1
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |5/2|   |   | 2
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |   | 3
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |   | 4
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |4/5|   |   |   | 5
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |   | 6
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |   | 7
    #        +---+---+---+---+---+---+---+---+
    #

    # -------------------------------------------------------------------------------------
    # -- Add some LED mode "constants" for better usability.
    # -------------------------------------------------------------------------------------
    def __init__(self):
        self.MODE_BRIGHT = [i + 18 for i in range(16)]
        self.MODE_TOGGLE = [i + 34 for i in range(8)]
        self.MODE_PULSE = [i + 42 for i in range(8)]
        self.MODE_ANIM_SQUARE = 50
        self.MODE_ANIM_CIRCLE = 51
        self.MODE_ANIM_STAR = 52
        self.MODE_ANIM_TRIANGLE = 53

        super().__init__()

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- Uses search string "Fighter 64", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Open(self, number=0, name="Fighter 64"):
        return super().Open(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "Fighter 64", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadBase" method
    def Check(self, number=0, name="Fighter 64"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Controls a the mode of a grid LED by its <number> and the mode <mode> of the LED.
    # --  <number> 36..99
    # --  <mode>   18..53 for brightness, toggling and animation
    # -- Internal LED numbers are 3 octaves lower than the color numbers.
    # -- The mode must be sent over channel 4
    # -------------------------------------------------------------------------------------
    def LedCtrlRawMode(self, number, mode):
        # uses the original button numbers for usability
        if number < 36 or number > 99:
            return
        if mode < 18 or mode > 53:
            return

        self.midi.RawWrite(147, number - 3 * 12, mode)

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <button>, <velocity> ], in which <button> is the raw number of the button and
    # -- <velocity> the button state.
    # --   >0 = button pressed; 0 = button released
    # -------------------------------------------------------------------------------------
    def ButtonStateRaw(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # The Midi Fighter 64 does not support velocities. For 500 bucks. Lol :'-)
            # What we see here are either channel 3 or 2 NoteOn/NoteOff commands,
            # the factory settings, depending on the "bank selection".
            #   Channel 3 -> hold upper left  button for longer than 2s
            #   Channel 2 -> hold upper right button for longer than 2s
            #
            #    [[[146, 81, 127, 0], 47365]]
            #    [[[130, 81, 127, 0], 47443]]
            #    [[[146, 82, 127, 0], 47610]]
            #
            #    [[[ <NoteOn/Off>, <button>, 127, 0], 47610]]
            #
            #    146/145 -> NoteOn
            #    130/129 -> NoteOff
            #    127     -> fixed velocity (as set by the Midi Fighter utility )

            # Mhh, I guess it's about time to think about adding MIDI channels, isn't it?
            # But for now, we just check ch 2 and 3:
            if a[0][0][0] == 145 or a[0][0][0] == 146:
                return [a[0][0][1], a[0][0][2]]
            else:
                if a[0][0][0] == 130 or a[0][0][0] == 129:
                    return [a[0][0][1], 0]
                else:
                    return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <x>, <y>, <velocity> ], in which <x>/<y> are the coordinates of the grid and
    # -- <velocity> the state of the button.
    # --   >0 = button pressed; 0 = button released
    # -------------------------------------------------------------------------------------
    def ButtonStateXY(self):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # whatever that is, does not belong here...
            if a[0][0][1] < 36 or a[0][0][1] > 99:
                return []

            x = (a[0][0][1] - 36) % 4
            if a[0][0][1] >= 68:
                x += 4
            y = 7 - ((a[0][0][1] - 36) % 32) // 4

            if a[0][0][0] == 145 or a[0][0][0] == 146:
                return [x, y, a[0][0][2]]
            else:
                if a[0][0][0] == 130 or a[0][0][0] == 129:
                    return [x, y, 0]
                else:
                    return []
        else:
            return []


# ==========================================================================
# CLASS LaunchpadPROMk3
#
# For 3-color Pro Mk3 Launchpads
# ==========================================================================
class LaunchpadProMk3(LaunchpadPro):
    #
    # LED AND BUTTON NUMBERS IN RAW MODE
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 90|  | 91|   |   |   |   |   |   | 98|  | 99|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 80|  | 81|   |   |   |   |   |   |   |  | 89|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 70|  |   |   |   |   |   |   |   |   |  | 79|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 60|  |   |   |   |   |   |   | 67|   |  | 69|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 50|  |   |   |   |   |   |   |   |   |  | 59|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 40|  |   |   |   |   |   |   |   |   |  | 49|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 30|  |   |   |   |   |   |   |   |   |  | 39|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 20|  |   |   | 23|   |   |   |   |   |  | 29|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # | 10|  |   |   |   |   |   |   |   |   |  | 19|
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |101|102|   |   |   |   |   |108|
    #        +---+---+---+---+---+---+---+---+
    #        |  1|  2|   |   |   |   |   |  8|
    #        +---+---+---+---+---+---+---+---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY CLASSIC MODE (X/Y)
    #
    #   9      0   1   2   3   4   5   6   7      8
    #        +---+---+---+---+---+---+---+---+
    #        |0/0|   |2/0|   |   |   |   |   |         0
    #        +---+---+---+---+---+---+---+---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |0/1|   |   |   |   |   |   |   |  |   |  1
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |9/2|  |   |   |   |   |   |   |   |   |  |   |  2
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |5/3|   |   |  |   |  3
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  4
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  5
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |4/6|   |   |   |  |   |  6
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  7
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |9/8|  |   |   |   |   |   |   |   |   |  |8/8|  8
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |   |1/9|   |   |   |   |   |   |         9
    #        +---+---+---+---+---+---+---+---+
    #        |/10|   |   |   |   |   |   |   |        10
    #        +---+---+---+---+---+---+---+---+
    #
    #
    # LED AND BUTTON NUMBERS IN XY PRO MODE (X/Y)
    #
    #   0      1   2   3   4   5   6   7   8      9
    #        +---+---+---+---+---+---+---+---+
    #        |1/0|   |3/0|   |   |   |   |   |         0
    #        +---+---+---+---+---+---+---+---+
    #
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |1/1|   |   |   |   |   |   |   |  |   |  1
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |0/2|  |   |   |   |   |   |   |   |   |  |   |  2
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |6/3|   |   |  |   |  3
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  4
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  5
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |5/6|   |   |   |  |   |  6
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |   |  |   |   |   |   |   |   |   |   |  |   |  7
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    # |0/8|  |   |   |   |   |   |   |   |   |  |9/8|  8
    # +---+  +---+---+---+---+---+---+---+---+  +---+
    #
    #        +---+---+---+---+---+---+---+---+
    #        |   |2/9|   |   |   |   |   |8/9|         9
    #        +---+---+---+---+---+---+---+---+
    #        |   |   |   |   |   |   |   |/10|        10
    #        +---+---+---+---+---+---+---+---+

    # -------------------------------------------------------------------------------------
    # -- Opens one of the attached Launchpad MIDI devices.
    # -- Uses search string "ProMK3", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Open(self, number=0, name="ProMk3"):
        retval = super().Open(number=number, name=name)
        if retval == True:
            # enable Programmer's mode
            self.LedSetMode(1)
        return retval

    # -------------------------------------------------------------------------------------
    # -- Checks if a device exists, but does not open it.
    # -- Does not check whether a device is in use or other, strange things...
    # -- Uses search string "ProMk3", by default.
    # -------------------------------------------------------------------------------------
    # Overrides "LaunchpadPro" method
    def Check(self, number=0, name="ProMk3"):
        return super().Check(number=number, name=name)

    # -------------------------------------------------------------------------------------
    # -- Selects the ProMk3's mode.
    # -- <mode> -> 0 -> "Ableton Live mode"
    # --           1 -> "Programmer mode"	(what we need)
    # -------------------------------------------------------------------------------------
    def LedSetMode(self, mode):
        if mode < 0 or mode > 1:
            return

        self.midi.RawWriteSysEx([0, 32, 41, 2, 14, 14, mode])
        time.sleep(0.1)

    # -------------------------------------------------------------------------------------
    # -- Returns the raw value of the last button change (pressed/unpressed) as a list
    # -- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
    # -- <value> is the intensity from 0..127.
    # -- >0 = button pressed; 0 = button released
    # -- Notice that this is not (directly) compatible with the original ButtonStateRaw()
    # -- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
    # -- Compatibility would require checking via "== True" and not "is True".
    # -------------------------------------------------------------------------------------
    def ButtonStateXY(self, mode="classic", returnPressure=False):
        if self.midi.ReadCheck():
            a = self.midi.ReadRaw()

            # 8/2020: Try to mitigate too many pressure events that a bit (yep, seems to work fine!)
            # 9/2020: XY now also with pressure event functionality
            if returnPressure == False:
                while a[0][0][0] == 208:
                    a = self.midi.ReadRaw()
                    if a == []:
                        return []

            if a[0][0][0] == 144 or a[0][0][0] == 176:
                if mode.lower() != "pro":
                    x = (a[0][0][1] - 1) % 10
                else:
                    x = a[0][0][1] % 10
                if a[0][0][1] > 99:
                    y = 9
                elif a[0][0][1] < 10:
                    y = 10
                else:
                    y = (99 - a[0][0][1]) // 10

                return [x, y, a[0][0][2]]
            else:
                # TOCHK: this should be safe without checking "returnPressure"
                if a[0][0][0] == 208:
                    return [255, 255, a[0][0][1]]
                else:
                    return []
        else:
            return []

    # -------------------------------------------------------------------------------------
    # -- Go back to custom modes before closing connection
    # -- Otherwise Launchpad will stuck in programmer mode
    # -------------------------------------------------------------------------------------
    def Close(self):
        # re-enter Live mode
        if self.midi.devIn != None and self.midi.devOut != None:
            self.LedSetMode(0)
        # TODO: redundant (but needs fix for Py2 embedded anyway)
        # self.midi.CloseInput()
        # self.midi.CloseOutput()
