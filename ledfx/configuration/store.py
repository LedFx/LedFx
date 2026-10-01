"""ConfigStore: the only code that reads or writes config.json."""

import asyncio
import contextlib
import datetime
import json
import logging
import os
import shutil
import stat
import tempfile
import threading
from collections.abc import AsyncIterator
from typing import ClassVar

from ledfx.configuration.lenient import lenient_validate
from ledfx.configuration.migrations import (
    CURRENT_SCHEMA_VERSION,
    run_migrations,
    schema_version_of,
)
from ledfx.configuration.migrations.v2 import strip_envelope
from ledfx.configuration.models import DeviceEntry, LedFxConfig, VirtualEntry
from ledfx.consts import LEGACY_CONFIGURATION_VERSION
from ledfx.fsutil import fsync_directory

_LOGGER = logging.getLogger(__name__)

CONFIG_FILE_NAME = "config.json"
QUARANTINE_FILE_NAME = "config.quarantine.jsonl"
SAVE_DELAY_SECONDS = 1.0

BACKUP_REASONS = {
    "DECODE": "config.json is not valid JSON.",
    "OSERROR": "config.json could not be read.",
    "VERSION": "Upgrading config.json to a newer format.",
    "DOWNGRADE": "config.json was written by a newer LedFx.",
    "IMPORT": "Replacing config.json with an imported config.",
    "DELETE": "Resetting config.json to defaults.",
    "QUARANTINE": "Removing invalid entries from config.json.",
}


def backup_config_file(config_dir: str, reason: str, move: bool = False) -> str | None:
    """Copy (or move) config.json to a collision-proof backup; return its path."""
    source = os.path.join(config_dir, CONFIG_FILE_NAME)
    if not os.path.exists(source):
        return None
    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(config_dir, f"config_backup_{reason}_{stamp}")
    dest = f"{base}.json"
    suffix = 1
    while os.path.exists(dest):
        dest = f"{base}_{suffix}.json"
        suffix += 1
    try:
        if move:
            try:
                os.replace(source, dest)
            except OSError:
                shutil.copyfile(source, dest)
        else:
            shutil.copyfile(source, dest)
        # The backup must outlive a crash during the write that follows it.
        # r+b: Windows can only fsync a writable handle.
        with open(dest, "r+b") as file:
            os.fsync(file.fileno())
        fsync_directory(config_dir)
    except OSError as err:
        # An unreadable config.json must not crash startup (safe mode backs it up).
        _LOGGER.error("Could not back up config.json: %s", err)
        return None
    _LOGGER.warning("%s Backup created: %s", BACKUP_REASONS.get(reason, ""), dest)
    return dest


