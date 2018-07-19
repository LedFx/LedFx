from ledfxcontroller.utils import BaseRegistry, RegistryLoader
from abc import abstractmethod
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

@BaseRegistry.no_registration
class Device(BaseRegistry):

    CONFIG_SCHEMA = vol.Schema({
        vol.Required('name'): str,
        vol.Required('type'): str,
        vol.Optional('max_brightness', default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Optional('refresh_rate', default=60): int,
        vol.Optional('force_refresh', default=False): bool,
        vol.Optional('preview_only', default=False): bool
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

    @property
    def active_effect(self):
        return self._active_effect

    def thread_function(self):
        # TODO: Evaluate switching over to asyncio with UV loop optimization
        # instead of spinning a seperate thread.

        sleep_interval = 1 / self._config['refresh_rate']

        while self._active:
            start_time = time.time()

            # Assemble the frame if necessary, if nothing changed just sleep
            assembled_frame = self.assemble_frame()
            if assembled_frame is not None and not self._config['preview_only']:
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
        frame = None
        if self._active_effect._dirty:
            frame = np.clip(self._active_effect.pixels * self._config['max_brightness'], 0, 255)
            self._active_effect._dirty = self._config['force_refresh']
            self._latest_frame = frame

        return frame

    def activate(self):
        self._active = True
        self._device_thread = Thread(target = self.thread_function)
        self._device_thread.start()

    def deactivate(self):
        self._active = False
        if self._device_thread:
            self._device_thread.join()
            self._device_thread = None

    @abstractmethod
    def flush(self, data):
        """
        Flushes the provided data to the device. This abstract medthod must be 
        overwritten by the device implementation.
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


class Devices(RegistryLoader):
    """Thin wrapper around the device registry that manages devices"""

    PACKAGE_NAME = 'ledfxcontroller.devices'

    def __init__(self, ledfx):
        super().__init__(Device, self.PACKAGE_NAME, ledfx)

    def create_from_config(self, config):
        print(config)
        for device_id, device_config in config.items():
            self.create(
                config = device_config,
                id = device_id,
                name = device_config.get('type'))

    def clear_all_effects(self):
        for device in self.values():
            device.clear_effect()

    def get_device(self, device_id):
        for device in self.values():
            if device_id == device.id:
                return device
        return None


