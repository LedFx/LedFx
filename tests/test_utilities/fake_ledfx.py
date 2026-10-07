"""A MagicMock LedFx core backed by a real typed config and a mocked store."""

from functools import partial
from unittest.mock import MagicMock

from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore
from ledfx.preview import PreviewSampler, PreviewSettings


def fake_ledfx(config: dict[str, object] | None = None) -> MagicMock:
    ledfx = MagicMock()
    ledfx.config_store = MagicMock(spec=ConfigStore)
    ledfx.config_store.data = LedFxConfig.model_validate(config or {})
    ledfx.config = ledfx.config_store.data
    ledfx.config_store.quarantine_failed = False
    # Not in safe mode; set config_store.error to enter it. Mock classes are
    # per instance, so the real read_only property reads this mock's error.
    ledfx.config_store.error = None
    # Sampling off by default: closed no-ops exactly like the pre-sampler
    # fakes. Tests that want sampling install their own (install_sampler).
    ledfx.preview_sampler = PreviewSampler(
        ledfx,
        PreviewSettings(
            ledfx.config.visualisation_fps,
            ledfx.config.visualisation_maxlen,
            ledfx.config.ui_brightness_boost,
            ledfx.config.transmission_mode,
        ),
    )
    ledfx.preview_sampler.close()
    type(ledfx.config_store).read_only = ConfigStore.read_only
    # The real lookups, reading the mocked store's real data.
    ledfx.config_store.virtual_entry.side_effect = partial(
        ConfigStore.virtual_entry, ledfx.config_store
    )
    ledfx.config_store.device_entry.side_effect = partial(
        ConfigStore.device_entry, ledfx.config_store
    )
    return ledfx


def closed_sampler(core: MagicMock) -> MagicMock:
    """Attach a closed real PreviewSampler; no-ops exactly like no sampler."""
    from ledfx.preview import PreviewSampler, PreviewSettings

    core.preview_sampler = PreviewSampler(
        core,
        PreviewSettings(60, 100, 0, "compressed"),
    )
    core.preview_sampler.close()
    return core
