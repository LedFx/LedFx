import logging
import threading

import numpy as np
import sacn
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class E131Device(NetworkedDevice):
    """E1.31 device support"""

    class Config(NetworkedDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        universe: int = Field(1, description="DMX universe for the device", ge=1)
        universe_size: int = Field(510, description="Size of each DMX universe", ge=1)
        channel_offset: int = Field(
            0, description="Channel offset within the DMX universe", ge=0
        )
        packet_priority: int = Field(
            100,
            description="Priority given to the sACN packets for this device",
            ge=0,
            le=200,
        )

    config = TypedConfig(Config)

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
        # if self.config.rgbw_led is True:
        #     self._set_config_values(universe_size=512)
        # else:
        #     self._set_config_values(universe_size=510)

        self._device_type = "e131"
        self._set_channel_layout()

        self._sacn = None
        self.device_lock = threading.Lock()

    def _set_channel_layout(self) -> None:
        # pixel_count is a field with a default, so it is always present and
        # the old channel_count-only branch could never run.
        channel_count = self.config.pixel_count * 3

        # channel_offset is 0-based, so span is the index of the last channel
        # and span // universe_size is the universe it lands in.
        span = self.config.channel_offset + channel_count - 1
        universe_end = self.config.universe + span // self.config.universe_size
        self._set_config_values(
            channel_count=channel_count,
            universe_end=universe_end,
        )
        # Cache intersections once per configuration, including offsets that
        # skip entire universes. Slots outside these slices retain their values.
        size = self.config.universe_size
        offset = self.config.channel_offset
        self._channel_slices = []
        for universe in range(self.config.universe, universe_end + 1):
            base = (universe - self.config.universe) * size
            start = max(base, offset)
            end = min(base + size, offset + channel_count)
            if start < end:
                self._channel_slices.append(
                    (universe, start - base, end - base, start - offset, end - offset)
                )

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
            if self.config.ip_address.lower() == "multicast":
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
                self.config.universe,
                getattr(self.config, "universe_end") + 1,  # noqa: B009 - stored extra, not a declared field
            ):
                _LOGGER.info("sACN activating universe %s", universe)
                self._sacn.activate_output(universe)
                self._sacn[universe].priority = self.config.packet_priority
                self._sacn[universe].multicast = multicast
                if not multicast:
                    self._sacn[universe].destination = self.destination

            self._sacn.start()
            self._sacn.manual_flush = True

            _LOGGER.info("sACN sender for %s started.", self.config.name)
            super().activate()

    def deactivate(self):
        super().deactivate()

        if not self._sacn:
            # He's dead, Jim
            # _LOGGER.warning("sACN sender not started.")
            return

        self.flush(np.zeros(getattr(self.config, "channel_count")))  # noqa: B009 - stored extra, not a declared field

        with self.device_lock:
            self._sacn.stop()
            self._sacn = None
            _LOGGER.info("sACN sender for %s stopped.", self.config.name)

    def flush(self, data):
        """Flush the data to all the E1.31 channels account for spanning universes"""

        with self.device_lock:
            if self._sacn is not None:
                if data.size != getattr(self.config, "channel_count"):  # noqa: B009 - stored extra, not a declared field
                    raise Exception(  # noqa: TRY002
                        f"Invalid buffer size. {data.size} != {getattr(self.config, 'channel_count')}"  # noqa: B009 - stored extra, not a declared field
                    )

                # Convert once for the whole frame. The public sACN setter
                # still validates bytes and marks the output as changed.
                channels = data.astype(int).ravel().tolist()
                for (
                    universe,
                    start,
                    end,
                    input_start,
                    input_end,
                ) in self._channel_slices:
                    output = self._sacn[universe]
                    dmx_data = list(output.dmx_data)
                    dmx_data[start:end] = channels[input_start:input_end]
                    output.dmx_data = dmx_data

                self._sacn.flush()
