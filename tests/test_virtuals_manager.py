"""The Virtuals manager: CRUD, safe mode and mutators that never await."""

import asyncio
import inspect
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Scene, Segment, VirtualConfig
from ledfx.errors import Invalid, NotFound, SafeMode
from ledfx.events import GlobalPauseEvent, VirtualConfigUpdateEvent
from ledfx.virtuals import Virtuals
from tests.test_utilities.virtuals_core import (
    add_virtual,
    enter_safe_mode,
    running_core,
)
from tests.v1_golden.harness import build_app

BIRD = VirtualIdStr("dj bird")

# Every manager method that changes state. None may be a coroutine: the
# change and its save must happen with no await in between (Review Focus 4).
MUTATORS: tuple[str, ...] = ("add", "update", "remove", "set_paused")


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


def _entry_ids(ledfx: MagicMock) -> list[str]:
    return [entry.id for entry in ledfx.config.virtuals]


@pytest.mark.parametrize("name", MUTATORS)
def test_mutators_are_plain_functions(name: str) -> None:
    assert not inspect.iscoroutinefunction(getattr(Virtuals, name))


def test_get_or_raise(ledfx: MagicMock) -> None:
    assert ledfx.virtuals.get_or_raise(BIRD).id == "dj bird"
    with pytest.raises(NotFound, match="Virtual 'nope' not found"):
        ledfx.virtuals.get_or_raise(VirtualIdStr("nope"))


def test_add_stores_saves_and_fires(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.add(VirtualConfig(name="Küche"))
    assert virtual.id == "k-che"
    assert ledfx.virtuals.add(VirtualConfig(name="Küche")).id == "k-che-1"
    assert _entry_ids(ledfx)[-2:] == ["k-che", "k-che-1"]
    assert ledfx.config.virtuals[-2].config is virtual.config
    ledfx.config_store.request_save.assert_called()
    event = ledfx.events.fire_event.call_args.args[0]
    assert isinstance(event, VirtualConfigUpdateEvent)
    assert event.virtual_id == "k-che-1"


def test_update_config_segments_and_active(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.update(
        BIRD,
        config=VirtualConfig(name="Bird", max_brightness=0.5),
        segments=[Segment("strip", 0, 24, False)],
        active=False,
    )
    assert virtual.config.max_brightness == 0.5
    assert virtual.name == "Bird"
    entry = virtual.entry
    assert entry is not None
    assert entry.config is virtual.config
    assert entry.segments == [["strip", 0, 24, False]]
    assert entry.active is False
    ledfx.config_store.request_save.assert_called_once()


def test_update_refuses_bad_segments_and_changes_nothing(ledfx: MagicMock) -> None:
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.update(BIRD, segments=[Segment("nope", 0, 9, False)])
    assert caught.value.loc == ("body", "segments")
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert virtual.segments == [["strip", 0, 49, False]]
    ledfx.config_store.request_save.assert_not_called()


def test_update_active_without_segments_is_invalid(ledfx: MagicMock) -> None:
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.update(VirtualIdStr("empty"), active=True)
    assert caught.value.loc == ("body", "active")
    ledfx.config_store.request_save.assert_not_called()


def test_remove_drops_entry_and_scene_references(ledfx: MagicMock) -> None:
    ledfx.config.scenes["s"] = Scene.model_validate(
        {"name": "S", "virtuals": {"dj bird": {"type": "singleColor", "config": {}}}}
    )
    ledfx.virtuals.remove(BIRD)
    assert ledfx.virtuals.get(BIRD) is None
    assert "dj bird" not in _entry_ids(ledfx)
    assert "dj bird" not in ledfx.config.scenes["s"].virtuals
    ledfx.config_store.request_save.assert_called_once()


def test_remove_device_virtual_removes_its_device(ledfx: MagicMock) -> None:
    ledfx.virtuals.remove(VirtualIdStr("matrix"))
    assert ledfx.devices.get("matrix") is None
    assert "matrix" not in _entry_ids(ledfx)


def test_set_paused_is_runtime_only(ledfx: MagicMock) -> None:
    enter_safe_mode(ledfx)  # allowed: nothing is saved
    assert ledfx.virtuals.set_paused(True) is True
    assert ledfx.virtuals.paused is True
    assert all(v._paused for v in ledfx.virtuals.values())
    event = ledfx.events.fire_event.call_args.args[0]
    assert isinstance(event, GlobalPauseEvent)
    ledfx.config_store.request_save.assert_not_called()


# In safe mode a change raises SafeMode and changes nothing.
CRUD_CHANGES: dict[str, Callable[[Virtuals], object]] = {
    "add": lambda v: v.add(VirtualConfig(name="New")),
    "update-config": lambda v: v.update(BIRD, config=VirtualConfig(name="Renamed")),
    "update-segments": lambda v: v.update(
        BIRD, segments=[Segment("strip", 0, 9, False)]
    ),
    "update-active": lambda v: v.update(BIRD, active=False),
    "remove": lambda v: v.remove(BIRD),
}


@pytest.mark.parametrize("call", list(CRUD_CHANGES.values()), ids=list(CRUD_CHANGES))
def test_safe_mode_refuses_and_changes_nothing(
    ledfx: MagicMock, call: Callable[[Virtuals], object]
) -> None:
    enter_safe_mode(ledfx)
    before = ledfx.config.model_dump()
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    ids = list(ledfx.virtuals._virtuals)
    with pytest.raises(SafeMode):
        call(ledfx.virtuals)
    assert ledfx.config.model_dump() == before
    assert list(ledfx.virtuals._virtuals) == ids
    assert virtual.name == "dj bird"
    assert virtual.segments == [["strip", 0, 49, False]]
    ledfx.config_store.request_save.assert_not_called()


async def test_concurrent_v1_update_and_delete_leave_no_orphan(
    ledfx: MagicMock,
) -> None:
    """An update racing a delete through the v1 handlers
    ends with the virtual gone from both the manager and the config."""
    app = build_app(ledfx, (VirtualsEndpoint, VirtualEndpoint))
    async with TestClient(TestServer(app)) as client:
        for n in range(20):
            virtual_id = f"race-{n}"
            add_virtual(ledfx, virtual_id, virtual_id, [["strip", 0, 9, False]])
            update, delete = await asyncio.gather(
                client.post(
                    "/api/virtuals",
                    json={"id": virtual_id, "config": {"max_brightness": 0.5}},
                ),
                client.delete(f"/api/virtuals/{virtual_id}"),
            )
            assert update.status == 200
            assert delete.status == 200
            assert ledfx.virtuals.get(virtual_id) is None
            assert virtual_id not in _entry_ids(ledfx)
