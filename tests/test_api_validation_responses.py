"""Bad API input gets a 400 validation error or a clear failed reason, never
the catch-all 202 or a 500, and a rejected request changes nothing."""

import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from pydantic import ValidationError

import ledfx.devices.adalight
import ledfx.devices.dummy
import ledfx.devices.e131  # noqa: F401 - registers the e131 device
from ledfx.api import RestEndpoint
from ledfx.api.assets import AssetsEndpoint
from ledfx.api.assets_download import AssetsDownloadEndpoint
from ledfx.api.assets_thumbnail import AssetsThumbnailEndpoint
from ledfx.api.audio_devices import AudioDevicesEndpoint
from ledfx.api.colors import ColorEndpoint
from ledfx.api.config import ConfigEndpoint
from ledfx.api.device import DeviceEndpoint
from ledfx.api.devices import DevicesEndpoint
from ledfx.api.find_lifx import FindLifxEndpoint
from ledfx.api.find_openrgb import FindOpenRGBDevicesEndpoint
from ledfx.api.get_gif_frames import GetGifFramesEndpoint
from ledfx.api.integrations import IntegrationsEndpoint
from ledfx.api.log import LogWebsocket
from ledfx.api.ping import InfoEndpoint as PingEndpoint
from ledfx.api.playlists import PlaylistsEndpoint
from ledfx.api.presets import PresetsEndpoint
from ledfx.api.scenes import ScenesEndpoint
from ledfx.api.sendspin_servers import SendspinServersEndpoint
from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint as VirtualEffectsEndpoint
from ledfx.api.virtual_effects_delete import EffectsEndpoint as EffectsDeleteEndpoint
from ledfx.api.virtual_presets import VirtualPresetsEndpoint
from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.configuration.models import Preset, Segment, VirtualEntry
from ledfx.devices import Device, Devices, SerialDevice
from ledfx.devices.dummy import DummyDevice
from ledfx.integrations.spotify import Spotify
from ledfx.playlists import PlaylistManager
from ledfx.scenes import Scenes
from ledfx.utils import BaseRegistry, UserDefaultCollection
from ledfx.virtuals import Virtual, Virtuals
from tests.test_utilities.fake_ledfx import fake_ledfx


def _request(method: str, body: object = None, raw: str | None = None) -> MagicMock:
    request = MagicMock(spec=web.Request, method=method, path="/api/test")
    request.headers = dict[str, str]()
    request.has_body = True
    request.content_type = "application/json"
    if raw is None:
        request.json = AsyncMock(return_value=body)
    else:
        request.json = AsyncMock(side_effect=json.JSONDecodeError("bad", raw, 0))
        request.text = AsyncMock(return_value=raw)
    return request


async def _call(
    endpoint: RestEndpoint,
    method: str,
    body: object = None,
    raw: str | None = None,
    **match_info: str,
):
    """Go through RestEndpoint.handler, like a real request."""
    request = _request(method, body, raw)
    request.match_info = match_info
    response = await endpoint.handler(request)
    return response.status, json.loads(response.text or "")


def _reason(body: dict[str, dict[str, str]]) -> str:
    return body["payload"]["reason"]


def _devices(ledfx: MagicMock) -> Devices:
    devices = object.__new__(Devices)
    devices._ledfx = ledfx
    devices._cls = Device
    ledfx.devices = devices
    return devices


class _Virtual:
    """Just enough of a Virtual for the endpoints; activating can fail."""

    def __init__(self, fail_activate: bool = False) -> None:
        self.id = "v1"
        self._active = False
        self._fail_activate = fail_activate
        self._active_effect: object = None
        self.active_effect = MagicMock()
        self.active_effect.type = "singleColor"
        self.active_effect.config.as_dict.return_value = dict[str, object]()
        self.entry: object = None
        self.update_segments = MagicMock()
        self.segments: list[object] = []
        self.streaming = False
        self.set_effect = MagicMock()
        self.update_effect_config = MagicMock()
        self.get_effects_config = MagicMock(return_value=dict[str, object]())

    def validate_segment(self, segment: object) -> object:
        return segment

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        if self._fail_activate:
            raise RuntimeError("Virtual v1: Cannot activate, no configured effect")
        self._active = value


