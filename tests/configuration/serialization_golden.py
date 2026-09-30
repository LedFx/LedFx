"""Golden dumps that pin v1 output across serializer changes.

config_dumps.json holds, per corpus config, the sha256 of the loaded
LedFxConfig's model_dump(mode="json") and one sha256 per plugin type of the
stored plugin configs validated and dumped through that plugin's model.
schemas_dump.json holds the core kinds of build_schemas(None); the plugin
kinds are pinned by plugin_models.json already.

Regenerate only when a change to v1 output is intended:
    uv run python -c "from tests.configuration.serialization_golden import write_snapshots; write_snapshots()"
"""

import glob
import hashlib
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from pydantic import ValidationError
from pydantic.json_schema import JsonSchemaValue

import ledfx.utils
from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore
from tests.configuration.model_schema import _registry_by_kind

HERE = os.path.dirname(__file__)
CONFIG_DUMPS = os.path.join(HERE, "snapshots", "config_dumps.json")
SCHEMAS_DUMP = os.path.join(HERE, "snapshots", "schemas_dump.json")
CORPUS = sorted(
    glob.glob(os.path.join(HERE, "..", "configs", "*.json"))
    + [
        f
        for f in glob.glob(os.path.join(HERE, "legacy", "v*.json"))
        if not f.endswith(".golden.json")
    ]
)
CORE_KINDS = (
    "audio",
    "melbanks",
    "melbank_collection",
    "wled_preferences",
    "virtuals",
    "core",
)
# The Fps validator clamps to rates that depend on the clock resolution.
_FIXED_FPS = dict.fromkeys(range(10, 127), 1)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plugin_entries(data: LedFxConfig) -> list[tuple[str, str, dict[str, object]]]:
    """(kind, type, stored config) for every plugin config in data."""
    entries = [("devices", e.type, e.config) for e in data.devices]
    entries += [("integrations", e.type, e.config) for e in data.integrations]
    for virtual in data.virtuals:
        if virtual.effect is not None:
            entries.append(("effects", virtual.effect.type, virtual.effect.config))
        entries += [("effects", e.type, e.config) for e in virtual.effects.values()]
    return entries


def render_config_dumps() -> dict[str, dict[str, str]]:
    registries = {kind: dict(p) for kind, p in _registry_by_kind().items()}
    out: dict[str, dict[str, str]] = {}
    with patch.object(ledfx.utils, "AVAILABLE_FPS", _FIXED_FPS):
        for source in CORPUS:
            with tempfile.TemporaryDirectory() as config_dir:
                shutil.copy(source, os.path.join(config_dir, "config.json"))
                data = ConfigStore.load(config_dir).data
            digests = {
                "config": _sha(
                    json.dumps(data.model_dump(mode="json"), ensure_ascii=False)
                )
            }
            dumps: dict[str, list[str]] = {}
            for kind, plugin_type, config in _plugin_entries(data):
                cls = registries[kind].get(plugin_type)
                if cls is None:
                    continue
                try:
                    model = cls.config_model().model_validate(config)
                except ValidationError:
                    continue  # stored but invalid: v1 never dumps it either
                dumps.setdefault(f"{kind}:{plugin_type}", []).append(
                    json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
                )
            digests.update({key: _sha("\n".join(v)) for key, v in dumps.items()})
            out[os.path.basename(source)] = dict(sorted(digests.items()))
    return out


def render_core_schemas() -> dict[str, JsonSchemaValue]:
    from ledfx.api.schemas import build_schemas

    schemas = build_schemas(None)
    return {kind: schemas[kind] for kind in CORE_KINDS}


def write_snapshots() -> None:
    for path, payload in (
        (CONFIG_DUMPS, render_config_dumps()),
        (SCHEMAS_DUMP, render_core_schemas()),
    ):
        with open(path, "w", encoding="utf-8") as file:
            # No sort_keys: property order is part of what the snapshot pins.
            json.dump(payload, file, indent=1)
            file.write("\n")
