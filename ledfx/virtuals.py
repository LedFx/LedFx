import logging
import threading
import time
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, fields
from functools import cached_property
from typing import Literal

import numpy as np
from pydantic import ValidationError

from ledfx.color import build_gradient_config, parse_color, validate_color
from ledfx.configuration.fields import (
    EnumSource,
    VirtualIdStr,
    register_enum_source,
)
from ledfx.configuration.models import (
    ApplyConfigResult,
    EffectEntry,
    GlobalEffectUpdate,
    Highlight,
    OneshotParams,
    Segment,
    SetEffectAllResult,
    VirtualConfig,
    VirtualEntry,
    replace_model,
)
from ledfx.configuration.plugin import PluginConfig
from ledfx.configuration.randomize import randomize_effect_config
from ledfx.effects import DummyEffect, Effect
from ledfx.effects.math import CalibratorPatternCache, interpolate_pixels
from ledfx.effects.melbank import (
    MAX_FREQ,
    FrequencyRange,
)
from ledfx.effects.oneshots.oneshot import Flash, Oneshot
from ledfx.errors import Conflict, Invalid, NotFound, ensure_writable
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
from ledfx.utils import (
    Teleplot,
    fps_to_sleep_interval,
    generate_id,
    is_gap_device,
)

_LOGGER = logging.getLogger(__name__)

# The ids of the v2 collection paths /virtuals/oneshot and /virtuals/force-color,
# which win over /virtuals/{virtual_id}: add() refuses them.
RESERVED_IDS = frozenset({"oneshot", "force-color"})

# The longest id Virtuals.add makes (the v2 id parameters accept no more).
MAX_ID_LENGTH = 128


class EffectRejected(Conflict):
    """The virtual cannot run an effect (no segments, a device error)."""

    def __init__(self, effect: Effect, detail: str) -> None:
        super().__init__(detail)
        self.effect = effect


def _flash(params: OneshotParams) -> Flash:
    """The Flash oneshot for params."""
    return Flash(
        parse_color(params.color),
        params.ramp_ms,
        params.hold_ms,
        params.fade_ms,
        params.brightness,
    )


def restarts_effect(effect: Effect, patch: PluginConfig) -> bool:
    """Whether patch restarts the running effect: a colour change on an effect
    that blends colours restarts it, so the change transitions."""
    return bool(getattr(effect.config, "color_blend", True)) and any(
        "color" in key for key in patch.as_dict()
    )


def _stale_stored(err: ValidationError) -> Conflict:
    """A stored effect config that no longer validates: the stored field is the
    problem, not the request."""
    loc = ("config", *err.errors()[0]["loc"])
    return Conflict(f"Stored field '{'.'.join(map(str, loc))}' is invalid", loc=loc)


def _invalid_config(err: ValidationError) -> Invalid:
    """The first problem of a config that failed its type's model, as Invalid."""
    first = err.errors()[0]
    return Invalid(first["msg"], loc=("body", "config", *first["loc"]))


@dataclass(frozen=True)
class VirtualChanges:
    """What Virtuals.patch changes: only the parts that are set."""

    config: VirtualConfig | None = None
    segments: list[Segment] | None = None
    active: bool | None = None


def unknown_device(device_id: str) -> str:
    """The reason for a device id that names no device."""
    return f"Unknown device: {device_id}"


def segment_problem(
    devices, device_id: str, start: int, end: int, *, exempt_gaps: bool = True
) -> tuple[str, str] | None:
    """The first thing wrong with a run of a device's pixels: (field, reason),
    or None. Gap devices (placeholders) are exempt from the checks unless
    exempt_gaps is False (a highlight lights real pixels). The one rule behind
    the strict request checks (segments, highlight) and the load path's repair."""
    if exempt_gaps and device_id.startswith("gap-"):
        return None
    device = devices.get(device_id)
    if device is None:
        return "device_id", unknown_device(device_id)
    if exempt_gaps and is_gap_device(device):
        return None
    last = device.pixel_count - 1
    if start > end:
        return "start", "start must not be after end"
    if start < 0 or start > last:
        return "start", f"start must be within the device's pixels 0..{last}"
    if end > last:
        return "end", f"end must be within the device's pixels 0..{last}"
    return None


def repaired_frequency(config: VirtualConfig) -> VirtualConfig:
    """config with frequency_min < frequency_max: equal values are widened by
    1 Hz, reversed ones swapped. For stored and legacy input; the manager's
    request methods refuse such a range instead."""
    low, high = config.frequency_min, config.frequency_max
    if low == high:
        if high < MAX_FREQ:
            high += 1
        else:
            low -= 1
        _LOGGER.warning(
            "Frequency range was zero-width. Adjusted to %s-%s Hz.", low, high
        )
    elif low > high:
        _LOGGER.warning(
            "frequency_min (%s) must be less than frequency_max (%s). Swapping values.",
            low,
            high,
        )
        low, high = high, low
    if (low, high) == (config.frequency_min, config.frequency_max):
        return config
    return replace_model(config, frequency_min=low, frequency_max=high)


def repaired_config(config: VirtualConfig) -> VirtualConfig:
    """config as stored data is repaired: the frequency range made valid (see
    repaired_frequency) and a rotate on one row zeroed. For the load path and
    legacy callers; the manager's request methods refuse such a config."""
    config = repaired_frequency(config)
    if config.rows <= 1 and config.rotate != 0:
        config = replace_model(config, rotate=0)
    return config


