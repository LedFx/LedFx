import logging
from typing import TYPE_CHECKING, Annotated

from ledfx_senders import ArtNetSender, Frame
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import X_REQUIRED, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices.native_packet import NativePacketDevice
from ledfx.devices.utils.rgbw_conversion import RGB_MAPPING, WHITE_FUNCS_MAPPING
from ledfx.utils import check_if_ip_is_broadcast, extract_uint8_seq

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_LOGGER = logging.getLogger(__name__)


class ArtNetDevice(NativePacketDevice):
    """Art-Net output with immutable native layout and nonblocking flush ownership."""

    class Config(NativePacketDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        universe: int = Field(0, description="DMX universe for the device", ge=0)
        packet_size: int = Field(
            510, description="Size of each DMX universe", ge=1, le=512
        )
        pre_amble: str = Field(
            "", description="Channel bytes to insert before the RGB data"
        )
        post_amble: str = Field(
            "", description="Channel bytes to insert after the RGB data"
        )
        pixels_per_device: int = Field(
            0,
            description="Number of pixels to consume per device. Pre and post ambles are repeated per device. By default (0) all pixels will be used by one instance",
            ge=0,
        )
        dmx_start_address: int = Field(
            1, description="The start address within the universe", ge=1, le=512
        )
        even_packet_size: bool = Field(
            True, description="Whether to use even packet size"
        )
        rgb_order: Annotated[str, OneOf(RGB_MAPPING)] = Field(
            "RGB",
            description="RGB data order mode, supported for physical hardware that just doesn't play by the rules",
        )
        white_mode: Annotated[str, OneOf(WHITE_FUNCS_MAPPING.keys())] = Field(
            "None",
            description="White channel handling mode, if RGB leave as None. Commonly written as RGBW or RGBA",
        )
        port: int = Field(6454, description="port")

    config = TypedConfig(Config)

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "universe",
        "pixel_count",
        "packet_size",
        "even_packet_size",
        "pixels_per_device",
        "dmx_start_address",
        "rgb_order",
        "white_mode",
        "pre_amble",
        "post_amble",
    )

    def __init__(self, ledfx: "LedFxCore", config: Config) -> None:
        super().__init__(ledfx, config)
        self._device_type = "ArtNet"
        self._validate_configuration()

    @override
    def _validate_configuration(self) -> None:
        ArtNetSender.validate_layout(
            pixel_count=self.config.pixel_count,
            universe=self.config.universe,
            packet_size=self.config.packet_size,
            dmx_start_address=self.config.dmx_start_address,
            pixels_per_device=self.config.pixels_per_device,
            pre_amble=bytes(extract_uint8_seq(self.config.pre_amble)),
            post_amble=bytes(extract_uint8_seq(self.config.post_amble)),
            rgb_order=self.config.rgb_order,
            white_mode=self.config.white_mode,
        )

    @override
    def _make_sender(self, destination: str) -> ArtNetSender:
        return ArtNetSender(
            destination=destination,
            port=self.config.port,
            universe=self.config.universe,
            packet_size=self.config.packet_size,
            even_packet_size=self.config.even_packet_size,
            dmx_start_address=self.config.dmx_start_address,
            pixel_count=self.config.pixel_count,
            pixels_per_device=self.config.pixels_per_device,
            pre_amble=bytes(extract_uint8_seq(self.config.pre_amble)),
            post_amble=bytes(extract_uint8_seq(self.config.post_amble)),
            rgb_order=self.config.rgb_order,
            white_mode=self.config.white_mode,
            broadcast=check_if_ip_is_broadcast(destination),
        )

    @override
    def flush(self, data: Frame) -> None:
        # Keep PR2066 skip-on-busy semantics. Layout construction is now part of
        # candidate preparation, so no do_once can mutate state before ownership.
        if not self.lock.acquire(blocking=False):
            return
        try:
            if not self.device_lock.acquire(blocking=False):
                return
            try:
                if isinstance(self._sender, ArtNetSender):
                    self._sender.send(data)
            finally:
                self.device_lock.release()
        finally:
            self.lock.release()
