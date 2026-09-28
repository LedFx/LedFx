"""Persistent Sendspin identity shared by streams in one config directory."""

import os
import tempfile
from pathlib import Path

from aiosendspin.noise import Identity, b64url_decode


def load_or_create_identity(directory: Path) -> Identity:
    """Publish a complete private key atomically, retaining any concurrent winner."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sendspin_identity"
    try:
        return Identity.from_private_bytes(
            b64url_decode(path.read_text("ascii").strip())
        )
    except FileNotFoundError:
        pass

    identity = Identity.generate()
    # mkstemp creates the private key file with mode 0600. Linking the completed
    # file avoids exposing an empty/partial key or replacing another stream's key.
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, prefix=".sendspin-")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as key_file:
            key_file.write(identity.private_b64u)
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            return Identity.from_private_bytes(
                b64url_decode(path.read_text("ascii").strip())
            )
        return identity
    finally:
        temporary_path.unlink()
