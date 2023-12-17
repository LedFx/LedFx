import PyDMXControl
import logging
import voluptuous as vol
from ledfx.color import parse_color
from ledfx.config import save_config
from ledfx.consts import PROJECT_VERSION
from ledfx.effects.audio import AudioInputSource
from ledfx.events import Event
from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)

# Create an instance of the OpenDMX or uDMX controller
# This will start outputting data immediately
from PyDMXControl.controllers import OpenDMXController
dmx = OpenDMXController()
dmx = PyDMXControl.OpenDMXController() # or PyDMXControl.uDMXController()

# Start the web control panel
dmx.web_control()

_LOGGER.debug("### Available USB Devices ###", dmx)

class USBDMX(Integration):
    """DMX Integration"""

    beta = False
    NAME = "DMX USB Controller"
    DESCRIPTION = "DMX USB, For stage lighting such as DMXKing"

    _usb_devices = {
        "Test1": "Test2",
        "Test3": "Test4",
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
            ): vol.In(list(_usb_devices.keys())),
        }
    )
