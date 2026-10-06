import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ClassVar, Literal

from pydantic import Field
from typing_extensions import override

import ledfx.devices as device_api
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.e131 import E131Device
from ledfx.devices.native_packet import NativePacketDevice
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

    SYNC_MODES: ClassVar[dict[str, type[NativePacketDevice] | type[E131Device]]] = {
        "UDP": UDPRealtimeDevice,
        "DDP": DDPDevice,
        "E131": E131Device,
    }

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.device_lock = threading.RLock()
        self._destination = None
        self._generation = 0
        self._requested = False
        self.subdevice: NativePacketDevice | E131Device | None = None

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

    @override
    @contextmanager
    def _config_update_context(self, config: dict[str, object]) -> Iterator[None]:
        # Device.update_config releases this boundary before virtual callbacks.
        with (
            self._output_lock,
            self.device_lock,
            super()._config_update_context(config),
        ):
            yield

    def config_updated(self, config):
        with self._output_lock, self.device_lock:
            if self.subdevice is None or self._output_changed():
                self.setup_subdevice()

    def setup_subdevice(self):
        with self._output_lock, self.device_lock:
            device = self.SYNC_MODES[self.config.sync_mode]
            config = self.device_configs[self.config.sync_mode].copy()
            config["name"] = self.config.name
            config["ip_address"] = self.config.ip_address
            config["pixel_count"] = self.pixel_count
            config["refresh_rate"] = self.config.refresh_rate
            candidate = device(self._ledfx, device.Config.model_validate(config))
            candidate._destination = self._destination
            try:
                if self._requested:
                    candidate.activate()
            except Exception:
                candidate.deactivate()
                raise
            old = self.subdevice
            self.subdevice = candidate
            self._generation += 1
            self._built_settings = self._output_settings()
            if old is not None:
                old.deactivate()

    def activate(self):
        with self._output_lock, self.device_lock:
            self._requested = True
            if self.subdevice is None:
                self.setup_subdevice()
            else:
                self.subdevice.activate()
            super().activate()

    def deactivate(self):
        with self._output_lock, self.device_lock:
            self._requested = False
            self._generation += 1
            if self.subdevice is not None:
                self.subdevice.deactivate()
            super().deactivate()

    @override
    async def resolve_address(
        self, success_callback: Callable[[], object] | None = None
    ) -> None:
        with self._output_lock, self.device_lock:
            address, generation = self.config.ip_address, self._generation
        try:
            destination = await device_api.resolve_destination(
                self._ledfx.loop, self._ledfx.thread_executor, address
            )
        except ValueError as error:
            with self._output_lock, self.device_lock:
                if generation == self._generation and address == self.config.ip_address:
                    self._online = False
                    _LOGGER.warning("Device %s: %s", self.name, error)
            return
        with self._output_lock, self.device_lock:
            if generation != self._generation or address != self.config.ip_address:
                return
            child = self.subdevice
            if child is not None:
                # Parent ownership precedes child ownership and its sender lock.
                with child._output_lock, child.device_lock:
                    previous = child._destination
                    child._destination = destination
                    try:
                        if self._requested and (
                            previous != destination or child._sender is None
                        ):
                            child.activate()
                    except Exception:
                        child._destination = previous
                        raise
                    child._online = True
            self._destination = destination
            self._online = True
        if success_callback is not None:
            success_callback()

    def flush(self, data):
        with self._output_lock, self.device_lock:
            if self.subdevice is not None:
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
