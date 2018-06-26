from ledfxcontroller.utils import MetaRegistry
from threading import Thread
import voluptuous as vol
import numpy as np
import importlib
import pkgutil
import logging
import time
import os
import re

_LOGGER = logging.getLogger(__name__)

class Device(object, metaclass=MetaRegistry):

    CONFIG_SCHEMA = vol.Schema({
        vol.Required('name'): str,
        vol.Required('type'): str,
        vol.Required('max_brightness', default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Required('refresh_rate', default=60): int,
        vol.Required('force_refresh', default=False): bool
    })

    _active = False
    _output_thread = None
    _active_effect = None
    _latest_frame = None

    def __init__(self, config):
        self._config = config

    def __del__(self):
        if self._active:
            self.deactivate()

    @property
    def pixel_count(self):
        pass

    def set_effect(self, effect, start_pixel = None, end_pixel = None):
        if self._active_effect != None:
            self._active_effect.deactivate()

        self._active_effect = effect
        self._active_effect.activate(self.pixel_count)
        if not self._active:
            self.activate()

    def clear_effect(self):
        if self._active_effect != None:
            self._active_effect.deactivate()
            self._active_effect = None
        
        if self._active:
            # Clear all the pixel data before deactiving the device
            self._latest_frame = np.zeros((self.pixel_count, 3))
            self.flush(self._latest_frame)

            self.deactivate()

    def thread_function(self):
        # TODO: Evaluate switching over to asyncio with UV loop optimization
        # instead of spinning a seperate thread.

        sleep_interval = 1 / self._config['refresh_rate']

        while self._active:
            start_time = time.time()

            # Assemble the frame if necessary, if nothing changed just sleep
            assembled_frame = self.assemble_frame()
            if assembled_frame is not None:
                self._latest_frame = assembled_frame
                self.flush(assembled_frame)

            # Calculate the time to sleep accounting for potential heavy
            # frame assembly operations
            time_to_sleep = sleep_interval - (time.time() - start_time)
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)
        _LOGGER.info("Output device thread terminated.")

    def assemble_frame(self):
        """
        Assembles the frame to be flushed. Currently this will just return
        the active channels pixels, but will eventaully handle things like
        merging multiple segments segments and alpha blending channels
        """
        if self._active_effect._dirty:
            frame = self._active_effect.pixels * self._config['max_brightness']
            self._active_effect._dirty = self._config['force_refresh']
            return np.clip(frame, 0, 255)

        return None

    def activate(self):
        self._active = True
        self._device_thread = Thread(target = self.thread_function)
        self._device_thread.start()

    def deactivate(self):
        self._active = False
        if self._device_thread:
            self._device_thread.join()
            self._device_thread = None

    def flush(self, data):
        """
        Flushes the provided data to the device. This should be overwritten
        by the device implementation
        """

    @property
    def name(self):
        return self._config['name']

    @property
    def max_brightness(self):
        return self._config['max_brightness'] * 256
    
    @property
    def refresh_rate(self):
        return self._config['refresh_rate']

    @property
    def latest_frame(self):
        return self._latest_frame



class DeviceManager(object):
    def __init__(self):
        self._platforms = {}
        self._load_device_platforms()

        self._devices = {}

    @property
    def platforms(self):
        return self._platforms

    def _load_device_platforms(self):
        _LOGGER.info("Loading device platforms.")

        package_directory = os.path.dirname(__file__)
        for (_, moduleName, _) in pkgutil.iter_modules([package_directory]):
            importlib.import_module('.' + moduleName, __package__)

        self._platforms = {}
        for device_platform in Device.get_registry():
            if hasattr(device_platform, 'TYPE_ID'):
                self._platforms[device_platform.TYPE_ID] = device_platform

    def add_device(self, config):
        device_type = config.get('type')
        if device_type is None:
            _LOGGER.error("Invalid device type")
            return None

        validated_config = self._platforms[device_type].get_schema()(config)
        device = self._platforms[device_type](validated_config)
        device.id = re.sub('[^a-z0-9 \.]', '', config['name'].lower()).replace(' ', '_')

        self._devices[device.id] = device
        return device

    def get_device(self, device_id):
        return self._devices.get(device_id)

    def get_devices(self):
        return self._devices

    def clear_all_effects(self):
        for device_id, device in self._devices.items():
            device.clear_effect()




