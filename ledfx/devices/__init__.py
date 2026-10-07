from __future__ import annotations

import asyncio
import logging
import threading
from abc import abstractmethod
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager, nullcontext
from functools import cached_property, partial
from typing import TYPE_CHECKING, Annotated, ClassVar

import numpy as np
import serial
import serial.tools.list_ports
from ledfx_senders.e131_packet import DEFAULT_PORT
from numpy.typing import NDArray
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import (
    RUNTIME_CONTEXT,
    X_REQUIRED,
    EnumSource,
    Fps,
    FromSource,
    register_enum_source,
)
from ledfx.configuration.models import DeviceEntry, VirtualEntry
from ledfx.configuration.plugin import PluginConfig, TypedConfig
from ledfx.events import (
    DeviceCreatedEvent,
    DevicesUpdatedEvent,
    DeviceUpdateEvent,
    Event,
)
from ledfx.preview import OwnedFrame, SourceKey
from ledfx.utils import (
    AVAILABLE_FPS,
    WLED,
    BaseRegistry,
    RegistryLoader,
    async_fire_and_forget,
    clean_ip,
    generate_id,
    get_icon_name,
    is_gap_device,
    resolve_destination,
    wled_support_DDP,
)

if TYPE_CHECKING:
    from ledfx.virtuals import Virtual

_LOGGER = logging.getLogger(__name__)
_MISSING = object()  # a key absent from the stored config
PixelUpdate = (
    tuple[NDArray[np.generic], NDArray[np.generic]]
    | tuple[NDArray[np.generic], int, int]
)


