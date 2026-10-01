"""Persistent Sendspin identity shared by streams in one config directory."""

import logging
import os
import tempfile
from pathlib import Path

from aiosendspin.noise import Identity, b64url_decode

from ledfx.fsutil import fsync_directory

_LOGGER = logging.getLogger(__name__)


def _read_identity(path: Path) -> Identity:
    return Identity.from_private_bytes(b64url_decode(path.read_text("ascii").strip()))


def load_or_create_identity(directory: Path) -> Identity:
    """Publish a complete private key atomically, retaining any concurrent winner."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sendspin_identity"
    corrupt = False
    try:
        return _read_identity(path)
    except FileNotFoundError:
        pass
    except (ValueError, UnicodeDecodeError):
        _LOGGER.warning("Replacing unreadable Sendspin identity at %s", path)
        corrupt = True

    identity = Identity.generate()
    # mkstemp creates the private key file with mode 0600. Linking the completed
    # file avoids exposing an empty/partial key or replacing another stream's key.
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, prefix=".sendspin-")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as key_file:
            key_file.write(identity.private_b64u)
            key_file.flush()
            os.fsync(key_file.fileno())
        if corrupt:
            os.replace(temporary_path, path)
        else:
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                return _read_identity(path)
            except OSError:
                # Filesystems without hard links (FAT, some SMB/FUSE mounts).
                os.replace(temporary_path, path)
        fsync_directory(directory)
        return identity
    finally:
        temporary_path.unlink(missing_ok=True)
