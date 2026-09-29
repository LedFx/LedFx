"""POST/DELETE /api/config against a real ConfigStore on disk."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web

from ledfx.api.config import ConfigEndpoint
from ledfx.config import CORE_CONFIG_SCHEMA
from ledfx.configuration.migrations import CURRENT_SCHEMA_VERSION
from ledfx.configuration.store import ConfigStore

LEGACY = os.path.join(os.path.dirname(__file__), "legacy", "v2_3_5_equalizer.json")


def _disk(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / "config.json").read_text())


def _backups(tmp_path: Path, reason: str) -> list[Path]:
    return sorted(tmp_path.glob(f"config_backup_{reason}_*.json"))


def _setup(tmp_path: Path) -> tuple[ConfigEndpoint, ConfigStore, MagicMock]:
    store = ConfigStore.load(str(tmp_path), CORE_CONFIG_SCHEMA)
    store.data["port"] = 1234  # marks the pre-request config
    assert store.save_now()
    core = MagicMock()
    core.config_store = store
    return ConfigEndpoint(core), store, core


def _legacy_body() -> dict[str, object]:
    with open(LEGACY, encoding="utf-8") as file:
        return json.load(file)


async def _call(endpoint: ConfigEndpoint, method: str) -> web.Response:
    if method == "delete":
        return await endpoint.delete()
    request = MagicMock()
    request.json = AsyncMock(return_value=_legacy_body())
    return await endpoint.post(request)


async def test_delete_backs_up_writes_defaults_and_leaves_safe_mode(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.json").write_text("{bad")
    store = ConfigStore.load(str(tmp_path), CORE_CONFIG_SCHEMA)
    assert store.error
    core = MagicMock()
    core.config_store = store

    response = await ConfigEndpoint(core).delete()

    assert response.status == 200
    backups = _backups(tmp_path, "DELETE")
    assert len(backups) == 1 and backups[0].read_text() == "{bad"
    data = _disk(tmp_path)
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert data["port"] == 8888
    assert store.error is None
    core.loop.call_soon_threadsafe.assert_called_once_with(core.stop, 4)


async def test_delete_without_config_file_goes_ahead(tmp_path: Path) -> None:
    endpoint, _store, _core = _setup(tmp_path)
    (tmp_path / "config.json").unlink()
    response = await endpoint.delete()
    assert response.status == 200
    assert _disk(tmp_path)["port"] == 8888
    assert not _backups(tmp_path, "DELETE")


async def test_post_migrates_legacy_import_backs_up_and_writes(
    tmp_path: Path,
) -> None:
    endpoint, store, core = _setup(tmp_path)

    response = await _call(endpoint, "post")

    assert response.status == 200
    backups = _backups(tmp_path, "IMPORT")
    assert len(backups) == 1 and json.loads(backups[0].read_text())["port"] == 1234
    data = _disk(tmp_path)
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    virtuals = data["virtuals"]
    assert isinstance(virtuals, list)
    # legacy_to_v1 inverts equalizer2d flip_vertical for 2.3.5 files
    assert virtuals[0]["effect"]["config"]["flip_vertical"] is True
    assert store.data["virtuals"] == virtuals
    core.loop.call_soon_threadsafe.assert_called_once_with(core.stop, 4)


@pytest.mark.parametrize("method", ["delete", "post"])
async def test_aborts_when_backup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    endpoint, store, core = _setup(tmp_path)

    def no_backup(reason: str) -> None:
        return None

    monkeypatch.setattr(store, "backup", no_backup)

    response = await _call(endpoint, method)

    assert response.status == 500
    assert _disk(tmp_path)["port"] == 1234
    assert store.data["port"] == 1234
    core.loop.call_soon_threadsafe.assert_not_called()


@pytest.mark.parametrize("method", ["delete", "post"])
async def test_aborts_and_keeps_config_when_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    endpoint, store, core = _setup(tmp_path)

    def failing_write(seq: int, text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "_write", failing_write)

    response = await _call(endpoint, method)

    assert response.status == 500
    assert response.text is not None and "success" not in response.text
    assert _disk(tmp_path)["port"] == 1234
    assert store.data["port"] == 1234  # replace() rolled back
    assert store.error is None
    core.loop.call_soon_threadsafe.assert_not_called()
