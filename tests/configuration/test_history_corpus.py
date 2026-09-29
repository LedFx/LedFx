import glob
import json
import os
import shutil
from pathlib import Path

import pytest

from ledfx.configuration.store import QUARANTINE_FILE_NAME, ConfigStore

HERE = os.path.dirname(__file__)
CORPUS = sorted(
    glob.glob(os.path.join(HERE, "..", "configs", "*.json"))
    + [
        f
        for f in glob.glob(os.path.join(HERE, "legacy", "v*.json"))
        if not f.endswith(".golden.json")
    ]
)


@pytest.mark.parametrize("source", CORPUS, ids=os.path.basename)
def test_every_known_config_loads_without_quarantine_and_round_trips(
    tmp_path: Path, source: str
) -> None:
    shutil.copy(source, tmp_path / "config.json")
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None
    assert not (tmp_path / QUARANTINE_FILE_NAME).exists()
    first = store.serialise()
    reloaded = ConfigStore.load(str(tmp_path))
    assert reloaded.serialise() == first
    assert json.loads(first)["configuration_version"] == "2.3.6"


EVERY_PLUGIN = os.path.join(HERE, "..", "configs", "v2_3_6_every_plugin.json")


def test_every_plugin_2_3_6_config_keeps_every_entry(tmp_path: Path) -> None:
    # Written by 2.3.6's own schemas: every device, effect and integration type.
    # The round trip is pinned by the corpus test above.
    with open(EVERY_PLUGIN, encoding="utf-8") as file:
        raw = json.load(file)
    shutil.copy(EVERY_PLUGIN, tmp_path / "config.json")
    store = ConfigStore.load(str(tmp_path))
    assert store.error is None and store.quarantined == 0
    saved = json.loads(store.serialise())
    for section in ("devices", "virtuals", "integrations"):
        before = {entry["id"]: entry for entry in raw[section]}
        after = {entry["id"]: entry for entry in saved[section]}
        assert before.keys() == after.keys(), section
        for entry_id, entry in before.items():
            assert entry["config"].items() <= after[entry_id]["config"].items(), (
                entry_id
            )
    for virtual in raw["virtuals"]:
        kept = next(v for v in saved["virtuals"] if v["id"] == virtual["id"])
        assert kept.get("active") == virtual.get("active"), virtual["id"]
        assert kept["effect"] == virtual["effect"], virtual["id"]
        assert kept["effects"] == virtual["effects"], virtual["id"]
    for section in (
        "scenes",
        "playlists",
        "user_presets",
        "user_colors",
        "user_gradients",
        "sendspin_servers",
        "now_playing",
        "image_cache",
        "audio",
        "wled_preferences",
    ):
        assert raw[section].items() <= saved[section].items(), section
