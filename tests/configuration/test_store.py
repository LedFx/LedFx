import json
import os
from pathlib import Path

import pytest
import voluptuous as vol

from ledfx.configuration.migrations import CURRENT_SCHEMA_VERSION
from ledfx.configuration.store import (
    QUARANTINE_FILE_NAME,
    ConfigStore,
    backup_config_file,
)

SCHEMA = vol.Schema(
    {
        vol.Optional("port", default=8888): int,
        vol.Optional("devices", default=[]): list,
        vol.Optional("scenes", default={}): dict,
    },
    extra=vol.ALLOW_EXTRA,
)


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "config.json"
    path.write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )
    return path


def _backups(tmp_path: Path, reason: str) -> list[str]:
    return sorted(p.name for p in tmp_path.iterdir() if f"backup_{reason}_" in p.name)


def test_missing_file_creates_defaults(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.data["port"] == 8888
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["schema_version"] == CURRENT_SCHEMA_VERSION
    assert on_disk["configuration_version"] == "2.3.6"


def test_saved_file_keeps_legacy_version_marker_for_downgrades(tmp_path: Path) -> None:
    # Review Focus 3: pre-overhaul builds must see configuration_version 2.3.6
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    store.data["port"] = 2
    assert store.save_now()
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["configuration_version"] == "2.3.6"
    assert on_disk["port"] == 2


def test_ledfx_presets_are_never_saved(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    store.data["ledfx_presets"] = {"big": 1}
    store.save_now()
    assert "ledfx_presets" not in json.loads((tmp_path / "config.json").read_text())


def test_corrupt_json_enters_safe_mode_and_never_overwrites(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Review Focus 2
    path = _write(tmp_path, "{not json")
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.error is not None
    assert store.data["port"] == 8888
    assert _backups(tmp_path, "DECODE")
    store.data["port"] = 9999
    assert store.save_now() is False
    assert store.save_now() is False
    assert path.read_text() == "{not json"
    blocked = [r for r in caplog.records if "not saved" in r.getMessage()]
    assert len(blocked) == 1 and blocked[0].levelname == "ERROR"


def test_top_level_non_object_is_corrupt(tmp_path: Path) -> None:
    _write(tmp_path, "[1, 2]")
    assert ConfigStore.load(str(tmp_path), SCHEMA).error is not None


def test_legacy_file_is_migrated_backed_up_and_saved(tmp_path: Path) -> None:
    _write(tmp_path, {"configuration_version": "2.3.6", "port": 1234})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.error is None
    assert store.data["port"] == 1234
    assert _backups(tmp_path, "VERSION")
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["schema_version"] == CURRENT_SCHEMA_VERSION


def test_failed_migration_enters_safe_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, {"configuration_version": "1.0.0", "devices": "broken"})

    def boom(
        raw: dict[str, object], from_version: int | None = None
    ) -> dict[str, object]:
        raise RuntimeError("step failed")

    monkeypatch.setattr("ledfx.configuration.store.run_migrations", boom)
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.error is not None and "step failed" in store.error
    assert _backups(tmp_path, "VERSION")
    assert json.loads((tmp_path / "config.json").read_text())["devices"] == "broken"


def test_newer_schema_version_backs_up_and_loads(tmp_path: Path) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION + 5, "port": 7})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.error is None and store.data["port"] == 7
    assert _backups(tmp_path, "DOWNGRADE")


def test_invalid_top_level_key_is_quarantined_and_defaulted(tmp_path: Path) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.data["port"] == 8888
    lines = (tmp_path / QUARANTINE_FILE_NAME).read_text().splitlines()
    record = json.loads(lines[-1])
    assert record["path"] == "port" and record["value"] == "nope"
    assert record["errors"]


def test_quarantined_key_is_saved_as_default_so_it_is_not_quarantined_again(
    tmp_path: Path,
) -> None:
    # spec §7: the bad value falls back to its default *on disk* too; the
    # original lives only in the quarantine file.
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    ConfigStore.load(str(tmp_path), SCHEMA)
    assert json.loads((tmp_path / "config.json").read_text())["port"] == 8888
    quarantine_file = tmp_path / QUARANTINE_FILE_NAME
    first = quarantine_file.read_text()
    assert first.count("\n") == 1
    ConfigStore.load(str(tmp_path), SCHEMA)
    assert quarantine_file.read_text() == first  # no new record on the next boot


def test_backup_names_never_collide(tmp_path: Path) -> None:
    _write(tmp_path, {"port": 1})
    names = {backup_config_file(str(tmp_path), "IMPORT") for _ in range(3)}
    assert len(names) == 3


def test_backup_move_removes_original(tmp_path: Path) -> None:
    _write(tmp_path, {"port": 1})
    backup_config_file(str(tmp_path), "DELETE", move=True)
    assert not (tmp_path / "config.json").exists()


def test_save_and_backup_make_their_renames_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    synced_dirs: list[str] = []
    synced_files: list[int] = []
    monkeypatch.setattr("ledfx.configuration.store.fsync_directory", synced_dirs.append)
    real_fsync = os.fsync

    def fsync(fd: int) -> None:
        synced_files.append(os.fstat(fd).st_ino)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)

    assert store.save_now()
    assert synced_dirs == [str(tmp_path)]

    backup = backup_config_file(str(tmp_path), "IMPORT")
    assert backup is not None
    assert os.stat(backup).st_ino in synced_files
    assert synced_dirs == [str(tmp_path)] * 2


def test_failed_write_leaves_previous_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    store.data["port"] = 2

    def fail(src: str, dst: str) -> None:
        raise PermissionError("locked by antivirus")

    monkeypatch.setattr(os, "replace", fail)
    assert store.save_now() is False
    assert json.loads((tmp_path / "config.json").read_text())["port"] == 1
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permissions and a non-root user",
)
def test_unreadable_file_enters_safe_mode_without_crashing(tmp_path: Path) -> None:
    path = _write(tmp_path, {"port": 1})
    path.chmod(0)
    try:
        store = ConfigStore.load(str(tmp_path), SCHEMA)
    finally:
        path.chmod(0o644)
    assert store.error is not None and store.data["port"] == 8888


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_save_keeps_existing_file_mode(tmp_path: Path) -> None:
    path = _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    path.chmod(0o644)
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    store.data["port"] = 2
    assert store.save_now() is True
    assert path.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize(
    "raw",
    [
        {"configuration_version": "2.3.6", "port": 1234},
        {"schema_version": CURRENT_SCHEMA_VERSION + 5, "port": 1234},
    ],
)
def test_failed_safety_backup_blocks_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: dict[str, object]
) -> None:
    path = _write(tmp_path, raw)
    before = path.read_bytes()

    def no_backup(config_dir: str, reason: str, move: bool = False) -> None:
        return None

    monkeypatch.setattr("ledfx.configuration.store.backup_config_file", no_backup)
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    assert store.error is not None and "backed up" in store.error
    assert store.data["port"] == 1234
    assert path.read_bytes() == before
    assert store.save_now() is False
    assert path.read_bytes() == before


def test_unserialisable_value_fails_save_without_raising(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path), SCHEMA)
    store.data["bad"] = {1: 1, "a": 2}  # mixed keys break sort_keys -> TypeError
    assert store.save_now() is False