def _entry() -> VirtualEntry:
    return VirtualEntry.model_validate(
        {"id": "v1", "config": {"name": "v1"}, "last_effect": "singleColor"}
    )


@pytest.fixture(autouse=True)
def _restore_virtuals_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    # _with_virtual replaces the singleton; this restores it at teardown.
    monkeypatch.setattr(Virtuals, "_instance", Virtuals._instance)


def _with_virtual(virtual: _Virtual | None = None) -> tuple[MagicMock, _Virtual]:
    """A fake core whose real Virtuals manager holds one fake virtual, "v1"."""
    ledfx = fake_ledfx()
    virtual = virtual or _Virtual()
    Virtuals._instance = None
    ledfx.virtuals = Virtuals(ledfx)
    ledfx.virtuals._virtuals["v1"] = virtual
    ledfx.effects.types.return_value = ["singleColor"]
    return ledfx, virtual


# The three reported bugs


async def test_device_without_name_is_a_validation_error() -> None:
    ledfx = fake_ledfx()
    _devices(ledfx)
    body = {"type": "dummy", "config": {"pixel_count": 10}}
    status, response = await _call(DevicesEndpoint(ledfx), "POST", body)
    assert status == 400
    assert [e["loc"] for e in response["errors"]] == [["name"]]
    assert not ledfx.config.devices


@pytest.fixture
def no_serial_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    import serial.tools.list_ports

    monkeypatch.setattr(serial.tools.list_ports, "comports", list)


async def test_creating_a_device_on_an_absent_port_is_a_400(
    no_serial_ports: None,
) -> None:
    ledfx = fake_ledfx()
    _devices(ledfx)
    config = {"name": "Strip", "pixel_count": 10, "com_port": "/dev/absent"}
    body = {"type": "adalight", "config": config}
    status, response = await _call(DevicesEndpoint(ledfx), "POST", body)
    assert status == 400
    assert [e["loc"] for e in response["errors"]] == [["com_port"]]


def _serial_device(ledfx: MagicMock, com_port: str) -> SerialDevice:
    from ledfx.utils import RegistryLoader

    config = {"name": "Strip", "pixel_count": 10, "com_port": com_port}
    device = RegistryLoader(ledfx, Device, "ledfx.devices").create(
        type="adalight", id="strip", config=config, ledfx=ledfx
    )  # a load: the stored port is not checked
    assert isinstance(device, SerialDevice)
    ledfx.devices.get = MagicMock(return_value=device)
    return device


@pytest.mark.parametrize("full_body", [False, True], ids=["partial", "full"])
async def test_moving_a_device_to_an_absent_port_is_a_400(
    no_serial_ports: None, full_body: bool
) -> None:
    ledfx = fake_ledfx()
    device = _serial_device(ledfx, "")
    config = device.config.as_dict() if full_body else {}
    body = {"config": {**config, "com_port": "/dev/absent"}}
    status, response = await _call(
        DeviceEndpoint(ledfx), "PUT", body, device_id="strip"
    )
    assert status == 400
    assert [e["loc"] for e in response["errors"]] == [["com_port"]]
    assert device.config.com_port == ""


async def test_moving_a_device_to_a_present_port_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import types

    import serial.tools.list_ports

    ports = [types.SimpleNamespace(device="/dev/ttyUSB0")]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)
    ledfx = fake_ledfx()
    device = _serial_device(ledfx, "")
    body = {"config": {"com_port": "/dev/ttyUSB0"}}
    status, _ = await _call(DeviceEndpoint(ledfx), "PUT", body, device_id="strip")
    assert status == 200
    assert device.config.com_port == "/dev/ttyUSB0"


