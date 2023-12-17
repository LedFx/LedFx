# pip install pyusb
import usb.core
import usb.util
import asyncio
import logging
import aiohttp
import voluptuous as vol
from ledfx.integrations import Integration
from ledfx.utils import async_fire_and_forget, resolve_destination

_LOGGER = logging.getLogger(__name__)


class DMX(Integration):
    """DMX Integration"""

    beta = False
    _widget_types = ["Button", "Slider", "Audio Triggers"]
    NAME = "DMX USB Controller"
    DESCRIPTION = "DMX USB, For stage lighting such as DMXKing"
    usb_devices = usb.core.find(find_all=True)  # Retrieve USB DMX devices

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default="DMX USB",
            ): str,
            vol.Required(
                "usb_device",
                description="Select the USB DMX device",
                default=None,
            ): vol.In([f"{dev.idVendor:04X}:{dev.idProduct:04X}" for dev in usb_devices]),
        }
    )
