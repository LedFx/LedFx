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