def _on_loop_thread(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


class ConfigStore:
    """Owns config.json: load -> migrate -> validate, and atomic saves."""

    _registry: ClassVar[dict[str, "ConfigStore"]] = {}

    def __init__(self, config_dir: str, data: LedFxConfig) -> None:
        self.config_dir = config_dir
        self.data = data
        self.error: str | None = None
        # config.json exists but could not be read at load (OSERROR safe mode).
        self.unreadable = False
        self.quarantined = 0  # records written; load() saves the repaired data
        self.quarantine_failed = False  # a dropped value has no record on disk
        self._blocked_logged = False
        self._write_lock = threading.Lock()
        self._lock = asyncio.Lock()  # mutate()/replace(); binds a loop on first wait
        self._seq = 0
        self._written_seq = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._save_handle: asyncio.TimerHandle | None = None

    @property
    def path(self) -> str:
        return os.path.join(self.config_dir, CONFIG_FILE_NAME)

    # ---- loading -------------------------------------------------------
    @classmethod
    def load(cls, config_dir: str) -> "ConfigStore":
        os.makedirs(config_dir, exist_ok=True)
        store = cls(config_dir, LedFxConfig())
        if not os.path.isfile(store.path):
            store.save_now()
            return store
        try:
            with open(store.path, encoding="utf-8") as file:
                raw = json.load(file)
            if not isinstance(raw, dict):
                raise ValueError("top level is not a JSON object")  # noqa: TRY004
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            store._enter_safe_mode("DECODE", f"config.json is not valid JSON: {err}")
            return store
        except OSError as err:
            store.unreadable = True
            store._enter_safe_mode("OSERROR", f"config.json could not be read: {err}")
            return store

        version = schema_version_of(raw)
        migrated = False
        backup_failed = False
        if version > CURRENT_SCHEMA_VERSION:
            backup_failed = store.backup("DOWNGRADE") is None
        elif version < CURRENT_SCHEMA_VERSION:
            backup_failed = store.backup("VERSION") is None
            try:
                raw = run_migrations(raw, version)
            except Exception as err:  # nothing may reach disk after a failed migration
                _LOGGER.exception("Config migration failed.")
                store._enter_safe_mode(
                    None, f"config.json could not be migrated: {err}"
                )
                return store
            migrated = True
        if backup_failed:
            # Keep the data in memory, but never overwrite the only copy.
            store.error = (
                "config.json could not be backed up before upgrading; "
                "changes will not be saved"
            )
            _LOGGER.error(store.error)
        # Also after a downgrade and re-upgrade: old builds write hosts back but keep
        # schema_version 2, so the v2 step alone would not strip it.
        strip_envelope(raw)
        config = lenient_validate(LedFxConfig, raw, "", store.quarantine)
        if config is None:
            store._enter_safe_mode(None, "config.json is not a LedFx config")
            return store
        store.data = config
        # No VERSION/DOWNGRADE backup was taken, and the rewrite below drops the
        # invalid entries; keep the original file first. That includes values
        # whose quarantine record could not be written: the file is then their
        # only copy.
        dropped = store.quarantined or store.quarantine_failed
        if (
            dropped
            and version == CURRENT_SCHEMA_VERSION
            and store.backup("QUARANTINE") is None
        ):
            store.error = (
                "config.json could not be backed up before removing invalid "
                "entries; changes will not be saved"
            )
            _LOGGER.error(store.error)
        if migrated or dropped:
            store.save_now()  # persist the defaulted values, not the bad ones
        return store

    def _enter_safe_mode(self, reason: str | None, message: str) -> None:
        if reason is not None:
            self.backup(reason)
        self.data = LedFxConfig()
        self.error = message
        _LOGGER.error(
            "%s LedFx is running on default settings and will not save until "
            "a config is imported or the config is reset.",
            message,
        )

    # ---- side files ----------------------------------------------------
    def backup(self, reason: str) -> str | None:
        return backup_config_file(self.config_dir, reason)

    def quarantine(self, path: str, value: object, errors: list[str]) -> None:
        _LOGGER.warning("Quarantined invalid config at %s: %s", path, "; ".join(errors))
        record = {
            "time": datetime.datetime.now().astimezone().isoformat(),
            "path": path,
            "value": value,
            "errors": errors,
        }
        try:
            with open(
                os.path.join(self.config_dir, QUARANTINE_FILE_NAME),
                "a",
                encoding="utf-8",
            ) as file:
                file.write(json.dumps(record, ensure_ascii=False, default=repr) + "\n")
        except OSError as err:
            self.quarantine_failed = True
            _LOGGER.error("Could not write quarantine record: %s", err)
            return
        self.quarantined += 1

    # ---- saving --------------------------------------------------------
    def serialise(self) -> str:
        view = self.data.model_dump(mode="json")
        view["schema_version"] = CURRENT_SCHEMA_VERSION
        view["configuration_version"] = LEGACY_CONFIGURATION_VERSION
        return json.dumps(view, ensure_ascii=False, sort_keys=True, indent=4)

    def _blocked(self) -> bool:
        if self.error is None:
            return False
        if not self._blocked_logged:
            self._blocked_logged = True
            _LOGGER.error("Config change not saved: %s", self.error)
        return True

    def _next_text(self) -> tuple[int, str]:
        self._seq += 1
        return self._seq, self.serialise()

    def _write(self, seq: int, text: str) -> None:
        """Atomically replace config.json; skip writes older than one already done."""
        with self._write_lock:
            if seq < self._written_seq:
                return
            fd, tmp = tempfile.mkstemp(
                dir=self.config_dir, prefix=".config.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    file.write(text)
                    file.flush()
                    os.fsync(file.fileno())
                # mkstemp creates 0600; keep the existing mode (or the usual 0644),
                # plus owner read, so replacing an unreadable file fixes it.
                if os.path.exists(self.path):
                    mode = stat.S_IMODE(os.stat(self.path).st_mode) | stat.S_IRUSR
                    os.chmod(tmp, mode)
                else:
                    os.chmod(tmp, 0o644)
                os.replace(tmp, self.path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
            # Persist the rename itself; a failure here doesn't undo the write.
            fsync_directory(self.config_dir)
            self._written_seq = seq

    def save_now(self) -> bool:
        """Write synchronously. Returns False if blocked by safe mode or on error."""
        if self._blocked():
            return False
        self._cancel_pending()
        try:
            self._write(*self._next_text())
        except (OSError, TypeError, ValueError) as err:
            _LOGGER.error("Failed to save config.json: %s", err)
            return False
        return True

    def _cancel_pending(self) -> None:
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_handle = None

    # ---- loop integration ------------------------------------------------
    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def request_save(self) -> None:
        """Schedule a debounced save. Safe to call from any thread."""
        if self._blocked():
            return
        loop = self._loop
        if loop is None or not loop.is_running():
            self.save_now()
            return
        if not _on_loop_thread(loop):
            loop.call_soon_threadsafe(self.request_save)
            return
        self._cancel_pending()
        self._save_handle = loop.call_later(SAVE_DELAY_SECONDS, self._save_later)

    def _save_later(self) -> None:
        self._save_handle = None
        if self._blocked() or self._loop is None:
            return
        try:
            seq, text = self._next_text()  # serialise on the loop: data is consistent
        except (TypeError, ValueError) as err:
            _LOGGER.error("Failed to save config.json: %s", err)
            return
        future = self._loop.run_in_executor(None, self._write, seq, text)
        future.add_done_callback(self._log_write_failure)

    @staticmethod
    def _log_write_failure(future: "asyncio.Future[None]") -> None:
        if not future.cancelled() and future.exception() is not None:
            _LOGGER.error("Failed to save config.json: %s", future.exception())

    async def flush(self) -> bool:
        """Write any pending change now and wait for it. False if blocked or failed."""
        if self._blocked():
            return False
        self._cancel_pending()
        loop = asyncio.get_running_loop()
        try:
            seq, text = self._next_text()
            await loop.run_in_executor(None, self._write, seq, text)
        except (OSError, TypeError, ValueError) as err:
            _LOGGER.error("Failed to save config.json: %s", err)
            return False
        return True

    def flush_sync(self) -> None:
        """Shutdown path: cancel the timer and write synchronously."""
        self.save_now()

    async def replace(self, data: LedFxConfig) -> bool:
        """Swap in a whole new config (import/reset), leave safe mode, write now.

        On a failed write the previous data and safe-mode state are restored,
        so memory never holds a config that is not on disk. Returns success.
        Never call inside mutate(): the lock is not re-entrant.
        """
        async with self._lock:
            previous = (self.data, self.error, self._blocked_logged)
            self.data = data
            self.error = None
            self._blocked_logged = False
            if await self.flush():
                return True
            self.data, self.error, self._blocked_logged = previous
            return False

    @contextlib.asynccontextmanager
    async def mutate(self) -> AsyncIterator[LedFxConfig]:
        """For changes that await between read and write; saves on clean exit."""
        async with self._lock:
            yield self.data
        self.request_save()

    # ---- lookups ---------------------------------------------------------
    def device_entry(self, id: str) -> DeviceEntry | None:
        return next((e for e in self.data.devices if e.id == id), None)

    def virtual_entry(self, id: str) -> VirtualEntry | None:
        # ponytail: linear scan; index by id if virtual counts reach the thousands
        return next((e for e in self.data.virtuals if e.id == id), None)

    # ---- registry for the legacy save_config shim -----------------------
    @classmethod
    def registered(cls, config_dir: str) -> "ConfigStore | None":
        return cls._registry.get(os.path.abspath(config_dir))

    def register(self) -> None:
        ConfigStore._registry[os.path.abspath(self.config_dir)] = self

    def unregister(self) -> None:
        if ConfigStore._registry.get(os.path.abspath(self.config_dir)) is self:
            del ConfigStore._registry[os.path.abspath(self.config_dir)]