@pytest.mark.parametrize("full_body", [False, True], ids=["partial", "full"])
async def test_renaming_a_device_whose_port_is_unplugged_succeeds(
    no_serial_ports: None, full_body: bool
) -> None:
    # Only a com_port the request changes is checked, not the stored one. The
    # frontend's edit dialog sends the whole stored config with the new name.
    stored = {"name": "Strip", "pixel_count": 10, "com_port": "/dev/unplugged"}
    ledfx = fake_ledfx(
        {"devices": [{"id": "strip", "type": "adalight", "config": stored}]}
    )
    device = _serial_device(ledfx, "/dev/unplugged")
    entry = ledfx.config_store.device_entry("strip")
    assert entry is not None
    config = device.config.as_dict() if full_body else {}
    body = {"config": {**config, "name": "Renamed"}}
    status, _ = await _call(DeviceEndpoint(ledfx), "PUT", body, device_id="strip")
    assert status == 200
    assert device.config.name == "Renamed"
    assert device.config.com_port == "/dev/unplugged"
    assert entry.config["name"] == "Renamed"
    ledfx.config_store.request_save.assert_called()


async def test_comports_lists_only_the_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    import serial.tools.list_ports

    from ledfx.api.com_ports import InfoEndpoint as ComPortsEndpoint

    ports = [types.SimpleNamespace(device=d) for d in ("/dev/ttyUSB0", "COM3")]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)
    status, body = await _call(ComPortsEndpoint(fake_ledfx()), "GET")
    assert (status, body) == (200, ["/dev/ttyUSB0", "COM3"])  # no "" (none)


async def test_integration_config_that_is_not_an_object_is_a_validation_error() -> None:
    ledfx = fake_ledfx()
    ledfx.integrations.get_class.return_value = Spotify
    body = {"type": "spotify", "config": 5}
    status, response = await _call(IntegrationsEndpoint(ledfx), "POST", body)
    assert status == 400 and response["errors"][0]["type"] == "model_type"
    ledfx.integrations.create.assert_not_called()


async def test_virtual_put_without_active_points_to_the_config_endpoint() -> None:
    ledfx, _ = _with_virtual()
    status, response = await _call(
        VirtualEndpoint(ledfx), "PUT", {"config": {"name": "x"}}, virtual_id="v1"
    )
    assert status == 200 and "POST it to /api/virtuals" in _reason(response)


# RestEndpoint.handler


@pytest.mark.parametrize("body", [[], "x", 5, None])
async def test_a_body_that_is_not_an_object_is_rejected(body: object) -> None:
    ledfx, virtual = _with_virtual()
    status, response = await _call(VirtualEndpoint(ledfx), "PUT", body, virtual_id="v1")
    assert status == 200
    assert _reason(response) == "Request body must be a JSON object"
    assert virtual.active is False


async def test_colors_delete_still_takes_a_list() -> None:
    ledfx = fake_ledfx()
    user_colors = {"my_red": "#ff0000", "keep": "#00ff00"}
    ledfx.colors = UserDefaultCollection(ledfx, "Colors", {}, user_colors)
    ledfx.gradients = UserDefaultCollection(ledfx, "Gradients", {}, {})
    status, response = await _call(ColorEndpoint(ledfx), "DELETE", ["my_red"])
    assert status == 200 and response["status"] == "success"
    assert user_colors == {"keep": "#00ff00"}
    _, response = await _call(ColorEndpoint(ledfx), "DELETE", {"keep": 1})
    assert _reason(response) == "Request body must be a JSON list of color names"
    assert user_colors == {"keep": "#00ff00"}


async def test_a_get_body_may_still_be_a_list() -> None:
    ledfx = fake_ledfx()
    ledfx.hosts = ["10.0.0.2"]
    ledfx.audio = None
    status, response = await _call(ConfigEndpoint(ledfx), "GET", ["global_brightness"])
    assert status == 200 and set(response) == {"global_brightness"}


async def test_importing_a_non_object_config_says_so() -> None:
    status, response = await _call(ConfigEndpoint(fake_ledfx()), "POST", [1, 2])
    assert (
        status == 200 and _reason(response) == "Imported config is not a LedFx config."
    )