class Virtual:
    # Set by Virtuals.create.
    is_device: str | Literal[False] = False
    auto_generated: bool = False

    _paused = False
    _active = False
    _output_thread = None
    _active_effect = None
    _transition_effect = None

    _min_time = time.get_clock_info("perf_counter").resolution
    _last_render_error = float("-inf")

    def _checked_frequency_range(self, config: VirtualConfig) -> VirtualConfig:
        """Set frequency_range from config, repaired (see repaired_frequency);
        the repaired config is returned."""
        config = repaired_frequency(config)
        self.frequency_range = FrequencyRange(
            config.frequency_min, config.frequency_max
        )
        return config

    def __init__(self, ledfx, config: VirtualConfig):
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
        self.complex_segments = config.complex_segments

        # Precompiled device remap structure for fast pixel mapping
        # Maps virtual indices to device indices per device
        self._device_remap: dict = {}

        self._debug_flush_total = 0.0
        self._debug_last_report = time.perf_counter()
        self._debug_flush_frames = 0

        # Initialize calibration cache per instance to avoid concurrent access issues
        self._calibration_cache = CalibratorPatternCache()

        # Validate, adjust, and initialize frequency range
        self._config = self._checked_frequency_range(config)

        # Initialize transitions - will be resized in _reactivate_effect() when effect activates
        self.transitions = Transitions(0)

    def __del__(self):
        self.active = False

    def activate_segments(self, segments):
        # Always use optimized batch mode for segment activation
        # Group segments by device for batch adding
        segments_by_device = {}
        for device_id, start_pixel, end_pixel, _invert in segments:
            # Skip gap devices - they are configuration placeholders, never
            # registered in the device registry (so device will be None)
            if device_id.startswith("gap-"):
                continue
            device = self._ledfx.devices.get(device_id)
            if device is None or is_gap_device(device):
                continue
            if device_id not in segments_by_device:
                segments_by_device[device_id] = []
            segments_by_device[device_id].append((start_pixel, end_pixel))

        # Activate devices and add all segments in batch
        for device_id, device_segments in segments_by_device.items():
            device = self._ledfx.devices.get(device_id)
            if not device.is_active():
                device.activate()
            device.add_segments_batch(self.id, device_segments, force=True)

    def deactivate_segments(self):
        for device in self._devices:
            device.clear_virtual_segments(self.id)

    def validate_segment(self, segment):
        if not (
            isinstance(segment, (list, tuple))
            and len(segment) == 4
            and isinstance(segment[0], str)
            and isinstance(segment[1], int)
            and isinstance(segment[2], int)
        ):
            msg = f"Invalid segment format: {segment}, should be [device_id, start, end, invert]"
            _LOGGER.warning(msg)
            raise ValueError(msg)

        device_id, start_pixel, end_pixel, invert = segment

        problem = segment_problem(
            self._ledfx.devices, device_id, start_pixel, end_pixel
        )
        if problem is None:
            return segment
        if problem[0] == "device_id":
            msg = f"Invalid device id: {device_id}"
            _LOGGER.warning(msg)
            raise ValueError(msg)

        device = self._ledfx.devices.get(device_id)
        _LOGGER.warning(
            "Invalid segment pixels in Virtual '%s': segment('%s' (%s, %s)) valid pixels between (0, %s)",
            self.name,
            device.name,
            start_pixel,
            end_pixel,
            device.pixel_count - 1,
        )
        start_pixel = max(start_pixel, 0)
        end_pixel = max(end_pixel, 0)
        start_pixel = min(start_pixel, end_pixel)
        if start_pixel >= device.pixel_count:
            start_pixel = device.pixel_count - 1
        if end_pixel >= device.pixel_count:
            end_pixel = device.pixel_count - 1
        segment = [device_id, start_pixel, end_pixel, invert]
        _LOGGER.warning("Fixed to %s", segment)
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
            if not isinstance(segments_config, (list, tuple)):
                raise ValueError(  # noqa: TRY004 - callers catch ValueError
                    f"Invalid segments: {segments_config}, should be a list of segments"
                )
            segments_config = [
                list(item) if isinstance(item, (list, tuple)) else item
                for item in segments_config
            ]
            _segments = [self.validate_segment(s) for s in segments_config]

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

                old_segments = self._segments
                self._segments = _segments

                self.invalidate_cached_props()

                # Compile device remap structure for fast pixel mapping
                self._compile_device_remap()

                # Restart active effect if total pixel count has changed
                # eg. devices might be reordered, but total pixel count is same
                # so no need to restart the effect
                if self.pixel_count != _pixel_count:
                    # chenging segments is a deep edit, just flush any transition
                    try:
                        self._reactivate_effect()
                    except Exception:
                        # Roll back fully: device segments, our segments, and
                        # the effect restarted at the old size.
                        if self._active:
                            self.deactivate_segments()
                            self.activate_segments(old_segments)
                        self._segments = old_segments
                        self.invalidate_cached_props()
                        self._compile_device_remap()
                        try:
                            self._reactivate_effect()
                        except Exception:
                            # Same effect, same fault: report the original.
                            _LOGGER.exception(
                                "Virtual %s: effect did not restart after the "
                                "segment rollback",
                                self.id,
                            )
                        # Turn off devices only the new segments activated.
                        self._ledfx.virtuals.check_and_deactivate_devices()
                        raise

                mode = self._config.transition_mode
                self.frame_transitions = self.transitions[mode]
            # Update internal config with new segment if it exists, device creation only substantiates this later, so we need the test
            entry = self.entry
            if entry is not None:
                entry.segments = self._segments

            _LOGGER.debug(
                "Virtual %s: updated with %s segments, totalling %s pixels",
                self.id,
                len(self._segments),
                self.pixel_count,
            )
            self._ledfx.virtuals.check_and_deactivate_devices()

    def _compile_device_remap(self):
        """
        Precompile device remap structure for fast pixel mapping in flush().
        Only active when complex_segments is enabled.
        Builds src (virtual indices) and dst (device indices) arrays per device.
        """
        device_remap = {}

        if not self.complex_segments:
            # Complex segments disabled - skip compilation
            self._device_remap = {}
            return

        if self._config.mapping != "span":
            # Only compile for span mode - copy mode needs different handling
            self._device_remap = {}
            return

        _LOGGER.info("Virtual %s: compiling device remap for complex segments", self.id)

        # Group segments by device and build index arrays
        device_buffers = {}  # {device_id: {"src": list, "dst": list}}
        virtual_offset = 0

        for device_id, device_start, device_end, reverse in self._segments:
            segment_width = device_end - device_start + 1

            # Skip gap devices - they are placeholders for empty space
            # But still advance virtual_offset to consume those pixels from the virtual's buffer
            device = self._ledfx.devices.get(device_id)
            if is_gap_device(device):
                virtual_offset += segment_width
                continue

            # Skip segments with invalid width
            if segment_width <= 0:
                continue

            # Build virtual indices for this segment
            virtual_indices = np.arange(
                virtual_offset, virtual_offset + segment_width, dtype=np.int32
            )

            # Build device indices for this segment
            device_indices = np.arange(device_start, device_end + 1, dtype=np.int32)

            # Handle reverse flag by reversing virtual indices
            if reverse:
                virtual_indices = virtual_indices[::-1]

            # Initialize device buffer if needed
            if device_id not in device_buffers:
                device_buffers[device_id] = {"src": [], "dst": []}

            # Append indices to device buffers
            device_buffers[device_id]["src"].append(virtual_indices)
            device_buffers[device_id]["dst"].append(device_indices)

            virtual_offset += segment_width

        # Convert lists to numpy arrays
        for device_id, buffers in device_buffers.items():
            device_remap[device_id] = {
                "src": (
                    np.concatenate(buffers["src"])
                    if buffers["src"]
                    else np.array([], dtype=np.int32)
                ),
                "dst": (
                    np.concatenate(buffers["dst"])
                    if buffers["dst"]
                    else np.array([], dtype=np.int32)
                ),
            }

        # Filter out devices that don't exist (like gap-mapping)
        device_remap = {
            device_id: remap
            for device_id, remap in device_remap.items()
            if self._ledfx.devices.get(device_id) is not None
        }

        self._device_remap = device_remap

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
                _LOGGER.info("%s set_fallback: suppress = False", self.name)
            else:
                # there was no active effect when the fallback effect started
                self.clear_effect()
                # and make sure we save the config with the effect removed
                entry = self.entry
                if entry is not None:
                    entry.effect = None

            self._ledfx.config_store.request_save()
            self.fallback_clear()

    def fallback_clear(self):
        """clear down all fallback behaviours, normally called after a fallback has completed"""
        self.fallback_effect_type = None
        if self.fallback_timer is not None:
            self.fallback_timer.cancel()
            self.fallback_timer = None
        self.fallback_suppress_transition = False
        self.fallback_active = False
        _LOGGER.info("%s fallback_clear: suppress = False", self.name)

    def fallback_start(self, fallback: float):
        """Suppress transitions, clear and start the fallback timer
        This funciton should only be called from within the virtual lock

        Args:
            fallback (float): Time in seconds to wait before firing the fallback
        """
        self.fallback_suppress_transition = True
        _LOGGER.info("%s fallback_start: suppress = True", self.name)

        if self.fallback_timer is not None:
            self.fallback_timer.cancel()
        _LOGGER.info("Setting fallback timer for %s seconds", fallback)
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
            _LOGGER.info("%s fallback_fire_set", self.name)
            self.fallback_fire = True

    def set_effect(self, effect, fallback: float | None = None):
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
                error = (
                    f"Virtual {self.id}: Cannot activate, no configured device segments"
                )
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
                    _LOGGER.info("Setting fallback to %s", self.fallback_effect_type)
                # else: don't let new fallbacks override active fallbacks, just bump the timer
                self.fallback_start(fallback)

            if (
                self._config.transition_mode != "None"
                and self._config.transition_time > 0
                and not self.fallback_suppress_transition
            ):
                self.transition_frame_total = (
                    self.refresh_rate * self._config.transition_time
                )
                self.transition_frame_counter = 0
                self.clear_transition_effect()

                if self._active_effect is None:
                    self._transition_effect = DummyEffect(self.effective_pixel_count)
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
            if self._active_effect is None:
                _LOGGER.warning(
                    "No effect was set (effect is None). Skipping activation for virtual '%s'.",
                    self.id,
                )
                return
            self._active_effect.activate(self)
            self._ledfx.events.fire_event(
                EffectSetEvent(
                    self._active_effect.name,
                    self._active_effect.id,
                    self.id,
                    self._active_effect.type,
                    self._active,
                    self._streaming,
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
                self._config.transition_mode != "None"
                and self._config.transition_time > 0
                and not self.fallback_suppress_transition
            ):
                self._transition_effect = self._active_effect
                self._active_effect = DummyEffect(self.effective_pixel_count)

                self.transition_frame_total = (
                    self.refresh_rate * self._config.transition_time
                )
                self.transition_frame_counter = 0
            else:
                # no transition effect to clean up, so clear the active effect now!
                self.clear_active_effect()

            self.flush_pending_clear_frame()

            delay = (
                0 if self.fallback_suppress_transition else self._config.transition_time
            )
            self.clear_handle = self._ledfx.loop.call_later(delay, self.clear_frame)

    def flush_pending_clear_frame(self):
        if self.clear_handle is not None:
            self.clear_handle.cancel()
            self.clear_handle = None

    def clear_transition_effect(self):
        effect, self._transition_effect = self._transition_effect, None
        self._discard_effect(effect)

    def clear_active_effect(self):
        effect, self._active_effect = self._active_effect, None
        self._discard_effect(effect)

    def _discard_effect(self, effect: Effect | DummyEffect | None) -> None:
        # The slot is already empty, so a failure here cannot wedge the virtual.
        if effect is None:
            return
        # Save effect_id before deactivating (in case deactivate clears it)
        effect_id = getattr(effect, "id", None)
        effect._deactivate()
        # CRITICAL: Remove effect from registry to allow garbage collection
        # Only destroy if it has an ID (DummyEffect doesn't have one), and only
        # this effect's entry: ids are reused once destroyed.
        if effect_id is not None and self._ledfx.effects.get(effect_id) is effect:
            self._ledfx.effects.destroy(effect_id)

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
            VirtualUpdateEvent(self.id, self._effective_to_physical_pixels(frame))
        )

    def set_calibration(self, calibration):
        self._calibration = calibration
        if not calibration:
            self._hl_state = False

    @property
    def calibrating(self) -> bool:
        return self._calibration is not False

    def clear_highlight(self) -> None:
        self._hl_state = False

    def set_highlight(self, h: Highlight) -> None:
        """Light a device's pixel range. Raises Invalid (at body.device_id,
        body.start or body.end, see segment_problem) for an unknown device or
        a range the device lacks, then Conflict when not calibrating; a
        refused highlight changes nothing."""
        device_id = h.device_id.lower()
        problem = segment_problem(
            self._ledfx.devices, device_id, h.start, h.end, exempt_gaps=False
        )
        if problem is not None:
            field, reason = problem
            raise Invalid(reason, loc=("body", field))
        if not self.calibrating:
            raise Conflict(
                f"Cannot set highlight when {self.name} is not in calibration mode"
            )

        # The render thread reads the range once _hl_state is on: set it last.
        self._hl_device = device_id
        self._hl_start = h.start
        self._hl_end = h.end
        self._hl_step = -1 if h.flip else 1
        self._hl_state = True

    @property
    def active_effect(self):
        return self._active_effect

    def thread_function(self):
        while True:
            if not self._active:
                break
            start_time = time.perf_counter()

            if self.fallback_fire:
                self.set_fallback()
                self.fallback_fire = False

            # An exception here would end the thread and freeze the virtual
            # while it still reports active; log it (rate-limited) and carry on.
            try:
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
                            if not self._config.preview_only:
                                # self._ledfx.thread_executor.submit(self.flush)
                                # await self._ledfx.loop.run_in_executor(
                                #     self._ledfx.thread_executor, self.flush
                                # )
                                self.flush()

                            self._fire_update_event()
            except Exception:
                if start_time - self._last_render_error >= 5:
                    self._last_render_error = start_time
                    _LOGGER.exception("Virtual %s: frame render failed", self.id)

            # adjust for the frame assemble time, min allowed sleep 1 ms
            # this will be more frame accurate on high res sleep systems
            run_time = time.perf_counter() - start_time
            sleep_time = max(0.001, fps_to_sleep_interval(self.refresh_rate) - run_time)
            time.sleep(sleep_time)

            # use an aggressive check for did we sleep against expected min clk
            # for all high res scenarios this will be passive
            # for unexpected high res sleep on windows scenarios it will adapt
            pass_time = time.perf_counter() - start_time
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

            if self._config.center_offset:
                frame = np.roll(frame, self._config.center_offset, axis=0)

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

                if self._config.center_offset:
                    transition_frame = np.roll(
                        transition_frame,
                        self._config.center_offset,
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
                    weight = self.transition_frame_counter / self.transition_frame_total

                # the effective pixel count can change without _reactivate_effect,
                # so rebuild the masks when they no longer fit the frame
                if self.transitions.pixel_count != len(frame):
                    self.transitions = Transitions(len(frame))

                # we will pre validate the transition, which will generate a sentry report if it fails and return False
                if self.transitions.pre_validate(frame, transition_frame):
                    # only call the transition effect if it will not crash
                    self.frame_transitions(
                        self.transitions, frame, transition_frame, weight
                    )
                if self.transition_frame_counter == self.transition_frame_total:
                    self.clear_transition_effect()

            np.multiply(frame, self._config.max_brightness, frame)
            np.multiply(frame, self._ledfx.config.global_brightness, frame)
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

        if not self._active:
            self._active = True
            try:
                self.activate_segments(self._segments)
            except ValueError as e:
                _LOGGER.error("%s", e)
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

        if self._config.mapping == "span":
            # In span mode we can calculate the final pixels once for all segments
            pixels = self._effective_to_physical_pixels(pixels)

        debug_track = (
            self._active_effect
            and self._active_effect.logsec
            and self._active_effect.logsec.diag
        )

        if debug_track:
            flush_start = time.perf_counter()

        # Choose flush path based on complex_segments configuration

        if (
            self.complex_segments
            and self._config.mapping == "span"
            and self._device_remap
            and not self._calibration
        ):
            self._flush_complex_segments(pixels)
        else:
            self._flush_simple_segments(pixels)

        if debug_track:
            flush_time = time.perf_counter() - flush_start
            self._debug_flush_total += flush_time
            self._debug_flush_frames += 1

            current_time = time.perf_counter()
            if current_time - self._debug_last_report >= 1.0:
                avg_flush_ms = (
                    self._debug_flush_total / self._debug_flush_frames * 1000.0
                )
                Teleplot.send(f"flush_{self.id}:{avg_flush_ms}")
                self._debug_last_report = current_time
                self._debug_flush_total = 0.0
                self._debug_flush_frames = 0

    def _flush_simple_segments(self, pixels):
        """
        Simple flush using segment-by-segment processing.
        Handles calibration, span mode, and copy mode.
        """
        for device_id, segments in self._segments_by_device.items():
            data = []
            device = self._ledfx.devices.get(device_id)
            if device is not None and device.is_active():
                if self._calibration:
                    # Reset color sequence for each device to maintain consistency
                    self._calibration_cache.reset_color_sequence()
                    self.render_calibration(data, device, segments, device_id)
                elif self._config.mapping == "span":
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
                elif self._config.mapping == "copy":
                    for (
                        start,
                        stop,
                        step,
                        device_start,
                        device_end,
                    ) in segments:
                        target_physical_len = device_end - device_start + 1
                        target_effect_len = self._get_effective_pixel_count(
                            target_physical_len
                        )
                        # In copy mode, we need to scale the effect and afterwards expand the
                        # pixel groups separately for every segment, because pre-calculating once
                        # and scaling would lead to incorrect pixel group lengths.
                        seg = interpolate_pixels(pixels, target_effect_len)[::step]
                        seg = self._effective_to_physical_pixels(
                            seg, target_physical_len
                        )
                        for oneshot in self._oneshots:
                            oneshot.apply(seg, start, stop)
                        data.append((seg, device_start, device_end))
                device.update_pixels(self.id, data)

    def _flush_complex_segments(self, pixels):
        """
        Optimized flush using precompiled device remap for complex virtuals.
        Uses scatter-mode with numpy fancy indexing for 13x performance gain.
        """
        for device_id, remap in self._device_remap.items():
            device = self._ledfx.devices.get(device_id)
            if device is not None and device.is_active():
                # Use precompiled indices for fast pixel mapping
                src_indices = remap["src"]
                dst_indices = remap["dst"]

                if len(src_indices) > 0:
                    # Extract pixels using fancy indexing
                    seg = pixels[src_indices]

                    # Apply oneshots to the entire device pixel set
                    # Virtual range spans from min to max of src_indices
                    for oneshot in self._oneshots:
                        virtual_start = int(src_indices.min())
                        virtual_end = int(src_indices.max())
                        oneshot.apply(seg, virtual_start, virtual_end)

                    # Use new scatter mode: send pixels with dst indices
                    data = [(seg, dst_indices)]

                    device.update_pixels(self.id, data)

    def render_calibration(self, data, device, segments, device_id):
        """
        Renders the calibration data to the virtual output
        """

        # set data to black for full length of led strip allow other segments to overwrite
        data.append(
            (
                self._calibration_cache.black_color,
                0,
                device.pixel_count - 1,
            )
        )

        # For complex_segments, use simple solid color fill for better performance
        # Otherwise use optimized batch pattern generation (shared timer call)
        if self.complex_segments:
            for _, _, step, device_start, device_end in segments:
                color = self._calibration_cache.get_next_color()
                segment_length = device_end - device_start + 1
                pattern = np.tile(color, (segment_length, 1))
                data.append((pattern, device_start, device_end))
        else:
            # Collect all segment data for batch processing
            batch_data = []
            device_positions = []
            for _, _, step, device_start, device_end in segments:
                color = self._calibration_cache.get_next_color()
                segment_length = device_end - device_start + 1
                batch_data.append((color, segment_length, step))
                device_positions.append((device_start, device_end))

            # Generate all patterns with one shared timer call
            patterns = self._calibration_cache.get_pattern_batch(batch_data)

            # Append patterns to data
            for pattern, (device_start, device_end) in zip(patterns, device_positions):
                data.append((pattern, device_start, device_end))

        # render the highlight
        if self._hl_state and device_id == self._hl_device:
            color = self._calibration_cache.white_color
            hl_length = self._hl_end - self._hl_start + 1

            # For complex_segments, use simple solid color fill for better performance
            # Otherwise use optimized cached pattern generation
            if self.complex_segments:
                pattern = np.tile(color, (hl_length, 1))
            else:
                pattern = self._calibration_cache.get_pattern(
                    color,
                    hl_length,
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
        return self._config.name

    @property
    def max_brightness(self):
        return self._config.max_brightness * 256

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

            # Skip gap devices - they are placeholders for empty space
            # But still advance data_start to consume those pixels from the virtual's buffer
            device = self._ledfx.devices.get(device_id)
            if is_gap_device(device):
                data_start += segment_width
                continue

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
            if device_id in segments_by_device:
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
        return [
            self._ledfx.devices.get(device_id)
            for device_id in {segment[0] for segment in self._segments}
            if not device_id.startswith("gap-")
            and self._ledfx.devices.get(device_id) is not None
        ]

    @cached_property
    def refresh_rate(self):
        if not self._devices:
            return False
        return min(device.max_refresh_rate for device in self._devices)

    @cached_property
    def pixel_count(self):
        if self._config.mapping == "span":
            total = 0
            for device_id, start_pixel, end_pixel, invert in self._segments:
                # Include ALL pixels, even gap devices
                # Gap pixels are rendered but not displayed - they create empty space in the layout
                total += end_pixel - start_pixel + 1
            return total
        elif self._config.mapping == "copy":
            if self._segments:
                # For copy mode, use the maximum segment size (including gaps)
                all_segments = [
                    (end_pixel - start_pixel + 1)
                    for device_id, start_pixel, end_pixel, _ in self._segments
                ]
                return max(all_segments) if all_segments else 0
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
        entry = self.entry
        if entry is not None:
            config = effect.config.as_dict()
            entry.effects[effect.type] = EffectEntry(type=effect.type, config=config)
            entry.effect = EffectEntry(type=effect.type, config=config)
            entry.last_effect = effect.type
            self._ledfx.config_store.request_save()

    def get_effects_config(self, effect_type):
        """
        Search the virtuals effects config backing store and return its config if found

        Args:
            effect_type: String name for effect to recover

        Returns:
            effect config or empty dict {}
        """
        entry = self.entry
        if entry is None or effect_type not in entry.effects:
            return {}
        return entry.effects[effect_type].config

    @property
    def entry(self) -> VirtualEntry | None:
        """This virtual's persisted entry (looked up by id; never cached)."""
        return self._ledfx.config_store.virtual_entry(self.id)

    @property
    def config(self) -> VirtualConfig:
        """The virtual's settings (frozen: change them with Virtuals.set_config)."""
        return self._config

    def _sync_entry(self) -> None:
        """Keep the saved entry on the same config instance as the virtual."""
        entry = self.entry
        if entry is not None:
            entry.config = self._config

    def update_config(self, changes: Mapping[str, object]) -> None:
        """Merge changes into the config, validate the result and apply it.

        Raises ValidationError, before changing anything, if the result is invalid.
        A reversed or zero-width frequency range is repaired and rotate is
        zeroed on one row (the manager's request methods refuse both).
        """
        old = self._config
        new = repaired_config(replace_model(old, **changes))
        self.replace_config(new)

    def replace_config(self, new: VirtualConfig) -> None:
        """Make new the config, as it is (no repair), and apply what changed."""
        old = self._config
        reactivate_effect = False
        mapping_changed = new.mapping != old.mapping
        if mapping_changed:
            self.invalidate_cached_props()
            reactivate_effect = True

        if (
            new.transition_mode != old.transition_mode
            or new.transition_time != old.transition_time
        ):
            self.frame_transitions = self.transitions[new.transition_mode]
            if self._ledfx.config.global_transitions:
                self._share_transition(new)

        if (new.frequency_min, new.frequency_max) != (
            old.frequency_min,
            old.frequency_max,
        ):
            self.frequency_range = FrequencyRange(new.frequency_min, new.frequency_max)
            # Clear cached effect properties so the changes take effect
            if self._active_effect is not None and hasattr(
                self._active_effect, "clear_melbank_freq_props"
            ):
                self._active_effect.clear_melbank_freq_props()

        if self._active_effect is not None:
            # if a virtual level config change impacts a 2d effect layout, then trigger an init
            if (new.rows != old.rows or new.rotate != old.rotate) and hasattr(
                self._active_effect, "set_init"
            ):
                self._active_effect.set_init()

            if new.grouping != old.grouping:
                # The effect needs to be reactivated later after the config has been applied
                reactivate_effect = True
                self.invalidate_cached_props()

        self._config = new
        self._sync_entry()

        old_complex_segments = self.complex_segments
        self.complex_segments = new.complex_segments

        # Recompile remap if complex_segments changed OR if mapping changed while complex_segments is True
        if old_complex_segments != self.complex_segments or (
            self.complex_segments and mapping_changed
        ):
            self._compile_device_remap()

        self._ledfx.events.fire_event(VirtualConfigUpdateEvent(self.id, self._config))

        if reactivate_effect:
            # The render thread clears a finished transition under this lock.
            with self.lock:
                self._reactivate_effect()

    def _share_transition(self, config: VirtualConfig) -> None:
        """global_transitions: every other virtual takes this transition."""
        for virtual in self._ledfx.virtuals.values():
            if virtual is self:
                continue
            if not hasattr(virtual, "frame_transitions"):
                _LOGGER.info("virtual of %s has no transitions", virtual.id)
                continue
            virtual.frame_transitions = virtual.transitions[config.transition_mode]
            virtual._config = replace_model(
                virtual._config,
                transition_time=config.transition_time,
                transition_mode=config.transition_mode,
            )
            # Persist it too.
            entry = virtual.entry
            if entry is not None:
                entry.config = virtual._config

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
        grouping = self._config.grouping

        if grouping is None or grouping < 1:
            return 1

        return grouping

    def _get_effective_pixel_count(self, physical_pixel_count):
        """Calculates the number of effective pixels for a given number of physical pixels, considering pixel grouping."""
        return int(np.ceil(physical_pixel_count / self.group_size))

    def _effective_to_physical_pixels(self, effective_pixels, pixel_count=None):
        """Projects an array of effective pixels into an array of pixels for physical rendering, considering pixel grouping."""
        if self.group_size <= 1:
            return effective_pixels

        if not pixel_count:
            pixel_count = self.pixel_count

        effective_pixels = np.repeat(effective_pixels, self.group_size, axis=0)[
            :pixel_count, :
        ]

        return effective_pixels

    @property
    def rows(self) -> int:
        """
        Property that returns the number of rows from the configuration.
        Returns:
            int: The number of rows specified in the configuration.
        """
        return self._config.rows

    @rows.setter
    def rows(self, rows: int) -> None:
        """
        Sets the number of rows in the configuration.

        If the number of rows passed is less than 1, it will be set to 1.

        Args:
            rows (int): The number of rows to set in the configuration.
        """
        self._config = replace_model(self._config, rows=max(1, rows))
        self._sync_entry()


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

            self._ledfx.events.add_listener(cleanup_effects, Event.LEDFX_SHUTDOWN)

    def create_from_config(
        self, config: list[VirtualEntry], pause_all: bool = False
    ) -> None:
        for entry in config:
            _LOGGER.debug("Loading virtual from config: %s", entry)
            new_virtual = self._ledfx.virtuals.create(
                id=entry.id,
                config=entry.config,
                is_device=entry.is_device,
                auto_generated=entry.auto_generated,
                ledfx=self._ledfx,
            )

            # Update the entry with the validated config in case initialization
            # adjusted frequencies
            entry.config = new_virtual.config
            self._repair_effect_history(entry)

            if "segments" in entry.model_fields_set:
                try:
                    new_virtual.update_segments(entry.segments)
                except (RuntimeError, ValueError) as e:
                    _LOGGER.warning(
                        "Virtual %s: failed to restore segments: %s",
                        entry.id,
                        e,
                    )
                    continue

            # Pre-check: skip effect restore if the virtual has no valid
            # device segments.  This prevents a ValueError crash when a
            # poisoned config (e.g. virtual whose device was deleted) is
            # loaded at startup.
            if entry.effect is not None and not new_virtual._devices:
                _LOGGER.warning(
                    "Virtual %s has no device segments; skipping "
                    "effect restore to avoid startup crash",
                    entry.id,
                )
            elif entry.effect is not None:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=entry.effect.type,
                        config=entry.effect.config,
                        lenient=self._ledfx.config_store.quarantine,
                        lenient_path=f"virtuals.{entry.id}.effect.config",
                        lenient_entry=entry.effect,
                    )
                    if effect is not None:
                        new_virtual.set_effect(effect)
                except (RuntimeError, ValueError) as e:
                    _LOGGER.warning(
                        "Virtual %s: failed to restore effect: %s",
                        entry.id,
                        e,
                    )

            # This adds support for configs that are configured as paused
            # via the active key if it exists. Let the setter deal with it
            if entry.active is False:
                new_virtual.active = False

            # global pause is handled differently to virtual pause
            if pause_all:
                new_virtual._paused = True

            self._ledfx.events.fire_event(
                VirtualConfigUpdateEvent(entry.id, new_virtual.config)
            )

    def _repair_effect_history(self, entry: VirtualEntry) -> None:
        """Startup: validate each stored effect config leniently, as the active
        one is, so switching back to an effect never meets a bad value. A slot
        whose effect type is no longer registered is left untouched."""
        effects = self._ledfx.effects
        for effect_type, slot in entry.effects.items():
            if effect_type not in effects.types():
                continue
            effects.validate_leniently(
                effects.get_class(effect_type),
                effect_type,
                entry.id,
                dict(slot.config),
                self._ledfx.config_store.quarantine,
                f"virtuals.{entry.id}.effects.{effect_type}.config",
                slot,
            )

    def create(self, id=None, *args, **kwargs):
        """Creates a virtual"""

        # Find the first valid id based on what is already in the registry;
        # a suffixed id stays within MAX_ID_LENGTH, so it can be addressed.
        dupe_id = str(id)
        dupe_index = 1
        while id in self._virtuals:
            suffix = f"-{dupe_index}"
            id = f"{dupe_id[: MAX_ID_LENGTH - len(suffix)]}{suffix}"
            dupe_index = dupe_index + 1

        # Create the new virtual and validate the schema.
        _config = kwargs.pop("config", None)
        _is_device = kwargs.pop("is_device", False)
        _auto_generated = kwargs.pop("auto_generated", False)

        if _config is not None:
            _config = VirtualConfig.model_validate(_config)
            obj = Virtual(config=_config, *args, **kwargs)  # noqa: B026
        else:
            obj = Virtual(*args, **kwargs)

        # Attach some common properties
        obj._id = id
        obj.is_device = _is_device
        obj.auto_generated = _auto_generated

        # Store the object into the internal list and return it
        self._virtuals[id] = obj
        return obj

    def destroy(self, id):
        if id not in self._virtuals:
            raise AttributeError(f"Object with id '{id}' does not exist.")
        del self._virtuals[id]

    def __iter__(self):
        return iter(self._virtuals)

    def values(self):
        return self._virtuals.values()

    def fire_all_fallbacks(self):
        for virtual in self.values():
            virtual.set_fallback()

    def pause_all(self) -> None:
        """Toggle the global pause (the --pause-all flag and MQTT)."""
        self.set_paused(not self._paused)

    def get(self, *args):
        return self._virtuals.get(*args)

    # ---- manager API (v1 and v2 call these) -------------------------------
    # Mutators check safe mode first and never await, so no other request can
    # run between their change and its save.

    @property
    def paused(self) -> bool:
        """The global pause (runtime only, never saved)."""
        return self._paused

    def set_paused(self, paused: bool) -> bool:
        """Pause or resume every virtual. Runtime only, so allowed in safe mode."""
        self._paused = paused
        for virtual in self.values():
            virtual._paused = paused
        self._ledfx.events.fire_event(GlobalPauseEvent(paused))
        return paused

    def ensure_known(self, ids: Sequence[VirtualIdStr] | None) -> None:
        """Raise one NotFound naming every unknown id once, before any change."""
        missing = list(dict.fromkeys(v for v in ids or () if v not in self._virtuals))
        if missing:
            raise NotFound("Virtual", *missing)

    def get_or_raise(self, virtual_id: VirtualIdStr) -> Virtual:
        virtual = self._virtuals.get(virtual_id)
        if virtual is None:
            raise NotFound("Virtual", virtual_id)
        return virtual

    def add(self, config: VirtualConfig) -> Virtual:
        """Create a virtual (id from its name, made unique) and store it.

        Raises Invalid (loc body.config.<field>) for a frequency range with
        min >= max or a rotate with one row, and Invalid (loc body.config.name)
        when the name gives a reserved id (RESERVED_IDS); nothing is created
        then."""
        ensure_writable(self._ledfx)
        self._check_config(config, None)
        virtual_id = generate_id(config.name)[:MAX_ID_LENGTH]
        if virtual_id in RESERVED_IDS:
            raise Invalid(
                f"The id '{virtual_id}' is reserved; give the virtual another name",
                loc=("body", "config", "name"),
            )
        virtual = self.create(
            id=virtual_id,
            config=config,
            is_device=False,
            ledfx=self._ledfx,
        )
        self._ledfx.config.virtuals.append(
            VirtualEntry(
                id=virtual.id,
                config=virtual.config,
                is_device=virtual.is_device,
                auto_generated=virtual.auto_generated,
            )
        )
        self._ledfx.config_store.request_save()
        self._ledfx.events.fire_event(
            VirtualConfigUpdateEvent(virtual.id, virtual.config)
        )
        return virtual

    def set_segments(
        self, virtual_id: VirtualIdStr, segments: list[Segment]
    ) -> Virtual:
        """Replace the segments.

        Raises Invalid (loc body.segments.<i>.<field>) for a segment that
        names an unknown device or pixels outside it (gap devices are exempt),
        or when the new set cannot be activated; nothing changes then.
        """
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        self._check_segments(segments)
        self._apply_segments(virtual, segments)
        self._ledfx.config_store.request_save()
        return virtual

    def set_config(self, virtual_id: VirtualIdStr, config: VirtualConfig) -> Virtual:
        """Replace the config.

        Raises Invalid (loc body.config.<field>) when the change sets
        frequency_min >= frequency_max, or a rotate with one row; nothing
        changes then. A stored value the change leaves alone is not checked.
        """
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        self._check_config(config, virtual.config)
        self._apply_config(virtual, config)
        self._ledfx.config_store.request_save()
        return virtual

    def set_active(self, virtual_id: VirtualIdStr, active: bool) -> Virtual:
        """Activate or deactivate. Raises Conflict when activating is refused
        (no segments, no effect to restore, a stale stored config); the refused
        change is undone."""
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        self._apply_active(virtual, active)
        self._ledfx.config_store.request_save()
        return virtual

    def patch(self, virtual_id: VirtualIdStr, changes: VirtualChanges) -> Virtual:
        """Apply the parts of changes that are set: segments, config, active.

        All or nothing: if a step raises, the steps before it are undone and
        nothing is saved. Raises Invalid like set_segments and set_config, and
        Conflict like set_active.
        """
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        old_segments = list(virtual.segments)
        old_config = virtual.config
        # Every request input is checked before the first change.
        if changes.segments is not None:
            self._check_segments(changes.segments)
        if changes.config is not None:
            self._check_config(changes.config, old_config)
        attempted: list[str] = []
        try:
            if changes.segments is not None:
                attempted.append("segments")
                self._apply_segments(virtual, changes.segments)
            if changes.config is not None:
                attempted.append("config")
                self._apply_config(virtual, changes.config)
            if changes.active is not None:
                # _apply_active undoes itself when it raises.
                self._apply_active(virtual, changes.active)
        except Exception:
            # A step may have changed state before it raised, so every step
            # tried is restored, unchecked: what was stored (v1 can store what
            # v2 refuses) must come back; a restore that fails must not hide
            # the error.
            for step in reversed(attempted):
                try:
                    if step == "config":
                        self._apply_config(virtual, old_config)
                    elif list(virtual.segments) != old_segments:
                        self._apply_segments(virtual, old_segments)
                except Exception:
                    _LOGGER.exception(
                        "Could not undo %s of virtual %s", step, virtual.id
                    )
            raise
        self._ledfx.config_store.request_save()
        return virtual

    def remove(self, virtual_id: VirtualIdStr) -> None:
        """Delete a virtual, its device if it is one, and its scene entries."""
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        virtual.clear_effect()
        # Finish the clear now: a deferred clear_frame would run after destroy
        # and flush through devices whose segments still name this virtual.
        # Calibration would flush its pattern instead of the black frame.
        virtual.flush_pending_clear_frame()
        virtual.set_calibration(False)
        virtual.clear_frame()
        config = self._ledfx.config
        device_id = virtual.is_device
        device = self._ledfx.devices.get(device_id)
        if device is not None:
            device.remove_from_virtuals()
            # remove_from_virtuals may have already destroyed this device
            if self._ledfx.devices.get(device_id) is not None:
                self._ledfx.devices.destroy(device_id)
            config.devices = [d for d in config.devices if d.id != device_id]
        for scene in config.scenes.values():
            scene.virtuals.pop(virtual_id, None)
        # remove_from_virtuals may have already destroyed this virtual
        if virtual_id in self._virtuals:
            self.destroy(virtual_id)
        config.virtuals = [v for v in config.virtuals if v.id != virtual_id]
        self._ledfx.config_store.request_save()

    def _check_config(
        self, config: VirtualConfig, current: VirtualConfig | None
    ) -> None:
        """Invalid for a frequency range or a rotate that config sets wrongly.

        Only what differs from current is checked: v1 can store a rotate on
        one row, and changing something else must not be refused for it. With
        no current config (a new virtual) everything is checked."""
        self._check_frequency(config, current)
        if (
            (
                current is None
                or (config.rotate, config.rows) != (current.rotate, current.rows)
            )
            and config.rotate != 0
            and config.rows <= 1
        ):
            # Blame rows when only rows changed (the rotate was stored).
            stored = current is not None and config.rotate == current.rotate
            field = "rows" if stored else "rotate"
            raise Invalid(
                "rotate needs more than one row", loc=("body", "config", field)
            )

    def _check_frequency(
        self, config: VirtualConfig, current: VirtualConfig | None
    ) -> None:
        """Invalid for a frequency range that config sets to min >= max (a
        new virtual, current None, is always checked)."""
        if (
            current is None
            or (config.frequency_min, config.frequency_max)
            != (current.frequency_min, current.frequency_max)
        ) and config.frequency_min >= config.frequency_max:
            raise Invalid(
                "frequency_min must be below frequency_max",
                loc=("body", "config", "frequency_min"),
            )

    def _apply_config(self, virtual: Virtual, config: VirtualConfig) -> None:
        """Apply config as it is; callers check request input first."""
        virtual.replace_config(config)

    def _check_segments(self, segments: list[Segment]) -> None:
        """Invalid for a segment on an unknown device or outside its pixels
        (see segment_problem)."""
        for index, segment in enumerate(segments):
            problem = segment_problem(
                self._ledfx.devices, segment.device_id, segment.start, segment.end
            )
            if problem is not None:
                field, reason = problem
                raise Invalid(reason, loc=("body", "segments", index, field))

    def _apply_segments(self, virtual: Virtual, segments: list[Segment]) -> None:
        """Apply segments as they are; callers check request input first."""
        try:
            # update_segments validates first and restores on a failure.
            virtual.update_segments(segments)
        except ValueError as err:
            raise Invalid(str(err), loc=("body", "segments")) from err
        entry = virtual.entry
        if entry is not None:
            entry.segments = virtual.segments

    def _apply_active(self, virtual: Virtual, active: bool) -> None:
        old_active = virtual.active
        old_effect = virtual._active_effect
        entry = virtual.entry
        old_entry = entry.model_copy(deep=True) if entry is not None else None
        try:
            self._set_active(virtual, active)
        except Exception:
            try:
                if virtual._active_effect is not old_effect:
                    virtual.clear_active_effect()
                    virtual._active_effect = old_effect
                virtual.active = old_active
                if entry is not None and old_entry is not None:
                    entry.effect = old_entry.effect
                    entry.effects = old_entry.effects
                    entry.last_effect = old_entry.last_effect
                    entry.active = old_entry.active
            except Exception:
                _LOGGER.exception("Could not undo the activation of %s", virtual.id)
            raise

    def _set_active(self, virtual: Virtual, active: bool) -> None:
        effect = None
        if active and (
            not virtual._active_effect or isinstance(virtual.active_effect, DummyEffect)
        ):
            # Restore the last effect; a stale stored config refuses here too.
            entry = virtual.entry
            last_effect = entry.last_effect if entry is not None else None
            effect_config = (
                virtual.get_effects_config(last_effect) if last_effect else None
            )
            if last_effect and effect_config:
                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx, type=last_effect, config=effect_config
                    )
                except ValidationError as err:
                    raise _stale_stored(err) from err
        try:
            if effect is not None:
                virtual.set_effect(effect)
            virtual.active = active
        except (ValueError, RuntimeError) as err:  # the virtual cannot run
            if effect is not None:
                self._discard_refused(virtual, effect)
            raise Conflict(str(err)) from err
        if effect is not None:
            virtual.update_effect_config(effect)
        entry = virtual.entry
        if entry is not None:
            entry.active = virtual.active

    # ---- the running effect ------------------------------------------------

    def set_effect(
        self,
        virtual_id: VirtualIdStr,
        type_id: str,
        config: PluginConfig | None,
        *,
        fallback: float | None = None,
        store: bool = True,
    ) -> Virtual:
        """Start an effect; config None restores the type's stored config.

        config is already checked by the caller; a config the type's model
        refuses is Invalid at body.config.<field>. With fallback (seconds) the
        current effect comes back afterwards. Raises Invalid for an
        unregistered type, Conflict for a fallback on a virtual that is
        streamed to or for a stored config that no longer validates, and
        EffectRejected when the virtual cannot run the effect. Every check
        runs before an effect is created. With store False the effect only
        runs: nothing is stored or saved, so a restart brings back the stored
        effect.
        """
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        self._ensure_type(type_id)
        if config is not None:
            self._check_effect_config(type_id, config)
        if fallback is not None and virtual.streaming:
            raise Conflict(f"Virtual {virtual_id} is being streamed to")
        if config is None:
            config = self._stored_config(virtual, type_id)
        effect = self._create_effect(type_id, config)
        self._start_effect(virtual, effect, fallback, store=store)
        if store:
            self._ledfx.config_store.request_save()
        return virtual

    def patch_effect(
        self,
        virtual_id: VirtualIdStr,
        patch: PluginConfig,
        *,
        type_id: str | None = None,
    ) -> Virtual:
        """Change some settings of the running effect.

        patch holds only the settings to change, already validated. A colour
        change on an effect that blends colours restarts it, so the change
        transitions (see restarts_effect and, for the pause state,
        _start_effect). type_id is the type the caller
        checked the patch against. Raises Conflict when no effect runs or
        another type runs (a fallback can end in between), Invalid when the
        effect refuses a value, and EffectRejected when the virtual refuses
        the restarted effect.
        """
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        effect = self._running_effect(virtual)
        if type_id is not None and effect.type != type_id:
            raise Conflict(f"Virtual {virtual_id} runs {effect.type}, not {type_id}")
        if restarts_effect(effect, patch):
            try:
                merged = effect.config.with_values(**patch.as_dict())
            except ValidationError as err:
                raise _invalid_config(err) from err
            self._start_effect(
                virtual, self._create_effect(effect.type, merged), keep_active=True
            )
        else:
            try:
                effect.update_config(patch.as_dict())
            except ValidationError as err:
                raise _invalid_config(err) from err
            except (ValueError, RuntimeError) as err:
                raise Invalid(str(err), loc=("body", "config")) from err
            virtual.update_effect_config(effect)
        self._ledfx.config_store.request_save()
        return virtual

    def randomize_effect(self, virtual_id: VirtualIdStr) -> Virtual:
        """Random values for the running effect's settings (not brightness)."""
        ensure_writable(self._ledfx)
        effect = self._running_effect(self.get_or_raise(virtual_id))
        model = self._ledfx.effects.get_class(effect.type).config_model()
        return self.patch_effect(
            virtual_id,
            PluginConfig.model_validate(randomize_effect_config(model, ["brightness"])),
        )

    def reset_effect(self, virtual_id: VirtualIdStr) -> Virtual:
        """Restart the running effect with its default settings (a restart:
        see _start_effect)."""
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        effect = self._running_effect(virtual)
        defaults = self._defaults(effect.type)
        self._start_effect(
            virtual, self._create_effect(effect.type, defaults), keep_active=True
        )
        self._ledfx.config_store.request_save()
        return virtual

    def _ensure_type(self, type_id: str) -> None:
        if type_id not in self._ledfx.effects.types():
            raise Invalid(f"Unknown effect type: {type_id}", loc=("body", "type"))

    def _defaults(self, type_id: str) -> PluginConfig:
        return self._ledfx.effects.get_class(type_id).config_model().model_validate({})

    def _stored_config(self, virtual: Virtual, type_id: str) -> PluginConfig:
        """The config this virtual last used for the type; Conflict when it no
        longer validates (the stored field is the problem, not the request)."""
        model = self._ledfx.effects.get_class(type_id).config_model()
        try:
            return model.model_validate(virtual.get_effects_config(type_id))
        except ValidationError as err:
            raise _stale_stored(err) from err

    def _check_effect_config(self, type_id: str, config: PluginConfig) -> None:
        """Invalid when the type's model refuses config, before anything is
        created (the model is the one _create_effect builds the effect with)."""
        try:
            self._ledfx.effects.get_class(type_id).config_model().model_validate(
                config.as_dict()
            )
        except ValidationError as err:
            raise _invalid_config(err) from err

    def _create_effect(self, type_id: str, config: PluginConfig) -> Effect:
        try:
            return self._ledfx.effects.create(
                ledfx=self._ledfx, type=type_id, config=config
            )
        except ValidationError as err:
            raise _invalid_config(err) from err

    def clear_effect(self, virtual_id: VirtualIdStr) -> Virtual:
        """Stop the running effect (it stays in the history)."""
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        virtual.clear_effect()
        entry = virtual.entry
        if entry is not None:
            entry.effect = None
        self._ledfx.config_store.request_save()
        return virtual

    def effect_history(
        self, virtual_id: VirtualIdStr
    ) -> list[tuple[str, PluginConfig]]:
        """The stored config of every effect type this virtual has run.

        A type may be unregistered (its plugin is gone), so each config is the
        open PluginConfig with every stored key, not the type's own model."""
        entry = self.get_or_raise(virtual_id).entry
        if entry is None:
            return []
        return [
            (type_id, PluginConfig.model_validate(stored.config))
            for type_id, stored in entry.effects.items()
        ]

    def delete_effect_history(self, virtual_id: VirtualIdStr, type_id: str) -> None:
        """Forget an effect type's stored config, stopping it if it runs.

        NotFound for a type the virtual has neither stored nor running. A
        failure to stop the effect propagates and nothing is forgotten."""
        ensure_writable(self._ledfx)
        virtual = self.get_or_raise(virtual_id)
        entry = virtual.entry
        effect = virtual.active_effect
        running = (
            effect is not None
            and not isinstance(effect, DummyEffect)
            and effect.type == type_id
        )
        if not running and (entry is None or type_id not in entry.effects):
            raise NotFound("Effect", type_id)
        _LOGGER.info(
            "Deleting effect %s for virtual %s from effects", type_id, virtual_id
        )
        if running:
            virtual.clear_effect()
            if entry is not None:
                entry.effect = None
        if entry is not None:
            entry.effects.pop(type_id, None)
        self._ledfx.config_store.request_save()

    def fire_fallback(self, virtual_id: VirtualIdStr) -> None:
        """End a temporary effect now (runtime only, allowed in safe mode)."""
        _LOGGER.info("Fire fallback for virtual %s", virtual_id)
        self.get_or_raise(virtual_id).fallback_fire_set_with_lock()

    def _start_effect(
        self,
        virtual: Virtual,
        effect: Effect,
        fallback: float | None = None,
        *,
        store: bool = True,
        keep_active: bool = False,
    ) -> None:
        """Run a freshly created effect on a virtual and store its config
        (unless store is False).

        Starting an effect makes the virtual active, and that is stored with
        the config, except for a fallback (temporary) effect, which leaves the
        stored flag alone. keep_active is for a restart of the running effect
        (a colour patch, randomize, reset): the virtual keeps its pause state,
        at runtime and stored.

        Raises EffectRejected (the effect unregistered) when the virtual
        refuses it."""
        was_active = virtual.active
        try:
            virtual.set_effect(effect, fallback=fallback)
        except (ValueError, RuntimeError) as err:
            self._discard_refused(virtual, effect)
            raise EffectRejected(effect, str(err)) from err
        if store:
            virtual.update_effect_config(effect)
        if keep_active:
            if virtual.active != was_active:
                virtual.active = was_active
        elif store and fallback is None and virtual.entry is not None:
            virtual.entry.active = virtual.active

    def _discard_refused(self, virtual: Virtual, effect: Effect) -> None:
        """Unregister a refused effect, unless the virtual already holds it
        (activate() failed after it was assigned)."""
        effects = self._ledfx.effects
        if effects.get(effect.id) is effect and virtual.active_effect is not effect:
            effects.destroy(effect.id)

    def running_effect(self, virtual_id: VirtualIdStr) -> tuple[str, PluginConfig]:
        """The running effect's type and settings; Conflict when none runs."""
        effect = self._running_effect(self.get_or_raise(virtual_id))
        return effect.type, effect.config

    def _running_effect(self, virtual: Virtual) -> Effect:
        effect = virtual.active_effect
        if not effect or isinstance(effect, DummyEffect):
            raise Conflict(f"Virtual {virtual.id} has no active effect")
        return effect

    # ---- bulk actions and tools --------------------------------------------

    def clear_all_effects(
        self, virtual_ids: Sequence[VirtualIdStr] | None = None
    ) -> None:
        """Blank the output of every virtual, or of those listed (runtime only:
        the stored effects come back on restart). Raises NotFound for an
        unknown id, before anything is cleared."""
        self.ensure_known(virtual_ids)
        for virtual in self.values():
            if virtual_ids is None or virtual.id in virtual_ids:
                virtual.clear_frame()

    def apply_global_config(
        self,
        update: GlobalEffectUpdate,
        virtual_ids: Sequence[VirtualIdStr] | None = None,
    ) -> ApplyConfigResult:
        """Write the given settings into every running effect that has them.

        Returns the counts: skipped effects have none of the settings, failed
        ones refused them.
        A gradient also sets the colours sampled from it, except those given.
        Raises NotFound for an unknown id.
        """
        ensure_writable(self._ledfx)
        self.ensure_known(virtual_ids)
        given = {
            field.name: getattr(update, field.name)
            for field in fields(update)
            if getattr(update, field.name) is not None
        }
        changes: dict[str, object] = {}
        for key, value in given.items():
            if key != "gradient":
                changes[key] = value
                continue
            try:
                changes.update(
                    build_gradient_config(
                        value, self._ledfx.gradients, skip_keys=set(given)
                    )
                )
            except ValueError as err:
                raise Invalid(str(err), loc=("body", "gradient")) from err
        result = _apply_to_running_effects(
            self.values(), changes, target_ids=virtual_ids
        )
        if result.updated > 0:
            self._ledfx.config_store.request_save()
        return result

    def set_effect_all(
        self,
        type_id: str,
        config: PluginConfig | None,
        virtual_ids: Sequence[VirtualIdStr] | None = None,
        *,
        fallback: float | None = None,
    ) -> SetEffectAllResult:
        """Start one effect on every virtual, or on those listed (config None:
        the defaults; otherwise already validated by the type's model).

        Raises Invalid for an unregistered type and NotFound for an unknown id,
        both before any virtual changes. A repeated id is applied once. With a
        fallback, streamed-to virtuals are blocked; virtuals that refuse the
        effect failed.
        """
        ensure_writable(self._ledfx)
        ids = list(
            dict.fromkeys(self._virtuals if virtual_ids is None else virtual_ids)
        )
        self.ensure_known(ids)
        self._ensure_type(type_id)
        if config is None:
            config = self._defaults(type_id)
        applied = blocked = failed = 0
        for virtual_id in ids:
            virtual = self._virtuals[virtual_id]
            if fallback is not None and virtual.streaming:
                _LOGGER.debug(
                    "Skipping virtual %s: streaming active and fallback provided",
                    virtual_id,
                )
                blocked += 1
                continue
            try:
                self._start_effect(
                    virtual, self._create_effect(type_id, config), fallback
                )
                applied += 1
            except EffectRejected as err:
                _LOGGER.warning(
                    "Unable to set effect on virtual %s: %s", virtual_id, err
                )
                failed += 1
        if applied > 0:
            self._ledfx.config_store.request_save()
        return SetEffectAllResult(applied, blocked, failed)

    def oneshot(self, virtual_id: VirtualIdStr | None, params: OneshotParams) -> None:
        """Flash one virtual (Conflict if it is not active), or every active one."""
        if virtual_id is None:
            for virtual in self.values():
                virtual.add_oneshot(_flash(params))
            return
        virtual = self.get_or_raise(virtual_id)
        if virtual.add_oneshot(_flash(params)) is False:
            raise Conflict(f"Virtual {virtual_id} is not active")

    def clear_oneshots(self, virtual_id: VirtualIdStr | None) -> bool:
        """End the flashes on one virtual or all; False if none were running."""
        virtuals = (
            self.values() if virtual_id is None else [self.get_or_raise(virtual_id)]
        )
        found = False
        for virtual in virtuals:
            for oneshot in virtual.oneshots:
                if isinstance(oneshot, Flash):
                    oneshot.active = False
                    found = True
        return found

    def force_color(self, virtual_id: VirtualIdStr | None, color: str) -> None:
        """Fill one virtual, or every device's own virtual, with a colour."""
        target = None if virtual_id is None else self.get_or_raise(virtual_id)
        try:
            rgb = parse_color(validate_color(color))
        except ValueError as err:
            raise Invalid(str(err), loc=("body", "color")) from err
        if target is not None:
            target.force_frame(rgb)
            return
        for virtual in self.values():
            if virtual.is_device == virtual.id:
                virtual.force_frame(rgb)

    def set_calibration(self, virtual_id: VirtualIdStr, enabled: bool) -> None:
        """Calibration mode, where highlights are allowed (runtime only)."""
        self.get_or_raise(virtual_id).set_calibration(enabled)

    def set_highlight(self, virtual_id: VirtualIdStr, h: Highlight | None) -> None:
        """Light a device's pixel range on a calibrating virtual (None: off).

        Raises Conflict when the virtual is not calibrating, Invalid for an
        unknown device or a range past its end; a refused highlight changes
        nothing. None turns the highlight off, calibrating or not."""
        virtual = self.get_or_raise(virtual_id)
        if h is None:
            virtual.clear_highlight()
        else:
            virtual.set_highlight(h)

    def copy_effect(
        self, virtual_id: VirtualIdStr, targets: Sequence[VirtualIdStr]
    ) -> None:
        """Start the source's effect, with its settings, on each target.

        Raises NotFound for an unknown target before anything starts, Conflict
        if the source runs nothing or no target took the effect. A target that
        refuses is passed over when another takes it; a repeated one is copied
        to once."""
        ensure_writable(self._ledfx)
        source = self.get_or_raise(virtual_id).active_effect
        self.ensure_known(targets)
        if source is None or isinstance(source, DummyEffect):
            raise Conflict(f"Virtual {virtual_id} has no active effect")
        updated = 0
        for target_id in dict.fromkeys(targets):  # a repeated target once
            try:
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx, type=source.type, config=source.config
                )
                self._start_effect(self._virtuals[target_id], effect)
            except EffectRejected as err:
                _LOGGER.warning(
                    "Unable to copy effect to virtual %s: %s", target_id, err
                )
                continue
            updated += 1
        if updated == 0:
            raise Conflict("No target could run the effect")
        self._ledfx.config_store.request_save()

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
            except Exception:  # noqa: BLE001
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
            self._ledfx.events.add_listener(cleanup_effects, Event.LEDFX_SHUTDOWN)
        except Exception:  # noqa: BLE001, S110
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
                    "Deactivating device %s as it is not in use by any active virtuals",
                    device.id,
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

            virtual._streaming = virtual_id in active_devices and not virtual.active

            _LOGGER.info(
                "%-29s %-29s%-10s%-10s",
                virtual_id,
                virtual.is_device,
                virtual.active,
                virtual.streaming,
            )
        _LOGGER.info("Active Devices: %s", active_devices)


