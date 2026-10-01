"""A MagicMock LedFx core backed by a real typed config and a mocked store."""

from functools import partial
from unittest.mock import MagicMock

from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore


def fake_ledfx(config: dict[str, object] | None = None) -> MagicMock:
    ledfx = MagicMock()
    ledfx.config_store = MagicMock(spec=ConfigStore)
    ledfx.config_store.data = LedFxConfig.model_validate(config or {})
    ledfx.config = ledfx.config_store.data
    # The real lookups, reading the mocked store's real data.
    ledfx.config_store.virtual_entry.side_effect = partial(
        ConfigStore.virtual_entry, ledfx.config_store
    )
    ledfx.config_store.device_entry.side_effect = partial(
        ConfigStore.device_entry, ledfx.config_store
    )
    return ledfx