async def test_a_validation_error_with_an_unencodable_input_is_still_a_400() -> None:
    with pytest.raises(ValidationError) as info:
        Preset.model_validate(object())
    response = await VirtualsEndpoint(fake_ledfx()).validation_error(info.value)
    assert response.status == 400
    assert isinstance(json.loads(response.text or "")["errors"][0]["input"], str)


async def test_invalid_json_carries_a_snackbar_reason() -> None:
    ledfx, _ = _with_virtual()
    status, response = await _call(
        VirtualEndpoint(ledfx), "PUT", raw="not json", virtual_id="v1"
    )
    assert status == 400 and _reason(response) == "Request body is not valid JSON"


async def test_an_escaped_validation_error_is_a_400_and_saves_nothing() -> None:
    # Saving a preset named 5: Preset() raises inside the endpoint.
    ledfx, _ = _with_virtual()
    status, response = await _call(
        VirtualPresetsEndpoint(ledfx), "POST", {"name": 5}, virtual_id="v1"
    )
    assert status == 400 and response["errors"][0]["loc"] == ["name"]
    assert not ledfx.config.user_presets


async def test_http_exceptions_are_not_turned_into_202() -> None:
    @BaseRegistry.no_registration
    class Raises(RestEndpoint):
        async def get(self):
            raise web.HTTPBadRequest()

    request = _request("GET")
    request.has_body = False
    request.match_info = dict[str, str]()
    with pytest.raises(web.HTTPBadRequest):
        await Raises(MagicMock()).handler(request)


async def test_a_refused_log_websocket_does_not_break_the_next_one() -> None:
    socket = LogWebsocket(MagicMock(), MagicMock())
    for _ in range(2):
        with pytest.raises(web.HTTPBadRequest):
            await socket.handle(make_mocked_request("GET", "/api/log"))


# Devices


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"type": "dummy", "config": 5}, "Device config must be an object"),
        ({"type": "nope", "config": {}}, "Unknown device type: nope"),
        ({"type": {}, "config": {}}, "Unknown device type"),
        (
            {"type": "dummy", "config": {"name": "d", "ip_address": 5}},
            "ip_address must be a string",
        ),
    ],
)
async def test_bad_device_posts_are_named(body: object, reason: str) -> None:
    ledfx = fake_ledfx()
    _devices(ledfx)
    status, response = await _call(DevicesEndpoint(ledfx), "POST", body)
    assert status == 200 and reason in _reason(response)
    assert not ledfx.config.devices


async def test_an_unresolvable_device_address_is_an_error_not_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledfx = fake_ledfx()
    devices = _devices(ledfx)
    with (
        patch("ledfx.devices.resolve_destination", AsyncMock(side_effect=ValueError)),
        pytest.raises(ValueError, match="Could not resolve nowhere"),
    ):
        await devices.add_new_device("dummy", {"name": "d", "ip_address": "nowhere"})
    # mDNS discovery swallows the exception, so the warning is its only trace.
    assert "nowhere as it could not be resolved" in caplog.text


async def test_a_device_that_fails_to_initialise_is_not_left_registered() -> None:
    ledfx = fake_ledfx()
    devices = _devices(ledfx)
    devices._objects = {}
    failing = AsyncMock(side_effect=ValueError("unreachable"))
    with (
        patch.object(DummyDevice, "async_initialize", failing, create=True),
        pytest.raises(ValueError, match="unreachable"),
    ):
        await devices.add_new_device("dummy", {"name": "d", "pixel_count": 10})
    assert list(devices.values()) == []
    assert not ledfx.config.devices


async def test_shared_ip_checks_use_config_defaults() -> None:
    ledfx = fake_ledfx()
    devices = _devices(ledfx)
    existing = MagicMock(type="e131")
    existing.name = "Old"
    existing.config.ip_address = "10.0.0.5"
    existing.config.universe = 1
    devices._objects = {"old": existing}
    config = {"name": "New", "ip_address": "10.0.0.5", "pixel_count": 10}
    with (
        patch("ledfx.devices.resolve_destination", AsyncMock(return_value="10.0.0.5")),
        pytest.raises(ValueError, match="starting universe with existing device Old"),
    ):
        await devices.add_new_device("e131", config)


