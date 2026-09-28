import os
import stat
from pathlib import Path

import pytest

from ledfx.fsutil import fsync_directory


@pytest.mark.skipif(os.name == "nt", reason="directories can't be fsynced on Windows")
def test_fsync_directory_syncs_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[bool] = []
    real_fsync = os.fsync

    def record(fd: int) -> None:
        synced.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", record)
    fsync_directory(tmp_path)
    assert synced == [True]


def test_fsync_directory_ignores_a_missing_directory(tmp_path: Path) -> None:
    fsync_directory(tmp_path / "gone")
