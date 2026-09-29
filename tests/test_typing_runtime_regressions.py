"""Behavioral regressions exposed by existing Pyrefly diagnostics."""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import voluptuous as vol
from aiohttp import MultipartWriter, WSMessage, WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from ledfx.api import RestEndpoint
from ledfx.api.assets import AssetsEndpoint
from ledfx.api.config import ConfigEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint, randomize_effect_config
from ledfx.api.websocket import WebsocketConnection, websocket_handlers
from ledfx.config import load_logger
from ledfx.configuration.migrations.legacy import legacy_to_v1
from ledfx.devices import Devices
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
    schema = vol.Schema(
        {
            vol.Optional("text"): str,
            vol.Optional("flag"): bool,
            vol.Optional("other_text"): str,
            vol.Optional("unbounded"): vol.All(vol.Coerce(float)),
            vol.Optional("count"): vol.All(vol.Coerce(int), vol.Range(min=2, max=5)),
        }
    )
    ledfx = MagicMock()
    virtual = ledfx.virtuals.get.return_value
    effect = MagicMock()
    effect.type = "test-effect"
    effect.name = "Test Effect"
    effect.config = dict[str, object]()
    virtual.active_effect = effect
    ledfx.effects.create.return_value = effect
    ledfx.effects.get_class.return_value.schema.return_value = schema
    request = MagicMock()
    request.json = AsyncMock(
        return_value={"config": "RANDOMIZE", "type": "test-effect"}
    )
    endpoint = EffectsEndpoint(ledfx)
    if method == "put":
        response = await endpoint.put("virtual", request)
        generated = effect.update_config.call_args.args[0]
    else:
        response = await endpoint.post("virtual", request)
        generated = ledfx.effects.create.call_args.kwargs["config"]
    assert response.status == 200
    assert set(generated) == {"flag", "count"}
    assert isinstance(generated["flag"], bool)
    assert 2 <= generated["count"] <= 5


def test_randomize_int_respects_exclusive_bounds() -> None:
    def exclusive(low: int, high: int) -> vol.All:
        return vol.All(
            vol.Coerce(int),
            vol.Range(min=low, max=high, min_included=False, max_included=False),
        )

    schema: dict[object, object] = {
        vol.Optional("one"): exclusive(0, 2),
        vol.Optional("none"): exclusive(0, 1),
    }
    for _ in range(50):
        # 1 is the only integer in (0, 2); (0, 1) holds none, so it is skipped.
        assert randomize_effect_config(schema, ()) == {"one": 1}


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
    devices = object.__new__(Devices)
    devices._ledfx = MagicMock()
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
            "import ledfx.config as c; c.ensure_config_directory(__import__('sys').argv[1])",
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
    config = effect._config or {}
    assert config["intensity"] == 12
    assert config["color_shift"] == 0.5


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
    device._config = {"create_segments": True}
    device.lp = None
    with patch.object(LaunchpadDevice, "set_class"):
        await device.add_postamble()


def test_serial_device_reopens_after_deactivate() -> None:
    import serial

    from ledfx.devices import Device
    from ledfx.devices.adalight import AdalightDevice

    device = object.__new__(AdalightDevice)
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

    device = object.__new__(OSCServerDevice)
    device._device_type = "OSC"
    device._config = {"name": "osc"}
    device._client = None
    with patch.object(Device, "deactivate"):
        device.deactivate()


def test_wled_sync_mode_change_activates_new_subdevice() -> None:
    from ledfx.devices.wled import WLEDDevice

    device = object.__new__(WLEDDevice)
    device._ledfx = MagicMock()
    device._active = True
    device._destination = "10.0.0.2"
    device._config = {
        "sync_mode": "E131",
        "name": "wled",
        "ip_address": "10.0.0.2",
        "pixel_count": 10,
        "refresh_rate": 60,
    }
    device.device_configs = {"E131": {}}
    device.subdevice = MagicMock()
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
    import threading

    from ledfx.devices import NetworkedDevice
    from ledfx.devices.e131 import E131Device

    device = object.__new__(E131Device)
    device._ledfx = MagicMock()
    device.device_lock = threading.Lock()
    device._destination = None
    device._sacn = None
    device._config = {
        "name": "e131",
        "ip_address": "10.0.0.3",
        "universe": 1,
        "universe_end": 1,
        "packet_priority": 100,
    }
    with (
        patch("ledfx.devices.e131.sacn.sACNsender") as sender,
        patch("ledfx.devices.async_fire_and_forget"),
        patch.object(NetworkedDevice, "activate") as base_activate,
    ):
        device.activate()
    sender.assert_not_called()
    base_activate.assert_called_once()
