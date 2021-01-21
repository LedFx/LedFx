# import asyncio
import logging

# import socket
import time

# from abc import abstractmethod
from functools import cached_property

import numpy as np

# import requests
import voluptuous as vol
import zeroconf

# from ledfx.config import save_config
from ledfx.events import (
    DeviceUpdateEvent,
    EffectClearedEvent,
    EffectSetEvent,
    Event,
)
from ledfx.utils import BaseRegistry, RegistryLoader  # , generate_id

_LOGGER = logging.getLogger(__name__)


class Display(BaseRegistry):

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Friendly name for the display"
            ): str,
            vol.Optional(
                "max_brightness",
                description="Max brightness for the display",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "center_offset",
                description="Number of pixels from the perceived center of the display",
                default=0,
            ): int,
            vol.Optional(
                "preview_only",
                description="Preview the pixels without updating the devices",
                default=False,
            ): bool,
        }
    )

    _active = False
    _output_thread = None
    _active_effect = None
    _fadeout_effect = None

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = config
        # the multiplier to fade in/out of an effect. -ve values mean fading
        # in, +ve mean fading out
        self.fade_timer = 0

        self.SEGMENTS_SCHEMA = vol.Schema(
            {
                self._valid_id: {
                    vol.Required(
                        "start_pixel",
                        description="First pixel the display will map onto device (inclusive)",
                    ): int,
                    vol.Required(
                        "end_pixel",
                        description="Last pixel the display will map onto device (inclusive)",
                    ): int,
                    vol.Optional(
                        "invert",
                        description="Reverse the display mapping onto this device",
                        default=False,
                    ): bool,
                }
            }
        )

    def __del__(self):
        if self._active:
            self.deactivate()

    def _valid_id(self, id):
        device = self._ledfx.devices.get(id)
        if device is not None:
            return device
        else:
            raise ValueError

    def update_segments(self, segments_config):
        _segments = self.SEGMENTS_SCHEMA(segments_config)
        _pixel_count = self.pixel_count

        for new_values, old_values in zip(
            _segments.iteritems(), self._segments.iteritems()
        ):
            if new_values != old_values:
                _LOGGER.debug(
                    f"Display {self.id} segments config changed, reloading devices."
                )
                self._segments = _segments

                # invalidate cached properties
                for prop in [
                    "pixel_count",
                    "refresh_rate",
                    "_devices",
                    "_pixel_indices",
                ]:
                    if hasattr(self, prop):
                        delattr(self, prop)

                break

        # Restart active effect if total pixel count has changed
        # eg. devices might be reordered, but total pixel count is same
        # so no need to restart the effect
        if self.pixel_count != _pixel_count:
            if self._active_effect is not None:
                self._active_effect.deactivate()
                if self.pixel_count > 0:
                    self._active_effect.activate(self.pixel_count)

    def set_effect(self, effect):
        self.fade_duration = (
            self._config["refresh_rate"] * self._ledfx.config["crossfade"]
        )
        self.fade_timer = self.fade_duration

        if self._active_effect is not None:
            self._fadeout_effect = self._active_effect
            self._ledfx.loop.call_later(
                self._ledfx.config["crossfade"], self.clear_fadeout_effect
            )

        self._active_effect = effect
        self._active_effect.activate(self.pixel_count)
        self._ledfx.events.fire_event(EffectSetEvent(self.active_effect.name))
        if not self._active:
            self.activate()

    def clear_effect(self):
        self._ledfx.events.fire_event(EffectClearedEvent())

        self.fade_duration = (
            self._config["refresh_rate"] * self._ledfx.config["crossfade"]
        )
        self.fade_timer = -self.fade_duration

        self._ledfx.loop.call_later(
            self._ledfx.config["crossfade"], self.clear_frame
        )

    def clear_fadeout_effect(self):
        if self._fadeout_effect is not None:
            self._fadeout_effect.deactivate()
        self._fadeout_effect = None

    def clear_frame(self):
        if self._active_effect is not None:
            self._active_effect.deactivate()
            self._active_effect = None

        if self._active:
            # Clear all the pixel data before deactivating the device
            self.assembled_frame = np.zeros((self.pixel_count, 3))
            self.flush(self.assembled_frame)
            self._ledfx.events.fire_event(
                DeviceUpdateEvent(self.id, self.assembled_frame)
            )

            self.deactivate()

    @property
    def active_effect(self):
        return self._active_effect

    def process_active_effect(self):
        # Assemble the frame if necessary, if nothing changed just sleep
        self.assembled_frame = self.assemble_frame()
        if self.assembled_frame is not None:
            if not self._config["preview_only"]:
                self.flush(self.assembled_frame)

            def trigger_device_update_event():
                self._ledfx.events.fire_event(
                    DeviceUpdateEvent(self.id, self.assembled_frame)
                )

            self._ledfx.loop.call_soon_threadsafe(trigger_device_update_event)

    def thread_function(self):
        # TODO: Evaluate switching # over to asyncio with UV loop optimization
        # instead of spinning a separate thread.
        if self._active:
            sleep_interval = 1 / self.refresh_rate
            start_time = time.time()

            self.process_active_effect()

            # Calculate the time to sleep accounting for potential heavy
            # frame assembly operations
            time_to_sleep = sleep_interval - (time.time() - start_time)
            # print(1/time_to_sleep, end="\r") prints current fps

            self._ledfx.loop.call_later(time_to_sleep, self.thread_function)

    def assemble_frame(self):
        """
        Assembles the frame to be flushed. Currently this will just return
        the active channels pixels, but will eventually handle things like
        merging multiple segments segments and alpha blending channels
        """
        frame = None

        # quick bugfix.
        # this all needs to be reworked for effects like real_strobe
        # where the effect drives the device, not vice-versa
        if self._active_effect is None:
            return None

        if self._active_effect._dirty:
            # Get and process active effect frame
            pixels = self._active_effect.get_pixels()
            frame = np.clip(
                pixels * self._config["max_brightness"],
                0,
                255,
            )
            if self._config["center_offset"]:
                frame = np.roll(frame, self._config["center_offset"], axis=0)
            self._active_effect._dirty = self._config["force_refresh"]

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
                fadeout_frame = np.clip(
                    self._fadeout_effect.pixels
                    * self._config["max_brightness"],
                    0,
                    255,
                )
                if self._config["center_offset"]:
                    fadeout_frame = np.roll(
                        fadeout_frame,
                        self._config["center_offset"],
                        axis=0,
                    )
                self._fadeout_effect._dirty = self._config["force_refresh"]

                # handle fading out the fadeout frame
                if self.fade_timer:
                    fadeout_frame *= self.fade_timer / self.fade_duration

        # Blend both frames together
        if (fadeout_frame is not None) and (frame is not None):
            frame += fadeout_frame

        return frame

    def activate(self):
        self._active = True
        # self._device_thread = Thread(target = self.thread_function)
        # self._device_thread.start()
        self._device_thread = None
        self.thread_function()

    def deactivate(self):
        self._active = False
        # if self._device_thread:
        #     self._device_thread.join()
        #     self._device_thread = None

    def flush(self, data):
        """
        Flushes the provided data to the devices.
        """
        idx = 0
        for device, start, end in zip(self._devices, *self._pixel_indices):
            segment_width = end - start + 1
            device.update_pixels(self.id, data[idx:segment_width], start, end)
            idx += segment_width

    @property
    def name(self):
        return self._config["name"]

    @property
    def max_brightness(self):
        return self._config["max_brightness"] * 256

    @property
    def is_active(self):
        return self._active

    @cached_property
    def _pixel_indices(self):
        """
        Lists to help split effect output to the correct pixels of each device
        """
        start_pixels = []
        end_pixels = []
        for segment in self._segments.values():
            start_pixels.append(segment["start_pixel"])
            end_pixels.append(segment["end_pixel"])
        return (start_pixels, end_pixels)

    @cached_property
    def _devices(self):
        """
        Return an iterable of device objects for each segment of the display
        """
        return list(
            self._ledfx.devices.get(device_id)
            for device_id in self._segments.keys()
        )

    @cached_property
    def refresh_rate(self):
        return min(
            self._ledfx.devices.get(device_id).refresh_rate
            for device_id in self._segments.keys()
        )

    @cached_property
    def pixel_count(self):
        total = 0
        for device_info in self._segments.values():
            total += device_info["end_pixel"] - device_info["start_pixel"] + 1
        return total


class Displays(RegistryLoader):
    """Thin wrapper around the device registry that manages displays"""

    PACKAGE_NAME = "ledfx.displays"

    def __init__(self, ledfx):
        super().__init__(ledfx, Display, self.PACKAGE_NAME)

        def cleanup_effects(e):
            self.clear_all_effects()

        self._ledfx.events.add_listener(cleanup_effects, Event.LEDFX_SHUTDOWN)
        self._zeroconf = zeroconf.Zeroconf()

    def create_from_config(self, config):
        for device in config:
            _LOGGER.info("Loading device from config: {}".format(device))
            self._ledfx.devices.create(
                id=device["id"],
                type=device["type"],
                config=device["config"],
                ledfx=self._ledfx,
            )
            if "effect" in device:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=device["effect"]["type"],
                        config=device["effect"]["config"],
                    )
                    self._ledfx.devices.get_device(device["id"]).set_effect(
                        effect
                    )
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Effect schema changed. Not restoring effect"
                    )

    def clear_all_effects(self):
        for display in self.values():
            display.clear_frame()

    def get_display(self, display_id):
        for display in self.values():
            if display_id == display.id:
                return display
        return None
