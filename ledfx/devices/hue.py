"""Hue HTTPS control plane and owned native Entertainment streaming sessions."""

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, ClassVar, Literal, TypeVar, cast

import numpy as np
import requests
from ledfx_senders import HueSender
from numpy.typing import NDArray
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import PluginConfig, TypedConfig
from ledfx.devices import Device, NetworkedDevice
from ledfx.utils import resolve_destination

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


@dataclass(frozen=True)
class HueSettings:
    destination: str
    bridge: str
    username: str = field(repr=False)
    psk_identity: bytes = field(repr=False)
    client_key: bytes = field(repr=False)
    entertainment_id: str
    channel_ids: tuple[int, ...]
    port: int = 2100
    connect_timeout: float = 5.0
    send_timeout: float = 0.2
    close_timeout: float = 0.2


@dataclass(frozen=True)
class HueControlSettings:
    bridge: str
    group_name: str
    username: str | None = field(repr=False)
    clientkey: str | None = field(repr=False)
    application_id: str | None = field(repr=False)


@dataclass
class HueZoneLease:
    settings: HueSettings
    generation: int
    started: bool = False


@dataclass
class HueRetirement:
    lease: HueZoneLease | None
    sender: HueSender | None
    candidate: HueSender | None
    service: asyncio.Task[None] | None
    recovery: asyncio.Task[None] | None
    claimed: bool = False


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("Unexpected Hue response")
    return cast(dict[str, object], value)


