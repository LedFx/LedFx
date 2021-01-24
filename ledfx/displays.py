# import asyncio
import logging
import time
from functools import cached_property

import numpy as np
import voluptuous as vol
import zeroconf

# from ledfx.config import save_config
from ledfx.events import (
    DisplayUpdateEvent,
    EffectClearedEvent,
    EffectSetEvent,
    Event,
)

_LOGGER = logging.getLogger(__name__)


class Display(object):

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
            vol.Optional(
                "crossfade",
                description="Fade time between effects",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
        }
    )

    # vol.Required(
    #     "start_pixel",
    #     description="First pixel the display will map onto device (inclusive)",
    # ): int,
    # vol.Required(
    #     "end_pixel",
    #     description="Last pixel the display will map onto device (inclusive)",
    # ): int,
    # vol.Optional(
    #     "invert",
    #     description="Reverse the display mapping onto this device",
    #     default=False,
    # ): bool,

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
        self._segments = []

        # list of devices in order of their mapping on the display
        # [[id, start, end, invert]...]
        # not a very good schema, but vol seems a bit handicapped in terms of lists.
        # this won't necessarily ensure perfectly validated segments, but it at
        # least gives an idea of the format
        self.SEGMENTS_SCHEMA = vol.Schema([[self._valid_id, int, int, bool]])

    def __del__(self):
        if self._active:
            self.deactivate()

    def _valid_id(self, id):
        device = self._ledfx.devices.get(id)
        if device is not None:
            return id
        else:
            raise ValueError

    def register_segments(self, segments):
        for device_id, start_pixel, end_pixel, invert in segments:
            device = self._ledfx.devices.get(device_id)
            device.add_segment(self.id, start_pixel, end_pixel)

    def clear_segments(self):
        for device in self._devices:
            device.clear_display_segments(self.id)

    def update_segments(self, segments_config):
        segments_config = [list(item) for item in segments_config]
        _segments = self.SEGMENTS_SCHEMA(segments_config)
        _pixel_count = self.pixel_count

        if _segments != self._segments:
            self.clear_segments()
            # try to register this new set of segments
            # if it fails, restore previous segments and raise the error
            try:
                self.register_segments(_segments)
            except ValueError:
                self.clear_segments()
                self.register_segments(self._segments)
                raise

            self._segments = _segments

            # invalidate cached properties
            for prop in [
                "pixel_count",
                "refresh_rate",
                "_devices",
                "_segments_by_device",
            ]:
                if hasattr(self, prop):
                    delattr(self, prop)

            _LOGGER.info(
                f"Updated display {self.name} with {len(self._segments)} segments, totalling {self.pixel_count} pixels"
            )

            # Restart active effect if total pixel count has changed
            # eg. devices might be reordered, but total pixel count is same
            # so no need to restart the effect
            if self.pixel_count != _pixel_count:
                if self._active_effect is not None:
                    self._active_effect.deactivate()
                    if self.pixel_count > 0:
                        self._active_effect.activate(self.pixel_count)

    def set_effect(self, effect):
        self.fade_duration = self.refresh_rate * self._config["crossfade"]
        self.fade_timer = self.fade_duration

        if self._active_effect is not None:
            self._fadeout_effect = self._active_effect
            self._ledfx.loop.call_later(
                self._config["crossfade"], self.clear_fadeout_effect
            )

        self._active_effect = effect
        self._active_effect.activate(self.pixel_count)
        self._ledfx.events.fire_event(EffectSetEvent(self.active_effect.name))
        if not self._active:
            self.activate()

    def clear_effect(self):
        self._ledfx.events.fire_event(EffectClearedEvent())

        self.fade_duration = self.refresh_rate * self._config["crossfade"]
        self.fade_timer = -self.fade_duration

        self._ledfx.loop.call_later(
            self._config["crossfade"], self.clear_frame
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
                DisplayUpdateEvent(self.id, self.assembled_frame)
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

            def trigger_display_update_event():
                self._ledfx.events.fire_event(
                    DisplayUpdateEvent(self.id, self.assembled_frame)
                )

            self._ledfx.loop.call_soon_threadsafe(trigger_display_update_event)

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

                # handle fading out the fadeout frame
                if self.fade_timer:
                    fadeout_frame *= self.fade_timer / self.fade_duration

        # Blend both frames together
        if (fadeout_frame is not None) and (frame is not None):
            frame += fadeout_frame

        return frame

    def activate(self):
        if not self._devices:
            error = f"Cannot activate display {self.id}, it has no configured device segments"
            _LOGGER.warning(error)
            raise RuntimeError(error)
        if not self._active_effect:
            error = f"Cannot activate display {self.id}, it has no configured effect"
            _LOGGER.warning(error)
            raise RuntimeError(error)

        _LOGGER.info(f"Activating display {self.id}")
        for device in self._devices:
            device.activate()
        self._active = True
        self.thread_function()

    def deactivate(self):
        self._active = False
        # for device in self._devices:
        #     device.deactivate()

    def flush(self, pixels):
        """
        Flushes the provided data to the devices.
        """
        for device_id, segments in self._segments_by_device.items():
            data = []
            for (
                start,
                stop,
                step,
                device_start,
                device_end,
            ) in segments:
                data.append(
                    (pixels[start:stop:step], device_start, device_end)
                )
            self._ledfx.devices.get(device_id).update_pixels(self.id, data)

    @property
    def name(self):
        return self._config["name"]

    @property
    def max_brightness(self):
        return self._config["max_brightness"] * 256

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, _active):
        _active = bool(_active)
        try:
            if _active:
                self.deactivate()
            else:
                self.activate()
        except RuntimeError:
            raise

    @property
    def id(self) -> str:
        """Returns the id for the display"""
        return getattr(self, "_id", None)

    @property
    def segments(self):
        return self._segments

    @cached_property
    def _segments_by_device(self):
        """
        List to help split effect output to the correct pixels of each device
        """
        data_start = 0
        segments_by_device = {}
        for device_id, device_start, device_end, inverse in self._segments:
            segment_width = device_end - device_start + 1
            if not inverse:
                start = data_start
                stop = data_start + segment_width
                step = 1
            else:
                start = data_start + segment_width - 1
                stop = None if data_start == 0 else data_start - 1
                step = -1
            segment_info = (
                start,
                stop,
                step,
                device_start,
                device_end,
            )
            if device_id in segments_by_device.keys():
                segments_by_device[device_id].append(segment_info)
            else:
                segments_by_device[device_id] = [segment_info]
            data_start += segment_width
        return segments_by_device

    @cached_property
    def _devices(self):
        """
        Return an iterable of the device object of each segment of the display
        """
        return list(
            self._ledfx.devices.get(device_id)
            for device_id in set(segment[0] for segment in self._segments)
        )

    @cached_property
    def refresh_rate(self):
        if not self._devices:
            return False
        return min(device.max_refresh_rate for device in self._devices)

    @cached_property
    def pixel_count(self):
        total = 0
        for device_id, start_pixel, end_pixel, invert in self._segments:
            total += end_pixel - start_pixel + 1
        return total

    @property
    def config(self) -> dict:
        """Returns the config for the object"""
        return getattr(self, "_config", None)

    @config.setter
    def config(self, _config):
        """Updates the config for an object"""
        _config = self.CONFIG_SCHEMA(_config)
        return setattr(self, "_config", _config)


