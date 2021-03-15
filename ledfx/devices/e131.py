import logging
import time

import numpy as np
import sacn
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import (
    resolve_destination,
    turn_wled_off,
    turn_wled_on,
    wled_identifier,
    wled_power_state,
)

_LOGGER = logging.getLogger(__name__)


class E131Device(Device):
    """E1.31 device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device, or "
                "multicast"
                " for multicast",
            ): str,
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                "universe",
                description="DMX universe for the device",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                "universe_size",
                description="Size of each DMX universe. Leave at 510 unless you know what you're doing",
                default=510,
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                "channel_offset",
                description="Channel offset within the DMX universe",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        # Allow for configuring in terms of "pixels" or "channels"

        if "pixel_count" in self._config:
            self._config["channel_count"] = self._config["pixel_count"] * 3
        else:
            self._config["pixel_count"] = self._config["channel_count"] // 3

        span = (
            self._config["channel_offset"] + self._config["channel_count"] - 1
        )
        self._config["universe_end"] = self._config["universe"] + int(
            span / self._config["universe_size"]
        )
        if span % self._config["universe_size"] == 0:
            self._config["universe_end"] -= 1
        self.WLEDReceiver = False
        self._sacn = None

    @property
    def pixel_count(self):
        return int(self._config["pixel_count"])

    def activate(self):
        if self._config["ip_address"].lower() == "multicast":
            multicast = True
        else:
            multicast = False
        if self._sacn:
            raise Exception("sACN sender already started.")

        if multicast is False:
            self.device_ip = resolve_destination(self._config["ip_address"])
            if not self.device_ip:
                _LOGGER.warning(
                    f"Cannot resolve destination {self._config['ip_address']}, aborting device {self.name} activation. Make sure the IP/hostname is correct and device is online."
                )
                return

            if wled_identifier(self.device_ip, self.name):
                self.WLEDReceiver = True
                self.wled_state = wled_power_state(self.device_ip, self.name)
                if self.wled_state is False:
                    turn_wled_on(self.device_ip, self.name)

        # Configure sACN and start the dedicated thread to flush the buffer
        # Some variables are immutable and must be called here
        self._sacn = sacn.sACNsender(source_name=self.name)
        for universe in range(
            self._config["universe"], self._config["universe_end"] + 1
        ):
            _LOGGER.info(f"sACN activating universe {universe}")
            self._sacn.activate_output(universe)

            if self._config["ip_address"] == "multicast":
                self._sacn[universe].multicast = True
            else:
                self._sacn[universe].destination = self.device_ip
                self._sacn[universe].multicast = False
        self._sacn._fps = self._config["refresh_rate"]
        self._sacn.start()
        self._sacn.manual_flush = True

        _LOGGER.info("sACN sender started.")
        super().activate()

    def deactivate(self):
        super().deactivate()

        if not self._sacn:
            raise Exception("sACN sender not started.")

        # Turn off all the LEDs when deactivating. With how the sender
        # works currently we need to sleep to ensure the pixels actually
        # get updated. Need to replace the sACN sender such that flush
        # directly writes the pixels.
        self.flush(np.zeros(self._config["channel_count"]))
        time.sleep(1.5)

        if self.WLEDReceiver is True and self.wled_state is False:
            turn_wled_off(self.device_ip, self.name)

        self._sacn.stop()
        self._sacn = None
        _LOGGER.info("sACN sender stopped.")

    def flush(self, data):
        """Flush the data to all the E1.31 channels account for spanning universes"""

        if not self._sacn:
            raise Exception("sACN sender not started.")
        if data.size != self._config["channel_count"]:
            raise Exception(
                f"Invalid buffer size. {data.size} != {self._config['channel_count']}"
            )

        data = data.flatten()
        current_index = 0
        for universe in range(
            self._config["universe"], self._config["universe_end"] + 1
        ):
            # Calculate offset into the provide input buffer for the channel. There are some
            # cleaner ways this can be done... This is just the quick and dirty
            universe_start = (
                universe - self._config["universe"]
            ) * self._config["universe_size"]
            universe_end = (
                universe - self._config["universe"] + 1
            ) * self._config["universe_size"]

            dmx_start = (
                max(universe_start, self._config["channel_offset"])
                % self._config["universe_size"]
            )
            dmx_end = (
                min(
                    universe_end,
                    self._config["channel_offset"]
                    + self._config["channel_count"],
                )
                % self._config["universe_size"]
            )
            if dmx_end == 0:
                dmx_end = self._config["universe_size"]

            input_start = current_index
            input_end = current_index + dmx_end - dmx_start
            current_index = input_end

            dmx_data = np.array(self._sacn[universe].dmx_data)
            dmx_data[dmx_start:dmx_end] = data[input_start:input_end]

            # Because the sACN library checks for data to be of int type, we have to
            # convert the numpy array into a python list of ints using tolist()
            self._sacn[universe].dmx_data = dmx_data.clip(0, 255).tolist()
            # output = dmx_data.clip(0, 255)

        # This is ugly - weird race condition where loading on startup from a device with a short ID results in the sACN thread trying to send data to NoneType.
        # No idea how to properly handle it - but this stops it breaking and seems to be reasonably resilient. Sorry to whoever stumbles onto it. -Shaun
        try:
            self._sacn.flush()
        except AttributeError:
            _LOGGER.info(
                "Attempted to start sACN thread prior to sACN activating. Restarting sACN thread."
            )
            self.activate

        # # Hack up a manual flush of the E1.31 data vs having a background thread
        # if self._sacn._output_thread._socket:
        #     for output in list(self._sacn._output_thread._outputs.values()):
        #         self._sacn._output_thread.send_out(output)