@BaseRegistry.no_registration
class Device(BaseRegistry):
    _id: str  # assigned by the device registry before source activation

    class Config(PluginConfig):
        name: str = Field(
            description="Friendly name for the device",
            json_schema_extra={X_REQUIRED: True},
        )
        icon_name: str = Field(
            "mdi:led-strip",
            description="https://material-ui.com/components/material-icons/",
        )
        center_offset: int = Field(
            0, description="Number of pixels from the perceived center of the device"
        )
        refresh_rate: Fps = Field(
            next(
                (f for f in AVAILABLE_FPS if f >= 60),
                list(AVAILABLE_FPS)[-1],
            ),
            description="Target rate that pixels are sent to the device",
        )

    config = TypedConfig(Config)

    _active = False
    # Config keys the running output is built from. config_updated hooks
    # rebuild only when one changes: a rebuild blanks or drops the output.
    OUTPUT_KEYS: ClassVar[tuple[str, ...]] = ()
    _built_settings: tuple[object, ...] | None = None

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = config
        self._segments = []
        self._pixels: NDArray[np.generic] | None = None
        self._silence_start = None
        self._device_type = ""
        self._online = True
        self.lock = threading.Lock()
        # Order: output -> sender/device -> frame. Sender failures may reenter
        # activate/deactivate, so the output boundary must be reentrant.
        self._output_lock = threading.RLock()
        self._frame_lock = threading.RLock()
        self._output_epoch = 0
        self._source_generation = 0
        self._frame_sequence = 0
        self._physical_rows = 1
        self._built_settings = self._output_settings()

    def __del__(self):
        if self._active:
            self.deactivate()

    def update_config(self, config, *, runtime=False):
        """runtime=True for API writes: also check the live choices (serial ports)
        this update changes. Unchanged ones are not rechecked, as a port may be
        unplugged, and the frontend sends the whole stored config back."""
        # Only publication/output replacement belongs under device locks.
        # Virtual callbacks can join rendering or acquire Virtual.lock.
        with self._output_lock, self.lock, self._config_update_context(config):
            old_config = self._config
            stored = (
                old_config.as_dict() if old_config is not None else dict[str, object]()
            )
            changed = frozenset(
                k for k, v in config.items() if stored.get(k, _MISSING) != v
            )
            context = {**RUNTIME_CONTEXT, "fields": changed} if runtime else None
            config = stored | config

            validated_config = (
                type(self).config_model().model_validate(config, context=context)
            )
            with self._frame_lock:
                self._renew_source_generation()
                self._config = validated_config

            # Iterate all the base classes and check to see if there is a custom
            # implementation of config updates. If to notify the base class.
            valid_classes = list(type(self).__bases__)
            valid_classes.append(type(self))
            try:
                for base in valid_classes:
                    if "config_updated" in vars(base):  # base's own override
                        base.config_updated(self, validated_config)
            except Exception:
                # The update failed; keep the config the device is running with.
                with self._frame_lock:
                    self._config = old_config
                    self._renew_source_generation()
                raise

            # The pixel buffer is sized on activate; resize a live one here so
            # segment writes and clears match the new pixel count.
            with self._frame_lock:
                if self._pixels is not None and len(self._pixels) != self.pixel_count:
                    self._pixels = np.zeros((self.pixel_count, 3))

        _LOGGER.info("Device %s config updated to %s.", self.name, validated_config)

        for virtual_id in self._ledfx.virtuals:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if virtual.is_device == self.id:
                segments = [[self.id, 0, self.pixel_count - 1, False]]
                virtual.update_segments(segments)
                virtual.invalidate_cached_props()

        for virtual in self._virtuals_objs:
            virtual.deactivate_segments()
            virtual.activate_segments(virtual._segments)

    def _config_update_context(
        self, config: dict[str, object]
    ) -> AbstractContextManager[None]:
        """Output ownership/rollback boundary, excluding virtual callbacks."""
        return nullcontext()

    def config_updated(self, config):
        """
        to be reimplemented by child classes
        """

    def _output_settings(self) -> tuple[object, ...]:
        # Some keys (pixel_count) are stored extras, so read each one by name.
        return tuple(getattr(self.config, key, None) for key in self.OUTPUT_KEYS)

    def _output_changed(self) -> bool:
        return self._output_settings() != self._built_settings

    @property
    def pixel_count(self):
        return int(getattr(self.config, "pixel_count"))  # noqa: B009 - declared by subclasses

    def is_active(self):
        return self._active

    def is_online(self):
        return self._online

    def _renew_source_generation(self) -> None:
        # Hardware ownership survives absent/closed preview observation.
        self._output_epoch += 1
        if hasattr(self, "_id"):
            self._source_generation = (
                self._ledfx.preview_sampler.allocate_source_generation(
                    SourceKey("device", self.id)
                )
            )
            if self._source_generation > 0:
                self._frame_sequence = 0

    def _refresh_physical_rows(self) -> None:
        # Read immutable virtual configs outside the frame lock; never acquire
        # a virtual lock while holding a device lock. Publication is serialized.
        with self._output_lock:
            rows = next(
                (
                    v.rows
                    for v in self._ledfx.virtuals.values()
                    if v.is_device == self.id
                ),
                1,
            )
            with self._frame_lock:
                if rows != self._physical_rows:
                    self._renew_source_generation()
                    self._physical_rows = rows

    def _captured_physical_rows(self) -> int:
        return self._physical_rows

    def _publish_captured_frame(
        self, pixels: NDArray[np.generic], rows: int, generation: int, sequence: int
    ) -> None:
        # Delayed publishers must not resurrect a superseded layout/teardown.
        with self._frame_lock:
            if generation != self._source_generation:
                return
        key = SourceKey("device", self.id)
        sampler = self._ledfx.preview_sampler
        if sampler.interested(key, generation):
            sampler.submit(
                OwnedFrame(
                    key,
                    generation,
                    sequence,
                    pixels,
                    rows,
                    len(pixels),
                    sampler.settings_generation,
                )
            )
        if self._ledfx.events.may_have_listeners(
            Event.DEVICE_UPDATE, {"device_id": self.id}
        ):
            self._ledfx.events.fire_event(DeviceUpdateEvent(self.id, pixels))

    def _write_pixels(self, data: Sequence[PixelUpdate]) -> None:
        buffer = self._pixels
        if buffer is None:
            return
        for item in data:
            if len(item) == 2:
                pixels, dst_indices = item
                if pixels.shape[0] != 0:
                    try:
                        buffer[dst_indices] = pixels
                    except (IndexError, ValueError, TypeError) as error:
                        _LOGGER.warning(
                            "Device %s: scatter assignment failed: %s", self.name, error
                        )
            else:
                pixels, start, end = item
                if pixels.shape[0] != 0 and (
                    np.shape(pixels) == (3,)
                    or np.shape(buffer[start : end + 1]) == np.shape(pixels)
                ):
                    buffer[start : end + 1] = pixels

    def update_pixels(
        self,
        virtual_id: str,
        data: Sequence[PixelUpdate],
        *,
        output_epoch: int | None = None,
    ) -> None:
        # Non-priority contributions do not wait for a slow sender. Only a
        # priority capture holds output admission, always before the frame lock.
        with self._frame_lock:
            if not self._active or (
                output_epoch is not None and output_epoch != self._output_epoch
            ):
                return
            admission_epoch = self._output_epoch
            priority = self.priority_virtual
            if priority is None or virtual_id != priority.id:
                self._write_pixels(data)
                return
        frame = None
        rows = generation = sequence = 0
        with self._output_lock:
            with self._frame_lock:
                if not self._active or admission_epoch != self._output_epoch:
                    return
                self._write_pixels(data)
                priority = self.priority_virtual
                if priority is not None and virtual_id == priority.id:
                    frame = self.assemble_frame()
                    generation = self._source_generation
                    self._frame_sequence += 1
                    sequence = self._frame_sequence
                    rows = self._captured_physical_rows()
            if frame is not None:
                self.flush(frame)
        if frame is not None:
            self._publish_captured_frame(frame, rows, generation, sequence)

    def assemble_frame(self) -> NDArray[np.generic]:
        """Capture owned composed RGB, including the physical center offset."""
        with self._frame_lock:
            if self._pixels is None:
                raise RuntimeError("Cannot assemble an inactive device")
            if self.config.center_offset:
                return np.roll(self._pixels, self.config.center_offset, axis=0)
            return self._pixels.copy()

    def submit_final_black(self) -> None:
        """Send a complete physical blackout while the sender is still active."""
        with self._output_lock:
            with self._frame_lock:
                if not self._active or self._pixels is None:
                    return
                self._pixels[:] = 0
                frame = self.assemble_frame()
                generation = self._source_generation
                self._frame_sequence += 1
                sequence = self._frame_sequence
                rows = self._captured_physical_rows()
            self.flush(frame)
        self._publish_captured_frame(frame, rows, generation, sequence)

    def activate(self):
        with self._output_lock, self._frame_lock:
            self._renew_source_generation()
            self._pixels = np.zeros((self.pixel_count, 3))
            self._active = True

    def deactivate(self):
        with self._output_lock, self._frame_lock:
            self._output_epoch += 1
            if hasattr(self, "_id"):
                self._ledfx.preview_sampler.invalidate_source(
                    SourceKey("device", self.id)
                )
            self._source_generation = -1
            self._pixels = None
            self._active = False

    def set_offline(self):
        self.deactivate()
        self._online = False
        self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))

    @abstractmethod
    def flush(self, data):
        """
        Flushes the provided data to the device. This abstract method must be
        overwritten by the device implementation.
        """

    @property
    def name(self):
        return self.config.name

    @property
    def max_refresh_rate(self):
        return self.config.refresh_rate

    @property
    def refresh_rate(self):
        if self.priority_virtual:
            return self.priority_virtual.refresh_rate
        else:
            _LOGGER.warning(
                "refresh_rate() set 30 as %s has no priority_virtual", self.id
            )
            return 30

    @cached_property
    def priority_virtual(self):
        """
        Returns the first virtual that has the highest refresh rate of all virtuals
        associated with this device
        """
        if not any(virtual.active for virtual in self._virtuals_objs):
            return None

        refresh_rate = max(
            virtual.refresh_rate for virtual in self._virtuals_objs if virtual.active
        )
        return next(
            virtual
            for virtual in self._virtuals_objs
            if virtual.refresh_rate == refresh_rate
        )

    @cached_property
    def _virtuals_objs(self):
        return [self._ledfx.virtuals.get(virtual_id) for virtual_id in self.virtuals]

    @property
    def active_virtuals(self):
        """
        list of id of the virtuals active on this device.
        it's a list bc there can be more than one virtual streaming
        to a device.
        """
        return [virtual.id for virtual in self._virtuals_objs if virtual.active]

    @property
    def online(self):
        """
        bool indicator of online status
        """
        return self._online

    @cached_property
    def virtuals(self):
        return [segment[0] for segment in self._segments]

    def add_segments_batch(
        self,
        virtual_id: str,
        segments: Sequence[tuple[int, int]],
        force: bool = False,
        *,
        source: Virtual | None = None,
        source_generation: int | None = None,
        source_epoch: int | None = None,
        source_token: int | None = None,
    ) -> None:
        """Add multiple segments efficiently with single overlap check.

        Args:
            virtual_id: Virtual ID owning these segments
            segments: List of (start_pixel, end_pixel) tuples
            force: If True, deactivate overlapping virtuals
        """
        with self._frame_lock:
            registered_segments = tuple(self._segments)

        # Streaming mode only applies to device's own virtual vs external virtuals
        # Multiple external virtuals can coexist if they don't overlap (checked later)

        # If the device's own virtual is activating, deactivate all external virtuals
        # streaming to this device (exit streaming mode)
        if virtual_id == self.id:
            external_virtuals = set()
            for _virtual_id, _, _ in registered_segments:
                if _virtual_id != self.id:
                    external_virtuals.add(_virtual_id)

            if external_virtuals:
                _LOGGER.info(
                    "Device %s: Device virtual '%s' activating - deactivating external virtuals: %s",
                    self.id,
                    self.id,
                    external_virtuals,
                )
                for _virtual_id in external_virtuals:
                    external_virtual = self._ledfx.virtuals.get(_virtual_id)
                    if external_virtual and external_virtual.active:
                        self._ledfx.virtuals.deactivate_for_device(external_virtual)

        # If a non-device virtual is adding segments to this device,
        # deactivate the device's own virtual to enter streaming mode
        # (but allow multiple external virtuals - overlap check below will handle conflicts)
        elif virtual_id != self.id:
            device_virtual = self._ledfx.virtuals.get(self.id)
            if device_virtual and device_virtual.active:
                _LOGGER.info(
                    "Device %s: Deactivating device virtual '%s' as external virtual '%s' is streaming",
                    self.id,
                    self.id,
                    virtual_id,
                )
                self._ledfx.virtuals.deactivate_for_device(device_virtual)

        # Efficient overlap detection using sorted intervals
        overlapping_virtuals = set()

        # Skip overlap checking for gap devices (they are placeholders, not real hardware)
        if is_gap_device(self):
            overlapping_virtuals = set()
        else:
            # Group existing segments by virtual_id and sort by start position
            existing_by_virtual = {}
            for _virtual_id, segment_start, segment_end in registered_segments:
                if _virtual_id == virtual_id:
                    continue
                if _virtual_id not in existing_by_virtual:
                    existing_by_virtual[_virtual_id] = []
                existing_by_virtual[_virtual_id].append((segment_start, segment_end))

            # Sort each virtual's segments for binary search
            for existing_segments in existing_by_virtual.values():
                existing_segments.sort()

            # Check each new segment against sorted existing segments
            for start_pixel, end_pixel in segments:
                for (
                    _virtual_id,
                    sorted_segments,
                ) in existing_by_virtual.items():
                    # Binary search to find first segment that could overlap
                    # A segment at position i overlaps if: segment[i].end >= start_pixel AND segment[i].start <= end_pixel
                    left, right = 0, len(sorted_segments)
                    found_overlap = False

                    # Find first segment where segment_end >= start_pixel
                    while left < right:
                        mid = (left + right) // 2
                        if (
                            sorted_segments[mid][1] < start_pixel
                        ):  # segment_end < start_pixel
                            left = mid + 1
                        else:
                            right = mid

                    # Check segments starting from 'left' until we're past end_pixel
                    for i in range(left, len(sorted_segments)):
                        segment_start, segment_end = sorted_segments[i]
                        if segment_start > end_pixel:
                            # All remaining segments are beyond our range
                            break
                        # Check for actual overlap
                        overlap = (
                            min(segment_end, end_pixel)
                            - max(segment_start, start_pixel)
                            + 1
                        )
                        if overlap > 0:
                            overlapping_virtuals.add(_virtual_id)
                            found_overlap = True
                            break

                    if found_overlap and not force:
                        # Early exit if not forcing - we just need one overlap to fail
                        break

                if overlapping_virtuals and not force:
                    break

        if overlapping_virtuals:
            virtual = self._ledfx.virtuals.get(virtual_id)
            virtual_name = virtual.name if virtual else virtual_id
            if force:
                for _virtual_id in overlapping_virtuals:
                    blocking_virtual = self._ledfx.virtuals.get(_virtual_id)
                    if blocking_virtual:
                        self._ledfx.virtuals.deactivate_for_device(blocking_virtual)
            else:
                blocking_names = [
                    self._ledfx.virtuals.get(v).name
                    for v in overlapping_virtuals
                    if self._ledfx.virtuals.get(v) is not None
                ]
                msg = f"Failed to activate effect! '{virtual_name}' overlaps with active virtual(s): {', '.join(blocking_names)}"
                _LOGGER.warning(msg)
                raise ValueError(msg)

        # Callback phase is complete. The source identity/epoch start claim
        # does not acquire a virtual lock while holding the device mutexes.
        with self._output_lock, self._frame_lock:
            if source is not None and (
                self._ledfx.virtuals.get(virtual_id) is not source
                or (
                    source_generation is not None
                    and source._source_generation != source_generation
                )
                or (source_epoch is not None and source._source_epoch != source_epoch)
                or (source_token is not None and source._render_token != source_token)
            ):
                return
            needs_cache_invalidation = virtual_id not in (
                segment[0] for segment in self._segments
            )
            self._renew_source_generation()
            for start_pixel, end_pixel in segments:
                self._segments.append((virtual_id, start_pixel, end_pixel))

            if needs_cache_invalidation:
                self.invalidate_cached_props()

    def clear_virtual_segments(
        self,
        virtual_id: str,
        *,
        source: Virtual | None = None,
        source_epoch: int | None = None,
        source_token: int | None = None,
    ) -> None:
        with self._output_lock, self._frame_lock:
            # Destructive work has the same source start claim as registration;
            # old callback phases cannot erase a completed successor layout.
            if source is not None and (
                self._ledfx.virtuals.get(virtual_id) is not source
                or (source_epoch is not None and source._source_epoch != source_epoch)
                or (source_token is not None and source._render_token != source_token)
            ):
                return
            new_segments = []
            for segment in self._segments:
                if segment[0] != virtual_id:
                    new_segments.append(segment)
                else:
                    if (
                        self._pixels is not None
                        and self._ledfx.config.flush_on_deactivate
                    ):
                        # A scalar fill: the buffer may already be resized to a
                        # pixel count the old segment no longer fits.
                        self._pixels[segment[1] : segment[2] + 1] = 0
            if self._segments != new_segments:
                self._renew_source_generation()
                self._segments = new_segments
                self.invalidate_cached_props()

    def clear_segments(self):
        with self._output_lock, self._frame_lock:
            self._renew_source_generation()
            self._segments = []
            self.invalidate_cached_props()

    def invalidate_cached_props(self):
        # invalidate cached properties
        for prop in ["priority_virtual", "_virtuals_objs", "virtuals"]:
            if hasattr(self, prop):
                delattr(self, prop)

    def _cleanup_virtual_from_scenes(self, virtual_id):
        """Remove a virtual from all scene configurations."""
        for scene in self._ledfx.config.scenes.values():
            scene.virtuals.pop(virtual_id, None)

    def remove_from_virtuals(self) -> None:
        """Remove segments referencing this device from all virtuals.

        Any virtual (auto-generated or user-created) that loses all of
        its segments as a result is destroyed along with its scene
        references and config entries.  This prevents persisting
        "poisoned" zero-segment virtuals that would crash startup when
        their effect is restored.
        """

        if self._ledfx.devices.get(self.id) is not self:
            return

        # Collect ids of virtuals to destroy after the iteration
        virtuals_to_destroy = []
        for virtual in self._ledfx.virtuals.values():
            if not any(segment[0] == self.id for segment in virtual._segments):
                continue

            if not self._ledfx.virtuals.remove_device_segments(virtual, self.id, self):
                # A newer layout/device owner won admission. It owns any
                # follow-on activation, destruction and persisted state.
                continue

            # If the virtual has no segments left, it cannot host an
            # effect.  Destroy it regardless of auto_generated status to
            # avoid persisting an invalid state that crashes on restart.
            if len(virtual._segments) == 0:
                virtual.clear_effect()
                self._cleanup_virtual_from_scenes(virtual.id)
                virtuals_to_destroy.append(virtual.id)
                _LOGGER.info(
                    "Virtual %s lost all segments after device %s removal; "
                    "scheduled for destruction",
                    virtual.id,
                    self.id,
                )
                continue

            entry = virtual.entry
            if entry is not None:
                entry.segments = virtual.segments

        for id in virtuals_to_destroy:
            virtual = self._ledfx.virtuals.get(id)
            if virtual is None:
                continue
            virtual.clear_effect()
            device_id = virtual.is_device
            device = self._ledfx.devices.get(device_id)
            # Skip destroying the device we are currently processing;
            # the caller is responsible for that.
            if device is not None and device_id != self.id:
                device.remove_from_virtuals()
                self._ledfx.devices.destroy(device_id)

                # Update the configuration
                self._ledfx.config.devices = [
                    _device
                    for _device in self._ledfx.config.devices
                    if _device.id != device_id
                ]

            # cleanup this virtual from any scenes (may already be done,
            # but idempotent)
            self._cleanup_virtual_from_scenes(id)

            self._ledfx.virtuals.destroy(id)

            # Update the configuration
            self._ledfx.config.virtuals = [
                virtual for virtual in self._ledfx.config.virtuals if virtual.id != id
            ]

        # Save the configuration once after all deletions
        if virtuals_to_destroy:
            self._ledfx.config_store.request_save()

    async def add_postamble(self):
        # over ride in child classes for device specific behaviours
        pass

    def sub_v(self, name, icon, segs, rows):
        compound_name = f"{self.name}-{name}"
        _LOGGER.info("Creating a virtual for device %s", compound_name)
        virtual_id = generate_id(compound_name)
        icon_name = get_icon_name(compound_name)
        if icon_name == "wled" and icon is not None:
            icon_name = icon
        virtual_config = {
            "name": compound_name,
            "icon_name": icon_name,
            "transition_time": 0,
            "rows": rows,
        }

        segments = []
        for seg in segs:
            segments.append([self.id, seg[0], seg[1], False])

        # Create the virtual
        virtual = self._ledfx.virtuals.create(
            id=virtual_id,
            config=virtual_config,
            ledfx=self._ledfx,
            auto_generated=True,
        )

        # Create segment on the virtual
        virtual.update_segments(segments)

        # Update the configuration
        self._ledfx.config.virtuals.append(
            VirtualEntry.model_validate(
                {
                    "id": virtual.id,
                    "config": virtual.config,
                    "segments": virtual.segments,
                    "is_device": False,
                    "auto_generated": True,
                }
            )
        )