def _items(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("Unexpected Hue response")
    return cast(list[object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing Hue configuration")
    return value


class HueDevice(NetworkedDevice):
    """Publish a sender only after its zone and native connection succeed."""

    class Config(NetworkedDevice.Config):
        ip_address: str = Field(
            description="Hostname or IP address of the Hue bridge",
            json_schema_extra={X_REQUIRED: True},
        )
        group_name: str = Field(
            description="Entertainment zone group name",
            json_schema_extra={X_REQUIRED: True},
        )
        udp_port: int = Field(2100, description="port")

    config = TypedConfig(Config)
    OUTPUT_KEYS: ClassVar[tuple[str, ...]] = (
        "ip_address",
        "udp_port",
        "username",
        "clientkey",
        "hue_application_id",
        "entertainment_id",
        "channel_ids",
        "pixel_lights",
    )

    def __init__(self, ledfx: "LedFxCore", config: PluginConfig) -> None:
        super().__init__(ledfx, config)
        self._device_type = "Hue"
        self._destination = None
        self._publication_lock = threading.RLock()
        self._lifecycle_lock = asyncio.Lock()
        self._generation = 0
        self._requested = False
        self._shutting_down = False
        self._sender: HueSender | None = None
        self._candidate: HueSender | None = None
        self._zone_lease: HueZoneLease | None = None
        self._failed_leases: list[HueZoneLease] = []
        self._pending_retirements: list[HueRetirement] = []
        self._lifecycle_tasks: set[asyncio.Task[None]] = set()
        self._service_task: asyncio.Task[None] | None = None
        self._service_generation: int | None = None
        self._service_tasks: set[asyncio.Task[None]] = set()
        self._recovery_generation: int | None = None
        self._recovery_task: asyncio.Task[None] | None = None
        self._online = False

    @contextmanager
    def _config_update_context(
        self, config: dict[str, object]
    ) -> Generator[None, None, None]:
        with self._publication_lock, super()._config_update_context(config):
            yield

    def config_updated(self, config: Config) -> None:
        if self._output_changed():
            requested = self._requested
            self.deactivate()
            self._built_settings = self._output_settings()
            if requested:
                self.activate()

    def _spawn(self, coroutine: Coroutine[object, object, None]) -> asyncio.Task[None]:
        task = self._ledfx.loop.create_task(coroutine)
        self._lifecycle_tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task[None]) -> None:
        self._lifecycle_tasks.discard(task)
        self._service_tasks.discard(task)
        with self._publication_lock:
            if self._recovery_task is task:
                self._recovery_task = None
        if not task.cancelled() and task.exception() is not None:
            # Native/control errors can carry credentials: never interpolate them.
            _LOGGER.warning("Hue lifecycle operation failed")

    async def _executor(self, function: Callable[[], _T]) -> _T:
        future = self._ledfx.loop.run_in_executor(self._ledfx.thread_executor, function)
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(future)
                break
            except asyncio.CancelledError:
                # Repeated cancellation must not abandon an executor operation
                # that can still acquire a remote zone after its waiter exits.
                if future.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def resolve_address(
        self, success_callback: Callable[[], None] | None = None
    ) -> None:
        with self._publication_lock:
            generation, bridge = self._generation, self.config.ip_address
        try:
            destination = await resolve_destination(
                self._ledfx.loop, self._ledfx.thread_executor, bridge
            )
        except ValueError:
            with self._publication_lock:
                if generation == self._generation:
                    self._online = False
            return
        with self._publication_lock:
            if generation != self._generation or bridge != self.config.ip_address:
                return
            self._destination = destination
        if success_callback is not None:
            success_callback()

    def _channel_ids(self) -> tuple[int, ...]:
        stored = self.config.as_dict()
        channels = stored.get("channel_ids")
        if channels is None:
            return tuple(int(k) for k in _object(stored.get("pixel_lights", {})))
        if not isinstance(channels, (list, tuple)):
            raise TypeError("Invalid Hue channel mapping")
        values = cast(list[object] | tuple[object, ...], channels)
        if any(type(value) is not int for value in values):
            raise ValueError("Invalid Hue channel mapping")
        return cast(tuple[int, ...], tuple(values))

    def _settings_snapshot(self) -> HueSettings:
        if self._destination is None:
            raise ValueError("Hue bridge address has not been resolved")
        return HueSettings(
            destination=self._destination,
            bridge=self.config.ip_address,
            username=_text(self.config.as_dict().get("username")),
            psk_identity=_text(self.config.as_dict().get("hue_application_id")).encode(
                "utf-8"
            ),
            client_key=bytes.fromhex(_text(self.config.as_dict().get("clientkey"))),
            entertainment_id=_text(self.config.as_dict().get("entertainment_id")),
            channel_ids=self._channel_ids(),
            port=self.config.udp_port,
        )

    def _sender_for_settings(self, settings: HueSettings) -> HueSender:
        return HueSender(
            destination=settings.destination,
            psk_identity=settings.psk_identity,
            client_key=settings.client_key,
            entertainment_id=settings.entertainment_id,
            channel_ids=settings.channel_ids,
            port=settings.port,
            connect_timeout=settings.connect_timeout,
            send_timeout=settings.send_timeout,
            close_timeout=settings.close_timeout,
        )

    @staticmethod
    def _https_request(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        # Preserve Hue's existing certificate policy, with bounded HTTPS only.
        host = f"[{bridge}]" if ":" in bridge and not bridge.startswith("[") else bridge
        try:
            response = requests.request(
                method,
                f"https://{host}/{endpoint.lstrip('/')}",
                json=data,
                headers={"hue-application-key": username} if username else {},
                timeout=(3.0, 5.0),
                verify=False,
                allow_redirects=False,
            )
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise ConnectionError("Hue HTTPS request rejected")
            return cast(object, response.json()), response.headers
        except requests.RequestException:
            # requests errors include the URL; v1 endpoints contain a credential.
            raise ConnectionError("Hue HTTPS request failed") from None

    def _request_sync(
        self,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        username = self.config.as_dict().get("username")
        return self._https_request(
            self.config.ip_address,
            _text(username) if username else None,
            method,
            endpoint,
            data,
        )

    async def _zone_action(
        self, lease: HueZoneLease, action: Literal["start", "stop"]
    ) -> None:
        settings = lease.settings
        endpoint = (
            f"/clip/v2/resource/entertainment_configuration/{settings.entertainment_id}"
        )

        def request() -> None:
            response, _ = self._https_request(
                settings.bridge, settings.username, "PUT", endpoint, {"action": action}
            )
            if _object(response).get("errors"):
                raise ConnectionError("Hue zone action rejected")
            # Record acquisition in the worker, even if the waiter was cancelled.
            lease.started = action == "start"

        await self._executor(request)

    def activate(self) -> None:
        with self._publication_lock:
            if self._shutting_down or self._sender is not None:
                return
            self._requested = True
            self._generation += 1
            generation = self._generation
        self._schedule_activation(generation)

    def _schedule_activation(self, generation: int) -> None:
        self._ledfx.loop.call_soon_threadsafe(
            lambda: self._spawn(self._activate_generation(generation))
        )

    async def _retry_failed_cleanup(self) -> bool:
        for lease in list(self._failed_leases):
            for _ in range(3):
                try:
                    await self._zone_action(lease, "stop")
                except Exception:  # noqa: BLE001 - contain arbitrary control-plane failures
                    _LOGGER.warning("Hue zone cleanup retry failed")
                    continue
                self._failed_leases.remove(lease)
                break
            else:
                return False
        return True

    async def _activate_generation(self, generation: int) -> None:
        async with self._lifecycle_lock:
            await self._drain_retirements()
            with self._publication_lock:
                if (
                    generation != self._generation
                    or not self._requested
                    or self._sender is not None
                ):
                    return
            if not await self._retry_failed_cleanup():
                return
            with self._publication_lock:
                if (
                    generation != self._generation
                    or not self._requested
                    or self._sender is not None
                ):
                    return
            if self._destination is None:
                await self.resolve_address()
            with self._publication_lock:
                if (
                    generation != self._generation
                    or not self._requested
                    or self._sender is not None
                ):
                    return
                settings = self._settings_snapshot()
            lease = HueZoneLease(settings, generation)
            candidate: HueSender | None = None
            published = False
            try:
                await self._zone_action(lease, "start")
                candidate = self._sender_for_settings(settings)
                with self._publication_lock:
                    current = generation == self._generation and self._requested
                    if current:
                        self._candidate = candidate
                if not current:
                    return
                future = self._ledfx.loop.run_in_executor(
                    self._ledfx.thread_executor, candidate.connect
                )
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    # The native close interrupts connect. Cancelling its asyncio
                    # waiter alone would leave executor work running.
                    interruption = self._spawn(
                        self._interrupt_connect(candidate, future)
                    )
                    await self._await_owned(interruption)
                    raise
                with self._publication_lock:
                    if generation == self._generation and self._requested:
                        self._sender = candidate
                        self._candidate = None
                        self._zone_lease = lease
                        self._online = True
                        Device.activate(self)
                        published = True
                if published:
                    self._start_service(candidate, generation)
            finally:
                if not published:
                    with self._publication_lock:
                        if self._candidate is candidate:
                            self._candidate = None
                    await self._cleanup_generation(lease, candidate)

    async def _interrupt_connect(
        self, candidate: HueSender, future: asyncio.Future[None]
    ) -> None:
        try:
            await self._executor(candidate.close)
        finally:
            await asyncio.gather(future, return_exceptions=True)

    async def _await_owned(self, task: asyncio.Task[None]) -> None:
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _cleanup_generation(
        self, lease: HueZoneLease, sender: HueSender | None
    ) -> None:
        async def cleanup() -> None:
            if sender is not None:
                try:
                    await self._executor(sender.close)
                except Exception:  # noqa: BLE001 - cleanup must outlive failed transports
                    _LOGGER.warning("Hue sender close failed")
            if lease.started:
                try:
                    await self._zone_action(lease, "stop")
                except Exception:  # noqa: BLE001 - cleanup must outlive failed transports
                    if lease not in self._failed_leases:
                        self._failed_leases.append(lease)
                    _LOGGER.warning("Hue zone cleanup failed")

        await self._await_owned(self._spawn(cleanup()))

    def _register_retirement_locked(
        self,
        lease: HueZoneLease | None,
        sender: HueSender | None,
        candidate: HueSender | None,
        generation: int,
    ) -> HueRetirement:
        # Ownership must be visible before publication invalidation releases its
        # lock. Successor activation drains this record even if loop dispatch is
        # delayed by the render thread.
        service = self._service_task if self._service_generation == generation else None
        if service is not None:
            self._service_task = None
            self._service_generation = None
        recovery = self._recovery_task
        self._recovery_task = None
        retirement = HueRetirement(lease, sender, candidate, service, recovery)
        self._pending_retirements.append(retirement)
        return retirement

    @staticmethod
    def _cancel_retired_tasks(retirement: HueRetirement) -> None:
        for task in (retirement.service, retirement.recovery):
            if task is not None:
                task.cancel()

    async def _finish_retirement(self, retirement: HueRetirement) -> None:
        self._cancel_retired_tasks(retirement)
        if retirement.candidate is not None:
            await self._close_candidate(retirement.candidate)
        if retirement.lease is not None:
            await self._cleanup_generation(retirement.lease, retirement.sender)

    async def _drain_retirements(self) -> None:
        # The caller owns _lifecycle_lock throughout every close/stop, preserving
        # old rollback before successor zone start even under cancellation.
        while True:
            with self._publication_lock:
                if not self._pending_retirements:
                    return
                retirement = self._pending_retirements.pop(0)
                retirement.claimed = True
            await self._await_owned(self._spawn(self._finish_retirement(retirement)))

    async def _retire_pending(self) -> None:
        async with self._lifecycle_lock:
            await self._drain_retirements()

    def _queue_retirement(self, retirement: HueRetirement) -> None:
        def retire() -> None:
            with self._publication_lock:
                claimed = retirement.claimed
            if claimed:
                return
            self._cancel_retired_tasks(retirement)
            # Interrupt a connect that already owns the lifecycle lock. This
            # close refers only to the captured candidate, never its successor.
            if retirement.candidate is not None:
                self._spawn(self._close_candidate(retirement.candidate))
            self._spawn(self._retire_pending())

        self._ledfx.loop.call_soon_threadsafe(retire)

    async def _close_candidate(self, candidate: HueSender) -> None:
        await self._executor(candidate.close)

    def is_activation_requested(self) -> bool:
        with self._publication_lock:
            return self._requested

    def deactivate(self) -> None:
        with self._publication_lock:
            generation = self._generation
            self._requested = False
            self._recovery_generation = None
            self._generation += 1
            sender, candidate, lease = self._sender, self._candidate, self._zone_lease
            self._sender = self._candidate = None
            self._zone_lease = None
            self._online = False
            Device.deactivate(self)
            retirement = self._register_retirement_locked(
                lease, sender, candidate, generation
            )
        self._queue_retirement(retirement)

    def flush(self, data: NDArray[np.generic]) -> None:
        if not isinstance(data, np.ndarray):
            raise TypeError("Hue frames must be numpy arrays")
        with self._publication_lock:
            sender, generation = self._sender, self._generation
        if sender is None:
            return
        try:
            sender.send(data)
        except (OSError, ConnectionError, TimeoutError):
            self._sender_failed(sender, generation)

    def _sender_failed(self, sender: HueSender, generation: int) -> None:
        with self._publication_lock:
            if self._sender is not sender or generation != self._generation:
                return
            lease = self._zone_lease
            self._sender = None
            self._zone_lease = None
            self._generation += 1
            recovery_generation = self._generation
            self._online = False
            Device.deactivate(self)
            retirement = self._register_retirement_locked(
                lease, sender, None, generation
            )
            recover = self._requested
            if recover:
                self._recovery_generation = recovery_generation
        self._queue_retirement(retirement)
        if recover:
            self._ledfx.loop.call_soon_threadsafe(
                self._start_recovery, recovery_generation
            )

    def _start_recovery(self, generation: int) -> None:
        with self._publication_lock:
            if generation != self._generation or not self._requested:
                return
            self._recovery_task = self._spawn(self._recover(generation))

    async def _recover(self, generation: int) -> None:
        try:
            for delay in (0.25, 0.5, 1.0):
                await asyncio.sleep(delay)
                with self._publication_lock:
                    if generation != self._generation or not self._requested:
                        return
                try:
                    await self._activate_generation(generation)
                except Exception:  # noqa: BLE001 - cleanup must outlive failed transports
                    _LOGGER.warning("Hue recovery attempt failed")
                with self._publication_lock:
                    if self._sender is not None:
                        return
        finally:
            with self._publication_lock:
                if self._recovery_generation == generation:
                    self._recovery_generation = None

    def _start_service(self, sender: HueSender, generation: int) -> None:
        task = self._ledfx.loop.create_task(self._service(sender, generation))
        self._service_tasks.add(task)
        task.add_done_callback(self._task_done)
        with self._publication_lock:
            current = self._sender is sender and self._generation == generation
            previous = self._service_task if current else None
            if current:
                self._service_task = task
                self._service_generation = generation
        if previous is not None:
            previous.cancel()
        if not current:
            task.cancel()

    def _stop_service(self) -> None:
        with self._publication_lock:
            task = self._service_task
            self._service_task = None
            self._service_generation = None
        if task is not None:
            task.cancel()

    async def _service(self, sender: HueSender, generation: int) -> None:
        while True:
            await asyncio.sleep(0.1)
            with self._publication_lock:
                if self._sender is not sender or generation != self._generation:
                    return
            try:
                sender.service()
            except (OSError, ConnectionError, TimeoutError):
                self._sender_failed(sender, generation)
                return

    async def async_shutdown(self) -> None:
        with self._publication_lock:
            self._shutting_down = True
        self.deactivate()
        # Flush callbacks queued from render threads before taking task snapshots.
        await asyncio.sleep(0)
        self._stop_service()
        if self._service_tasks:
            await asyncio.gather(*tuple(self._service_tasks), return_exceptions=True)
        while self._lifecycle_tasks:
            await asyncio.gather(*tuple(self._lifecycle_tasks), return_exceptions=True)
            await asyncio.sleep(0)
        async with self._lifecycle_lock:
            await self._drain_retirements()
            await self._retry_failed_cleanup()

    def _control_request(
        self,
        settings: HueControlSettings,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        return self._https_request(
            settings.bridge, settings.username, method, endpoint, data
        )

    def _hue_register(self, settings: HueControlSettings) -> dict[str, object]:
        if not settings.username or not settings.clientkey:
            response, _ = self._control_request(
                settings,
                "POST",
                "api",
                {
                    "devicetype": f"LedFx#{settings.group_name}",
                    "generateclientkey": True,
                },
            )
            result = _object(_items(response)[0])
            if "success" not in result:
                raise ValueError("Press the Hue Bridge Link Button and retry")
            credentials = _object(result["success"])
            return {
                "username": _text(credentials.get("username")),
                "clientkey": _text(credentials.get("clientkey")),
            }
        response, _ = self._control_request(settings, "GET", f"api/{settings.username}")
        if isinstance(response, list) and any(
            "error" in _object(item) for item in _items(response)
        ):
            raise ValueError("Press the Hue Bridge Link Button and register again")
        return {}

    def _check_hue_bridge(self, settings: HueControlSettings) -> None:
        response, _ = self._control_request(settings, "GET", "api/config")
        if int(_text(_object(response).get("swversion"))) < 1948086000:
            raise ValueError("Update the Hue Bridge firmware using the Hue App")

    def _discover(self, settings: HueControlSettings) -> dict[str, object]:
        response, _ = self._control_request(
            settings, "GET", "/clip/v2/resource/entertainment_configuration"
        )
        groups = [_object(group) for group in _items(_object(response).get("data"))]
        group = next(
            (
                g
                for g in groups
                if str(
                    _object(g.get("metadata", {})).get("name", g.get("name", ""))
                ).lower()
                == settings.group_name.lower()
            ),
            None,
        )
        if group is None:
            raise ValueError(
                "Set up the requested Hue Entertainment zone in the Hue App"
            )
        identifier = _text(group.get("id"))
        response, _ = self._control_request(
            settings,
            "GET",
            f"/clip/v2/resource/entertainment_configuration/{identifier}",
        )
        channels = _items(
            _object(_items(_object(response).get("data"))[0]).get("channels")
        )
        lights: dict[str, list[float]] = {}
        ids: list[int] = []
        for item in channels:
            channel = _object(item)
            channel_id = channel.get("channel_id")
            if type(channel_id) is not int or not 0 <= channel_id <= 255:
                raise ValueError("Invalid Hue channel ID")
            ids.append(channel_id)
            position = _object(channel.get("position"))
            lights[str(channel_id)] = [
                float(cast(float, position[k])) for k in ("x", "y", "z")
            ]
        if not 1 <= len(ids) <= 256 or len(set(ids)) != len(ids):
            raise ValueError("Invalid Hue channel mapping")
        identity = settings.application_id
        if not identity:
            _, headers = self._control_request(settings, "GET", "/auth/v1")
            identity = _text(headers.get("hue-application-id"))
        return {
            "entertainment_id": identifier,
            "hue_application_id": identity,
            "channel_ids": tuple(ids),
            "pixel_count": len(ids),
            "pixel_lights": lights,
            "refresh_rate": 30,
            "group_id": str(group.get("id_v1", "")).rsplit("/", 1)[-1],
        }

    def _initialize_control(self, settings: HueControlSettings) -> dict[str, object]:
        credentials = self._hue_register(settings)
        if credentials:
            settings = replace(
                settings,
                username=_text(credentials.get("username")),
                clientkey=_text(credentials.get("clientkey")),
            )
        self._check_hue_bridge(settings)
        return credentials | self._discover(settings)

    async def async_initialize(self) -> None:
        # Capture before DNS/executor awaits: the registry already exposes this
        # device to API updates. Never read live bridge credentials in a worker.
        with self._publication_lock:
            owner = self.config
            stored = owner.as_dict()
            settings = HueControlSettings(
                bridge=owner.ip_address,
                group_name=owner.group_name,
                username=_text(stored["username"]) if stored.get("username") else None,
                clientkey=_text(stored["clientkey"])
                if stored.get("clientkey")
                else None,
                application_id=(
                    _text(stored["hue_application_id"])
                    if stored.get("hue_application_id")
                    else None
                ),
            )
        await super().async_initialize()
        result = await self._executor(lambda: self._initialize_control(settings))
        self.update_config(result, _expected_config=owner)
