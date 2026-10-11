"""Native Hue publication and bounded control-plane ownership."""

import asyncio
import threading
from collections.abc import AsyncIterator, Mapping
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from ledfx_senders import HueSender
from ledfx_senders.frames import Frame

from ledfx.core import LedFxCore
from ledfx.devices import Devices
from ledfx.devices.hue import HueDevice, HueRetirement, HueSettings
from ledfx.virtuals import Virtual

ZONE = "12345678-1234-1234-1234-123456789abc"


def config(**changes: object) -> HueDevice.Config:
    return HueDevice.Config.model_validate(
        {
            "name": "Hue",
            "ip_address": "127.0.0.1",
            "group_name": "Room",
            "username": "user",
            "clientkey": "11" * 16,
            "hue_application_id": "opaque-application",
            "entertainment_id": ZONE,
            "pixel_count": 2,
            "channel_ids": [7, 12],
            **changes,
        }
    )


def test_constructor_does_no_pairing_or_network() -> None:
    with (
        patch.object(HueDevice, "_hue_register") as register,
        patch.object(HueDevice, "_check_hue_bridge") as check,
    ):
        device = HueDevice(MagicMock(), config(hue_application_id=None))
        # A new device has no stored auth identity at all.
        device = HueDevice(
            MagicMock(),
            HueDevice.Config.model_validate(
                {"name": "new", "ip_address": "127.0.0.1", "group_name": "Room"}
            ),
        )
        assert register.call_count == 0
        assert check.call_count == 0
        assert not device.is_active()


class ControlledSender:
    def __init__(
        self, *, blocked: bool = False, failure: Exception | None = None
    ) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        if not blocked:
            self.release.set()
        self.failure = failure
        self.closed = False
        self.sent: list[Frame] = []
        self.services = 0

    def connect(self) -> None:
        self.entered.set()
        assert self.release.wait(2), "test did not release candidate"
        if self.failure:
            raise self.failure
        if self.closed:
            raise ConnectionError("closed")

    def close(self) -> None:
        self.closed = True
        self.release.set()

    def send(self, frame: Frame) -> None:
        if self.failure:
            raise self.failure
        self.sent.append(frame)

    def service(self) -> None:
        self.services += 1
        if self.failure:
            raise self.failure


