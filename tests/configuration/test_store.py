import json
import logging
import os
import tempfile
from pathlib import Path

import pytest

from ledfx.configuration.migrations import CURRENT_SCHEMA_VERSION
from ledfx.configuration.models import DeviceEntry
from ledfx.configuration.store import (
    QUARANTINE_FILE_NAME,
    ConfigStore,
    backup_config_file,
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
    store = ConfigStore.load(str(tmp_path))
    assert store.data.port == 8888
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["schema_version"] == CURRENT_SCHEMA_VERSION
    assert on_disk["configuration_version"] == "2.3.6"


def test_saved_file_keeps_legacy_version_marker_for_downgrades(tmp_path: Path) -> None:
    # Review Focus 3: pre-overhaul builds must see configuration_version 2.3.6
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    store = ConfigStore.load(str(tmp_path))
    store.data.port = 2
    assert store.save_now()
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["configuration_version"] == "2.3.6"
    assert on_disk["port"] == 2


def test_corrupt_json_enters_safe_mode_and_never_overwrites(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Review Focus 2
    path = _write(tmp_path, "{not json")
    store = ConfigStore.load(str(tmp_path))
    assert store.error is not None
    assert store.data.port == 8888
    assert _backups(tmp_path, "DECODE")
    store.data.port = 9999
    assert store.save_now() is False
    assert store.save_now() is False
    assert path.read_text() == "{not json"
    blocked = [r for r in caplog.records if "not saved" in r.getMessage()]
    assert len(blocked) == 1 and blocked[0].levelname == "ERROR"


def test_top_level_non_object_is_corrupt(tmp_path: Path) -> None:
    _write(tmp_path, "[1, 2]")
    assert ConfigStore.load(str(tmp_path)).error is not None


def test_legacy_file_is_migrated_backed_up_and_saved(tmp_path: Path) -> None:
    _write(tmp_path, {"configuration_version": "2.3.6", "port": 1234})
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None
    assert store.data.port == 1234
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
    store = ConfigStore.load(str(tmp_path))
    assert store.error is not None and "step failed" in store.error
    assert _backups(tmp_path, "VERSION")
    assert json.loads((tmp_path / "config.json").read_text())["devices"] == "broken"


def test_newer_schema_version_backs_up_and_loads(tmp_path: Path) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION + 5, "port": 7})
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None and store.data.port == 7
    assert _backups(tmp_path, "DOWNGRADE")


def test_invalid_top_level_key_is_quarantined_and_defaulted(tmp_path: Path) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    store = ConfigStore.load(str(tmp_path))
    assert store.data.port == 8888
    lines = (tmp_path / QUARANTINE_FILE_NAME).read_text().splitlines()
    record = json.loads(lines[-1])
    assert record["path"] == "port" and record["value"] == "nope"
    assert record["errors"]


def test_quarantined_key_is_saved_as_default_so_it_is_not_quarantined_again(
    tmp_path: Path,
) -> None:
    # The bad value falls back to its default *on disk* too; the
    # original lives only in the quarantine file.
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    ConfigStore.load(str(tmp_path))
    assert json.loads((tmp_path / "config.json").read_text())["port"] == 8888
    quarantine_file = tmp_path / QUARANTINE_FILE_NAME
    first = quarantine_file.read_text()
    assert first.count("\n") == 1
    ConfigStore.load(str(tmp_path))
    assert quarantine_file.read_text() == first  # no new record on the next boot


def test_unwritable_quarantine_backs_up_before_repairing(tmp_path: Path) -> None:
    _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    (tmp_path / QUARANTINE_FILE_NAME).mkdir()  # appending to it fails
    store = ConfigStore.load(str(tmp_path))
    assert store.quarantined == 0 and store.error is None
    (backup,) = _backups(tmp_path, "QUARANTINE")
    assert json.loads((tmp_path / backup).read_text())["port"] == "nope"
    assert json.loads((tmp_path / "config.json").read_text())["port"] == 8888


def test_unwritable_quarantine_and_backup_never_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": "nope"})
    original = path.read_text()
    (tmp_path / QUARANTINE_FILE_NAME).mkdir()

    def no_backup(config_dir: str, reason: str, move: bool = False) -> None:
        return None

    monkeypatch.setattr("ledfx.configuration.store.backup_config_file", no_backup)
    store = ConfigStore.load(str(tmp_path))
    assert store.error is not None and store.data.port == 8888
    assert path.read_text() == original


def test_quarantine_backs_up_original_before_rewriting(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "devices": [
                {"id": "good", "type": "dummy", "config": {}},
                {"id": "no-type", "config": {}},
            ],
        },
    )
    before = path.read_bytes()
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None and store.quarantined
    [backup] = _backups(tmp_path, "QUARANTINE")
    assert (tmp_path / backup).read_bytes() == before
    on_disk = json.loads(path.read_text())
    assert [d["id"] for d in on_disk["devices"]] == ["good"]


