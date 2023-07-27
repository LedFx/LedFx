import itertools
import logging
import sys
import threading
import time
import timeit
from functools import cached_property

import numpy as np
import voluptuous as vol
import zeroconf

from ledfx.color import parse_color
from ledfx.effects import DummyEffect
from ledfx.effects.math import interpolate_pixels
from ledfx.effects.melbank import (
    MAX_FREQ,
    MIN_FREQ,
    MIN_FREQ_DIFFERENCE,
    FrequencyRange,
)
from ledfx.events import (
    EffectClearedEvent,
    EffectSetEvent,
    Event,
    GlobalPauseEvent,
    VirtualConfigUpdateEvent,
    VirtualPauseEvent,
    VirtualUpdateEvent,
)

# from ledfx.config import save_config
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
        self._hl_flip = False

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

        if (
            (start_pixel < 0)
            or (end_pixel < 0)
            or (start_pixel > end_pixel)
            or (end_pixel >= device.pixel_count)
        ):
            msg = f"Invalid segment pixels: ({start_pixel}, {end_pixel}). Device '{self.name}' valid pixels between (0, {self.pixel_count-1})"
            valid = False

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
        ]:
            if hasattr(self, prop):
                delattr(self, prop)

    def update_segments(self, segments_config):
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

            _LOGGER.debug(
                f"Virtual {self.id}: updated with {len(self._segments)} segments, totalling {self.pixel_count} pixels"
            )

            # Restart active effect if total pixel count has changed
            # eg. devices might be reordered, but total pixel count is same
            # so no need to restart the effect
            if self.pixel_count != _pixel_count:
                self.transitions = Transitions(self.pixel_count)
                if self._active_effect is not None:
                    self._active_effect.deactivate()
                    if self.pixel_count > 0:
                        self._active_effect.activate(self)

            mode = self._config["transition_mode"]
            self.frame_transitions = self.transitions[mode]

    def set_preset(self, preset_info):
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

    def set_effect(self, effect):
        if not self._devices:
            error = f"Virtual {self.id}: Cannot activate, no configured device segments"
            _LOGGER.warning(error)
            raise ValueError(error)

        if (
            self._config["transition_mode"] != "None"
            and self._config["transition_time"] > 0
        ):
            self.transition_frame_total = (
                self.refresh_rate * self._config["transition_time"]
            )
            self.transition_frame_counter = 0

            if self._active_effect is None:
                self._transition_effect = DummyEffect(self.pixel_count)
            else:
                self.clear_transition_effect()
                self._transition_effect = self._active_effect
        else:
            # no transition effect to clean up, so clear the active effect now!
            self.clear_active_effect()
            self.clear_transition_effect()

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
        self._ledfx.events.fire_event(EffectClearedEvent())

        self._transition_effect = self._active_effect
        self._active_effect = DummyEffect(self.pixel_count)

        self.transition_frame_total = (
            self.refresh_rate * self._config["transition_time"]
        )
        self.transition_frame_counter = 0

        self._ledfx.loop.call_later(
            self._config["transition_time"], self.clear_frame
        )

    def clear_transition_effect(self):
        if self._transition_effect is not None:
            self._transition_effect.deactivate()
        self._transition_effect = None

    def clear_active_effect(self):
        if self._active_effect is not None:
            self._active_effect.deactivate()
        self._active_effect = None

    def clear_frame(self):
        self.clear_active_effect()
        self.clear_transition_effect()

        if self._active:
            # Clear all the pixel data before deactivating the device
            self.assembled_frame = np.zeros((self.pixel_count, 3))
            self.flush(self.assembled_frame)
            self._ledfx.events.fire_event(
                VirtualUpdateEvent(self.id, self.assembled_frame)
            )

            self.deactivate()

    def force_frame(self, color):
        """
        Force all pixels in device to color
        Use for pre-clearing in calibration scenarios
        """
        self.assembled_frame = np.full((self.pixel_count, 3), color)
        self.flush(self.assembled_frame)
        self._ledfx.events.fire_event(
            VirtualUpdateEvent(self.id, self.assembled_frame)
        )

    def set_calibration(self, calibration):
        self._calibration = calibration
        if calibration is False:
            self._hl_segment = -1

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
        self._hl_flip = flip
        return None

    @property
    def active_effect(self):
        return self._active_effect

    def thread_function(self):
        while True:
            if not self._active:
                break
            start_time = timeit.default_timer()
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

                    self._ledfx.events.fire_event(
                        VirtualUpdateEvent(self.id, self.assembled_frame)
                    )

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
        if frame is None:
            return
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
            weight = (
                self.transition_frame_counter / self.transition_frame_total
            )
            self.frame_transitions(
                self.transitions, frame, transition_frame, weight
            )
            if self.transition_frame_counter == self.transition_frame_total:
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
            try:
                self.activate_segments(self._segments)
            except ValueError as e:
                _LOGGER.error(e)
            self._active = True

        # self.thread_function()

        self._thread = threading.Thread(target=self.thread_function)
        self._thread.start()
        self._ledfx.events.fire_event(VirtualPauseEvent(self.id))
        # self._task = self._ledfx.loop.create_task(self.thread_function())
        # self._task.add_done_callback(lambda task: task.result())

    def deactivate(self):
        self._active = False
        if hasattr(self, "_thread"):
            self._thread.join()
        self.deactivate_segments()
        self._ledfx.events.fire_event(VirtualPauseEvent(self.id))

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

        color_cycle = itertools.cycle(color_list)
        hl_segment = 0

        for device_id, segments in self._segments_by_device.items():
            data = []
            device = self._ledfx.devices.get(device_id)
            if device is not None:
                if device.is_active():
                    if self._calibration:
                        # set data to black for full length of led strip allow other segments to overwrite
                        data.append(
                            (
                                np.array([0.0, 0.0, 0.0], dtype=float),
                                0,
                                device.pixel_count - 1,
                            )
                        )

                        for (
                            start,
                            stop,
                            step,
                            device_start,
                            device_end,
                        ) in segments:
                            # add data forced to color sequence of RGBCMY
                            color = np.array(
                                parse_color(next(color_cycle)), dtype=float
                            )

                            data.append((color, device_start, device_end))
                        if self._hl_state and device_id == self._hl_device:
                            color = np.array(parse_color("white"), dtype=float)
                            data.append((color, self._hl_start, self._hl_end))
                    elif self._config["mapping"] == "span":
                        for (
                            start,
                            stop,
                            step,
                            device_start,
                            device_end,
                        ) in segments:
                            data.append(
                                (
                                    pixels[start:stop:step],
                                    device_start,
                                    device_end,
                                )
                            )
                    elif self._config["mapping"] == "copy":
                        for (
                            start,
                            stop,
                            step,
                            device_start,
                            device_end,
                        ) in segments:
                            target_len = device_end - device_start + 1
                            data.append(
                                (
                                    interpolate_pixels(pixels, target_len)[
                                        ::step
                                    ],
                                    device_start,
                                    device_end,
                                )
                            )
                    device.update_pixels(self.id, data)

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

        if hasattr(self, "_config"):
            if _config["mapping"] != self._config["mapping"]:
                self.invalidate_cached_props()
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
                        virtual.frame_transitions = virtual.transitions[
                            _config["transition_mode"]
                        ]
                        virtual._config["transition_time"] = _config[
                            "transition_time"
                        ]
                        virtual._config["transition_mode"] = _config[
                            "transition_mode"
                        ]

            if (
                "frequency_min" in _config.keys()
                or "frequency_max" in _config.keys()
            ):
                # if these are in config, manually sanitise them
                _config["frequency_min"] = min(
                    _config["frequency_min"], MAX_FREQ - MIN_FREQ_DIFFERENCE
                )
                _config["frequency_min"] = min(
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
                # if they're changed, clear some cached properties
                # so the changes take effect
                if (
                    (
                        _config["frequency_min"]
                        != self._config["frequency_min"]
                        or _config["frequency_max"]
                        != self._config["frequency_max"]
                    )
                    and (self._active_effect is not None)
                    and (
                        hasattr(
                            self._active_effect, "clear_melbank_freq_props"
                        )
                    )
                ):
                    self._active_effect.clear_melbank_freq_props()

        setattr(self, "_config", _config)

        self.frequency_range = FrequencyRange(
            self._config["frequency_min"], self._config["frequency_max"]
        )

        self._ledfx.events.fire_event(
            VirtualConfigUpdateEvent(self.id, self._config)
        )


class Virtuals:
    """Thin wrapper around the device registry that manages virtuals"""

    PACKAGE_NAME = "ledfx.virtuals"
    _paused = False

    def __init__(self, ledfx):
        # super().__init__(ledfx, Virtual, self.PACKAGE_NAME)

        def cleanup_effects(e):
            self.clear_all_effects()

        self._ledfx = ledfx
        self._ledfx.events.add_listener(cleanup_effects, Event.LEDFX_SHUTDOWN)
        self._zeroconf = zeroconf.Zeroconf()
        self._virtuals = {}

    def create_from_config(self, config):
        for virtual in config:
            _LOGGER.debug(f"Loading virtual from config: {virtual}")
            self._ledfx.virtuals.create(
                id=virtual["id"],
                config=virtual["config"],
                is_device=virtual["is_device"],
                auto_generated=virtual["auto_generated"],
                ledfx=self._ledfx,
            )
            if "segments" in virtual:
                try:
                    self._ledfx.virtuals.get(virtual["id"]).update_segments(
                        virtual["segments"]
                    )
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Virtual Segment Changed. Not restoring segment"
                    )
                    continue
                except RuntimeError:
                    pass

            if "effect" in virtual:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=virtual["effect"]["type"],
                        config=virtual["effect"]["config"],
                    )
                    self._ledfx.virtuals.get(virtual["id"]).set_effect(effect)
                except vol.MultipleInvalid:
                    _LOGGER.warning(
                        "Effect schema changed. Not restoring effect"
                    )
                except RuntimeError:
                    pass
            self._ledfx.events.fire_event(
                VirtualConfigUpdateEvent(virtual["id"], virtual["config"])
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

    def pause_all(self):
        self._paused = not self._paused
        for virtual in self.values():
            virtual._paused = self._paused
        self._ledfx.events.fire_event(GlobalPauseEvent())

    def get(self, *args):
        return self._virtuals.get(*args)