@BaseRegistry.no_registration
class MidiDevice(Device):
    pass


@BaseRegistry.no_registration
class NetworkedDevice(Device):
    """
    Networked device, handles resolving IP
    """

    class Config(Device.Config):
        ip_address: str = Field(
            description="Hostname or IP address of the device",
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)
    _destination: str | None

    async def async_initialize(self):
        self._destination = None
        await self.resolve_address()

    @contextmanager
    def _config_update_context(self, config: dict[str, object]) -> Iterator[None]:
        old_config = self._config
        old_destination = getattr(self, "_destination", None)
        old_ip = getattr(old_config, "ip_address", None)
        if config.get("ip_address", old_ip) != old_ip:
            self._destination = None
        try:
            with super()._config_update_context(config):
                yield
        except Exception:
            if self._config is old_config:
                self._destination = old_destination
            raise

    async def resolve_address(self, success_callback=None):
        try:
            self._destination = await resolve_destination(
                self._ledfx.loop,
                self._ledfx.thread_executor,
                self.config.ip_address,
            )
            _LOGGER.info(
                "Device %s: Resolved destination to %s",
                self.name,
                self._destination,
            )
            self._online = True
            if success_callback:
                success_callback()
        except ValueError as msg:
            self._online = False
            _LOGGER.warning("Device %s: %s", self.name, msg)

    def activate(self, *args, **kwargs):
        if self._destination is None:
            msg = f"Device {self.name}: Failed to activate, is it online?"
            _LOGGER.warning(msg)
            callback = partial(self.activate, *args, **kwargs)
            async_fire_and_forget(
                self.resolve_address(success_callback=callback),
                loop=self._ledfx.loop,
            )
        else:
            self._online = True
            super().activate(*args, **kwargs)

    @property
    def destination(self):
        if self._destination is None:
            _LOGGER.warning(
                "Device %s: Searching for device... Is it online?", self.name
            )
            async_fire_and_forget(self.resolve_address(), loop=self._ledfx.loop)
            return
        else:
            return self._destination