def test_quarantine_during_migration_takes_no_second_backup(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "configuration_version": "2.3.6",
            "devices": [{"id": "no-type", "config": {}}],
        },
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None and store.quarantined
    assert _backups(tmp_path, "VERSION")
    assert not _backups(tmp_path, "QUARANTINE")


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
    store = ConfigStore.load(str(tmp_path))
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
    store = ConfigStore.load(str(tmp_path))
    store.data.port = 2

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
        store = ConfigStore.load(str(tmp_path))
    finally:
        path.chmod(0o644)
    assert store.error is not None and store.data.port == 8888


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_save_keeps_existing_file_mode(tmp_path: Path) -> None:
    path = _write(tmp_path, {"schema_version": CURRENT_SCHEMA_VERSION, "port": 1})
    path.chmod(0o644)
    store = ConfigStore.load(str(tmp_path))
    store.data.port = 2
    assert store.save_now() is True
    assert path.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize(
    "raw",
    [
        {"configuration_version": "2.3.6", "port": 1234},
        {"schema_version": CURRENT_SCHEMA_VERSION + 5, "port": 1234},
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "port": 1234,
            "devices": [{"id": "no-type", "config": {}}],
        },
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
    store = ConfigStore.load(str(tmp_path))
    assert store.error is not None and "backed up" in store.error
    assert store.data.port == 1234
    assert path.read_bytes() == before
    assert store.save_now() is False
    assert path.read_bytes() == before


def test_unserialisable_value_fails_save_without_raising(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    # Plugin config dicts are untyped, so a non-JSON value can reach them.
    store.data.devices = [DeviceEntry(id="d", type="x", config={"bad": object()})]
    assert store.save_now() is False


def test_entry_lookups(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "devices": [{"id": "d", "type": "dummy", "config": {}}],
                "virtuals": [{"id": "v", "config": {"name": "V"}, "segments": []}],
            }
        )
    )
    store = ConfigStore.load(str(tmp_path))
    device, virtual = store.device_entry("d"), store.virtual_entry("v")
    assert device is not None and device.type == "dummy"
    assert virtual is not None and virtual.config.name == "V"
    assert store.virtual_entry("nope") is None
    assert store.device_entry("nope") is None


def test_quarantined_core_value_is_saved_as_its_default(tmp_path: Path) -> None:
    # The field falls back to its default on disk too, so the next boot
    # finds nothing to quarantine and the append-only jsonl does not grow.
    (tmp_path / "config.json").write_text(
        json.dumps({"schema_version": 2, "visualisation_fps": 999, "port": 9})
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.data.visualisation_fps == 30 and store.data.port == 9
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["visualisation_fps"] == 30 and on_disk["port"] == 9
    quarantine_file = tmp_path / QUARANTINE_FILE_NAME
    first = quarantine_file.read_text()
    record = json.loads(first.splitlines()[0])
    assert record["path"] == "visualisation_fps" and record["value"] == 999
    ConfigStore.load(str(tmp_path))
    assert quarantine_file.read_text() == first  # no new record on the second load


def test_runtime_keys_from_old_files_are_dropped_silently(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps({"configuration_version": "2.3.6", "hosts": ["10.0.0.2"], "port": 9})
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.data.port == 9
    assert not (tmp_path / QUARANTINE_FILE_NAME).exists()
    assert "hosts" not in json.loads(store.serialise())


def test_runtime_keys_after_downgrade_round_trip_are_dropped_silently(
    tmp_path: Path,
) -> None:
    # An old build wrote hosts back but kept schema_version 2 (ALLOW_EXTRA)
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "configuration_version": "2.3.6",
                "hosts": ["10.0.0.2"],
                "port": 9,
            }
        )
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.data.port == 9
    assert not (tmp_path / QUARANTINE_FILE_NAME).exists()


def test_legacy_spotify_triggers_load_without_quarantine(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "configuration_version": "2.3.6",
            "scenes": {"s1": {"name": "S1", "virtuals": {}, "a-5": ["a", "A", 5]}},
            "integrations": [
                {"id": "spotify", "type": "spotify", "data": {"s1": {"name": "S1"}}}
            ],
        },
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None
    assert not (tmp_path / QUARANTINE_FILE_NAME).exists()
    assert store.data.integrations[0].data == {"s1": {"a-5": ["a", "A", 5]}}
    assert store.data.scenes["s1"].name == "S1"


def test_non_trigger_scene_list_is_quarantined_not_moved(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "configuration_version": "2.3.6",
            "scenes": {"s1": {"name": "S1", "virtuals": {"v": {}}, "x": [1]}},
            "integrations": [{"id": "spotify", "type": "spotify"}],
        },
    )
    store = ConfigStore.load(str(tmp_path))
    assert store.data.integrations[0].data == {}
    assert "x" not in store.data.scenes["s1"].model_dump()
    records = (tmp_path / QUARANTINE_FILE_NAME).read_text().splitlines()
    assert [(r["path"], r["value"]) for r in map(json.loads, records)] == [
        ("scenes.s1.x", [1])
    ]


def test_repeated_save_failures_log_one_error_until_a_save_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = ConfigStore.load(str(tmp_path))
    caplog.set_level(logging.DEBUG, logger="ledfx.configuration.store")
    real_mkstemp = tempfile.mkstemp

    def read_only_dir(**kwargs: str) -> tuple[int, str]:
        raise PermissionError("read-only config dir")

    def levels() -> list[int]:
        return [r.levelno for r in caplog.records if "Failed to save" in r.getMessage()]

    monkeypatch.setattr(tempfile, "mkstemp", read_only_dir)
    for _ in range(3):
        assert store.save_now() is False
    assert levels() == [logging.ERROR, logging.DEBUG, logging.DEBUG]

    monkeypatch.setattr(tempfile, "mkstemp", real_mkstemp)
    assert store.save_now() is True
    monkeypatch.setattr(tempfile, "mkstemp", read_only_dir)
    assert store.save_now() is False
    assert levels()[-1] == logging.ERROR
