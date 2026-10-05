import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import numpy as np
from ledfx_senders import E131Sender, Frame
from ledfx_senders.e131 import ChannelLayout
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import Device, NetworkedDevice, resolve_destination

_LOGGER = logging.getLogger(__name__)


class E131Device(NetworkedDevice):
    """E1.31 device support"""

    class Config(NetworkedDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        universe: int = Field(1, description="DMX universe for the device", ge=1)
        universe_size: int = Field(510, description="Size of each DMX universe", ge=1)
        channel_offset: int = Field(
            0, description="Channel offset within the DMX universe", ge=0
        )
        packet_priority: int = Field(
            100,
            description="Priority given to the sACN packets for this device",
            ge=0,
            le=200,
        )

    config = TypedConfig(Config)

    OUTPUT_KEYS = (
        "ip_address",
        "pixel_count",
        "universe",
        "universe_size",
        "channel_offset",
        "packet_priority",
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "e131"
        self.device_lock = threading.RLock()
        self._sender: E131Sender | None = None
        self._destination = None
        self._generation = 0
        self._requested = False
        self._maintenance_task: asyncio.Task[None] | None = None
        self._maintenance_future: asyncio.Future[None] | None = None
        self._set_channel_layout()

    def _layout(self) -> ChannelLayout:
        return ChannelLayout(
            self.config.pixel_count * 3,
            self.config.universe,
            self.config.universe_size,
            self.config.channel_offset,
        )

    def _set_channel_layout(self) -> None:
        layout = self._layout()
        self._set_config_values(
            channel_count=layout.channel_count, universe_end=layout.universes[-1]
        )

    @override
    @contextmanager
    def _config_update_context(self, config: dict[str, object]) -> Iterator[None]:
        with self.device_lock, super()._config_update_context(config):
            yield

    def config_updated(self, config: object) -> None:
        with self.device_lock:
            layout = self._layout()
            candidate = None
            changed = self._output_changed()
            if changed and self._requested:
                destination = self._destination
                if self.config.ip_address.lower() == "multicast":
                    destination = "multicast"
                if destination is not None:
                    candidate = E131Sender(
                        layout,
                        destination=destination,
                        source_name=self.name,
                        priority=self.config.packet_priority,
                    )
            self._set_channel_layout()
            self._built_settings = self._output_settings()
            if changed and self._requested:
                self._replace(candidate)
                if candidate is None:
                    self._schedule_resolution()

    def _replace(self, sender: E131Sender | None) -> None:
        old = self._sender
        self._sender = sender
        self._generation += 1
        try:
            self._ledfx.loop.call_soon_threadsafe(
                self._start_maintenance, sender, self._generation
            )
        except RuntimeError:
            # Shutdown may already have closed the loop; release native
            # resources even when no further cancellation can be scheduled.
            _LOGGER.debug("E1.31 maintenance loop unavailable for %s", self.name)
        if old is not None:
            old.close()

    def _start_maintenance(self, sender: E131Sender | None, generation: int) -> None:
        with self.device_lock:
            if sender is not self._sender or generation != self._generation:
                return
            if self._maintenance_task is not None:
                self._maintenance_task.cancel()
                self._maintenance_task = None
            if sender is not None:
                self._maintenance_task = self._ledfx.loop.create_task(
                    self._maintain(sender, generation)
                )

    async def _maintain(self, sender: E131Sender, generation: int) -> None:
        while True:
            await asyncio.sleep(0.25)
            with self.device_lock:
                if sender is not self._sender or generation != self._generation:
                    return
            try:
                # Cancellation stops scheduling, but cannot stop an executor
                # call. A replacement awaits that call before submitting work.
                if self._maintenance_future is not None:
                    await asyncio.shield(self._maintenance_future)
                with self.device_lock:
                    if sender is not self._sender or generation != self._generation:
                        return
                self._maintenance_future = self._ledfx.loop.run_in_executor(
                    self._ledfx.thread_executor, sender.service
                )
                self._maintenance_future.add_done_callback(self._maintenance_done)
                await asyncio.shield(self._maintenance_future)
            except OSError:
                pass  # The completion callback logs errors even after detachment.
            finally:
                if (
                    self._maintenance_future is not None
                    and self._maintenance_future.done()
                ):
                    self._maintenance_future = None

    def _maintenance_done(self, future: asyncio.Future[None]) -> None:
        if not future.cancelled() and (error := future.exception()) is not None:
            _LOGGER.warning("E1.31 maintenance failed for %s: %s", self.name, error)

    def _schedule_resolution(self) -> None:
        generation = self._generation
        address = self.config.ip_address
        self._ledfx.loop.call_soon_threadsafe(
            lambda: self._ledfx.loop.create_task(self._resolve(address, generation))
        )

    async def _resolve(
        self,
        address: str,
        generation: int,
        success_callback: Callable[[], object] | None = None,
        *,
        require_requested: bool = True,
    ) -> None:
        try:
            destination = await resolve_destination(
                self._ledfx.loop, self._ledfx.thread_executor, address
            )
        except ValueError as error:
            self._resolution_failed(address, generation, error)
            return
        with self.device_lock:
            if (
                generation != self._generation
                or address != self.config.ip_address
                or (require_requested and not self._requested)
            ):
                return
            candidate = None
            if self._requested and (
                self._sender is None or destination != self._destination
            ):
                candidate = E131Sender(
                    self._layout(),
                    destination=destination,
                    source_name=self.name,
                    priority=self.config.packet_priority,
                )
            # Construction can fail: publish DNS and sender state together only
            # once the replacement is ready, preserving a healthy live session.
            self._destination = destination
            self._online = True
            if candidate is not None:
                self._replace(candidate)
                if not self.is_active():
                    Device.activate(self)
        if success_callback is not None:
            success_callback()

    @override
    async def async_initialize(self) -> None:
        if self.config.ip_address.lower() != "multicast":
            await self.resolve_address()

    @override
    async def resolve_address(
        self, success_callback: Callable[[], object] | None = None
    ) -> None:
        with self.device_lock:
            address = self.config.ip_address
            generation = self._generation
        if address.lower() != "multicast":
            await self._resolve(
                address, generation, success_callback, require_requested=False
            )

    def _resolution_failed(
        self, address: str, generation: int, error: ValueError
    ) -> None:
        with self.device_lock:
            if generation == self._generation and address == self.config.ip_address:
                self._online = False
                _LOGGER.warning("Device %s: %s", self.name, error)

    def activate(self) -> None:
        with self.device_lock:
            self._requested = True
            destination = self._destination
            if self.config.ip_address.lower() == "multicast":
                destination = "multicast"
            if destination is None:
                self._schedule_resolution()
                return
            candidate = E131Sender(
                self._layout(),
                destination=destination,
                source_name=self.name,
                priority=self.config.packet_priority,
            )
            self._replace(candidate)
            self._online = True
            Device.activate(self)

    def deactivate(self) -> None:
        with self.device_lock:
            self._requested = False
            self._replace(None)
            Device.deactivate(self)

    def flush(self, data: Frame) -> None:
        with self.device_lock:
            if self._sender is not None:
                # A render already in flight may have the previous pixel count.
                count = (
                    data.size
                    if isinstance(data, np.ndarray)
                    else memoryview(data).nbytes
                )
                if count != self._sender.layout.channel_count:
                    _LOGGER.warning("Dropping stale E1.31 frame for %s", self.name)
                    return
                self._sender.send(data)
