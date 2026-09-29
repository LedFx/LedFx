import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from ledfx.api.config import ConfigEndpoint
from ledfx.configuration.models import (
    AudioConfig,
    MelbankConfig,
    MelbanksConfig,
    VirtualConfig,
    WledPreferences,
    validate_dict,
)


def test_virtual_requires_name_and_defaults_the_rest() -> None:
    with pytest.raises(ValidationError):
        VirtualConfig.model_validate({})
    cfg = validate_dict(VirtualConfig, {"name": "Desk"})
    assert cfg["mapping"] == "span" and cfg["transition_mode"] == "Add"


def test_virtual_rejects_unknown_transition_and_extra_keys() -> None:
    with pytest.raises(ValidationError):
        VirtualConfig.model_validate({"name": "x", "transition_mode": "Wipe"})
    with pytest.raises(ValidationError):
        VirtualConfig.model_validate({"name": "x", "bogus": 1})


def test_transition_modes_track_the_transitions_registry() -> None:
    from ledfx.transitions import Transitions

    enum = VirtualConfig.model_json_schema()["properties"]["transition_mode"]["enum"]
    assert enum == list(Transitions)


def test_audio_keeps_unknown_keys_like_voluptuous_allow_extra() -> None:
    cfg = validate_dict(AudioConfig, {"min_volume": "0.3", "legacy_key": 1})
    assert cfg["min_volume"] == 0.3 and cfg["legacy_key"] == 1


def test_audio_fft_size_default_matches_melbank_module() -> None:
    from ledfx.effects.melbank import FFT_SIZE

    assert AudioConfig().fft_size == FFT_SIZE


def test_melbank_name_absent_when_not_given() -> None:
    assert "name" not in validate_dict(MelbankConfig, {})


def test_melbanks_max_frequencies_items_are_coerced_and_bounded() -> None:
    assert validate_dict(MelbanksConfig, {"max_frequencies": [1.9]})[
        "max_frequencies"
    ] == (1,)
    with pytest.raises(ValidationError):
        MelbanksConfig.model_validate({"max_frequencies": [20000]})


def test_wled_defaults_and_partial_nested_update() -> None:
    cfg = validate_dict(WledPreferences, {"inactivity_timeout": {"setting": 5}})
    timeout = cfg["inactivity_timeout"]
    assert isinstance(timeout, dict) and timeout["setting"] == 5
    assert cfg["wled_preferred_mode"] == {"setting": "UDP", "user_enabled": False}


WLED_NULLS = [
    {key: {field: None}}
    for key in ("wled_preferred_mode", "realtime_gamma_enabled", "inactivity_timeout")
    for field in ("setting", "user_enabled")
]


@pytest.mark.parametrize("prefs", WLED_NULLS)
def test_wled_setting_rejects_explicit_null(prefs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        validate_dict(WledPreferences, prefs)


@pytest.mark.parametrize("prefs", WLED_NULLS)
async def test_put_config_rejects_null_wled_setting(prefs: dict[str, object]) -> None:
    core = MagicMock()
    request = MagicMock()
    request.json = AsyncMock(return_value={"wled_preferences": prefs})
    response = await ConfigEndpoint(core).put(request)
    assert json.loads(response.text or "{}")["status"] == "failed"
    core.events.fire_event.assert_not_called()


def test_dump_schemas_cli(tmp_path: Path) -> None:
    out = tmp_path / "schemas.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ledfx",
            "--dump-schemas",
            str(out),
            "-c",
            str(tmp_path / "cfg"),
        ],
        check=True,
        timeout=120,
    )
    data = json.loads(out.read_text())
    assert {"audio", "virtuals", "wled_preferences", "melbanks"} <= set(data)
    assert {"devices", "effects", "integrations"} <= set(data)
    brightness = data["effects"]["rainbow"]["schema"]["properties"]["brightness"]
    assert brightness["maximum"] == 1.0
    assert os.path.getsize(out) > 0


def test_schemas_endpoints_serve_all_kinds_and_one_kind() -> None:
    import asyncio

    from aiohttp.test_utils import make_mocked_request

    from ledfx.api.schemas import SchemasEndpoint
    from ledfx.api.schemas_kind import SchemasKindEndpoint

    everything = asyncio.run(
        SchemasEndpoint(None).get(make_mocked_request("GET", "/api/schemas"))
    )
    assert "virtuals" in json.loads(everything.text or "")

    def kind(name: str) -> dict[str, object]:
        request = make_mocked_request(
            "GET", f"/api/schemas/{name}", match_info={"kind": name}
        )
        response = asyncio.run(SchemasKindEndpoint(None).get(request))
        return json.loads(response.text or "")

    one = kind("virtuals")
    assert list(one) == ["virtuals"]
    assert "transition_mode" in json.dumps(one)
    effects, devices = kind("effects")["effects"], kind("devices")["devices"]
    assert isinstance(effects, dict) and "rainbow" in effects
    assert isinstance(devices, dict) and "dummy" in devices
    assert kind("nope")["status"] == "failed"
