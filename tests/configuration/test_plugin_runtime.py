from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ledfx.configuration.lenient import Quarantine
from ledfx.configuration.plugin import PluginConfig
from ledfx.utils import BaseRegistry
from tests.configuration.model_schema import _registry_classes
from tests.test_utilities.fake_ledfx import fake_ledfx

if TYPE_CHECKING:
    from ledfx.devices import Device

# Pre-existing stale UI hints, kept so legacy /api/schema stays byte-identical.
STALE_KEYS = {
    ("game_of_life", "gradient"),
    ("game_of_life", "gradient_roll"),
    ("gifplayer", "gradient"),
    ("imagespin", "speed"),
    ("keybeat2d", "pp_skip"),
}
Record = tuple[str, object]


def _collect() -> tuple[list[Record], Quarantine]:
    records: list[Record] = []

    def quarantine(path: str, value: object, errors: list[str]) -> None:
        records.append((path, value))

    return records, quarantine


@pytest.mark.parametrize(
    "plugin_type,cls",
    _registry_classes(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_plugin_has_a_model(plugin_type: str, cls: type[BaseRegistry]) -> None:
    assert issubclass(cls.config_model(), PluginConfig)


@pytest.mark.parametrize(
    "plugin_type,cls",
    _registry_classes(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_effect_key_lists_name_real_fields(
    plugin_type: str, cls: type[BaseRegistry]
) -> None:
    fields = set(cls.config_model().model_fields)
    for attr in ("HIDDEN_KEYS", "ADVANCED_KEYS", "PERMITTED_KEYS"):
        listed = getattr(cls, attr, None) or []
        unknown = {
            k for k in set(listed) - fields if (plugin_type, k) not in STALE_KEYS
        }
        assert not unknown, f"{plugin_type}.{attr} names unknown keys {unknown}"


def test_lenient_create_quarantines_bad_value_and_builds() -> None:
    from ledfx.effects import Effects

    ledfx = fake_ledfx()
    ledfx.dev_enabled.return_value = False
    records, quarantine = _collect()
    effect = Effects(ledfx).create(
        ledfx=ledfx,
        type="rainbow",
        config={"brightness": 7, "gradient_name": "UI only"},
        lenient=quarantine,
    )
    assert effect is not None
    assert effect.config.brightness == 1.0
    assert effect.config.as_dict()["gradient_name"] == "UI only"
    assert records == [("effects.rainbow.config.brightness", 7)]


def test_strict_create_raises() -> None:
    from ledfx.effects import Effects

    ledfx = fake_ledfx()
    with pytest.raises(ValidationError):
        Effects(ledfx).create(ledfx=ledfx, type="rainbow", config={"brightness": 7})


def test_unavailable_serial_port_still_loads_and_keeps_stored_value() -> None:
    # A port unplugged at startup is not checked at load: the device loads
    # (offline until the port returns) and the stored value is left alone.
    from ledfx.configuration.models import DeviceEntry
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    ledfx = fake_ledfx()
    records, quarantine = _collect()
    stored = {"name": "Strip", "pixel_count": 10, "com_port": "COM-UNPLUGGED"}
    entry = DeviceEntry(id="strip", type="adalight", config=dict(stored))
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="adalight",
        id="strip",
        config=stored,
        ledfx=ledfx,
        lenient=quarantine,
        lenient_entry=entry,
    )
    assert device is not None
    assert device.config.com_port == "COM-UNPLUGGED"
    assert records == []
    assert entry.config == stored
    ledfx.config_store.request_save.assert_not_called()


def test_lenient_repair_is_written_back_to_its_device_entry() -> None:
    # The repaired value replaces the bad one in the store entry, so the
    # next boot finds nothing to quarantine (the original stays in the jsonl).
    from ledfx.configuration.models import DeviceEntry
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    ledfx = fake_ledfx()
    records, quarantine = _collect()
    entry = DeviceEntry(
        id="strip",
        type="dummy",
        config={"name": "Strip", "pixel_count": 10, "center_offset": "x"},
    )
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="dummy",
        id="strip",
        config=dict(entry.config),
        ledfx=ledfx,
        lenient=quarantine,
        lenient_entry=entry,
    )
    assert device is not None
    assert records == [("devices.strip.config.center_offset", "x")]
    assert entry.config["center_offset"] == 0 and entry.config["name"] == "Strip"
    ledfx.config_store.request_save.assert_called()
    type(device).config_model().model_validate(entry.config)  # valid: no 2nd record


def test_lenient_repair_is_not_written_back_when_quarantine_failed() -> None:
    # The dropped value is then only in config.json: saving would lose it.
    from ledfx.configuration.models import DeviceEntry
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    ledfx = fake_ledfx()
    ledfx.config_store.quarantine_failed = True
    _, quarantine = _collect()
    stored = {"name": "Strip", "pixel_count": 10, "center_offset": "x"}
    entry = DeviceEntry(id="strip", type="dummy", config=dict(stored))
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="dummy",
        id="strip",
        config=dict(entry.config),
        ledfx=ledfx,
        lenient=quarantine,
        lenient_entry=entry,
    )
    assert device is not None and device.config.center_offset == 0
    assert entry.config == stored
    ledfx.config_store.request_save.assert_not_called()


def test_unchanged_valid_config_is_not_written_back() -> None:
    from ledfx.configuration.models import DeviceEntry
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    ledfx = fake_ledfx()
    _, quarantine = _collect()
    stored = {"name": "Strip", "pixel_count": 10}
    entry = DeviceEntry(id="strip", type="dummy", config=dict(stored))
    RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="dummy",
        id="strip",
        config=dict(stored),
        ledfx=ledfx,
        lenient=quarantine,
        lenient_entry=entry,
    )
    assert entry.config == stored
    ledfx.config_store.request_save.assert_not_called()


