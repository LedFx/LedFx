import logging
from typing import ClassVar, Literal

from pydantic import Field

from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.e131 import E131Device
from ledfx.devices.udp import UDPRealtimeDevice
from ledfx.utils import WLED, wled_support_DDP

_LOGGER = logging.getLogger(__name__)


class WLEDDevice(NetworkedDevice):
    """
    Dedicated WLED device support
    This class fetches its config (px count, etc) from the WLED device
    at launch, and lets the user choose a sync mode to use.
    """

    # The settings setup_subdevice copies into the sender.
    OUTPUT_KEYS = ("sync_mode", "name", "ip_address", "pixel_count", "refresh_rate")

    class Config(NetworkedDevice.Config):
        sync_mode: Literal["DDP", "UDP", "E131"] = Field(
            "DDP",
            description="Streaming protocol to WLED device. Recommended: DDP for 0.13 or later. Use UDP for older versions.",
        )
        timeout: int = Field(
            1,
            description="Time between LedFx effect off and WLED effect activate",
            ge=0,
            le=255,
        )
        create_segments: bool = Field(
            False, description="Import WLED segments into LedFx"
        )
        icon_name: str = Field("wled", description="Icon for the device*")

    config = TypedConfig(Config)

    SYNC_MODES: ClassVar[dict[str, type[NetworkedDevice]]] = {
        "UDP": UDPRealtimeDevice,
        "DDP": DDPDevice,
        "E131": E131Device,
    }

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.subdevice = None

        # moved DEVICE_CONFIGS class var to device_configs instance var as it is manipulated in seperate instances
        # see https://github.com/LedFx/LedFx/pull/237
        self.device_configs: dict[str, dict[str, object]] = {
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
                "destination_id": 1,
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
        # Rebuild only when a setting the subdevice copies changes: rebuilding
        # deactivates the sender, and E1.31 blanks the LEDs when it stops.
        if getattr(self, "subdevice", None) is None or self._output_changed():
            self.setup_subdevice()

    def setup_subdevice(self):
        if self.subdevice is not None:
            self.subdevice.deactivate()

        device = self.SYNC_MODES[self.config.sync_mode]
        config = self.device_configs[self.config.sync_mode]
        config["name"] = self.config.name
        config["ip_address"] = self.config.ip_address
        config["pixel_count"] = getattr(self.config, "pixel_count")  # noqa: B009 - stored extra, not a declared field
        config["refresh_rate"] = self.config.refresh_rate

        # Subdevices are built directly, not through RegistryLoader.create.
        self.subdevice = device(
            self._ledfx, device.config_model().model_validate(config)
        )
        self._built_settings = self._output_settings()
        self.subdevice._destination = self._destination
        # A sync_mode change on a live device must not leave the new sender idle.
        if self._active:
            self.subdevice.activate()

    def activate(self):
        if self.subdevice is None:
            self.setup_subdevice()
        self.subdevice.activate()
        super().activate()

    def deactivate(self):
        if self.subdevice is not None:
            self.subdevice.deactivate()
        super().deactivate()

    async def resolve_address(self, success_callback=None):
        await super().resolve_address(success_callback)
        if self.subdevice is not None:
            self.subdevice._destination = self._destination

    def flush(self, data):
        self.subdevice.flush(data)

    async def add_postamble(self):
        _LOGGER.debug("Doing post creation things for WLED...")
        if self.config.create_segments or self._ledfx.config.create_segments:
            segments = await self.wled.get_segments()
            isMatrix = segments[0].get("stopY", 0) > 0
            if len(segments) > 1 or isMatrix:
                for seg in segments:
                    if seg["stop"] - seg["start"] > 0:
                        name = seg.get("n", f"Seg-{seg['id']}")
                        rows = seg.get("stopY", 1)
                        if not rows > 1:
                            self.sub_v(
                                name,
                                None,
                                [[seg["start"], rows * (seg["stop"] - 1)]],
                                rows,
                            )

    async def async_initialize(self):
        await super().async_initialize()
        # if not self._destination:
        #     self.setup_subdevice()
        #     return
        self.wled = WLED(self._destination)
        wled_config = await self.wled.get_config()

        led_info = wled_config["leds"]
        wled_count = led_info["count"]
        wled_rgbmode = led_info["rgbw"]
        wled_build = wled_config["vid"]

        # Not the firmware name: the stored name is the user's choice.
        self._set_config_values(pixel_count=wled_count, rgbw_led=wled_rgbmode)
        self.setup_subdevice()

        # Currently *assuming* that this PR gets released in 0.13
        # https://github.com/Aircoookie/WLED/pull/1944
        if wled_support_DDP(wled_build):
            _LOGGER.info("WLED Build Supports Sync Setting API: %s", wled_build)
            await self.wled.get_sync_settings()
        # self.wled.enable_realtime_gamma()
        # self.wled.set_inactivity_timeout(self.config.timeout)
        # self.wled.first_universe()
        # self.wled.first_dmx_address()
        # self.wled.multirgb_dmx_mode()

        # await self.wled.flush_sync_settings()
