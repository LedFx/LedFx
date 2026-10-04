import logging
import threading

import numpy as np
import sacn
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class E131Device(NetworkedDevice):
    """E1.31 device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "universe",
                description="DMX universe for the device",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "universe_size",
                description="Size of each DMX universe",
                default=510,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "channel_offset",
                description="Channel offset within the DMX universe",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "packet_priority",
                description="Priority given to the sACN packets for this device",
                default=100,
            ): vol.All(int, vol.Range(min=0, max=200)),
        }
    )

    OUTPUT_KEYS = (
        "ip_address",
        "pixel_count",
        "universe",
        "universe_size",
        "channel_offset",
        "packet_priority",
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # Since RGBW data is 4 packets, we can use 512 for RGBW LEDs; 512/4 = 128
        # The 129th pixels data will span into the next universe correctly
        # If it's not, we lose nothing by using a smaller universe size and keeping things easy for the end user (and us!)
        # if self._config["rgbw_led"] is True:
        #     self._config["universe_size"] = 512
        # else:
        #     self._config["universe_size"] = 510
        # Allow for configuring in terms of "pixels" or "channels"

        self._device_type = "e131"
        self._set_channel_layout()

        self._sacn = None
        self.device_lock = threading.Lock()

    def _set_channel_layout(self) -> None:
        # pixel_count is a field with a default, so it is always present and
        # the old channel_count-only branch could never run.
        channel_count = self._config["pixel_count"] * 3

        # channel_offset is 0-based, so span is the index of the last channel
        # and span // universe_size is the universe it lands in.
        span = self._config["channel_offset"] + channel_count - 1
        universe_end = self._config["universe"] + span // self._config["universe_size"]
        self._config.update(channel_count=channel_count, universe_end=universe_end)

    def config_updated(self, config: object) -> None:
        # The stored channel_count and universe_end are stale until recomputed.
        self._set_channel_layout()
        if self._sacn is not None and self._output_changed():
            # A new sender starts with zeroed universes, so channels the
            # device no longer drives go dark without a blanking flush.
            with self.device_lock:
                self._sacn.stop()
                self._sacn = None
            self.activate()
        self._built_settings = self._output_settings()

    def activate(self):
        with self.device_lock:
            if self._config["ip_address"].lower() == "multicast":
                multicast = True
            else:
                multicast = False

            if not multicast and self._destination is None:
                # Resolves the address, then retries activate; no sender until then.
                return super().activate()

            if self._sacn:
                _LOGGER.warning("sACN sender already started for device %s", self.id)
                self._sacn.stop()

            # Configure sACN and start the dedicated thread to flush the buffer
            # Some variables are immutable and must be called here
            # Ephemeral source port: a fixed 5568 collides with other senders
            self._sacn = sacn.sACNsender(source_name=self.name, bind_port=0)

            for universe in range(
                self._config["universe"], self._config["universe_end"] + 1
            ):
                _LOGGER.info("sACN activating universe %s", universe)
                self._sacn.activate_output(universe)
                self._sacn[universe].priority = self._config["packet_priority"]
                self._sacn[universe].multicast = multicast
                if not multicast:
                    self._sacn[universe].destination = self.destination

            self._sacn.start()
            self._sacn.manual_flush = True

            _LOGGER.info("sACN sender for %s started.", self.config["name"])
            super().activate()

    def deactivate(self):
        super().deactivate()

        if not self._sacn:
            # He's dead, Jim
            # _LOGGER.warning("sACN sender not started.")
            return

        self.flush(np.zeros(self._config["channel_count"]))

        with self.device_lock:
            self._sacn.stop()
            self._sacn = None
            _LOGGER.info("sACN sender for %s stopped.", self.config["name"])

    def flush(self, data):
        """Flush the data to all the E1.31 channels account for spanning universes"""

        with self.device_lock:
            if self._sacn is not None:
                if data.size != self._config["channel_count"]:
                    raise Exception(  # noqa: TRY002
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
                    self._sacn[universe].dmx_data = dmx_data.tolist()

                self._sacn.flush()