async def test_device_update_rejects_a_config_that_is_not_an_object() -> None:
    ledfx = fake_ledfx()
    device = ledfx.devices.get.return_value
    _, response = await _call(
        DeviceEndpoint(ledfx), "PUT", {"config": 5}, device_id="d1"
    )
    assert _reason(response) == "'config' must be an object"
    device.update_config.assert_not_called()


async def test_device_update_errors_are_not_500s_and_name_the_device() -> None:
    ledfx = fake_ledfx()
    ledfx.devices.get.return_value.update_config.side_effect = ValueError("busy")
    status, response = await _call(
        DeviceEndpoint(ledfx), "PUT", {"config": {}}, device_id="d1"
    )
    assert status == 200 and "busy" in _reason(response)
    ledfx.devices.get.return_value = None
    _, response = await _call(DeviceEndpoint(ledfx), "PUT", {}, device_id="d1")
    assert _reason(response) == "Device with ID d1 not found"


async def test_ping_explains_a_device_without_an_address() -> None:
    ledfx = fake_ledfx()
    ledfx.devices.get.return_value.config = object()
    _, response = await _call(PingEndpoint(ledfx), "GET", device_id="d1")
    assert _reason(response) == "Device d1 has no IP address"


# Integrations


async def test_integration_update_cannot_change_type() -> None:
    ledfx = fake_ledfx({"integrations": [{"id": "sp", "type": "spotify"}]})
    ledfx.integrations.get_class.return_value = Spotify
    ledfx.integrations.get.return_value.type = "qlc"
    body = {"id": "sp", "type": "spotify", "config": {"name": "x"}}
    _, response = await _call(IntegrationsEndpoint(ledfx), "POST", body)
    assert "is a qlc integration" in _reason(response)
    ledfx.integrations.destroy.assert_not_called()


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_integration_toggle_and_delete_name_the_missing_id(method: str) -> None:
    ledfx = fake_ledfx()
    ledfx.integrations.get.return_value = None
    endpoint = IntegrationsEndpoint(ledfx)
    _, response = await _call(endpoint, method, {"id": "nope"})
    assert _reason(response) == "Integration with id nope not found"
    _, response = await _call(endpoint, method, {"id": {}})
    assert _reason(response) == "Required attribute 'id' was not provided"


@pytest.mark.parametrize(
    "body", [{"type": {}, "config": {}}, {"id": [], "type": "spotify", "config": {}}]
)
async def test_integration_post_rejects_unhashable_ids(body: object) -> None:
    ledfx = fake_ledfx()
    ledfx.integrations.get_class.return_value = Spotify
    status, response = await _call(IntegrationsEndpoint(ledfx), "POST", body)
    assert status == 200 and response["status"] == "failed"
    ledfx.integrations.create.assert_not_called()
    ledfx.integrations.destroy.assert_not_called()


async def test_integration_info_filter_needs_an_object() -> None:
    ledfx = fake_ledfx()
    request = _request("GET", [])
    request.body_exists = True
    response = await IntegrationsEndpoint(ledfx).get(request)
    assert (
        _reason(json.loads(response.text or "")) == "Request body must be a JSON object"
    )


# Virtuals


async def test_virtual_put_rejects_a_non_bool_active() -> None:
    ledfx, virtual = _with_virtual()
    for active in ("false", 1):
        _, response = await _call(
            VirtualEndpoint(ledfx), "PUT", {"active": active}, virtual_id="v1"
        )
        assert _reason(response) == '"active" must be true or false'
    assert virtual.active is False


async def test_virtual_activation_failure_is_not_a_500() -> None:
    ledfx, virtual = _with_virtual(_Virtual(fail_activate=True))
    entry = _entry()
    virtual.entry = entry
    before = entry.model_dump()
    status, response = await _call(
        VirtualEndpoint(ledfx), "PUT", {"active": False}, virtual_id="v1"
    )
    assert status == 200 and "Cannot activate" in _reason(response)
    ledfx.config_store.request_save.assert_not_called()
    assert entry.model_dump() == before