def available_com_ports() -> list[str]:
    """No port ("") plus the serial ports present now."""
    return ["", *(p.device for p in serial.tools.list_ports.comports())]


def _available_com_port(value: object) -> object:
    if value not in available_com_ports():
        raise ValueError(f"{value!r} is not an available serial port")
    return value


register_enum_source(
    "com_ports",
    EnumSource(options=available_com_ports, validate=_available_com_port),
)


@BaseRegistry.no_registration
class SerialDevice(Device):
    class Config(Device.Config):
        com_port: Annotated[str, FromSource("com_ports", legacy=True)] = Field(
            "",
            description="COM port for Adalight compatible device",
            json_schema_extra={X_REQUIRED: True},
        )
        baudrate: int = Field(
            500000,
            description="baudrate",
            ge=115200,
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.serial = None
        self.baudrate = self.config.baudrate
        self.com_port = self.config.com_port

    def activate(self):
        with self._output_lock:
            try:
                if self.serial and self.serial.is_open:
                    return

                self.serial = serial.Serial(self.com_port, self.baudrate)
                if self.serial.is_open:
                    super().activate()
                    self._online = True

            except serial.SerialException:
                _LOGGER.warning(
                    "Serial Error: Please ensure your device is connected, functioning and the correct COM port is selected."
                )
                self.set_offline()

    def deactivate(self):
        with self._output_lock:
            super().deactivate()
            if self.serial:
                self.serial.close()


class Devices(RegistryLoader):
    """Thin wrapper around the device registry that manages devices"""

    PACKAGE_NAME = "ledfx.devices"

    def __init__(self, ledfx):
        super().__init__(ledfx, Device, self.PACKAGE_NAME)

        def on_shutdown(e):
            self.deactivate_devices()

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)

    @override
    def create(
        self, type: str, id: str | None = None, *args: object, **kwargs: object
    ) -> Device | None:
        device = super().create(type, id, *args, **kwargs)
        if isinstance(device, Device):
            with device._output_lock, device._frame_lock:
                device._renew_source_generation()
            device._refresh_physical_rows()
            return device
        return None

    @override
    def destroy(self, id: str) -> None:
        device = self.get(id)
        if isinstance(device, Device):
            with device._output_lock, device._frame_lock:
                self._ledfx.preview_sampler.invalidate_source(SourceKey("device", id))
                device._output_epoch += 1
                device._source_generation = -1
                device._active = False
        super().destroy(id)

    def create_from_config(self, config: list[DeviceEntry]) -> None:
        for device in config:
            _LOGGER.info("Loading device from config: %s", device)
            try:
                self._ledfx.devices.create(
                    id=device.id,
                    type=device.type,
                    config=device.config,
                    ledfx=self._ledfx,
                    lenient=self._ledfx.config_store.quarantine,
                    lenient_entry=device,
                )
            except Exception as e:  # noqa: BLE001
                # be very prolific on ignoring devices if they are bad
                _LOGGER.warning("Failed to load device %s: %s", device.id, e)

    def deactivate_devices(self):
        for device in self.values():
            device.deactivate()

    def get_device(self, device_id):
        for device in self.values():
            if device_id == device.id:
                return device
        return None

    async def async_initialize_devices(self):
        tasks = [
            device.async_initialize()
            for device in self.values()
            if hasattr(device, "async_initialize")
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if type(result) is ValueError:
                _LOGGER.warning(result)

    async def add_new_device(self, device_type, device_config):
        """
        Creates a new device.

        Raises ValueError (a pydantic ValidationError for a bad config) when
        the device can't be created.
        """
        if not isinstance(device_config, dict):
            raise ValueError("Device config must be an object")  # noqa: TRY004 - callers catch ValueError
        try:
            device_class = self.get_class(device_type)
        except (KeyError, TypeError):
            raise ValueError(f"Unknown device type: {device_type}") from None
        # First, we try to make sure this device doesn't share a destination with any existing device
        resolved_dest: str | None = None
        if device_config.get("ip_address") is not None:
            if not isinstance(device_config["ip_address"], str):
                raise ValueError("ip_address must be a string")
            device_config["ip_address"] = clean_ip(device_config["ip_address"])
            device_ip = device_config["ip_address"]
            try:
                resolved_dest = await resolve_destination(
                    self._ledfx.loop, self._ledfx.thread_executor, device_ip
                )
            except ValueError:
                _LOGGER.warning(
                    "Discarding device %s as it could not be resolved.", device_ip
                )
                raise ValueError(f"Could not resolve {device_ip}") from None
            # The IP tests read type-specific keys (universe, port...), so give
            # them the validated config with its defaults. WLED fills its
            # config from the device below and only compares the address.
            checked = (
                device_config
                if device_type == "wled"
                else device_class.config_model().model_validate(device_config).as_dict()
            )

            for existing_device in self._ledfx.devices.values():
                existing_ip = getattr(existing_device.config, "ip_address", None)
                if existing_ip is not None and (
                    existing_ip == device_ip
                    or existing_ip == resolved_dest
                    or resolved_dest == getattr(existing_device, "_destination", None)
                ):
                    self.run_device_ip_tests(device_type, checked, existing_device)

        # If WLED device, get all the necessary config from the device itself
        if device_type == "wled":
            if resolved_dest is None:
                raise ValueError("WLED devices require an ip_address")
            wled = WLED(resolved_dest)
            wled_config = await wled.get_config()

            led_info = wled_config["leds"]
            # If we've found the device via WLED scan, it won't have a custom name from the frontend
            # However if it's "WLED" (i.e, Default) then we will name the device exactly how WLED does, by using the second half of it's MAC address
            # This allows us to respect the users choice of names if adding a WLED device via frontend
            # I turned black off as this logic is clearer on one line
            # fmt: off
            if "name" in device_config and device_config["name"] is not None:
                wled_name = device_config["name"]
            elif wled_config["name"] == "WLED":
                wled_name = f"{wled_config['name']}-{wled_config['mac'][6:]}".upper()
            else:
                wled_name = wled_config['name']
            # fmt: on
            wled_count = led_info["count"]
            wled_rgbmode = led_info["rgbw"]
            wled_build = wled_config["vid"]

            if wled_support_DDP(wled_build):
                _LOGGER.info("WLED build Supports DDP: %s", wled_build)
                sync_mode = "DDP"
            else:
                _LOGGER.info("WLED build pre DDP, default to UDP: %s", wled_build)
                sync_mode = "UDP"

            icon_name = get_icon_name(wled_name)

            wled_config = {
                "name": wled_name,
                "pixel_count": wled_count,
                "icon_name": icon_name,
                "rgbw_led": wled_rgbmode,
                "sync_mode": sync_mode,
            }

            device_config.update(wled_config)

        # Validate before anything is created, so a bad config changes nothing.
        # A new device (POST /api/devices, mDNS discovery, find_lifx): live choices
        # such as a serial port must exist now. Nothing is stored yet, so every
        # key is new; the default com_port "" (no port) always passes.
        device_class.config_model().model_validate(
            device_config, context=RUNTIME_CONTEXT
        )
        device_id = generate_id(device_config["name"])

        # Create the device
        _LOGGER.info(
            "Adding device of type %s with config %s",
            device_type,
            device_config,
        )
        device = self._ledfx.devices.create(
            id=device_id,
            type=device_type,
            config=device_config,
            ledfx=self._ledfx,
        )

        if hasattr(device, "async_initialize"):
            try:
                await device.async_initialize()
            except BaseException:
                # Not saved yet: leaving it registered would list a device
                # that disappears on restart, and push a retry to "<id>-1".
                self._ledfx.devices.destroy(device.id)
                raise

        device_config = device.config.as_dict()
        if device_type == "wled":
            device_config["name"] = wled_name
        # Update and save the configuration
        self._ledfx.config.devices.append(
            DeviceEntry.model_validate(
                {
                    "id": device.id,
                    "type": device.type,
                    "config": device_config,
                }
            )
        )

        # Generate virtual configuration for the device
        _LOGGER.info("Creating a virtual for device %s", device.name)
        virtual_id = generate_id(device.name)
        virtual_config = {
            "name": device.name,
            "icon_name": device_config["icon_name"],
            "rows": device_config.get("rows", 1),
        }

        if device_type == "wled" and "matrix" in led_info and "h" in led_info["matrix"]:
            virtual_config["rows"] = led_info["matrix"]["h"]

        segments = [[device.id, 0, device_config["pixel_count"] - 1, False]]

        # Create the virtual
        virtual = self._ledfx.virtuals.create(
            id=virtual_id,
            config=virtual_config,
            ledfx=self._ledfx,
            is_device=device.id,
            auto_generated=False,
        )

        # Create the device as a single segment on the virtual
        virtual.update_segments(segments)

        # Update the configuration
        self._ledfx.config.virtuals.append(
            VirtualEntry.model_validate(
                {
                    "id": virtual.id,
                    "config": virtual.config,
                    "segments": virtual.segments,
                    "is_device": device.id,
                    "auto_generated": virtual.auto_generated,
                }
            )
        )

        self._ledfx.events.fire_event(DeviceCreatedEvent(device.name))
        await device.add_postamble()

        # Finally, save the config to file!
        self._ledfx.config_store.request_save()

        return device

    async def set_wleds_sync_mode(self, mode):
        for device in self.values():
            if (
                device.type == "wled"
                and device.pixel_count > 480
                and device.config.sync_mode != mode
            ):
                device.wled.set_sync_mode(mode)
                await device.wled.flush_sync_settings()
                device.update_config({"sync_mode": mode})

    def generate_device_ip_tests(self, new_type, new_config, pre_device):
        """
        Generate tests to check if the devices are compatible with each other on a common IP

        There are various scenarios where devices can coexist on the same IP address
        1) device types with different port numbers or other access methods
        2) common device types that have secondary checks that must be performed
           for example e131 / artnet universe or openrgb openrgb_id
           port number could also be considered here

        Explicit device approval tests should be added prior to the final is_general_port_separated test
        which is a catch-all for any device type that does not have a specific test

        Args:
            new_type (_type_): new_config does not carry device type so must be explicit
            new_config (_type_): config from creation of new device
            pre_device (_type_): config from pre-existing device

        Yields:
            bool: True if the devices can explicity coexist, False if there is no rejection
            ValueError: if the devices cannot coexist due to a hard failure
        """
        for test in [
            self.is_wled_duplicate,
            self.is_universe_separated,
            self.is_openrgb_id_separated,
            self.is_osc_port_path_separated,
            self.is_ddp_destination_separated,
            self.is_hue_group_separated,
            self.is_general_port_separated,
        ]:
            yield test(new_type, new_config, pre_device)

    def run_device_ip_tests(self, new_type, new_config, pre_device):
        """
        Run tests to check if the devices are compatible with each other on a common IP
        This function will reach the end and return if no tests hard succeeded or hard failed
        Individual tests with will
            return False for a soft fail = coexistance was not covered by the test for success or hard fail
            return True for success = coexistance is viable and device should be created
            raise ValueError with suitable message for hard fail = coexistance is not viable and device should not be created

        Args:
            new_type (_type_): new_config does not carry device type so must be explicit
            new_config (_type_): config from creation of new device
            pre_device (_type_): config from pre-existing device
        """

        for result in self.generate_device_ip_tests(new_type, new_config, pre_device):
            if result:
                return

        # No test explicitly approved coexistence - reject by default
        msg = f"Ignoring {new_config.get('ip_address', 'unknown')}: Shares IP with existing device {pre_device.name} and no coexistence rule matched"
        _LOGGER.info(msg)
        raise ValueError(msg)

    def is_wled_duplicate(self, new_type, new_config, pre_device):
        """
        Check if the new WLED device is a duplicate of an existing WLED device
        on the same IP address.
        """
        if new_type == "wled" and pre_device.type == "wled":
            msg = f"Ignoring {new_config['ip_address']}: WLED device already exists as {pre_device.name}"
            _LOGGER.info(msg)
            raise ValueError(msg)
        return False

    def is_universe_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is universe separated from the pre-existing device
        """
        if new_type in ["e131", "artnet"] and pre_device.type in [
            "e131",
            "artnet",
        ]:
            if new_config["universe"] == pre_device.config.universe:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and port {new_config.get('port', DEFAULT_PORT)} and starting universe with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_openrgb_id_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is openrgb_id separated from the pre-existing device
        """
        if new_type == "openrgb" and pre_device.type == "openrgb":
            if new_config["openrgb_id"] == pre_device.config.openrgb_id:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and OpenRGB ID with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_osc_port_path_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is osc port and path separated from the pre-existing device
        """
        if new_type == "osc" and pre_device.type == "osc":
            if (
                new_config["port"] == pre_device.config.port
                and new_config["path"] == pre_device.config.path
                and new_config["starting_addr"] == pre_device.config.starting_addr
            ):
                msg = f"Ignoring {new_config['ip_address']}: Shares IP, Port, Path and starting address with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_ddp_destination_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is DDP destination_id separated from the pre-existing device
        """
        if new_type == "ddp" and pre_device.type == "ddp":
            if (
                new_config["port"] == pre_device.config.port
                and new_config.get("destination_id", 1)
                == pre_device.config.destination_id
            ):
                msg = f"Ignoring {new_config['ip_address']}: Shares IP, port {new_config['port']} and destination_id with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_hue_group_separated(self, new_type, new_config, pre_device):
        """
        Check if the new Hue device is group_name separated from the pre-existing Hue device
        """
        if new_type == "hue" and pre_device.type == "hue":
            if new_config["group_name"] == pre_device.config.group_name:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and group_name with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_general_port_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is port separated from the pre-existing device
        """
        # e131 is a special case as its port number is not in the config, but in the library
        new_port = None
        pre_port = None
        if new_type == "e131":
            new_port = DEFAULT_PORT
        if pre_device.type == "e131":
            pre_port = DEFAULT_PORT
        if "port" in new_config:
            new_port = new_config["port"]
        if getattr(pre_device.config, "port", None) is not None:
            pre_port = pre_device.config.port

        if new_port is not None and pre_port is not None:
            if new_port == pre_port:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and port with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False
