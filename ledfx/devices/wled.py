import logging

import voluptuous as vol
from pkg_resources import parse_version

from ledfx.devices import NetworkedDevice
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.e131 import E131Device
from ledfx.devices.udp import UDPRealtimeDevice
from ledfx.utils import WLED

_LOGGER = logging.getLogger(__name__)


class WLEDDevice(NetworkedDevice):
    """
    Dedicated WLED device support
    This class fetches its config (px count, etc) from the WLED device
    at launch, and lets the user choose a sync mode to use.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "sync_mode",
                description="Streaming protocol to WLED device. Recommended: UDP<480px, DDP>480px",
                default="UDP",
            ): vol.In(["UDP", "DDP", "E131"]),
            vol.Optional(
                "timeout",
                description="Time between LedFx effect off and WLED effect activate",
                default=1,
            ): vol.All(int, vol.Range(0, 255)),
        }
    )

    SYNC_MODES = {
        "UDP": UDPRealtimeDevice,
        "DDP": DDPDevice,
        "E131": E131Device,
    }

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.subdevice = None

        # moved DEVICE_CONFIGS class var to device_configs instance var as it is manipulated in seperate instances
        # see https://github.com/LedFx/LedFx/pull/237
        self.device_configs = {
            "UDP": {
                "name": None,
                "ip_address": None,
                "pixel_count": None,
                "port": 21324,
                "udp_packet_type": "DNRGB",
                "timeout": 1,
                "minimise_traffic": True,
            },
            "DDP": {
                "name": None,
                "ip_address": None,
                "pixel_count": None,
            },
            "E131": {
                "name": None,
                "ip_address": None,
                "pixel_count": None,
                "universe": 1,
                "universe_size": 510,
                "channel_offset": 0,
                "packet_priority": 100,
            },
        }

    def config_updated(self, config):
        if not isinstance(
            self.subdevice, self.SYNC_MODES[self._config["sync_mode"]]
        ):
            self.setup_subdevice()

    def setup_subdevice(self):
        if self.subdevice is not None:
            self.subdevice.deactivate()

        device = self.SYNC_MODES[self._config["sync_mode"]]
        config = self.device_configs[self._config["sync_mode"]]
        config["name"] = self._config["name"]
        config["ip_address"] = self._config["ip_address"]
        config["pixel_count"] = self._config["pixel_count"]
        config["refresh_rate"] = self._config["refresh_rate"]

        self.subdevice = device(self._ledfx, config)
        self.subdevice._destination = self._destination

    def activate(self):

        if self.subdevice is None:
            self.setup_subdevice()
        self.subdevice.activate()
        super().activate()

    def deactivate(self):
        if self.subdevice is not None:
            self.subdevice.deactivate()
        super().deactivate()

    def flush(self, data):
        self.subdevice.flush(data)

    async def async_initialize(self):
        await super().async_initialize()
        # if not self._destination:
        #     self.setup_subdevice()
        #     return
        self.wled = WLED(self._destination)
        wled_config = await self.wled.get_config()

        led_info = wled_config["leds"]
        wled_name = wled_config["name"]
        wled_count = led_info["count"]
        wled_rgbmode = led_info["rgbw"]
        wled_version = wled_config["ver"]

        wled_config = {
            "name": wled_name,
            "pixel_count": wled_count,
            "rgbw_led": wled_rgbmode,
        }

        self._config.update(wled_config)
        self.setup_subdevice()

        # Currently *assuming* that this PR gets released in 0.13
        # https://github.com/Aircoookie/WLED/pull/1944
        if parse_version(wled_version) >= parse_version("0.13.0"):
            _LOGGER.info(
                f"WLED Version Supports Sync Setting API: {wled_version}"
            )
            wled_sync_settings = await self.wled.get_sync_settings()
        # self.wled.enable_realtime_gamma()
        # self.wled.set_inactivity_timeout(self._config["timeout"])
        # self.wled.first_universe()
        # self.wled.first_dmx_address()
        # self.wled.multirgb_dmx_mode()

        # await self.wled.flush_sync_settings()
