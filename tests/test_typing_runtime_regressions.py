"""Behavioral regressions exposed by existing Pyrefly diagnostics."""

import asyncio
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from aiohttp import MultipartWriter, WSMessage, WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from pydantic import BaseModel, Field

from ledfx.api import RestEndpoint
from ledfx.api.assets import AssetsEndpoint
from ledfx.api.config import ConfigEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint
from ledfx.api.websocket import WebsocketConnection, websocket_handlers
from ledfx.configuration.fields import X_OMIT_DEFAULT, CoercedFloat, CoercedInt
from ledfx.configuration.migrations.legacy import legacy_to_v1
from ledfx.configuration.paths import load_logger
from ledfx.configuration.plugin import PluginConfig
from ledfx.configuration.randomize import randomize_effect_config
from ledfx.devices import Device, Devices
from ledfx.integrations.qlc import QLCWebsocketClient
from ledfx.utils import WLED, get_local_ip


async def test_missing_route_argument_returns_bad_request() -> None:
    class NeedsId(RestEndpoint):
        async def get(self, resource_id: str) -> web.Response:
            return web.json_response({"id": resource_id})

    endpoint = NeedsId(MagicMock())
    with pytest.raises(web.HTTPBadRequest):
        await endpoint.handler(make_mocked_request("GET", "/"))


async def test_config_body_read_error_returns_error_response() -> None:
    request = MagicMock()
    request.json = AsyncMock(side_effect=RuntimeError("body read failed"))
    response = await ConfigEndpoint(MagicMock()).put(request)
    assert response.status == 500
    assert json.loads(response.text or "{}")["status"] == "failed"


async def test_nested_multipart_upload_is_rejected_cleanly() -> None:
    endpoint = AssetsEndpoint(MagicMock())
    app = web.Application()
    app.router.add_post("/assets", endpoint.post)
    nested = MultipartWriter("mixed")
    nested.append(b"image contents")
    multipart = MultipartWriter("form-data")
    multipart.append(nested)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/assets", data=multipart)
        assert response.status == 400
        assert (await response.json())["status"] == "failed"


@pytest.mark.parametrize("method", ["put", "post"])
async def test_randomize_skips_unsupported_schema_without_reusing_values(
    method: str,
) -> None:
    class DemoEffectConfig(PluginConfig):
        text: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
        flag: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
        other_text: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
        unbounded: CoercedFloat | None = Field(
            None, json_schema_extra={X_OMIT_DEFAULT: True}
        )
        count: CoercedInt | None = Field(
            None, ge=2, le=5, json_schema_extra={X_OMIT_DEFAULT: True}
        )

    ledfx = MagicMock()
    virtual = ledfx.virtuals.get.return_value
    effect = MagicMock()
    effect.type = "test-effect"
    effect.name = "Test Effect"
    effect.config = DemoEffectConfig()
    virtual.active_effect = effect
    ledfx.config_store.read_only = False
    ledfx.virtuals.patch_effect.return_value = virtual
    ledfx.virtuals.set_effect.return_value = virtual
    ledfx.effects.types.return_value = ["test-effect"]
    ledfx.effects.get_class.return_value.config_model.return_value = DemoEffectConfig
    request = MagicMock()
    request.json = AsyncMock(
        return_value={"config": "RANDOMIZE", "type": "test-effect"}
    )
    endpoint = EffectsEndpoint(ledfx)
    if method == "put":
        response = await endpoint.put("virtual", request)
        generated = ledfx.virtuals.patch_effect.call_args.args[1]
    else:
        response = await endpoint.post("virtual", request)
        generated = ledfx.virtuals.set_effect.call_args.args[2]
    assert response.status == 200
    values = generated.as_dict()
    assert set(values) == {"flag", "count"}
    assert isinstance(values["flag"], bool)
    assert isinstance(values["count"], int) and 2 <= values["count"] <= 5


class _Bounded(BaseModel):
    one: CoercedInt = Field(1, gt=0, lt=2)  # 1 is the only integer
    empty: CoercedInt | None = Field(None, gt=0, lt=1)  # no integer: skipped
    ratio: CoercedFloat = Field(0.5, gt=0.0, lt=1.0)


@pytest.mark.parametrize("pick", ["low", "high"])
def test_randomize_honours_exclusive_bounds(
    monkeypatch: pytest.MonkeyPatch, pick: str
) -> None:
    def endpoint(low: float, high: float) -> float:
        return low if pick == "low" else high

    # uniform() may return either endpoint; an exclusive one must not be used.
    monkeypatch.setattr("ledfx.configuration.randomize.random.uniform", endpoint)
    for _ in range(20):
        result = randomize_effect_config(_Bounded, ())
        assert set(result) == {"one", "ratio"} and result["one"] == 1
        ratio = result["ratio"]
        assert isinstance(ratio, float) and 0.0 < ratio < 1.0


