from ledfx.utils import BaseRegistry, RegistryLoader, generate_id
from ledfx.config import save_config
from ledfx.events import DeviceUpdateEvent, Event
from abc import abstractmethod
from threading import Thread
import voluptuous as vol
import numpy as np
import importlib
import requests
import zeroconf
import pkgutil
import logging
import asyncio
import socket
import time
import os
import re

_LOGGER = logging.getLogger(__name__)

@BaseRegistry.no_registration
class Device(BaseRegistry):

    CONFIG_SCHEMA = vol.Schema({
        vol.Required('name', description='Friendly name for the device'): str,
        vol.Optional('max_brightness', description='Max brightness for the device', default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Optional('center_offset', description='Number of pixels from the preceived center of the device', default=0): int,
        vol.Optional('refresh_rate', description='Rate that pixels are sent to the device', default=60): int,
        vol.Optional('force_refresh', description='Force the device to always refresh', default=False): bool,
        vol.Optional('preview_only', description='Preview the pixels without updating the device', default=False): bool
    })

    _active = False
    _output_thread = None
    _active_effect = None
    _fadeout_effect = None

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = config
        self.fade_timer = 0 # the multiplier to fade in/out of an effect. -ve values mean fading in, +ve mean fading out

    def __del__(self):
        if self._active:
            self.deactivate()

    @property
    def pixel_count(self):
        pass

    def set_effect(self, effect, start_pixel = None, end_pixel = None):
        self.fade_duration = self._config['refresh_rate'] * self._ledfx.config['fade']
        self.fade_timer = self.fade_duration

        if self._active_effect != None:
            self._fadeout_effect = self._active_effect
            self._ledfx.loop.call_later(self._ledfx.config['fade'], self.clear_fadeout_effect)


        self._active_effect = effect
        self._active_effect.activate(self.pixel_count)
        #self._active_effect.setDirtyCallback(self.process_active_effect)
        if not self._active:
            self.activate()

    def clear_effect(self):
        self.fade_duration = self._config['refresh_rate'] * self._ledfx.config['fade']
        self.fade_timer = -self.fade_duration

        self._ledfx.loop.call_later(self._ledfx.config['fade'], self.clear_frame)

    def clear_fadeout_effect(self):
        if self._fadeout_effect is not None:
            self._fadeout_effect.deactivate()
        self._fadeout_effect = None

    def clear_frame(self):
        if self._active_effect != None:
            self._active_effect.deactivate()
            self._active_effect = None
        
        if self._active:
            # Clear all the pixel data before deactivating the device
            self.assembled_frame = np.zeros((self.pixel_count, 3))
            self.flush(self.assembled_frame)
            self._ledfx.events.fire_event(DeviceUpdateEvent(
                self.id, self.assembled_frame))

            self.deactivate()

    @property
    def active_effect(self):
        return self._active_effect

    def process_active_effect(self):
        # Assemble the frame if necessary, if nothing changed just sleep
        self.assembled_frame = self.assemble_frame()
        if self.assembled_frame is not None:
            if not self._config['preview_only']:
                self.flush(self.assembled_frame)

            def trigger_device_update_event(): 
                self._ledfx.events.fire_event(DeviceUpdateEvent(
                    self.id, self.assembled_frame))
            self._ledfx.loop.call_soon_threadsafe(trigger_device_update_event)

    def thread_function(self):
        # TODO: Evaluate switching over to asyncio with UV loop optimization
        # instead of spinning a seperate thread.
        sleep_interval = 1 / self._config['refresh_rate']

        if self._active:
            self._ledfx.loop.call_later(sleep_interval, self.thread_function)
            self.process_active_effect()

        # while self._active:
        #     start_time = time.time()
    
        #     self.process_active_effect()

        #     # Calculate the time to sleep accounting for potential heavy
        #     # frame assembly operations
        #     time_to_sleep = sleep_interval - (time.time() - start_time)
        #     if time_to_sleep > 0:
        #         time.sleep(time_to_sleep)
        # _LOGGER.info("Output device thread terminated.")

    def assemble_frame(self):
        """
        Assembles the frame to be flushed. Currently this will just return
        the active channels pixels, but will eventaully handle things like
        merging multiple segments segments and alpha blending channels
        """
        frame = None
        if self._active_effect._dirty:
            # Get and process active effect frame
            frame = np.clip(self._active_effect.pixels * self._config['max_brightness'], 0, 255)
            if self._config['center_offset']:
                frame = np.roll(frame, self._config['center_offset'], axis = 0)
            self._active_effect._dirty = self._config['force_refresh']
            
            # Handle fading effect in/out if just turned on or off
            if self.fade_timer == 0:
                pass    
            elif self.fade_timer > 0:
                # if +ve fade timer, fade in the effect
                frame *= 1 - (self.fade_timer / self.fade_duration)
                self.fade_timer -= 1
            elif self.fade_timer < 0:
                # if -ve fade timer, fade out the effect
                frame *= -self.fade_timer / self.fade_duration
                self.fade_timer += 1
        
        # This part handles blending two effects together
        fadeout_frame = None
        if self._fadeout_effect:
            if self._fadeout_effect._dirty:
                # Get and process fadeout effect frame
                fadeout_frame = np.clip(self._fadeout_effect.pixels * self._config['max_brightness'], 0, 255)
                if self._config['center_offset']:
                    fadeout_frame = np.roll(fadeout_frame, self._config['center_offset'], axis = 0)
                self._fadeout_effect._dirty = self._config['force_refresh']

                # handle fading out the fadeout frame
                if self.fade_timer:
                    fadeout_frame *= self.fade_timer / self.fade_duration

        # Blend both frames together
        if (fadeout_frame is not None) and (frame is not None):
            frame += fadeout_frame

        return frame

    def activate(self):
        self._active = True
        #self._device_thread = Thread(target = self.thread_function)
        #self._device_thread.start()
        self._device_thread = None
        self.thread_function()

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


class Devices(RegistryLoader):
    """Thin wrapper around the device registry that manages devices"""

    PACKAGE_NAME = 'ledfx.devices'

    def __init__(self, ledfx):
        super().__init__(ledfx, Device, self.PACKAGE_NAME)

        def cleanup_effects(e):
            self.clear_all_effects()

        self._ledfx.events.add_listener(
            cleanup_effects, Event.LEDFX_SHUTDOWN)

    def create_from_config(self, config):
        for device in config:
            _LOGGER.info("Loading device from config: {}".format(device))
            self._ledfx.devices.create(
                id = device['id'],
                type = device['type'],
                config = device['config'],
                ledfx = self._ledfx)
            if 'effect' in device:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx = self._ledfx,
                        type = device['effect']['type'],
                        config = device['effect']['config'])
                    self._ledfx.devices.get_device(device['id']).set_effect(effect)
                except vol.MultipleInvalid:
                    _LOGGER.warning('Effect schema changed. Not restoring effect')
                

    def clear_all_effects(self):
        for device in self.values():
            device.clear_frame()

    def get_device(self, device_id):
        for device in self.values():
            if device_id == device.id:
                return device
        return None

    async def find_wled_devices(self):
        #Scan the LAN network that match WLED using zeroconf - Multicast DNS Service Discovery Library
        _LOGGER.info("Scanning for WLED devices...")
        zeroconf_obj = zeroconf.Zeroconf()
        listener = MyListener(self._ledfx)
        browser = zeroconf.ServiceBrowser(zeroconf_obj, "_wled._tcp.local.", listener)
        try:
            await asyncio.sleep(10)
        finally:
            _LOGGER.info("Scan Finished")
            zeroconf_obj.close()