async def idle(device: HueDevice) -> None:
    for _ in range(100):
        tasks = list(device._lifecycle_tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(0)
        if not device._lifecycle_tasks:
            return
    pytest.fail("owned lifecycle tasks did not drain")


@HueDevice.no_registration
class HueFixture(HueDevice):
    zone_actions: list[str]
    senders: list[ControlledSender]
    snapshots: list[HueSettings]


def _no_virtuals(device: HueDevice) -> list[Virtual]:
    return []


@pytest.fixture
async def hue_device(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[HueFixture]:
    device = HueFixture(
        MagicMock(
            loop=asyncio.get_running_loop(), thread_executor=None, virtuals=MagicMock()
        ),
        config(),
    )
    device._destination = "127.0.0.1"
    actions: list[str] = []
    senders: list[ControlledSender] = []
    settings: list[HueSettings] = []

    def request(
        method: str, endpoint: str, data: dict[str, object] | None = None
    ) -> tuple[object, Mapping[str, str]]:
        if data and "action" in data:
            actions.append(str(data["action"]))
        return {"data": list[object](), "errors": list[object]()}, {}

    def factory(snapshot: HueSettings) -> HueSender:
        settings.append(snapshot)
        return cast(HueSender, senders.pop(0))

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        return request(method, endpoint, data)

    monkeypatch.setattr(device, "_https_request", https)
    monkeypatch.setattr(device, "_sender_for_settings", factory)
    device.zone_actions = actions
    device.senders = senders
    device.snapshots = settings
    yield device
    await device.async_shutdown()


async def test_failed_candidate_is_never_published(hue_device: HueFixture) -> None:
    hue_device.senders.append(ControlledSender(failure=ConnectionError("rejected")))
    hue_device.activate()
    await idle(hue_device)
    assert hue_device._sender is None
    assert not hue_device.is_active()
    assert hue_device.zone_actions == ["start", "stop"]


async def test_old_rollback_precedes_successor_start(hue_device: HueFixture) -> None:
    first, second = ControlledSender(blocked=True), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    await asyncio.to_thread(first.entered.wait, 2)
    assert not hue_device.is_active()
    hue_device.deactivate()
    hue_device.activate()
    await idle(hue_device)
    assert first.closed
    assert hue_device.zone_actions == ["start", "stop", "start"]
    assert hue_device._sender is second
    assert hue_device.is_active()


async def test_deactivation_interrupts_executor_connect(hue_device: HueFixture) -> None:
    sender = ControlledSender(blocked=True)
    hue_device.senders.append(sender)
    hue_device.activate()
    assert await asyncio.to_thread(sender.entered.wait, 2)
    hue_device.deactivate()
    await idle(hue_device)
    assert sender.closed
    assert hue_device.zone_actions == ["start", "stop"]
    assert not hue_device.is_active()


async def test_cancelled_before_lock_does_not_stop_zone(hue_device: HueFixture) -> None:
    await hue_device._lifecycle_lock.acquire()
    hue_device.activate()
    await asyncio.sleep(0)
    task = next(iter(hue_device._lifecycle_tasks))
    task.cancel()
    hue_device.deactivate()
    hue_device._lifecycle_lock.release()
    await idle(hue_device)
    assert hue_device.zone_actions == []


async def test_config_change_uses_old_lease_and_new_channels(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = ControlledSender(blocked=True), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    assert await asyncio.to_thread(first.entered.wait, 2)
    monkeypatch.setattr(HueDevice, "_virtuals_objs", property(_no_virtuals))
    hue_device.update_config(
        {
            "entertainment_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "channel_ids": [12, 7],
        }
    )
    await idle(hue_device)
    assert first.closed
    assert hue_device.zone_actions == ["start", "stop", "start"]
    assert hue_device.snapshots[0].entertainment_id == ZONE
    assert hue_device.snapshots[1].channel_ids == (12, 7)
    assert hue_device._sender is second


async def test_failed_stop_blocks_successor_and_explicit_retry(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    await idle(hue_device)
    fail_stop = True

    def request(
        method: str, endpoint: str, data: dict[str, object] | None = None
    ) -> tuple[object, Mapping[str, str]]:
        assert data is not None
        hue_device.zone_actions.append(str(data["action"]))
        if data["action"] == "stop" and fail_stop:
            raise TimeoutError("bounded stop")
        return {"errors": list[object]()}, {}

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        return request(method, endpoint, data)

    monkeypatch.setattr(hue_device, "_https_request", https)
    hue_device.deactivate()
    hue_device.activate()
    await idle(hue_device)
    assert not hue_device.is_active()
    assert hue_device.zone_actions.count("start") == 1
    fail_stop = False
    hue_device.activate()
    await idle(hue_device)
    assert hue_device._sender is second
    assert hue_device.zone_actions[-2:] == ["stop", "start"]


async def test_idempotent_deactivate(hue_device: HueFixture) -> None:
    hue_device.senders.append(ControlledSender())
    hue_device.activate()
    await idle(hue_device)
    hue_device.deactivate()
    hue_device.deactivate()
    await idle(hue_device)
    assert hue_device.zone_actions == ["start", "stop"]


async def test_failed_zone_start_never_constructs_candidate(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def request(*args: object) -> tuple[object, Mapping[str, str]]:
        raise TimeoutError("bounded start")

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        return request(method, endpoint, data)

    monkeypatch.setattr(hue_device, "_https_request", https)
    hue_device.activate()
    await idle(hue_device)
    assert hue_device._sender is None
    assert hue_device.snapshots == []
    assert hue_device.zone_actions == []


async def test_array_mapping_and_single_flight_recovery(hue_device: HueFixture) -> None:
    first, second = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    await idle(hue_device)
    frame = np.zeros((2, 3), dtype=np.uint8)
    hue_device.flush(frame)
    assert first.sent[0] is frame
    assert hue_device.snapshots[0].channel_ids == (7, 12)
    assert hue_device.snapshots[0].psk_identity == b"opaque-application"
    first.failure = ConnectionError("lost")
    for _ in range(20):
        hue_device.flush(frame)
    await idle(hue_device)
    assert hue_device._sender is second
    assert hue_device.zone_actions == ["start", "stop", "start"]


@pytest.mark.parametrize("failure", [ConnectionError("connect"), TimeoutError("read")])
def test_https_request_is_bounded(failure: Exception) -> None:
    device = HueDevice(MagicMock(), config())
    with (
        patch("ledfx.devices.hue.requests.request", side_effect=failure) as request,
        pytest.raises(type(failure)),
    ):
        device._request_sync("GET", "/api/config")
    assert request.call_args.args == ("GET", "https://127.0.0.1/api/config")
    assert request.call_args.kwargs["timeout"] == (3.0, 5.0)
    assert request.call_args.kwargs["verify"] is False


async def test_default_device_shutdown_is_noop() -> None:
    from ledfx.devices.ddp import DDPDevice

    device = object.__new__(DDPDevice)
    device._active = False
    await device.async_shutdown()


async def test_core_drains_hue_before_global_cancellation(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    from ledfx.core import LedFxCore
    from ledfx.devices import Devices

    hue_device.senders.append(ControlledSender())
    hue_device.activate()
    await idle(hue_device)
    shutdown_finished = []

    async def shutdown() -> None:
        await hue_device.async_shutdown()
        shutdown_finished.append(True)

    registry = MagicMock()
    registry.values.return_value = [SimpleNamespace(async_shutdown=shutdown)]
    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock())
    core.devices = MagicMock(
        async_shutdown_devices=lambda: Devices.async_shutdown_devices(registry)
    )
    core.config_store = MagicMock()
    core.thread_executor = MagicMock()
    core.exit_code = 0

    async def remaining_task() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            assert shutdown_finished == [True]
            assert hue_device.zone_actions == ["start", "stop"]

    remaining = asyncio.create_task(remaining_task())
    await asyncio.sleep(0)

    def all_tasks() -> set[asyncio.Task[object]]:
        assert shutdown_finished == [True]
        assert hue_device.zone_actions == ["start", "stop"]
        assert not hue_device._lifecycle_tasks
        current = asyncio.current_task()
        assert current is not None
        return {current, remaining}

    monkeypatch.setattr("ledfx.core.asyncio.all_tasks", all_tasks)
    await core.async_stop(0)
    core.thread_executor.shutdown.assert_called_once()
    assert remaining.cancelled()


async def test_cancelled_candidate_closes_before_waiting_for_executor(
    hue_device: HueFixture,
) -> None:
    sender = ControlledSender(blocked=True)
    hue_device.senders.append(sender)
    hue_device.activate()
    assert await asyncio.to_thread(sender.entered.wait, 2)
    activation = next(iter(hue_device._lifecycle_tasks))
    activation.cancel()
    for _ in range(10):
        await asyncio.sleep(0.01)
        if sender.closed:
            break
    assert sender.closed, (
        "native connect must be interrupted before draining its future"
    )
    await idle(hue_device)
    assert hue_device.zone_actions == ["start", "stop"]
    assert hue_device._sender is None


async def test_stop_uses_original_endpoint_and_credentials(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second])
    calls = []

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        assert data is not None
        calls.append((bridge, username, endpoint, data["action"]))
        return {"errors": list[object]()}, {}

    monkeypatch.setattr(hue_device, "_https_request", https)
    monkeypatch.setattr(HueDevice, "_virtuals_objs", property(_no_virtuals))
    hue_device.activate()
    await idle(hue_device)
    hue_device.update_config(
        {
            "ip_address": "127.0.0.2",
            "username": "new-user",
            "entertainment_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        }
    )
    await idle(hue_device)
    assert calls[1] == (
        "127.0.0.1",
        "user",
        f"/clip/v2/resource/entertainment_configuration/{ZONE}",
        "stop",
    )
    assert calls[2][:2] == ("127.0.0.2", "new-user")


async def test_initialization_moves_pairing_and_discovery_off_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop_thread = threading.get_ident()
    calls = []
    device = HueDevice(
        MagicMock(
            loop=asyncio.get_running_loop(), thread_executor=None, virtuals=MagicMock()
        ),
        HueDevice.Config.model_validate(
            {"name": "new", "ip_address": "127.0.0.1", "group_name": "Room"}
        ),
    )
    monkeypatch.setattr(HueDevice, "_virtuals_objs", property(_no_virtuals))

    def request(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        assert threading.get_ident() != loop_thread
        calls.append((method, endpoint))
        if method == "POST":
            return [{"success": {"username": "paired", "clientkey": "11" * 16}}], {}
        if endpoint == "api/config":
            return {"swversion": "1948086000"}, {}
        if endpoint == "/auth/v1":
            return dict[str, object](), {"hue-application-id": "opaque-discovered"}
        if endpoint.endswith(ZONE):
            return {
                "data": [
                    {
                        "channels": [
                            {"channel_id": 12, "position": {"x": 1, "y": 2, "z": 3}},
                            {"channel_id": 7, "position": {"x": 4, "y": 5, "z": 6}},
                        ]
                    }
                ]
            }, {}
        return {
            "data": [{"id": ZONE, "id_v1": "/groups/1", "metadata": {"name": "Room"}}]
        }, {}

    monkeypatch.setattr(device, "_https_request", request)
    assert calls == []
    await device.async_initialize()
    assert device.config.as_dict()["username"] == "paired"
    assert device.config.as_dict()["channel_ids"] == (12, 7)
    assert device.config.as_dict()["hue_application_id"] == "opaque-discovered"
    assert device.config.as_dict()["pixel_count"] == 2
    assert not device.is_active()
    await device.async_shutdown()


async def test_idle_service_and_recovery_are_bounded(hue_device: HueFixture) -> None:
    first = ControlledSender()
    failures = [ControlledSender(failure=TimeoutError("bounded")) for _ in range(3)]
    hue_device.senders.extend([first, *failures])
    hue_device.activate()
    await idle(hue_device)
    await asyncio.sleep(0.12)
    assert first.services >= 1
    first.failure = ConnectionError("idle transport loss")
    await asyncio.sleep(0.12)
    await idle(hue_device)
    assert len(hue_device.snapshots) == 4
    assert hue_device._sender is None
    assert hue_device._recovery_generation is None
    await asyncio.sleep(0.3)
    assert len(hue_device.snapshots) == 4


async def test_stale_failed_snapshot_cannot_invalidate_successor(
    hue_device: HueFixture,
) -> None:
    first, second = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    await idle(hue_device)
    generation = hue_device._generation
    hue_device.deactivate()
    hue_device.activate()
    await idle(hue_device)
    hue_device._sender_failed(cast(HueSender, first), generation)
    await idle(hue_device)
    assert hue_device._sender is second
    assert hue_device.zone_actions == ["start", "stop", "start"]


async def test_deactivate_during_address_resolution_never_starts_zone(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def resolve(*args: object, **kwargs: object) -> None:
        entered.set()
        await release.wait()
        hue_device._destination = "127.0.0.1"

    hue_device._destination = None
    hue_device.senders.append(ControlledSender())
    monkeypatch.setattr(hue_device, "resolve_address", resolve)
    hue_device.activate()
    await entered.wait()
    hue_device.deactivate()
    release.set()
    await idle(hue_device)
    assert hue_device.zone_actions == []
    assert hue_device._sender is None


async def test_cancelled_start_drains_and_rolls_back_before_successor(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = threading.Event(), threading.Event()
    calls: list[str] = []

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        assert data is not None
        action = str(data["action"])
        calls.append(action)
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
        return {"errors": list[object]()}, {}

    monkeypatch.setattr(hue_device, "_https_request", https)
    hue_device.senders.append(ControlledSender())
    hue_device.activate()
    assert await asyncio.to_thread(entered.wait, 2)
    activation = next(iter(hue_device._lifecycle_tasks))
    activation.cancel()
    hue_device.deactivate()
    hue_device.activate()
    release.set()
    await idle(hue_device)
    assert calls == ["start", "stop", "start"]
    assert hue_device._sender is not None


async def test_pairing_failure_destroys_unsaved_registry_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ledfx.devices import Devices

    core = MagicMock()
    core.loop = asyncio.get_running_loop()
    core.thread_executor = None
    registry = MagicMock()
    registry._ledfx = core
    registry.get_class.return_value = HueDevice
    core.devices = registry
    registry.values.return_value = list[HueDevice]()
    device = HueDevice(
        core,
        HueDevice.Config.model_validate(
            {"name": "new", "ip_address": "127.0.0.1", "group_name": "Room"}
        ),
    )
    device.__dict__["_id"] = "new"
    registry.create.return_value = device

    def reject(*args: object) -> tuple[object, Mapping[str, str]]:
        return [{"error": {"description": "link button"}}], {}

    monkeypatch.setattr(device, "_https_request", reject)
    with pytest.raises(ValueError, match="Link Button"):
        await Devices.add_new_device(
            registry,
            "hue",
            {"name": "new", "ip_address": "127.0.0.1", "group_name": "Room"},
        )
    registry.destroy.assert_called_once_with(device.id)
    core.config.devices.append.assert_not_called()


async def test_repeated_cancellation_cannot_abandon_zone_start(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = threading.Event(), threading.Event()
    calls: list[str] = []

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        assert data is not None
        calls.append(str(data["action"]))
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
        return {"errors": list[object]()}, {}

    monkeypatch.setattr(hue_device, "_https_request", https)
    hue_device.activate()
    assert await asyncio.to_thread(entered.wait, 2)
    activation = next(iter(hue_device._lifecycle_tasks))
    activation.cancel()
    await asyncio.sleep(0)
    activation.cancel()
    await asyncio.sleep(0.02)
    assert not activation.done(), (
        "owned zone acquisition must drain despite repeated cancellation"
    )
    release.set()
    await idle(hue_device)
    assert calls == ["start", "stop"]


async def test_old_dns_result_does_not_replace_new_generation(
    hue_device: HueFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def resolve(*args: object) -> str:
        entered.set()
        await release.wait()
        return "127.0.0.3"

    monkeypatch.setattr("ledfx.devices.hue.resolve_destination", resolve)
    task = asyncio.create_task(hue_device.resolve_address())
    await entered.wait()
    hue_device.deactivate()
    hue_device._destination = "127.0.0.2"
    release.set()
    await task
    assert hue_device._destination == "127.0.0.2"


def test_credentials_and_zone_metadata_persist_without_frontend_fields() -> None:
    model = config()
    properties = HueDevice.Config.model_json_schema()["properties"]
    for name in (
        "username",
        "clientkey",
        "hue_application_id",
        "entertainment_id",
        "channel_ids",
        "pixel_lights",
        "group_id",
    ):
        assert name not in properties
    stored = model.as_dict()
    assert stored["username"] == "user"
    assert stored["clientkey"] == "11" * 16
    assert stored["hue_application_id"] == "opaque-application"
    assert stored["channel_ids"] == [7, 12]


def test_https_errors_do_not_expose_credentials() -> None:
    import requests

    device = HueDevice(MagicMock(), config())
    with (
        patch(
            "ledfx.devices.hue.requests.request",
            side_effect=requests.ConnectionError("https://127.0.0.1/api/secret-user"),
        ),
        pytest.raises(ConnectionError) as error,
    ):
        device._request_sync("GET", "api/user")
    assert "secret-user" not in str(error.value)


async def test_superseded_recovery_does_not_suppress_successor_recovery(
    hue_device: HueFixture,
) -> None:
    first, second, third = ControlledSender(), ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second, third])
    hue_device.activate()
    await idle(hue_device)
    first.failure = ConnectionError("old failure")
    hue_device.flush(np.zeros((2, 3)))
    hue_device.deactivate()
    hue_device.activate()
    await asyncio.sleep(0)
    for _ in range(100):
        if hue_device._sender is second:
            break
        await asyncio.sleep(0.005)
    assert hue_device._sender is second
    second.failure = ConnectionError("new failure")
    hue_device.flush(np.zeros((2, 3)))
    await idle(hue_device)
    assert hue_device._sender is third


@pytest.mark.parametrize("invalidation", ["deactivate", "flush_failure"])
async def test_retirement_is_ordered_with_cross_thread_reactivation(
    hue_device: HueFixture,
    monkeypatch: pytest.MonkeyPatch,
    invalidation: str,
) -> None:
    first, second = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, second])
    hue_device.activate()
    await idle(hue_device)
    entered, release = threading.Event(), threading.Event()
    errors: list[BaseException] = []
    original = hue_device._queue_retirement

    def delayed_queue(retirement: HueRetirement) -> None:
        entered.set()
        assert release.wait(2)
        original(retirement)

    def invalidate() -> None:
        try:
            if invalidation == "deactivate":
                hue_device.deactivate()
            else:
                first.failure = ConnectionError("render failure")
                hue_device.flush(np.zeros((2, 3)))
        except Exception as error:  # noqa: BLE001 - surface worker failures in the test
            errors.append(error)

    monkeypatch.setattr(hue_device, "_queue_retirement", delayed_queue)
    worker = threading.Thread(target=invalidate)
    worker.start()
    assert await asyncio.to_thread(entered.wait, 2)
    try:
        hue_device.activate()
        await idle(hue_device)
        assert hue_device._sender is second
    finally:
        release.set()
        await asyncio.to_thread(worker.join, 2)
        monkeypatch.setattr(hue_device, "_queue_retirement", original)
    assert not worker.is_alive()
    assert errors == []
    await idle(hue_device)
    assert hue_device.zone_actions == ["start", "stop", "start"]
    assert first.closed and not second.closed
    assert hue_device.is_active()
    await asyncio.sleep(0.12)
    assert second.services >= 1, "old retirement must not cancel successor service"


async def test_shutdown_drains_retirement_before_delayed_dispatch(
    hue_device: HueFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = ControlledSender()
    hue_device.senders.append(sender)
    hue_device.activate()
    await idle(hue_device)
    entered, release = threading.Event(), threading.Event()
    original = hue_device._queue_retirement

    def delayed_queue(retirement: HueRetirement) -> None:
        if threading.current_thread() is not threading.main_thread():
            entered.set()
            assert release.wait(2)
        original(retirement)

    monkeypatch.setattr(hue_device, "_queue_retirement", delayed_queue)
    worker = threading.Thread(target=hue_device.deactivate)
    worker.start()
    assert await asyncio.to_thread(entered.wait, 2)
    try:
        await asyncio.wait_for(hue_device.async_shutdown(), 1)
        assert hue_device.zone_actions == ["start", "stop"]
        assert sender.closed
        assert not hue_device._pending_retirements
        assert not hue_device._lifecycle_tasks
    finally:
        release.set()
        await asyncio.to_thread(worker.join, 2)
        monkeypatch.setattr(hue_device, "_queue_retirement", original)
    await asyncio.sleep(0)
    assert not hue_device._lifecycle_tasks
    assert hue_device.zone_actions == ["start", "stop"]


@pytest.mark.parametrize("failure", ["http", "event"])
async def test_core_drains_owned_hue_work_after_earlier_shutdown_failure(
    hue_device: HueFixture,
    failure: str,
) -> None:
    sender = ControlledSender()
    hue_device.senders.append(sender)
    hue_device.activate()
    await idle(hue_device)
    order: list[str] = []
    registry = MagicMock()
    registry.values.return_value = [hue_device]

    async def drain_devices() -> None:
        await Devices.async_shutdown_devices(registry)
        order.append("devices")

    def flush_config() -> None:
        assert order == ["devices"]
        order.append("config")

    def stop_executor() -> None:
        assert hue_device.zone_actions == ["start", "stop"]
        assert sender.closed
        assert not hue_device._lifecycle_tasks
        assert not hue_device._pending_retirements
        assert all(task.done() for task in hue_device._service_tasks)
        assert order == ["devices", "config"]
        order.append("executor")

    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock())
    core.devices = MagicMock(
        async_shutdown_devices=AsyncMock(side_effect=drain_devices)
    )
    core.config_store = MagicMock(flush_sync=MagicMock(side_effect=flush_config))
    core.thread_executor = MagicMock(shutdown=MagicMock(side_effect=stop_executor))
    core.exit_code = None
    if failure == "http":
        # The real registry shutdown listener deactivates outputs synchronously,
        # queuing Hue work that the awaited hook must drain after HTTP fails.
        def shutdown_event(event: object) -> None:
            hue_device.deactivate()

        core.events.fire_event.side_effect = shutdown_event
        core.http.stop.side_effect = RuntimeError("HTTP shutdown failure")
    else:
        core.events.fire_event.side_effect = RuntimeError("shutdown event failure")

    await core.async_stop(4)
    core.devices.async_shutdown_devices.assert_awaited_once_with()
    core.config_store.flush_sync.assert_called_once_with()
    core.thread_executor.shutdown.assert_called_once_with()
    core.loop.stop.assert_called_once_with()
    assert core.exit_code == 1
    assert order == ["devices", "config", "executor"]
    assert not hue_device.is_active()


def owned_virtual(device: HueFixture, monkeypatch: pytest.MonkeyPatch) -> Virtual:
    from ledfx.virtuals import Virtuals
    from tests.test_utilities.fake_ledfx import fake_ledfx
    from tests.test_utilities.virtuals_core import add_virtual

    core = device._ledfx
    stored = fake_ledfx()
    core.config = stored.config
    core.config_store = stored.config_store
    device.__dict__["_id"] = "hue"
    core.devices.values.return_value = [device]

    def lookup(key: str) -> HueDevice | None:
        return device if key == "hue" else None

    core.devices.get.side_effect = lookup
    monkeypatch.setattr(Virtuals, "_instance", None)
    core.virtuals = Virtuals(core)
    virtual = add_virtual(core, "owner", "Owner", [["hue", 0, 1, False]])
    virtual._active = True
    virtual.activate_segments(virtual.segments)
    return virtual


@pytest.mark.parametrize("remove", [False, True])
async def test_last_virtual_cancels_pending_connect(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch, remove: bool
) -> None:
    from ledfx.configuration.fields import VirtualIdStr

    sender = ControlledSender(blocked=True)
    hue_device.senders.append(sender)
    virtual = owned_virtual(hue_device, monkeypatch)
    assert await asyncio.to_thread(sender.entered.wait, 1)
    assert not hue_device.is_active()
    if remove:
        hue_device._ledfx.virtuals.remove(VirtualIdStr("owner"))
    else:
        virtual.deactivate()
    try:
        assert not hue_device._requested
    finally:
        # Do not let an expected RED leave a blocked worker behind.
        sender.release.set()
    await idle(hue_device)
    assert sender.closed
    assert hue_device.zone_actions == ["start", "stop"]
    assert hue_device._sender is None
    assert not hue_device._segments


async def test_last_virtual_cancels_delayed_recovery(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    sender = ControlledSender()
    hue_device.senders.extend([sender, ControlledSender()])
    virtual = owned_virtual(hue_device, monkeypatch)
    await idle(hue_device)
    delayed = asyncio.Event()
    release = asyncio.Event()
    original_sleep = asyncio.sleep

    async def sleep(delay: float) -> None:
        if delay in (0.25, 0.5, 1.0):
            delayed.set()
            await release.wait()
        else:
            await original_sleep(delay)

    monkeypatch.setattr("ledfx.devices.hue.asyncio.sleep", sleep)
    sender.failure = ConnectionError("lost transport")
    hue_device.flush(np.zeros((2, 3)))
    await asyncio.wait_for(delayed.wait(), 1)
    assert not hue_device.is_active()
    virtual.deactivate()
    try:
        assert not hue_device._requested
    finally:
        release.set()
    await idle(hue_device)
    assert sender.closed
    assert hue_device.zone_actions == ["start", "stop"]
    assert len(hue_device.snapshots) == 1
    assert hue_device._sender is None


async def test_activation_keeps_caller_generation_across_delayed_dispatch(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, unexpected = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, unexpected])
    paused, release = threading.Event(), threading.Event()
    original = hue_device._schedule_activation

    def dispatch(generation: int) -> None:
        if threading.current_thread() is not threading.main_thread():
            paused.set()
            assert release.wait(2)
        original(generation)

    monkeypatch.setattr(hue_device, "_schedule_activation", dispatch)
    caller = asyncio.create_task(asyncio.to_thread(hue_device.activate))
    assert await asyncio.to_thread(paused.wait, 1)
    hue_device.activate()
    await idle(hue_device)
    assert hue_device._sender is first
    release.set()
    await caller
    await idle(hue_device)
    assert hue_device._sender is first
    assert len(hue_device.snapshots) == 1
    assert hue_device.zone_actions == ["start"]
    await hue_device.async_shutdown()
    assert first.closed
    assert hue_device.zone_actions == ["start", "stop"]


async def test_duplicate_generation_dispatch_cannot_replace_published_sender(
    hue_device: HueFixture,
) -> None:
    first, unexpected = ControlledSender(), ControlledSender()
    hue_device.senders.extend([first, unexpected])
    hue_device.activate()
    await idle(hue_device)
    await hue_device._activate_generation(hue_device._generation)
    assert hue_device._sender is first
    assert len(hue_device.snapshots) == 1
    assert hue_device.zone_actions == ["start"]


@pytest.mark.parametrize("stage", ["pairing", "discovery"])
async def test_initialization_does_not_publish_replaced_bridge_results(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    from ledfx.api.device import DeviceEndpoint
    from tests.test_utilities.fake_ledfx import fake_ledfx

    core = fake_ledfx()
    core.loop = asyncio.get_running_loop()
    core.thread_executor = None
    device = HueDevice(
        core,
        config(username=None, clientkey=None, hue_application_id=None),
    )
    device.__dict__["_id"] = "hue"
    core.devices.get.return_value = device
    monkeypatch.setattr(HueDevice, "_virtuals_objs", property(_no_virtuals))
    entered, release = threading.Event(), threading.Event()
    calls: list[tuple[str, str | None, str]] = []

    def https(
        bridge: str,
        username: str | None,
        method: str,
        endpoint: str,
        data: dict[str, object] | None = None,
    ) -> tuple[object, Mapping[str, str]]:
        calls.append((bridge, username, endpoint))
        if (stage == "pairing" and method == "POST") or (
            stage == "discovery"
            and endpoint == "/clip/v2/resource/entertainment_configuration"
        ):
            entered.set()
            assert release.wait(2)
        if method == "POST":
            return [{"success": {"username": "old-user", "clientkey": "22" * 16}}], {}
        if endpoint == "api/config":
            return {"swversion": "1948086000"}, {}
        if endpoint == "/auth/v1":
            return dict[str, object](), {"hue-application-id": "old-identity"}
        if endpoint.endswith(ZONE):
            return {
                "data": [
                    {
                        "channels": [
                            {"channel_id": 99, "position": {"x": 0, "y": 0, "z": 0}}
                        ]
                    }
                ]
            }, {}
        return {"data": [{"id": ZONE, "metadata": {"name": "Room"}}]}, {}

    monkeypatch.setattr(device, "_https_request", https)
    initialization = asyncio.create_task(device.async_initialize())
    assert await asyncio.to_thread(entered.wait, 1)
    replacement = config(
        ip_address="127.0.0.2",
        group_name="Replacement",
        username="new-user",
        clientkey="33" * 16,
        hue_application_id="new-identity",
        channel_ids=[4, 5],
        entertainment_id="87654321-4321-4321-4321-cba987654321",
    ).as_dict()
    request = MagicMock(json=AsyncMock(return_value={"config": replacement}))
    response = await DeviceEndpoint(core).put("hue", request)
    assert response.status == 200
    release.set()
    await initialization
    stored = device.config.as_dict()
    for key, value in replacement.items():
        assert stored[key] == value, key
    assert all(bridge == "127.0.0.1" for bridge, _, _ in calls)
    assert not device.is_active()
    await device.async_shutdown()