class Displays(object):
    """Thin wrapper around the device registry that manages displays"""

    PACKAGE_NAME = "ledfx.displays"

    def __init__(self, ledfx):
        # super().__init__(ledfx, Display, self.PACKAGE_NAME)

        def cleanup_effects(e):
            self.clear_all_effects()

        self._ledfx = ledfx
        self._ledfx.events.add_listener(cleanup_effects, Event.LEDFX_SHUTDOWN)
        self._zeroconf = zeroconf.Zeroconf()
        self._displays = {}

    def create_from_config(self, config):
        for display in config:
            _LOGGER.info(f"Loading display from config: {display}")
            self._ledfx.displays.create(
                id=display["id"],
                config=display["config"],
                ledfx=self._ledfx,
            )
            if "segments" in display:
                self._ledfx.displays.get(display["id"]).update_segments(
                    display["segments"]
                )
            if "effect" in display:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=display["effect"]["type"],
                        config=display["effect"]["config"],
                    )
                    self._ledfx.displays.get(display["id"]).set_effect(effect)
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Effect schema changed. Not restoring effect"
                    )

    def schema(self):
        return Display.CONFIG_SCHEMA

    def create(self, id=None, *args, **kwargs):
        """Creates a display"""

        # Find the first valid id based on what is already in the registry
        dupe_id = id
        dupe_index = 1
        while id in self._displays.keys():
            id = "{}-{}".format(dupe_id, dupe_index)
            dupe_index = dupe_index + 1

        # Create the new display and validate the schema.
        _config = kwargs.pop("config", None)
        if _config is not None:
            _config = Display.CONFIG_SCHEMA(_config)
            obj = Display(config=_config, *args, **kwargs)
        else:
            obj = Display(*args, **kwargs)

        # Attach some common properties
        setattr(obj, "_id", id)

        # Store the object into the internal list and return it
        self._displays[id] = obj
        return obj

    def destroy(self, id):
        if id not in self._displays:
            raise AttributeError(
                ("Object with id '{}' does not exist.").format(id)
            )
        del self._displays[id]

    def __iter__(self):
        return iter(self._displays)

    def values(self):
        return self._displays.values()

    def clear_all_effects(self):
        for display in self.values():
            display.clear_frame()

    def get(self, display_id):
        for id, display in self._displays.items():
            if display_id == id:
                return display
        return None
