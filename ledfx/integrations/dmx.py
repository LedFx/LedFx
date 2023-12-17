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


async def on_start(self):
    # Scan and populate USB DMX devices
    usb_devices = await self.scan_usb_dmx_devices()
    device_names = [
        f"{dev.idVendor:04X}:{dev.idProduct:04X}" for dev in usb_devices]

    # Add USB DMX devices to dropdown field
    self.config_schema = self.config_schema.extend(
        {
            vol.Required(
                "usb_device",
                description="Select the USB DMX device",
                default=None,
                valid_values=device_names,
            ): str,
        }
    )


async def scan_usb_dmx_devices(self):
    """Scan for USB DMX devices"""
    usb_devices = usb.core
    # usb_devices = usb.core.find(find_all=True, idVendor=0xXXXX, idProduct=0xXXXX)  # Replace with your vendor and product IDs
    return usb_devices


class DMX(Integration):
    """DMX Integration"""
    beta = False
    _widget_types = ["Button", "Slider", "Audio Triggers"]
    NAME = "DMX USB Controller"
    DESCRIPTION = "DMX USB, For stage lighting such as DMXKing"

    _usb_dmx = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

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
            ): vol.In(list(_usb_dmx.keys())),
            # vol.Required(
            #     "description",
            #     description="Description of this integration",
            #     default="DMX USB",
            # ): str,
        }
    )

    # Add other methods as needed


# Example usage:
# Create an instance of the DMX class
# dmx_instance = DMX()

# Start the integration
# asyncio.run(dmx_instance.on_start())