def _apply_to_running_effects(
    virtuals,
    config_updates: dict,
    target_ids: Collection[str] | None = None,
) -> ApplyConfigResult:
    """Apply *config_updates* to every active effect on the given virtuals.

    For each virtual the function:
    1. Skips virtuals not in *target_ids* (when provided).
    2. Skips virtuals without an active effect or with a ``DummyEffect``.
    3. Filters *config_updates* against the effect's schema and
       ``HIDDEN_KEYS``.
    4. Calls ``update_config`` / ``update_effect_config``.

    Args:
        virtuals: iterable of ``Virtual`` instances (e.g. ``ledfx.virtuals.values()``).
        config_updates: key/value pairs to push into each compatible effect.
        target_ids: when not ``None``, only update virtuals whose ``.id``
            is in this set.

    Returns:
        The ``ApplyConfigResult`` counts: skipped effects have none of the
        settings, failed ones refused them.

    Only ``ValueError``/``RuntimeError`` from an effect count as a refusal;
    anything else is a bug and propagates, leaving the effects already visited
    updated in memory and not saved.
    """
    updated = 0
    skipped = 0
    failed = 0

    for virtual in virtuals:
        if target_ids is not None and virtual.id not in target_ids:
            continue

        eff = virtual.active_effect
        if eff is None or isinstance(eff, DummyEffect):
            continue

        normalized_keys = set(type(eff).config_model().model_fields)
        hidden_keys = getattr(eff, "HIDDEN_KEYS", []) or []

        # Build per-effect update
        effect_config_update = {}
        for key, value in config_updates.items():
            if key not in normalized_keys:
                continue
            if key in hidden_keys:
                continue
            effect_config_update[key] = value

        if not effect_config_update:
            skipped += 1
            continue

        try:
            eff.update_config(effect_config_update)
            virtual.update_effect_config(eff)
            updated += 1
        except (ValueError, RuntimeError) as exc:
            _LOGGER.warning(
                "Effect on virtual %s refused the config: %s",
                virtual.id,
                exc,
            )
            failed += 1

    return ApplyConfigResult(updated, skipped, failed)


register_enum_source(
    "virtuals",
    EnumSource(
        options=lambda: Virtuals.get_virtual_ids(),
        names=lambda: Virtuals.get_virtual_names(),
    ),
)
