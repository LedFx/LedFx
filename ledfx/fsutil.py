"""Durability helpers for files that must survive a crash."""

import contextlib
import os


def fsync_directory(directory: str | os.PathLike[str]) -> None:
    """Persist a rename or new file in `directory`.

    fsync on the file alone does not persist its directory entry on POSIX.
    Windows can't open a directory with os.open, and NTFS journals the rename,
    so this is a no-op there. Failure is ignored: the data is already written.
    """
    if os.name == "nt":
        return
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
