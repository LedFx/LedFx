"""Shared ownership and publication lifecycle for synchronous packet senders."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ledfx_senders import (
    ArtNetSender,
    DDPSender,
    OPCSender,
    OSCSender,
    UDPRealtimeSender,
)
from typing_extensions import override

from ledfx.devices import Device, NetworkedDevice, resolve_destination
from ledfx.utils import BaseRegistry

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_LOGGER = logging.getLogger(__name__)


@BaseRegistry.no_registration
class NativePacketDevice(NetworkedDevice):
    def __init__(self, ledfx: LedFxCore, config: NetworkedDevice.Config) -> None:
        super().__init__(ledfx, config)
        self.device_lock = threading.RLock()
        self._sender: (
            ArtNetSender | DDPSender | OPCSender | OSCSender | UDPRealtimeSender | None
        ) = None
        self._destination = None
        self._generation = 0
        self._requested = False

    @override
    @contextmanager
    def _config_update_context(self, config: dict[str, object]) -> Iterator[None]:
        with (
            self._output_lock,
            self.device_lock,
            super()._config_update_context(config),
        ):
            yield

    def _validate_configuration(self) -> None:
        raise NotImplementedError

    def _make_sender(
        self, destination: str
    ) -> ArtNetSender | DDPSender | OPCSender | OSCSender | UDPRealtimeSender:
        raise NotImplementedError

    def _replace(
        self,
        candidate: ArtNetSender
        | DDPSender
        | OPCSender
        | OSCSender
        | UDPRealtimeSender
        | None,
    ) -> None:
        old = self._sender
        self._sender = candidate
        self._generation += 1
        if old is not None:
            old.close()

    @override
    def config_updated(self, config: object) -> None:
        with self._output_lock, self.device_lock:
            if not self._output_changed():
                return
            self._validate_configuration()
            candidate = None
            if self._requested and self._destination is not None:
                candidate = self._make_sender(self._destination)
            self._replace(candidate)
            self._built_settings = self._output_settings()
            if self._requested and candidate is None:
                self._schedule_resolution()

    def _schedule_resolution(self) -> None:
        address, generation = self.config.ip_address, self._generation
        self._ledfx.loop.call_soon_threadsafe(
            lambda: self._ledfx.loop.create_task(self._resolve(address, generation))
        )

    @override
    async def resolve_address(
        self, success_callback: Callable[[], object] | None = None
    ) -> None:
        with self._output_lock, self.device_lock:
            address, generation = self.config.ip_address, self._generation
        await self._resolve(address, generation, success_callback)

    async def _resolve(
        self,
        address: str,
        generation: int,
        success_callback: Callable[[], object] | None = None,
    ) -> None:
        try:
            destination = await resolve_destination(
                self._ledfx.loop, self._ledfx.thread_executor, address
            )
        except ValueError as error:
            with self._output_lock, self.device_lock:
                if generation == self._generation and address == self.config.ip_address:
                    self._online = False
                    _LOGGER.warning("Device %s: %s", self.name, error)
            return
        with self._output_lock, self.device_lock:
            if generation != self._generation or address != self.config.ip_address:
                return
            candidate = None
            if self._requested and (
                self._sender is None or destination != self._destination
            ):
                self._validate_configuration()
                candidate = self._make_sender(destination)
            # Publish only after construction succeeds, keeping the live sender
            # and DNS metadata consistent on candidate failure.
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
        await self.resolve_address()

    @override
    def activate(self, *args: object, **kwargs: object) -> None:
        with self._output_lock, self.device_lock:
            self._validate_configuration()
            self._requested = True
            if self._destination is None:
                self._schedule_resolution()
                return
            candidate = self._make_sender(self._destination)
            self._replace(candidate)
            self._online = True
            Device.activate(self)

    @override
    def deactivate(self) -> None:
        with self._output_lock, self.device_lock:
            self._requested = False
            self._replace(None)
            Device.deactivate(self)