def test_migration_discards_effect_without_type_and_keeps_virtual() -> None:
    load_logger()
    original: dict[str, object] = {
        "virtuals": [{"id": "broken", "effect": {"config": dict[str, object]()}}]
    }
    result = legacy_to_v1(original)
    assert result["virtuals"] == [{"id": "broken", "auto_generated": False}]
    assert original["virtuals"] == [
        {"id": "broken", "effect": {"config": {}}}
    ]  # the input is not mutated


def test_scene_migration_handles_empty_and_mixed_legacy_scenes() -> None:
    load_logger()
    original: dict[str, object] = {
        "virtuals": [{"id": "v1"}],
        "scenes": {
            "empty": {"name": "Empty"},
            "old": {"name": "Old", "displays": {"v1": dict[str, object]()}},
            "current": {"name": "Current", "virtuals": {"v1": dict[str, object]()}},
        },
    }
    result = legacy_to_v1(original)
    scenes = result["scenes"]
    assert isinstance(scenes, dict)
    assert scenes["empty"] == {"name": "Empty", "virtuals": {}}
    assert scenes["old"]["virtuals"] == {"v1": {}}
    assert scenes["current"]["virtuals"] == {"v1": {}}


def test_ip_detection_survives_socket_creation_failure() -> None:
    with (
        patch("ledfx.utils.socket.socket", side_effect=OSError("no sockets")),
        patch("ledfx.utils.socket.gethostbyname", side_effect=socket.gaierror()),
    ):
        assert get_local_ip() == "127.0.0.1"


async def test_qlc_dispatches_each_message_to_the_supplied_callback() -> None:
    client = object.__new__(QLCWebsocketClient)
    ws = MagicMock()
    first = WSMessage(WSMsgType.TEXT, "first", "")
    second = WSMessage(WSMsgType.TEXT, "second", "")
    ws.receive = AsyncMock(
        side_effect=[first, second, WSMessage(WSMsgType.CLOSED, None, "")]
    )
    client.websocket = ws
    callback = MagicMock()

    await client.read(callback)

    assert [call.args[0] for call in callback.call_args_list] == [first, second]
    assert ws.receive.await_count == 3


async def test_wled_without_address_fails_before_discovery() -> None:
    import ledfx.devices.wled  # noqa: F401 - registers the wled type

    devices = object.__new__(Devices)
    devices._ledfx = MagicMock()
    devices._cls = Device
    with pytest.raises(ValueError, match="ip_address"):
        await devices.add_new_device("wled", {"name": "Missing address"})


@pytest.mark.parametrize("payload", ["[]", '"text"', "42"])
async def test_websocket_rejects_non_object_json_without_handler_crash(
    payload: str,
) -> None:
    ledfx = MagicMock()
    ledfx.loop = asyncio.get_running_loop()
    connection = WebsocketConnection(ledfx)
    ws = MagicMock()
    ws.prepare = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    # A valid frame first, so a stale ID from it would be reused on failure.
    ws.receive = AsyncMock(
        side_effect=[
            WSMessage(WSMsgType.TEXT, '{"id": 7, "type": "noop_test"}', ""),
            WSMessage(WSMsgType.TEXT, payload, ""),
        ]
    )
    connection.send_error = MagicMock()
    noop = MagicMock()
    request = MagicMock(remote="127.0.0.1")
    with (
        patch("ledfx.api.websocket.web.WebSocketResponse", return_value=ws),
        patch.dict(websocket_handlers, {"noop_test": noop}),
    ):
        await connection.handle(request)
    ws.close.assert_awaited_once()
    noop.assert_called_once()
    connection.send_error.assert_not_called()


async def test_wled_power_state_awaits_before_indexing() -> None:
    wled = WLED("127.0.0.1")
    with patch.object(WLED, "get_state", AsyncMock(return_value={"on": True})):
        assert await wled.get_power_state() is True