@pytest.mark.parametrize("failure", ["set_effect", "stale_config"])
async def test_failed_effect_restore_on_activation_is_not_a_202(failure: str) -> None:
    ledfx, virtual = _with_virtual()
    entry = _entry()
    virtual.entry = entry
    before = entry.model_dump()
    virtual.get_effects_config.return_value = {"brightness": 1.0}
    if failure == "set_effect":
        virtual.set_effect.side_effect = ValueError(
            "Cannot activate, no configured device segments"
        )
    else:
        ledfx.effects.create.side_effect = ValidationError.from_exception_data(
            "Preset", [{"type": "missing", "loc": ("name",), "input": {}}]
        )
    status, response = await _call(
        VirtualEndpoint(ledfx), "PUT", {"active": True}, virtual_id="v1"
    )
    assert status == 200 and _reason(response).startswith("Unable to set virtual v1")
    ledfx.config_store.request_save.assert_not_called()
    virtual.update_effect_config.assert_not_called()
    assert entry.model_dump() == before
    assert virtual.active is False


async def test_segment_errors_are_not_500s() -> None:
    ledfx, virtual = _with_virtual()
    virtual.update_segments.side_effect = ValueError("bad")
    segments = [["gap-1", 0, 1, False]]
    status, response = await _call(
        VirtualEndpoint(ledfx), "POST", {"segments": segments}, virtual_id="v1"
    )
    assert status == 200 and "bad" in _reason(response)
    # update_segments restores itself; the endpoint doesn't call it again.
    virtual.update_segments.assert_called_once_with([Segment("gap-1", 0, 1, False)])
    ledfx.config_store.request_save.assert_not_called()


@pytest.mark.parametrize(
    "segments", [5, [5], [[5, 0, 1, False]], [["d1", "0", 1, False]], [["d1", 0]]]
)
def test_malformed_segments_are_a_value_error(segments: object) -> None:
    virtual = object.__new__(Virtual)
    virtual.lock = threading.Lock()
    virtual._ledfx = MagicMock()
    with pytest.raises(ValueError, match="Invalid segment"):
        virtual.update_segments(segments)


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"config": 5}, '"config" must be an object'),
        ({"id": {}, "config": {}}, '"id" must be a string'),
    ],
)
async def test_bad_virtual_posts_are_named(body: object, reason: str) -> None:
    ledfx = fake_ledfx()
    _, response = await _call(VirtualsEndpoint(ledfx), "POST", body)
    assert _reason(response) == reason


async def test_new_virtual_is_validated_before_its_id_is_made() -> None:
    ledfx = fake_ledfx()
    status, response = await _call(VirtualsEndpoint(ledfx), "POST", {"config": {}})
    assert status == 400 and response["errors"][0]["loc"] == ["name"]
    ledfx.virtuals.create.assert_not_called()


# Virtual effects and presets


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"type": 5}, "Unknown effect type: 5"),
        ({"type": "nope"}, "Unknown effect type: nope"),
        ({"type": "singleColor", "config": 5}, "'config' must be an object"),
    ],
)
async def test_bad_effect_posts_are_named(body: object, reason: str) -> None:
    ledfx, _ = _with_virtual()
    _, response = await _call(
        VirtualEffectsEndpoint(ledfx), "POST", body, virtual_id="v1"
    )
    assert _reason(response) == reason
    ledfx.effects.create.assert_not_called()


async def test_effect_put_without_type_updates_the_active_effect() -> None:
    ledfx, virtual = _with_virtual()
    virtual.active_effect.config = dict[str, object]()
    virtual.active_effect.name = "Single Color"
    body = {"config": {"brightness": 0.5}}
    _, response = await _call(
        VirtualEffectsEndpoint(ledfx), "PUT", body, virtual_id="v1"
    )
    assert response["status"] == "success"
    virtual.active_effect.update_config.assert_called_once_with({"brightness": 0.5})
    ledfx.effects.create.assert_not_called()