def _dummy_device(ledfx: object) -> "Device":
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="dummy",
        id="strip",
        config={"name": "Strip", "pixel_count": 10},
        ledfx=ledfx,
    )
    assert device is not None
    return device


def test_derived_values_are_mirrored_to_the_device_entry() -> None:
    ledfx = fake_ledfx(
        {"devices": [{"id": "strip", "type": "dummy", "config": {"name": "Strip"}}]}
    )
    device = _dummy_device(ledfx)
    device._set_config_values(pixel_count=64)
    assert getattr(device.config, "pixel_count") == 64  # noqa: B009
    assert ledfx.config.devices[0].config["pixel_count"] == 64
    ledfx.config_store.request_save.assert_called_once()


def test_unchanged_derived_values_do_not_save() -> None:
    ledfx = fake_ledfx(
        {"devices": [{"id": "strip", "type": "dummy", "config": {"name": "Strip"}}]}
    )
    device = _dummy_device(ledfx)
    device._set_config_values(pixel_count=10)
    assert ledfx.config.devices[0].config == {"name": "Strip"}
    ledfx.config_store.request_save.assert_not_called()


def test_e131_derives_channel_count_and_universe_end() -> None:
    from ledfx.devices import Device
    from ledfx.utils import RegistryLoader

    ledfx = fake_ledfx()
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="e131",
        config={"name": "E", "ip_address": "10.0.0.9", "pixel_count": 200},
        ledfx=ledfx,
    )
    assert device is not None
    assert getattr(device.config, "channel_count") == 600  # noqa: B009
    # 600 channels / 510 per universe
    assert getattr(device.config, "universe_end") == 2  # noqa: B009


def test_configs_match_accepts_a_running_effect_config() -> None:
    # A running effect's config is a PluginConfig; preset and scene "active"
    # checks compare it with stored dicts.
    from ledfx.configuration.presets import configs_match
    from ledfx.effects import Effects

    ledfx = fake_ledfx()
    effect = Effects(ledfx).create(ledfx=ledfx, type="rainbow", config={})
    assert effect is not None
    assert configs_match(effect.config, effect.config.as_dict())
    assert not configs_match(effect.config, {**effect.config.as_dict(), "speed": 9})