def test_config_directory_failure_logs_before_logger_setup(tmp_path: Path) -> None:
    # Runs in a fresh interpreter: __main__ calls this before load_logger().
    blocker = tmp_path / "file"
    blocker.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ledfx.configuration.paths as c; c.ensure_config_directory(__import__('sys').argv[1])",
            str(blocker / "config"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "NameError" not in result.stderr


def test_transition_mode_none_is_callable_mid_transition() -> None:
    from ledfx.transitions import Transitions

    transitions = Transitions(10)
    frame = np.zeros((10, 3))
    transitions["None"](transitions, frame, np.ones((10, 3)), 0.5)
    assert not frame.any()


def test_effect_update_config_stores_coerced_values() -> None:
    from ledfx.effects.fire import Fire

    effect = Fire(MagicMock(), {})
    effect.update_config({"intensity": 12.7, "color_shift": "0.5"})
    assert effect.config.intensity == 12
    assert effect.config.color_shift == 0.5


def test_number_switching_from_time_to_bpm_formats_a_number() -> None:
    from ledfx.effects.number import Number

    effect = Number(MagicMock(), {"value_source": "Time (HH:MM)"})
    effect.update_time_hhmm()
    effect.update_config({"value_source": "BPM"})
    assert effect._format_number(effect.display_value, 3, 2) == "000.00"


def test_gif_reprocessing_replaces_frames() -> None:
    from PIL import Image

    from ledfx.effects.gifplayer import GifPlayer

    player = object.__new__(GifPlayer)
    player.frames = []
    player.r_width, player.r_height = 4, 2
    player.resize_method = Image.Resampling.NEAREST
    for _ in range(2):
        gif = Image.new("RGBA", (8, 8))
        player.gif = MagicMock(
            size=gif.size, n_frames=3, convert=MagicMock(return_value=gif)
        )
        player.process_gif()
    assert len(player.frames) == 3


async def test_launchpad_segments_skipped_without_device() -> None:
    from ledfx.devices.launchpad import LaunchpadDevice

    device = object.__new__(LaunchpadDevice)
    device._config = LaunchpadDevice.config_model().model_construct(
        create_segments=True
    )
    device.lp = None
    with patch.object(LaunchpadDevice, "set_class"):
        await device.add_postamble()


def test_serial_device_reopens_after_deactivate() -> None:
    import serial

    from ledfx.devices import Device
    from ledfx.devices.adalight import AdalightDevice

    device = object.__new__(AdalightDevice)
    # SerialDevice owns output across open/close, just as Device.__init__ sets up.
    device._output_lock = threading.RLock()
    device.serial = None
    device.com_port, device.baudrate = "loop://", 115200
    with (
        patch("ledfx.devices.serial.Serial", side_effect=serial.serial_for_url),
        patch.object(Device, "activate"),
        patch.object(Device, "deactivate"),
    ):
        device.activate()
        device.deactivate()
        device.activate()
    assert device.serial is not None
    assert device.serial.is_open
    device.serial.close()


def test_osc_device_deactivates_twice() -> None:
    from ledfx.devices import Device
    from ledfx.devices.osc import OSCServerDevice

    device = OSCServerDevice(
        MagicMock(),
        OSCServerDevice.Config.model_validate(
            {"name": "osc", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    with patch.object(Device, "deactivate"):
        device.deactivate()
        device.deactivate()
    assert device._sender is None


def test_wled_sync_mode_change_activates_new_subdevice() -> None:
    from ledfx.devices.wled import WLEDDevice

    device = WLEDDevice(
        MagicMock(),
        WLEDDevice.Config.model_validate(
            {
                "sync_mode": "E131",
                "name": "wled",
                "ip_address": "10.0.0.2",
                "pixel_count": 10,
                "refresh_rate": 60,
            }
        ),
    )
    device._destination = "10.0.0.2"
    device.subdevice = MagicMock()
    device.activate()
    new_sender = MagicMock()
    with patch.dict(WLEDDevice.SYNC_MODES, {"E131": new_sender}):
        device.setup_subdevice()
    new_sender.return_value.activate.assert_called_once()


async def test_unconnected_mqtt_hass_can_be_deleted() -> None:
    from ledfx.integrations.mqtt_hass import MQTT_HASS

    integration = object.__new__(MQTT_HASS)
    integration._active = False
    integration._client = None
    await integration.on_delete()


async def test_qlc_widgets_without_connection_and_prefix_parsing() -> None:
    from ledfx.integrations.qlc import QLC

    integration = object.__new__(QLC)
    integration._active = False
    integration._client = None
    assert await integration.get_widgets() == []

    offline = object.__new__(QLCWebsocketClient)
    offline.websocket = None
    assert await offline.query("QLC+API|getWidgetsList") == ""

    integration._client = MagicMock()
    integration._client.query = AsyncMock(
        side_effect=["getWidgetsList|1|Trig", "getWidgetType|Audio Triggers"]
    )
    assert await integration.get_widgets() == [("1", "Audio Triggers", "Trig")]


def test_e131_waits_for_destination_before_starting_sender() -> None:
    from ledfx.devices.e131 import E131Device

    device = E131Device(
        MagicMock(),
        E131Device.config_model().model_validate(
            {"name": "e131", "ip_address": "10.0.0.3"}
        ),
    )
    with patch("ledfx.devices.e131.E131Sender") as sender:
        device.activate()
    sender.assert_not_called()
    assert device._destination is None
    assert device._ledfx.loop.call_soon_threadsafe.called
    device.deactivate()


def test_update_checker_is_a_class() -> None:
    # A decorator orphaned by a deleted function once wrapped it in lru_cache.
    from ledfx.utils import UpdateChecker

    assert isinstance(UpdateChecker, type)
