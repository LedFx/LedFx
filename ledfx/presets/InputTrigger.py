from ledfx.devices import Device
import logging
import voluptuous as vol
import numpy as np
import socket
from ledfx.devices.lib.opc import Client

_LOGGER = logging.getLogger(__name__)

class Fadecandy(Device):
    """Generic UDP device support"""

    CONFIG_SCHEMA = vol.Schema({
        vol.Required('ip_address', description='Hostname or IP address of the device'): str,
        vol.Required('port', description='Port for the UDP device'): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required('channel', description='Pixel Channel'): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        vol.Required('pixel_count', description='Number of individual pixels'): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional('data_prefix', description='Data to be appended in hex format'): str,
        vol.Optional('data_postfix', description='Data to be prepended in hex format'): str,
    })

    def activate(self):
        self._opc = Client(self._config['ip_address'] + ":" + str(self._config['port']))
        super().activate()

    def deactivate(self):
        super().deactivate()
        if self._opc:
            self._opc.disconnect()
            self._opc = None

    @property
    def pixel_count(self):
        return int(self._config['pixel_count'])

    def flush(self, data):
        d = data.astype(np.dtype('B'))
        #print(d)
        self._opc.put_pixels(d, channel = self._config['channel'])