async def test_effect_put_rejects_a_config_that_is_not_an_object() -> None:
    ledfx, virtual = _with_virtual()
    _, response = await _call(
        VirtualEffectsEndpoint(ledfx), "PUT", {"config": [1]}, virtual_id="v1"
    )
    assert _reason(response) == "'config' must be an object"
    virtual.active_effect.update_config.assert_not_called()


async def test_effect_set_failure_is_not_a_500() -> None:
    ledfx, virtual = _with_virtual()
    virtual.set_effect.side_effect = ValueError("no segments")
    status, response = await _call(
        VirtualEffectsEndpoint(ledfx), "POST", {"type": "singleColor"}, virtual_id="v1"
    )
    assert status == 200 and "no segments" in _reason(response)


async def test_effect_delete_needs_a_string_type() -> None:
    ledfx, _ = _with_virtual()
    _, response = await _call(
        EffectsDeleteEndpoint(ledfx), "POST", {"type": {}}, virtual_id="v1"
    )
    assert _reason(response) == "Required attribute 'type' was not provided"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (
            {"category": "user_presets", "effect_id": {}, "preset_id": "p"},
            "category, effect_id and preset_id must be strings",
        ),
        (
            {"category": "ledfx_presets", "effect_id": "nope", "preset_id": "reset"},
            "Unknown effect type: nope",
        ),
    ],
)
async def test_bad_preset_activations_are_named(body: object, reason: str) -> None:
    ledfx, _ = _with_virtual()
    _, response = await _call(
        VirtualPresetsEndpoint(ledfx), "PUT", body, virtual_id="v1"
    )
    assert _reason(response) == reason
    ledfx.effects.create.assert_not_called()


async def test_renaming_a_preset_of_an_effect_without_user_presets() -> None:
    ledfx = fake_ledfx()
    body = {"category": "user_presets", "preset_id": "p", "name": "n"}
    _, response = await _call(PresetsEndpoint(ledfx), "PUT", body, effect_id="energy")
    assert "Preset p does not exist" in _reason(response)


async def test_preset_delete_needs_a_string_id() -> None:
    ledfx = fake_ledfx({"user_presets": {"energy": {}}})
    body = {"category": "user_presets", "preset_id": ["p"]}
    _, response = await _call(
        PresetsEndpoint(ledfx), "DELETE", body, effect_id="energy"
    )
    assert _reason(response) == 'Required attribute "preset_id" was not provided'


# Scenes


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_scene_requests_without_an_id_are_named(method: str) -> None:
    ledfx = fake_ledfx()
    _, response = await _call(ScenesEndpoint(ledfx), method, {"action": "activate"})
    assert _reason(response) == 'Required attribute "id" was not provided'


async def test_deleting_a_missing_scene_names_it() -> None:
    ledfx = fake_ledfx()
    _, response = await _call(ScenesEndpoint(ledfx), "DELETE", {"id": "nope"})
    assert _reason(response) == "Scene nope does not exist"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"name": 5}, '"name" must be a string'),
        ({"id": 5}, '"id" must be a string'),
        ({"name": "s", "virtuals": []}, '"virtuals" must be an object'),
    ],
)
async def test_bad_scene_posts_are_named(body: object, reason: str) -> None:
    ledfx = fake_ledfx()
    _, response = await _call(ScenesEndpoint(ledfx), "POST", body)
    assert _reason(response) == reason
    assert not ledfx.config.scenes


async def test_scene_delay_is_in_seconds() -> None:
    ledfx = fake_ledfx({"scenes": {"s1": {"name": "S1"}}})
    ledfx.scenes = Scenes(ledfx)
    body = {"id": "s1", "action": "activate_in", "ms": 5}
    _, response = await _call(ScenesEndpoint(ledfx), "PUT", body)
    assert _reason(response) == "Scene S1 will activate in 5s"
    assert ledfx.loop.call_later.call_args.args[0] == 5


# Playlists


def _playlists(ledfx: MagicMock) -> PlaylistsEndpoint:
    ledfx.playlists = PlaylistManager(ledfx)
    return PlaylistsEndpoint(ledfx)