def test_integration_data_changes_reach_the_entry_only_through_its_api() -> None:
    import copy

    from ledfx.api.integration_spotify import QLCEndpoint as SpotifyEndpoint
    from ledfx.integrations import Integrations
    from ledfx.integrations.spotify import Spotify

    stored = {"scene": {"a-0": ["a", "Song A", 0]}}
    ledfx = fake_ledfx(
        {"integrations": [{"id": "sp", "type": "spotify", "data": stored}]}
    )
    ledfx.integrations = Integrations(ledfx)
    ledfx.integrations.create_from_config(ledfx.config.integrations)
    spotify = ledfx.integrations.get("sp")
    assert isinstance(spotify, Spotify)
    entry = ledfx.config.integrations[0]

    before = copy.deepcopy(entry.data)
    spotify.add_trigger("scene", "b", "Song B", 5)
    assert entry.data == before  # the plugin's copy changed, not the entry

    SpotifyEndpoint(ledfx)._save_triggers(spotify)
    data = entry.data
    assert isinstance(data, dict) and set(data["scene"]) == {"a-0", "b-5"}

    spotify.delete_trigger("b-5")
    assert set(data["scene"]) == {"a-0", "b-5"}  # not shared after write-back


async def test_wled_boot_keeps_the_stored_custom_name() -> None:
    import json
    from unittest.mock import AsyncMock, MagicMock, patch

    from ledfx.configuration.store import ConfigStore
    from ledfx.devices import Device, NetworkedDevice
    from ledfx.utils import RegistryLoader

    config = {"name": "My Strip", "ip_address": "10.0.0.2", "pixel_count": 10}
    ledfx = fake_ledfx(
        {"devices": [{"id": "strip", "type": "wled", "config": dict(config)}]}
    )
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="wled", id="strip", config=config, ledfx=ledfx
    )
    assert device is not None
    wled = MagicMock()
    wled.get_config = AsyncMock(
        return_value={"name": "WLED-ABC", "leds": {"count": 50, "rgbw": True}, "vid": 1}
    )
    with (
        patch("ledfx.devices.wled.WLED", return_value=wled),
        patch.object(NetworkedDevice, "async_initialize", AsyncMock()),
    ):
        device._destination = "10.0.0.2"
        await device.async_initialize()

    saved = json.loads(ConfigStore.serialise(ledfx.config_store))
    stored = saved["devices"][0]["config"]
    assert stored["name"] == "My Strip"
    assert device.name == "My Strip"  # the live object keeps it too
    assert stored["pixel_count"] == 50 and stored["rgbw_led"] is True
    ledfx.config_store.request_save.assert_called()


async def test_setting_an_invalid_effect_config_is_a_400() -> None:
    import json
    from unittest.mock import AsyncMock, MagicMock

    from ledfx.api.virtual_effects import EffectsEndpoint
    from ledfx.effects import Effects

    ledfx = fake_ledfx()
    ledfx.effects = Effects(ledfx)
    request = MagicMock()
    request.json = AsyncMock(
        return_value={"type": "rainbow", "config": {"brightness": 7}}
    )
    response = await EffectsEndpoint(ledfx).post("virtual", request)
    assert response.status == 400
    assert "brightness" in json.dumps(json.loads(response.text or ""))


def test_toggle_flips_flags_on_a_real_effect() -> None:
    from ledfx.effects import Effects
    from ledfx.virtuals import apply_config_to_active_effects

    ledfx = fake_ledfx()
    ledfx.dev_enabled.return_value = False
    effect = Effects(ledfx).create(ledfx=ledfx, type="rainbow", config={"flip": True})
    assert effect is not None
    virtual = MagicMock(id="v", active_effect=effect)
    updates: dict[str, object] = {"flip": "toggle", "mirror": "toggle"}
    assert apply_config_to_active_effects([virtual], updates) == (1, 0)
    assert effect.config.flip is False and effect.config.mirror is True
