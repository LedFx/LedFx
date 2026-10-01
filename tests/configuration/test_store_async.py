import asyncio
import json
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from ledfx.configuration import store as store_module
from ledfx.configuration.models import DeviceEntry, LedFxConfig
from ledfx.configuration.store import ConfigStore


async def _until(check: Callable[[], bool], timeout: float = 5.0) -> None:
    """Wait for a debounced save; slow CI runners outlast a fixed sleep."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not check():
        assert loop.time() < deadline, "timed out waiting for the save"
        await asyncio.sleep(0.01)


def _disk(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / "config.json").read_text())


async def test_request_save_debounces_to_one_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_module, "SAVE_DELAY_SECONDS", 0.05)
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    writes: list[int] = []
    real_write = store._write

    def counting_write(seq: int, text: str) -> None:
        writes.append(seq)
        real_write(seq, text)

    monkeypatch.setattr(store, "_write", counting_write)
    for port in range(10):
        store.data.port = port
        store.request_save()
    # The write runs in the executor: wait for it, then for any straggler.
    await _until(lambda: _disk(tmp_path)["port"] == 9)
    await asyncio.sleep(0.2)
    assert len(writes) == 1


async def test_flush_sync_writes_pending_change_before_exit(tmp_path: Path) -> None:
    # Review Focus 4: change then immediate stop must reach disk
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    store.data.port = 4242
    store.request_save()
    store.flush_sync()
    assert _disk(tmp_path)["port"] == 4242
    assert store._save_handle is None


async def test_flush_writes_pending_change(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    store.data.port = 77
    store.request_save()
    assert await store.flush() is True
    assert _disk(tmp_path)["port"] == 77
    assert store._save_handle is None


async def test_request_save_from_other_thread_is_marshalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_module, "SAVE_DELAY_SECONDS", 0.01)
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    store.data.port = 5
    write_threads: list[threading.Thread] = []
    real_write = store._write

    def recording_write(seq: int, text: str) -> None:
        write_threads.append(threading.current_thread())
        real_write(seq, text)

    monkeypatch.setattr(store, "_write", recording_write)
    thread = threading.Thread(target=store.request_save)
    thread.start()
    thread.join()
    await asyncio.sleep(0)
    assert store._save_handle is not None
    await _until(lambda: _disk(tmp_path)["port"] == 5)
    assert thread not in write_threads
    assert _disk(tmp_path)["port"] == 5


def test_request_save_with_loop_not_running_saves_now(tmp_path: Path) -> None:
    loop = asyncio.new_event_loop()
    try:
        store = ConfigStore.load(str(tmp_path))
        store.attach_loop(loop)
        store.data.port = 12
        store.request_save()
        assert _disk(tmp_path)["port"] == 12
    finally:
        loop.close()


async def test_stale_write_never_overwrites_newer(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    store.data.port = 1
    old = store._next_text()
    store.data.port = 2
    store._write(*store._next_text())
    store._write(*old)
    assert _disk(tmp_path)["port"] == 2


async def test_replace_clears_safe_mode_and_writes(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{bad")
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    assert store.error
    assert await store.replace(LedFxConfig(port=1)) is True
    assert store.error is None
    assert _disk(tmp_path)["port"] == 1


async def test_flush_returns_false_when_blocked(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{bad")
    store = ConfigStore.load(str(tmp_path))
    assert await store.flush() is False
    assert (tmp_path / "config.json").read_text() == "{bad"


async def test_replace_rolls_back_when_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.json").write_text("{bad")
    store = ConfigStore.load(str(tmp_path))
    before, error = store.data, store.error

    def failing_write(seq: int, text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "_write", failing_write)
    assert await store.replace(LedFxConfig(port=1)) is False
    assert store.data is before and store.error == error
    assert (tmp_path / "config.json").read_text() == "{bad"


async def test_serialise_failure_is_logged_not_raised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(store_module, "SAVE_DELAY_SECONDS", 0.01)
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    store.data.devices = [DeviceEntry(id="d", type="x", config={"bad": object()})]
    store.request_save()
    # The timer callback must log, not raise.
    await _until(
        lambda: any("Failed to save" in r.getMessage() for r in caplog.records)
    )
    await store.flush()
    messages = [r.getMessage() for r in caplog.records]
    assert sum("Failed to save config.json" in m for m in messages) == 2
    assert not any("Exception in callback" in m for m in messages)


async def test_mutate_requests_a_save(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    async with store.mutate() as cfg:
        cfg.port = 1234
    assert store._save_handle is not None
    store.flush_sync()
    assert _disk(tmp_path)["port"] == 1234


async def test_mutate_serialises_concurrent_changes(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    order: list[str] = []

    async def change(tag: str) -> None:
        async with store.mutate():
            order.append(f"{tag}-in")
            await asyncio.sleep(0.01)
            order.append(f"{tag}-out")

    await asyncio.gather(change("a"), change("b"), store.replace(store.data))
    assert order == ["a-in", "a-out", "b-in", "b-out"]
    store.flush_sync()