class MyListener:
    def __init__(self, _ledfx):
        self._ledfx = _ledfx

    def remove_service(self, zeroconf_obj, type, name):
        _LOGGER.info(f"Service {name} removed")

    def add_service(self, zeroconf_obj, type, name):
        # DMX universe_size
        c = 510
        d = 512
        info = zeroconf_obj.get_service_info(type, name)

        if info:
            address = socket.inet_ntoa(info.addresses[0])
            url = f"http://{address}/json/info"
            # For each WLED device found, based on the WLED IPv4 address, do a GET requests
            response = requests.get(url)
            b = response.json()
            # For each WLED json response, format from WLED payload to LedFx payload.
            # Note, set universe_size to 510 if LED 170 or less, If you have more than 170 LED, set universe_size to 510
            wledled = b["leds"]
            wledname = b["name"]
            wledcount = wledled["count"]
            
            if wledcount > 170:
                unisize = c
            else:
                unisize = d

            device_id = generate_id(wledname)
            device_type = "e131"
            device_config = {
                "max_brightness": 1,
                "refresh_rate": 60,
                "universe": 1,
                "universe_size": unisize,
                "name": wledname,
                "pixel_count": wledcount,
                "ip_address": address
            }

            # Check this device doesn't share IP with any other device
            for device in self._ledfx.devices.values():
                if device.config["ip_address"] == address:
                    return

            # Create the device
            _LOGGER.info("Adding device of type {} with config {}".format(device_type, device_config))
            device = self._ledfx.devices.create(
                id = device_id,
                type = device_type,
                config = device_config,
                ledfx = self._ledfx)

            # Update and save the configuration
            self._ledfx.config['devices'].append({'id': device.id, 'type': device.type, 'config': device.config })
            save_config(
                config = self._ledfx.config, 
                config_dir = self._ledfx.config_dir)