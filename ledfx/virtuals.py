import itertools
import logging
import sys
import threading
import time
import timeit
from functools import cached_property
from typing import Optional

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color
from ledfx.config import save_config
from ledfx.effects import DummyEffect
from ledfx.effects.math import interpolate_pixels, make_pattern
from ledfx.effects.melbank import (
    MAX_FREQ,
    MIN_FREQ,
    MIN_FREQ_DIFFERENCE,
    FrequencyRange,
)
from ledfx.effects.oneshots.oneshot import Oneshot
from ledfx.events import (
    EffectClearedEvent,
    EffectSetEvent,
    Event,
    GlobalPauseEvent,
    VirtualConfigUpdateEvent,
    VirtualPauseEvent,
    VirtualUpdateEvent,
)
from ledfx.transitions import Transitions
from ledfx.utils import fps_to_sleep_interval

_LOGGER = logging.getLogger(__name__)

color_list = ["red", "green", "blue", "cyan", "magenta", "#ffff00"]


class Virtual:
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Friendly name for the device"
            ): str,
            vol.Required(
                "mapping",
                description="Span: Effect spans all segments. Copy: Effect copied on each segment",
                default="span",
            ): vol.In(["span", "copy"]),
            vol.Required(
                "grouping",
                description="Number of physical pixels to combine into larger virtual pixel groups",
                default=1,
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "icon_name",
                description="Icon for the device*",
                default="mdi:led-strip-variant",
            ): str,
            vol.Optional(
                "max_brightness",
                description="Max brightness for the device",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "center_offset",
                description="Number of pixels from the perceived center of the device",
                default=0,
            ): int,
            vol.Optional(
                "preview_only",
                description="Preview the pixels without updating the devices",
                default=False,
            ): bool,
            vol.Optional(
                "transition_time",
                description="Length of transition between effects",
                default=0.4,
            ): vol.All(
                vol.Coerce(float),
                vol.Range(min=0, max=5, min_included=True, max_included=True),
            ),
            vol.Optional(
                "transition_mode",
                description="Type of transition between effects",
                default="Add",
            ): vol.In([mode for mode in Transitions]),
            vol.Optional(
                "frequency_min",
                description="Lowest frequency for this virtual's audio reactive effects",
                default=MIN_FREQ,  # GET THIS FROM CORE AUDIO
            ): vol.All(
                vol.Coerce(int),
                vol.Range(
                    min=MIN_FREQ,
                    max=MAX_FREQ,
                ),
            ),  # AND HERE TOO,
            vol.Optional(
                "frequency_max",
                description="Highest frequency for this virtual's audio reactive effects",
                default=MAX_FREQ,  # GET THIS FROM CORE AUDIO
            ): vol.All(
                vol.Coerce(int),
                vol.Range(
                    min=MIN_FREQ,
                    max=MAX_FREQ,
                ),
            ),  # AND HERE TOO,
            vol.Optional(
                "rows",
                description="Amount of rows. > 1 if this virtual is a matrix",
                default=1,
            ): int,
            # we will hide this slider in the front end if rows is <= 1
            vol.Optional(
                "rotate",
                description="90 Degree rotations",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
        }
    )

    # vol.Required(
    #     "start_pixel",
    #     description="First pixel the virtual will map onto device (inclusive)",
    # ): int,
    # vol.Required(
    #     "end_pixel",
    #     description="Last pixel the virtual will map onto device (inclusive)",
    # ): int,
    # vol.Optional(
    #     "invert",
    #     description="Reverse the virtual mapping onto this device",
    #     default=False,
    # ): bool,

    _paused = False
    _active = False
    _output_thread = None
    _active_effect = None
    _transition_effect = None

    if (
        sys.version_info[0] == 3 and sys.version_info[1] >= 11
    ) or sys.version_info[0] >= 4:
        _min_time = time.get_clock_info("perf_counter").resolution
    else:
        _min_time = time.get_clock_info("monotonic").resolution

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = config
        # the multiplier to fade in/out of an effect. -ve values mean fading
        # in, +ve mean fading out
        self.fade_timer = 0
        self._segments = []
        self._calibration = False
        self._hl_state = False
        self._hl_device = None
        self._hl_start = 0
        self._hl_end = 0
        self._hl_step = 1
        self._oneshots = []
        self._os_active = False
        self.lock = threading.Lock()
        self.clear_handle = None
        self.fallback_effect_type = None
        self.fallback_active = False
        self.fallback_fire = False
        self.fallback_config = None
        self.fallback_timer = None
        self.fallback_suppress_transition = False
        self._streaming = False

        self.frequency_range = FrequencyRange(
            self._config["frequency_min"], self._config["frequency_max"]
        )

        # list of devices in order of their mapping on the virtual
        # [[id, start, end, invert]...]
        # not a very good schema, but vol seems a bit handicapped in terms of lists.
        # this won't necessarily ensure perfectly validated segments, but it at
        # least gives an idea of the format
        self.SEGMENTS_SCHEMA = vol.Schema([self.validate_segment])

    def __del__(self):
        self.active = False

    def _valid_id(self, id):
        device = self._ledfx.devices.get(id)
        if device is not None:
            return id
        else:
            msg = f"Invalid device id: {id}"
            _LOGGER.warning(msg)
            raise ValueError(msg)

    def activate_segments(self, segments):
        for device_id, start_pixel, end_pixel, invert in segments:
            device = self._ledfx.devices.get(device_id)
            if not device.is_active():
                device.activate()
            device.add_segment(self.id, start_pixel, end_pixel, force=True)

    def deactivate_segments(self):
        for device in self._devices:
            device.clear_virtual_segments(self.id)

    def validate_segment(self, segment):
        valid = True
        msg = None

        if len(segment) != 4:
            msg = f"Invalid segment format: {segment}, should be [device_id, start, end, invert]"
            valid = False

        device_id, start_pixel, end_pixel, invert = segment

        device = self._ledfx.devices.get(device_id)

        if device is None:
            msg = f"Invalid device id: {device_id}"
            valid = False
        elif (
            start_pixel < 0
            or end_pixel < 0
            or start_pixel > end_pixel
            or start_pixel >= device.pixel_count
            or end_pixel >= device.pixel_count
        ):
            _LOGGER.warning(
                f"Invalid segment pixels in Virtual '{self.name}': segment('{device.name}' ({start_pixel}, {end_pixel})) valid pixels between (0, {device.pixel_count - 1})"
            )
            if start_pixel < 0:
                start_pixel = 0
            if end_pixel < 0:
                end_pixel = 0
            if start_pixel > end_pixel:
                start_pixel = end_pixel
            if start_pixel >= device.pixel_count:
                start_pixel = device.pixel_count - 1
            if end_pixel >= device.pixel_count:
                end_pixel = device.pixel_count - 1
            segment = [device_id, start_pixel, end_pixel, invert]
            _LOGGER.warning(f"Fixed to {segment}")

        if not valid:
            _LOGGER.error(msg)
            raise ValueError(msg)
        else:
            return segment

    def invalidate_cached_props(self):
        # invalidate cached properties
        for prop in [
            "pixel_count",
            "refresh_rate",
            "_devices",
            "_segments_by_device",
            "effective_pixel_count",
            "group_size",
        ]:
            if hasattr(self, prop):
                delattr(self, prop)

    def _reactivate_effect(self):
        self.clear_transition_effect()
        self.transitions = Transitions(self.effective_pixel_count)
        if self._active_effect is not None:
            self._active_effect._deactivate()
            if self.pixel_count > 0:
                self._active_effect.activate(self)

    def update_segments(self, segments_config):
        """
        Update the segments of the virtual with the given configuration.

        Args:
            segments_config (list): A list of segment configurations.

        Raises:
            ValueError: If the new set of segments cannot be activated.

        Returns:
            None
        """
        with self.lock:
            segments_config = [list(item) for item in segments_config]
            _segments = self.SEGMENTS_SCHEMA(segments_config)

            _pixel_count = self.pixel_count

            if _segments != self._segments:
                if self._active:
                    self.deactivate_segments()
                    # try to register this new set of segments
                    # if it fails, restore previous segments and raise the error
                    try:
                        self.activate_segments(_segments)
                    except ValueError:
                        self.deactivate_segments()
                        self.activate_segments(self._segments)
                        raise

                self._segments = _segments

                self.invalidate_cached_props()

                # Restart active effect if total pixel count has changed
                # eg. devices might be reordered, but total pixel count is same
                # so no need to restart the effect
                if self.pixel_count != _pixel_count:
                    # chenging segments is a deep edit, just flush any transition
                    self._reactivate_effect()

                mode = self._config["transition_mode"]
                self.frame_transitions = self.transitions[mode]
            # Update internal config with new segment if it exists, device creation only substantiates this later, so we need the test
            if hasattr(self, "virtual_cfg") and self.virtual_cfg is not None:
                self.virtual_cfg["segments"] = self._segments

            _LOGGER.debug(
                f"Virtual {self.id}: updated with {len(self._segments)} segments, totalling {self.pixel_count} pixels"
            )
            self._ledfx.virtuals.check_and_deactivate_devices()

    def set_preset(self, preset_info):
        """
        Sets the preset for the virtual.

        Args:
            preset_info (tuple): A tuple containing the category, effect_id, and preset_id of the preset.

        Returns:
            None
        """
        category, effect_id, preset_id = preset_info

        # Create the effect and add it to the virtual
        try:
            effect_config = self._ledfx.config[category][effect_id][preset_id][
                "config"
            ]
        except KeyError:
            _LOGGER.error(f"Cannot find preset: {preset_info}")
            return
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_id, config=effect_config
        )
        self.set_effect(effect)

    def set_fallback(self):
        """
        Sets the active effect to the stored fallback effect if available.
        """

        if self.fallback_active:
            if self.fallback_effect_type is not None:

                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx,
                    type=self.fallback_effect_type,
                    config=self.fallback_config,
                )
                self.set_effect(effect, fallback=None)
                self.update_effect_config(effect)
                _LOGGER.info(f"{self.name} set_fallback: suppress = False")
            else:
                # there was no active effect when the fallback effect started
                self.clear_effect()
                # and make sure we save the config with the effect removed
                self.virtual_cfg.pop("effect", None)

            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
            self.fallback_clear()

    def fallback_clear(self):
        """clear down all fallback behaviours, normally called after a fallback has completed"""
        self.fallback_effect_type = None
        if self.fallback_timer is not None:
            self.fallback_timer.cancel()
            self.fallback_timer = None
        self.fallback_suppress_transition = False
        self.fallback_active = False
        _LOGGER.info(f"{self.name} fallback_clear: suppress = False")

    def fallback_start(self, fallback: float):
        """Suppress transitions, clear and start the fallback timer
        This funciton should only be called from within the virtual lock

        Args:
            fallback (float): Time in seconds to wait before firing the fallback
        """
        self.fallback_suppress_transition = True
        _LOGGER.info(f"{self.name} fallback_start: suppress = True")

        if self.fallback_timer is not None:
            self.fallback_timer.cancel()
        _LOGGER.info(f"Setting fallback timer for {fallback} seconds")
        self.fallback_timer = threading.Timer(fallback, self.fallback_fire_set)
        self.fallback_timer.start()
        self.fallback_active = True

    def fallback_fire_set_with_lock(self):
        """Use this function to trigger a fallback from an external source such as api calls"""
        with self.lock:
            self.fallback_fire_set()

    def fallback_fire_set(self):
        """clear fallback timers and trigger the fallback to enact"""
        if self.fallback_timer is not None:
            self.fallback_timer.cancel()
            self.fallback_timer = None
        if self.fallback_active:
            _LOGGER.info(f"{self.name} fallback_fire_set")
            self.fallback_fire = True

    def set_effect(self, effect, fallback: Optional[float] = None):
        """
        Sets the active effect for the virtual device.

        Args:
            effect: The effect to set as the active effect.
            fallback: If not None, the current active effect is set as the fallback effect
                      and a fallback timer triggered for fallback seconds
                      If None, the new effect is set and any existing fallback timer is cleared

        Raises:
            ValueError: If no configured device segments are available.
            RuntimeError: If an error occurs while setting the active effect.

        """
        with self.lock:
            if not self._devices:
                error = f"Virtual {self.id}: Cannot activate, no configured device segments"
                _LOGGER.warning(error)
                raise ValueError(error)

            if fallback is not None:
                _LOGGER.info("Fallback requested")
                if self._active_effect is None:
                    _LOGGER.info("No current _active_effect to fallback to")
                    self.fallback_effect_type = None
                elif not self.fallback_active:
                    self.fallback_effect_type = self._active_effect.type
                    self.fallback_config = self._active_effect.config
                    _LOGGER.info(
                        f"Setting fallback to {self.fallback_effect_type}"
                    )
                # else: don't let new fallbacks override active fallbacks, just bump the timer
                self.fallback_start(fallback)

            if (
                self._config["transition_mode"] != "None"
                and self._config["transition_time"] > 0
                and not self.fallback_suppress_transition
            ):
                self.transition_frame_total = (
                    self.refresh_rate * self._config["transition_time"]
                )
                self.transition_frame_counter = 0
                self.clear_transition_effect()

                if self._active_effect is None:
                    self._transition_effect = DummyEffect(
                        self.effective_pixel_count
                    )
                else:
                    self._transition_effect = self._active_effect
            else:
                # no transition effect to clean up, so clear the active effect now!
                self.clear_active_effect()
                self.clear_transition_effect()

            if fallback is None:
                # any effect being set without fallback will clear the fallback
                # remove suppression of transitions
                self.fallback_clear()

            self.flush_pending_clear_frame()

            self._active_effect = effect
            self._active_effect.activate(self)
            self._ledfx.events.fire_event(
                EffectSetEvent(
                    self._active_effect.name,
                    self._active_effect.id,
                    self.active_effect.config,
                    self.id,
                )
            )
        try:
            self.active = True
        except RuntimeError:
            self.active = False
            raise

    def transition_to_active(self):
        self._active_effect = self._transition_effect
        self._transition_effect = None

    def active_to_transition(self):
        self._transition_effect = self._active_effect
        self._active_effect = None

    def clear_effect(self):
        with self.lock:
            self._ledfx.events.fire_event(EffectClearedEvent(self.id))
            self.clear_transition_effect()

            if (
                self._config["transition_mode"] != "None"
                and self._config["transition_time"] > 0
                and not self.fallback_suppress_transition
            ):
                self._transition_effect = self._active_effect
                self._active_effect = DummyEffect(self.effective_pixel_count)

                self.transition_frame_total = (
                    self.refresh_rate * self._config["transition_time"]
                )
                self.transition_frame_counter = 0
            else:
                # no transition effect to clean up, so clear the active effect now!
                self.clear_active_effect()

            self.flush_pending_clear_frame()

            delay = (
                0
                if self.fallback_suppress_transition
                else self._config["transition_time"]
            )
            self.clear_handle = self._ledfx.loop.call_later(
                delay, self.clear_frame
            )

    def flush_pending_clear_frame(self):
        if self.clear_handle is not None:
            self.clear_handle.cancel()
            self.clear_handle = None

    def clear_transition_effect(self):
        if self._transition_effect is not None:
            self._transition_effect._deactivate()
        self._transition_effect = None

    def clear_active_effect(self):
        if self._active_effect is not None:
            self._active_effect._deactivate()
        self._active_effect = None

    def clear_frame(self):
        """
        Clears the frame by performing the following steps:
        1. Clears the active effect.
        2. Clears the transition effect.
        3. If the virtual device is active:
           - Clears all the pixel data by setting it to zeros.
           - Flushes the assembled frame to the device.
           - Fires a VirtualUpdateEvent to notify listeners of the updated frame.
           - Releases the lock.
           - Deactivates the virtual device.
        """
        # Little tricky logic here - we need to clear the active effect and
        # transition effect before we flush the frame, but we need to flush
        # the frame before we deactivate the virtual device. We also need to
        # make sure that we don't clear the frame if the virtual device is
        # not active.
        # All of this requires thread lock management that's a bit unwieldy

        assembled_frame = None
        with self.lock:
            self.clear_active_effect()
            self.clear_transition_effect()
            if self._active:
                assembled_frame = np.zeros((self.pixel_count, 3))
                self.flush(assembled_frame)
                self._fire_update_event(assembled_frame)

        # Deactivate the device - this requires the thread lock
        # Hence why we do it outside of the lock and after the frame is cleared
        # This is because the deactivate method will join the thread
        # and we don't want to call join while holding the lock
        if assembled_frame is not None:
            self.deactivate()

    def force_frame(self, color):
        """
        Force all pixels in device to color
        Use for pre-clearing in calibration scenarios
        """
        self.assembled_frame = np.full((self.effective_pixel_count, 3), color)
        self.flush(self.assembled_frame)
        self._fire_update_event()

    def _fire_update_event(self, frame=None):
        if frame is None:
            frame = self.assembled_frame

        self._ledfx.events.fire_event(
            VirtualUpdateEvent(
                self.id, self._effective_to_physical_pixels(frame)
            )
        )

    def set_calibration(self, calibration):
        self._calibration = calibration

    def set_highlight(self, state, device_id, start, end, flip):
        if self._calibration is False:
            return f"Cannot set highlight when {self.name} is not in calibration mode"

        self._hl_state = state
        if not state:
            return None

        device_id = device_id.lower()
        device = self._ledfx.devices.get(device_id)
        if device is None:
            return f"Device {device_id} not found"

        if start > device.pixel_count - 1 or end > device.pixel_count - 1:
            return f"start and end must be less than {device.pixel_count}"

        self._hl_device = device_id
        self._hl_start = start
        self._hl_end = end
        if flip:
            self._hl_step = -1
        else:
            self._hl_step = 1
        return None

    @property
    def active_effect(self):
        return self._active_effect

    def thread_function(self):
        while True:
            if not self._active:
                break
            start_time = timeit.default_timer()

            if self.fallback_fire:
                self.set_fallback()
                self.fallback_fire = False

            # we need to lock before we test, or we could deactivate
            # between test and execution
            with self.lock:
                if (
                    self._active_effect
                    and self._active_effect.is_active
                    and hasattr(self._active_effect, "pixels")
                ):
                    # self.assembled_frame = await self._ledfx.loop.run_in_executor(
                    #     self._ledfx.thread_executor, self.assemble_frame
                    # )
                    self.assembled_frame = self.assemble_frame()
                    if self.assembled_frame is not None and not self._paused:
                        if not self._config["preview_only"]:
                            # self._ledfx.thread_executor.submit(self.flush)
                            # await self._ledfx.loop.run_in_executor(
                            #     self._ledfx.thread_executor, self.flush
                            # )
                            self.flush()

                        self._fire_update_event()

            # adjust for the frame assemble time, min allowed sleep 1 ms
            # this will be more frame accurate on high res sleep systems
            run_time = timeit.default_timer() - start_time
            sleep_time = max(
                0.001, fps_to_sleep_interval(self.refresh_rate) - run_time
            )
            time.sleep(sleep_time)

            # use an aggressive check for did we sleep against expected min clk
            # for all high res scenarios this will be passive
            # for unexpected high res sleep on windows scenarios it will adapt
            pass_time = timeit.default_timer() - start_time
            if pass_time < (self._min_time / 2):
                time.sleep(max(0.001, self._min_time - pass_time))

    def assemble_frame(self):
        """
        Assembles the frame to be flushed.
        """
        # Get and process active effect frame
        self._active_effect._render()
        frame = self._active_effect.get_pixels()
        if frame is not None:
            frame[frame > 255] = 255
            frame[frame < 0] = 0
            # np.clip(frame, 0, 255, frame)

            if self._config["center_offset"]:
                frame = np.roll(frame, self._config["center_offset"], axis=0)

            # This part handles blending two effects together
            if (
                self._transition_effect is not None
                and self._transition_effect.is_active
                and hasattr(self._transition_effect, "pixels")
            ):
                # Get and process transition effect frame
                self._transition_effect._render()
                transition_frame = self._transition_effect.get_pixels()
                transition_frame[transition_frame > 255] = 255
                transition_frame[transition_frame < 0] = 0

                if self._config["center_offset"]:
                    transition_frame = np.roll(
                        transition_frame,
                        self._config["center_offset"],
                        axis=0,
                    )

                # Blend both frames together
                self.transition_frame_counter += 1
                self.transition_frame_counter = min(
                    max(self.transition_frame_counter, 0),
                    self.transition_frame_total,
                )

                if self.transition_frame_total == 0:
                    # the transition should happen immediately
                    weight = 1
                else:
                    # calculates how far in we are in the transition
                    # 0 = previous effect and 1 = next effect
                    weight = (
                        self.transition_frame_counter
                        / self.transition_frame_total
                    )

                # we will pre validate the transition, which will generate a sentry report if it fails and return False
                if self.transitions.pre_validate(frame, transition_frame):
                    # only call the transition effect if it will not crash
                    self.frame_transitions(
                        self.transitions, frame, transition_frame, weight
                    )
                if (
                    self.transition_frame_counter
                    == self.transition_frame_total
                ):
                    self.clear_transition_effect()

            np.multiply(frame, self._config["max_brightness"], frame)
            np.multiply(frame, self._ledfx.config["global_brightness"], frame)
        return frame

    def activate(self):
        if not self._devices:
            error = f"Virtual {self.id}: Cannot activate, no configured device segments"
            _LOGGER.warning(error)
            raise RuntimeError(error)
        if not self._active_effect:
            error = f"Virtual {self.id}: Cannot activate, no configured effect"
            _LOGGER.warning(error)
            raise RuntimeError(error)

        if hasattr(self, "_thread"):
            self._thread.join()

        _LOGGER.debug(
            f"Virtual {self.id}: Activating with segments {self._segments}"
        )
        if not self._active:
            self._active = True
            try:
                self.activate_segments(self._segments)
            except ValueError as e:
                _LOGGER.error(e)
            self._os_active = False

        # self.thread_function()

        self._thread = threading.Thread(
            name=f"Virtual: {self.id}", target=self.thread_function
        )
        self._thread.start()
        self._ledfx.events.fire_event(VirtualPauseEvent(self.id, not self._active))
        # self._task = self._ledfx.loop.create_task(self.thread_function())
        # self._task.add_done_callback(lambda task: task.result())
        self._ledfx.virtuals.check_and_deactivate_devices()

    def deactivate(self):
        self._active = False
        self._os_active = False
        if hasattr(self, "_thread"):
            self._thread.join()
        self.deactivate_segments()
        self._ledfx.events.fire_event(VirtualPauseEvent(self.id, not self._active))
        self._ledfx.virtuals.check_and_deactivate_devices()

    # @lru_cache(maxsize=32)
    # def _normalized_linspace(self, size):
    #     return np.linspace(0, 1, size)

    # def interp_channel(self, channel, x_new, x_old):
    #     return np.interp(x_new, x_old, channel)

    # # TODO cache this!
    # # need to be able to access pixels but not through args
    # # @lru_cache(maxsize=8)
    # def interpolate(self, pixels, new_length):
    #     """Resizes the array by linearly interpolating the values"""
    #     if len(pixels) == new_length:
    #         return pixels

    #     x_old = self._normalized_linspace(len(pixels))
    #     x_new = self._normalized_linspace(new_length)

    #     z = np.apply_along_axis(self.interp_channel, 0, pixels, x_new, x_old)
    #     return z

    def flush(self, pixels=None):
        """
        Flushes the provided data to the devices.
        """

        if pixels is None:
            pixels = self.assembled_frame

        # Where we update oneshots
        oneshot_index = 0
        while oneshot_index < len(self._oneshots):
            oneshot = self._oneshots[oneshot_index]
            oneshot.update()
            if not oneshot.active:
                self._oneshots.remove(oneshot)
            else:
                oneshot_index += 1

        if self._config["mapping"] == "span":
            # In span mode we can calculate the final pixels once for all segments
            pixels = self._effective_to_physical_pixels(pixels)

        color_cycle = itertools.cycle(color_list)

        for device_id, segments in self._segments_by_device.items():
            data = []
            device = self._ledfx.devices.get(device_id)
            if device is not None:
                if device.is_active():
                    if self._calibration:
                        self.render_calibration(
                            data, device, segments, device_id, color_cycle
                        )
                    elif self._config["mapping"] == "span":
                        for (
                            start,
                            stop,
                            step,
                            device_start,
                            device_end,
                        ) in segments:
                            seg = pixels[start:stop:step]
                            # Where we override segment
                            for oneshot in self._oneshots:
                                oneshot.apply(seg, start, stop)
                            data.append((seg, device_start, device_end))
                    elif self._config["mapping"] == "copy":
                        for (
                            start,
                            stop,
                            step,
                            device_start,
                            device_end,
                        ) in segments:
                            target_physical_len = device_end - device_start + 1
                            target_effect_len = (
                                self._get_effective_pixel_count(
                                    target_physical_len
                                )
                            )
                            # In copy mode, we need to scale the effect and afterwards expand the
                            # pixel groups separately for every segment, because pre-calculating once
                            # and scaling would lead to incorrect pixel group lengths.
                            seg = interpolate_pixels(
                                pixels, target_effect_len
                            )[::step]
                            seg = self._effective_to_physical_pixels(
                                seg, target_physical_len
                            )
                            for oneshot in self._oneshots:
                                oneshot.apply(seg, start, stop)
                            data.append((seg, device_start, device_end))
                    device.update_pixels(self.id, data)

    def render_calibration(
        self, data, device, segments, device_id, color_cycle
    ):
        """
        Renders the calibration data to the virtual output
        """

        # set data to black for full length of led strip allow other segments to overwrite
        data.append(
            (
                np.array([0.0, 0.0, 0.0], dtype=float),
                0,
                device.pixel_count - 1,
            )
        )

        for start, stop, step, device_start, device_end in segments:
            # add data forced to color sequence of RGBCMY
            color = np.array(parse_color(next(color_cycle)), dtype=float)
            pattern = make_pattern(color, device_end - device_start + 1, step)
            data.append((pattern, device_start, device_end))
        # render the highlight
        if self._hl_state and device_id == self._hl_device:
            color = np.array(parse_color("white"), dtype=float)
            pattern = make_pattern(
                color,
                self._hl_end - self._hl_start + 1,
                self._hl_step,
            )
            data.append((pattern, self._hl_start, self._hl_end))

    def add_oneshot(self, oneshot: Oneshot):
        if not self._active:
            return False

        oneshot.pixel_count = self.pixel_count
        oneshot.init()
        with self.lock:
            self._oneshots.append(oneshot)
        return True

    @property
    def name(self):
        return self._config["name"]

    @property
    def max_brightness(self):
        return self._config["max_brightness"] * 256

    @property
    def active(self):
        return self._active

    @property
    def streaming(self):
        return self._streaming

    @active.setter
    def active(self, active):
        active = bool(active)
        if active and not self._active:
            self.activate()
        if not active and self._active:
            self.deactivate()
        self._active = active

    @property
    def id(self) -> str:
        """Returns the id for the virtual"""
        return getattr(self, "_id", None)

    @property
    def segments(self):
        return self._segments

    @property
    def oneshots(self):
        return self._oneshots

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
        Return an iterable of the device object of each segment of the virtual
        """
        return list(
            self._ledfx.devices.get(device_id)
            for device_id in {segment[0] for segment in self._segments}
        )

    @cached_property
    def refresh_rate(self):
        if not self._devices:
            return False
        return min(device.max_refresh_rate for device in self._devices)

    @cached_property
    def pixel_count(self):
        if self._config["mapping"] == "span":
            total = 0
            for device_id, start_pixel, end_pixel, invert in self._segments:
                total += end_pixel - start_pixel + 1
            return total
        elif self._config["mapping"] == "copy":
            if self._segments:
                return max(
                    end_pixel - start_pixel + 1
                    for _, start_pixel, end_pixel, _ in self._segments
                )
            else:
                return 0

    def update_effect_config(self, effect):
        """
        Update the effect configuration of a virtual
        Handle both an active effect and the effects history

        Args:
            effect (Effect): The effect object containing the updated configuration.

        Returns:
            None
        """
        # Store as both the active effect to protect existing code, and one of effects
        self.virtual_cfg.setdefault("effects", {})
        self.virtual_cfg["effects"][effect.type] = {
            "type": effect.type,
            "config": effect.config,
        }
        self.virtual_cfg.setdefault("effect", {})
        self.virtual_cfg["effect"] = {
            "type": effect.type,
            "config": effect.config,
        }
        self.virtual_cfg["last_effect"] = effect.type

    def get_effects_config(self, effect_type):
        """
        Search the virtuals effects config backing store and return its config if found

        Args:
            effect_type: String name for effect to recover

        Returns:
            effect config or empty dict {}
        """
        return (
            self.virtual_cfg.get("effects", {})
            .get(effect_type, {})
            .get("config", {})
        )

    @staticmethod
    def schema() -> vol.Schema:
        """returns the schema for the object"""
        return Virtual.CONFIG_SCHEMA

    @property
    def config(self) -> dict:
        """Returns the config for the object"""
        return getattr(self, "_config", None)

    def update_config(self, config):
        self.config = config

    @config.setter
    def config(self, new_config):
        """Updates the config for an object"""
        if self._config is not None:
            _config = {**self._config, **new_config}
        else:
            _config = new_config

        _config = self.CONFIG_SCHEMA(_config)
        reactivate_effect = False

        if hasattr(self, "_config"):
            if _config["mapping"] != self._config["mapping"]:
                self.invalidate_cached_props()
                reactivate_effect = True
            if (
                _config["transition_mode"] != self._config["transition_mode"]
                or _config["transition_time"]
                != self._config["transition_time"]
            ):
                self.frame_transitions = self.transitions[
                    _config["transition_mode"]
                ]
                if self._ledfx.config["global_transitions"]:
                    for virtual_id in self._ledfx.virtuals:
                        if virtual_id == self.id:
                            continue
                        virtual = self._ledfx.virtuals.get(virtual_id)
                        if hasattr(virtual, "frame_transitions"):
                            virtual.frame_transitions = virtual.transitions[
                                _config["transition_mode"]
                            ]
                            virtual._config["transition_time"] = _config[
                                "transition_time"
                            ]
                            virtual._config["transition_mode"] = _config[
                                "transition_mode"
                            ]
                        else:
                            _LOGGER.info(
                                f"virtual of {virtual_id} has no transitions"
                            )
            if (
                "frequency_min" in _config.keys()
                or "frequency_max" in _config.keys()
            ):
                # if these are in config, manually sanitise them
                _config["frequency_min"] = min(
                    _config["frequency_min"], MAX_FREQ - MIN_FREQ_DIFFERENCE
                )
                _config["frequency_min"] = max(
                    _config["frequency_min"], MIN_FREQ
                )
                _config["frequency_max"] = max(
                    _config["frequency_max"], MIN_FREQ + MIN_FREQ_DIFFERENCE
                )
                _config["frequency_max"] = min(
                    _config["frequency_max"], MAX_FREQ
                )
                diff = abs(_config["frequency_max"] - _config["frequency_min"])
                if diff < MIN_FREQ_DIFFERENCE:
                    _config["frequency_max"] += diff

                if self._active_effect is not None:
                    # if they're changed, clear some cached properties
                    # so the changes take effect
                    if (
                        _config["frequency_min"]
                        != self._config["frequency_min"]
                        or _config["frequency_max"]
                        != self._config["frequency_max"]
                    ) and (
                        hasattr(
                            self._active_effect, "clear_melbank_freq_props"
                        )
                    ):
                        self._active_effect.clear_melbank_freq_props()

            if self._active_effect is not None:
                # if a virtual level config change impacts a 2d effect layout, then trigger an init
                if (
                    _config["rows"] != self._config["rows"]
                    or _config["rotate"] != self._config["rotate"]
                ):
                    if hasattr(self._active_effect, "set_init"):
                        self._active_effect.set_init()

                if _config["grouping"] != self._config["grouping"]:
                    # The effect needs to be reactivated later after the config has been applied
                    reactivate_effect = True
                    self.invalidate_cached_props()

        # force rotate to 0 if this is a 1d virtual
        if _config["rows"] <= 1:
            _config["rotate"] = 0

        setattr(self, "_config", _config)

        self.frequency_range = FrequencyRange(
            self._config["frequency_min"], self._config["frequency_max"]
        )

        self._ledfx.events.fire_event(
            VirtualConfigUpdateEvent(self.id, self._config)
        )

        if reactivate_effect:
            self._reactivate_effect()

    @cached_property
    def effective_pixel_count(self):
        """The number of pixels to calculate by effects.

        Can be less than the number of physical pixels (:attr:`~pixel_count`) when
        pixel grouping (:attr:`~group_size`) is activated.
        """
        return self._get_effective_pixel_count(self.pixel_count)

    @cached_property
    def group_size(self):
        """The number of physical pixels to group into virtual effect pixels."""
        grouping = self._config["grouping"]

        if grouping is None or grouping < 1:
            return 1

        return grouping

    def _get_effective_pixel_count(self, physical_pixel_count):
        """Calculates the number of effective pixels for a given number of physical pixels, considering pixel grouping."""
        return int(np.ceil(physical_pixel_count / self.group_size))

    def _effective_to_physical_pixels(
        self, effective_pixels, pixel_count=None
    ):
        """Projects an array of effective pixels into an array of pixels for physical rendering, considering pixel grouping."""
        if self.group_size <= 1:
            return effective_pixels

        if not pixel_count:
            pixel_count = self.pixel_count

        effective_pixels = np.repeat(
            effective_pixels, self.group_size, axis=0
        )[:pixel_count, :]

        return effective_pixels

    @property
    def rows(self) -> int:
        """
        Property that returns the number of rows from the configuration.
        Returns:
            int: The number of rows specified in the configuration.
        """
        return self._config["rows"]

    @rows.setter
    def rows(self, rows: int) -> None:
        """
        Sets the number of rows in the configuration.

        If the number of rows passed is less than 1, it will be set to 1.

        Args:
            rows (int): The number of rows to set in the configuration.
        """
        self._config["rows"] = max(1, rows)


class Virtuals:
    """Thin wrapper around the device registry that manages virtuals
    Enforce as a singleton so that there is only one instance of this class"""

    PACKAGE_NAME = "ledfx.virtuals"
    _paused = False
    # there can be only one!
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Override the __new__ method to enforce a singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, ledfx):
        # Always update the reference to the current LedFx core instance.
        # Virtuals is implemented as a singleton and may be instantiated
        # multiple times across different LedFxCore lifecycles; binding
        # _ledfx unconditionally ensures we reference the correct
        # Devices/Events registries when restoring from config.
        self._ledfx = ledfx

        if not hasattr(self, "_initialized"):  # Ensure one-time init
            self._initialized = True
            self._virtuals = {}
            self._paused = False

            def cleanup_effects(e):
                self.fire_all_fallbacks()
                self.clear_all_effects()

            self._ledfx.events.add_listener(
                cleanup_effects, Event.LEDFX_SHUTDOWN
            )

    def create_from_config(self, config, pause_all=False):
        for virtual_cfg in config:
            _LOGGER.debug(f"Loading virtual from config: {virtual_cfg}")
            new_virtual = self._ledfx.virtuals.create(
                id=virtual_cfg["id"],
                config=virtual_cfg["config"],
                is_device=virtual_cfg["is_device"],
                auto_generated=virtual_cfg["auto_generated"],
                ledfx=self._ledfx,
            )

            # set the virtual up to have a reference into the cfg directly, so elsewhere we do not have to discover it
            # used for effect, effects, last_effect etc
            new_virtual.virtual_cfg = virtual_cfg

            if "segments" in virtual_cfg:
                try:
                    new_virtual.update_segments(virtual_cfg["segments"])
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Virtual Segment Changed. Not restoring segment"
                    )
                    continue
                except RuntimeError:
                    pass

            if "effect" in virtual_cfg:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=virtual_cfg["effect"]["type"],
                        config=virtual_cfg["effect"]["config"],
                    )
                    new_virtual.set_effect(effect)
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Effect schema changed. Not restoring effect"
                    )
                except RuntimeError:
                    pass

            # This adds support for configs that are configured as paused
            # via the active key if it exists. Let the setter deal with it
            if "active" in virtual_cfg and not virtual_cfg["active"]:
                new_virtual.active = False

            # global pause is handled differently to virtual pause
            if pause_all:
                new_virtual._paused = True

            self._ledfx.events.fire_event(
                VirtualConfigUpdateEvent(
                    virtual_cfg["id"], virtual_cfg["config"]
                )
            )

    def schema(self):
        return Virtual.CONFIG_SCHEMA

    def create(self, id=None, *args, **kwargs):
        """Creates a virtual"""

        # Find the first valid id based on what is already in the registry
        dupe_id = id
        dupe_index = 1
        while id in self._virtuals.keys():
            id = f"{dupe_id}-{dupe_index}"
            dupe_index = dupe_index + 1

        # Create the new virtual and validate the schema.
        _config = kwargs.pop("config", None)
        _is_device = kwargs.pop("is_device", False)
        _auto_generated = kwargs.pop("auto_generated", False)

        if _config is not None:
            _config = Virtual.CONFIG_SCHEMA(_config)
            obj = Virtual(config=_config, *args, **kwargs)
        else:
            obj = Virtual(*args, **kwargs)

        # Attach some common properties
        setattr(obj, "_id", id)
        setattr(obj, "is_device", _is_device)
        setattr(obj, "auto_generated", _auto_generated)

        # Store the object into the internal list and return it
        self._virtuals[id] = obj
        return obj

    def destroy(self, id):
        if id not in self._virtuals:
            raise AttributeError(
                ("Object with id '{}' does not exist.").format(id)
            )
        del self._virtuals[id]

    def __iter__(self):
        return iter(self._virtuals)

    def values(self):
        return self._virtuals.values()

    def clear_all_effects(self):
        for virtual in self.values():
            virtual.clear_frame()

    def fire_all_fallbacks(self):
        for virtual in self.values():
            virtual.set_fallback()

    def pause_all(self):
        self._paused = not self._paused
        for virtual in self.values():
            virtual._paused = self._paused
        self._ledfx.events.fire_event(GlobalPauseEvent(self._paused))

    def get(self, *args):
        return self._virtuals.get(*args)

    @classmethod
    def get_virtual_ids(cls):
        """
        Returns a list of all virtual IDs in the registry.
        """
        instance = cls._instance
        if instance is None or not hasattr(instance, "_virtuals"):
            return []
        return list(instance._virtuals.keys())

    @classmethod
    def get_virtual_names(cls):
        """
        Returns a list of all virtual names in the registry.
        """
        instance = cls._instance
        if instance is None or not hasattr(instance, "_virtuals"):
            return []
        return [virtual.name for virtual in instance._virtuals.values()]

    def reset_for_core(self, ledfx):
        """Reset internal singleton state for a new LedFxCore instance.

        This encapsulates the previous ad-hoc clearing of private
        attributes so callers don't mutate internals directly.
        """
        # Rebind to the new core instance
        self._ledfx = ledfx

        # Ensure registry exists and is empty
        if not hasattr(self, "_virtuals"):
            self._virtuals = {}
        else:
            try:
                self._virtuals.clear()
            except Exception:
                self._virtuals = {}

        # Reset pause state and any cached flags
        self._paused = False

        # Register cleanup listener on the new core's event bus.
        # The previous listener was registered on the old core; it's
        # acceptable to leave it attached to the old core's Events
        # instance (it will be triggered when that core shuts down).
        def cleanup_effects(e):
            self.fire_all_fallbacks()
            self.clear_all_effects()

        try:
            self._ledfx.events.add_listener(
                cleanup_effects, Event.LEDFX_SHUTDOWN
            )
        except Exception:
            # Be defensive: don't crash if events shape differs
            pass

    def check_and_deactivate_devices(self):
        """
        Checks all active virtuals and segments to compile a list of active devices,
        then deactivates any active devices not in that list.

        This process ensures that devices are only deactivated if no virtual or segment
        is using them, which is especially relevant during virtual or segment deactivation
        or reconfiguration.

        It also walks through all virtuals, if they are in the active devices list, but not active, they will be marked as streaming

        Note: This is a relatively expensive operation but only runs when a virtual
        is deactivated or segments are modified.
        """

        active_devices = set()
        for virtual in self.values():
            if virtual.active:
                for device_id, _, _, _ in virtual.segments:
                    active_devices.add(device_id)

        for device in self._ledfx.devices.values():
            if device.id not in active_devices and device.is_active():
                _LOGGER.info(
                    f"Deactivating device {device.id} as it is not in use by any active virtuals"
                )
                device.deactivate()

        # go through each device in the registry and work out its streaming state
        # if it has segments, but its paired virtual is not active, then it should it must be streaming
        _LOGGER.info(
            "-------------------------------------------------------------------------------"
        )
        _LOGGER.info(
            "Virtual                       is_device                    Active    Streaming "
        )
        _LOGGER.info(
            "-------------------------------------------------------------------------------"
        )

        for virtual_id in self._ledfx.virtuals:
            virtual = self._ledfx.virtuals.get(virtual_id)

            virtual._streaming = (
                virtual_id in active_devices and not virtual.active
            )

            _LOGGER.info(
                f"{virtual_id:<29} {str(virtual.is_device):<29}{str(virtual.active):<10}{str(virtual.streaming):<10}"
            )
        _LOGGER.info(f"Active Devices: {active_devices}")


def virtual_id_validator(virtual_id: str) -> str:
    """
    Support an empty validator function for static voluptuous validation.
    Allows any string value in the schema, as substantiated before virtuals
    are created

    Args:
        virtual_id (str): the virtual ID to validate

    Returns:
        str: the validated virtual ID
    """
    return virtual_id
