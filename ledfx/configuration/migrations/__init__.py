"""Ordered, pure config migrations.

Each step maps the raw ``config.json`` dict of one schema version to the next.
Steps never touch the registry, models or disk, so they can run on imports,
at load time and in tests alike.
"""

import copy
from collections.abc import Callable

from ledfx.configuration.migrations.legacy import legacy_to_v1

Migration = Callable[[dict[str, object]], dict[str, object]]

# (target schema_version, step). Append only; never edit a released step.
MIGRATIONS: list[tuple[int, Migration]] = [(1, legacy_to_v1)]
CURRENT_SCHEMA_VERSION = MIGRATIONS[-1][0]


def schema_version_of(raw: dict[str, object]) -> int:
    """Return the file's schema_version, treating anything but a plain int as 0."""
    version = raw.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    return 0


def run_migrations(
    raw: dict[str, object], from_version: int | None = None
) -> dict[str, object]:
    """Apply every step newer than the file's version to a deep copy of raw."""
    version = schema_version_of(raw) if from_version is None else from_version
    data = copy.deepcopy(raw)
    for target, step in MIGRATIONS:
        if target > version:
            data = step(data)
            data["schema_version"] = target
    return data
