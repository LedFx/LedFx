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
                "port": 4048,
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

    # def async onAfterDeviceAdded():
    #     _LOGGER.info("HACKED BY Y WLED-after")
    #      if device_config["create_segments"]:
    #         segments = await get_segments() #from utils.py
    #         if segments.length > 1: # this is javascript condition for if array has more than one element
    #             for seg in segments:
    #                 if seg.stop - seg.start > 0:
    #                     self.sub_v(device, seg.id, "wled", [[seg.start, seg.stop]], 1)

    # def onBeforeDeviceAdded():
    #     _LOGGER.info("HACKED BY Y WLED-b4")

    # wled = WLED(resolved_dest)
    # wled_config = await wled.get_config()

    # led_info = wled_config["leds"]
    # # If we've found the device via WLED scan, it won't have a custom name from the frontend
    # # However if it's "WLED" (i.e, Default) then we will name the device exactly how WLED does, by using the second half of it's MAC address
    # # This allows us to respect the users choice of names if adding a WLED device via frontend
    # # I turned black off as this logic is clearer on one line
    # # fmt: off
    # if "name" in device_config.keys() and device_config["name"] is not None:
    #     wled_name = device_config["name"]
    # elif wled_config["name"] == "WLED":
    #     wled_name = f"{wled_config['name']}-{wled_config['mac'][6:]}".upper()
    # else:
    #     wled_name = wled_config['name']
    # # fmt: on
    # wled_count = led_info["count"]
    # wled_rgbmode = led_info["rgbw"]

    # wled_config = {
    #     "name": wled_name,
    #     "pixel_count": wled_count,
    #     "icon_name": "wled",
    #     "rgbw_led": wled_rgbmode,
    # }

    # # determine sync mode
    # # UDP < 480
    # # DDP or E131 depending on: ledfx's configured preferred mode first, else the device's mode
    # # ARTNET can do one

    # if wled_count > 480:
    #     await wled.get_sync_settings()
    #     sync_mode = wled.get_sync_mode()
    # else:
    #     sync_mode = "UDP"

    #     # preferred_mode = self._ledfx.config["wled_preferences"][
    #     #     "wled_preferred_mode"
    #     # ]
    #     # if preferred_mode:
    #     #     sync_mode = preferred_mode
    #     # else:
    #     #     await wled.get_sync_settings()
    #     #     sync_mode = wled.get_sync_mode()

    # if sync_mode == "ARTNET":
    #     msg = f"Cannot add WLED device at {resolved_dest}. Unsupported mode: 'ARTNET', and too many pixels for UDP sync (>480)"
    #     _LOGGER.warning(msg)
    #     raise ValueError(msg)

    # wled_config["sync_mode"] = sync_mode
    # device_config.update(wled_config)