async def test_invalid_playlist_is_a_validation_error() -> None:
    ledfx = fake_ledfx()
    body = {"name": "p", "mode": "sideways"}
    status, response = await _call(_playlists(ledfx), "POST", body)
    assert status == 400
    assert ["mode"] in [e["loc"] for e in response["errors"]]
    assert not ledfx.config.playlists


async def test_playlist_name_must_be_a_string() -> None:
    ledfx = fake_ledfx()
    _, response = await _call(_playlists(ledfx), "POST", {"name": 5})
    assert "'id' or 'name'" in _reason(response)


async def test_invalid_playlist_timing_is_a_validation_error() -> None:
    ledfx = fake_ledfx()
    body = {"action": "start", "id": "p", "timing": {"jitter": "lots"}}
    status, response = await _call(_playlists(ledfx), "PUT", body)
    assert status == 400 and response["errors"]


@pytest.mark.parametrize(
    ("method", "body"),
    [("PUT", {"action": "start", "id": [1]}), ("DELETE", {"id": {}})],
)
async def test_playlist_ids_must_be_strings(method: str, body: object) -> None:
    ledfx = fake_ledfx()
    status, response = await _call(_playlists(ledfx), method, body)
    assert status == 200 and "id required" in _reason(response)


# Assets, images, discovery, audio, Sendspin


async def test_asset_upload_must_be_multipart() -> None:
    request = _request("POST", raw="not json")
    request.match_info = dict[str, str]()
    response = await AssetsEndpoint(fake_ledfx()).handler(request)
    assert (
        _reason(json.loads(response.text or "")) == "Upload must be multipart/form-data"
    )


@pytest.mark.parametrize(
    ("endpoint", "method", "body", "reason"),
    [
        (AssetsEndpoint, "DELETE", {"path": 5}, "No path provided for deletion"),
        (
            AssetsDownloadEndpoint,
            "POST",
            {"path": 5},
            'Required string attribute "path" was not provided',
        ),
        (
            GetGifFramesEndpoint,
            "POST",
            {"path_url": []},
            'Required string attribute "path_url" was not provided',
        ),
        (
            FindLifxEndpoint,
            "POST",
            {"ip_address": 5},
            'Required string attribute "ip_address" was not provided',
        ),
        (
            FindOpenRGBDevicesEndpoint,
            "POST",
            {"port": []},
            "Unable to convert [] to int.",
        ),
        # A JSON Infinity is a float inf: int() raises OverflowError.
        (
            FindOpenRGBDevicesEndpoint,
            "POST",
            {"port": float("inf")},
            "Unable to convert inf to int.",
        ),
        (
            AssetsThumbnailEndpoint,
            "POST",
            {"path": "a.png", "size": float("inf")},
            "Size must be an integer",
        ),
        (
            AudioDevicesEndpoint,
            "PUT",
            {},
            "Required attribute 'audio_device' was not provided",
        ),
    ],
)
async def test_wrong_typed_fields_are_named(
    endpoint: type[RestEndpoint], method: str, body: object, reason: str
) -> None:
    ledfx = fake_ledfx()
    request = _request(method, body)
    request.query = dict[str, str]()
    request.match_info = dict[str, str]()
    response = await endpoint(ledfx).handler(request)
    assert _reason(json.loads(response.text or "")) == reason


async def test_audio_device_index_cannot_be_a_bool() -> None:
    with patch(
        "ledfx.api.audio_devices.AudioInputSource.valid_device_indexes",
        return_value=[0, 1],
    ):
        _, response = await _call(
            AudioDevicesEndpoint(fake_ledfx()), "PUT", {"audio_device": True}
        )
    assert _reason(response) == "Invalid device index [True]"


@patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
async def test_sendspin_server_id_must_be_a_string(_) -> None:
    body = {"id": 5, "server_url": "ws://192.168.1.12:8927/sendspin"}
    _, response = await _call(SendspinServersEndpoint(fake_ledfx()), "POST", body)
    assert _reason(response) == "Required key not provided: 'id'"
