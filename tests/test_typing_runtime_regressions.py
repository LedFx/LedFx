"""Behavioral regressions exposed by existing Pyrefly diagnostics."""

import asyncio
import json
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from aiohttp import MultipartWriter, WSMessage, WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from ledfx.api import RestEndpoint
from ledfx.api.assets import AssetsEndpoint
from ledfx.api.config import ConfigEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint, randomize_effect_config
from ledfx.api.websocket import WebsocketConnection, websocket_handlers
from ledfx.config import load_logger, migrate_config
from ledfx.devices import Devices
from ledfx.integrations.qlc import QLCWebsocketClient
from ledfx.utils import get_local_ip


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
    with patch("ledfx.api.virtual_effects.save_config"):
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
    original = {
        "virtuals": [{"id": "broken", "effect": {"config": dict[str, object]()}}]
    }
    with patch("ledfx.effects.Effects") as effects:
        effects.return_value.classes.return_value = dict[str, object]()
        result = migrate_config(original)
    assert result["virtuals"] == [{"id": "broken", "auto_generated": False}]
    assert "effect" in original["virtuals"][0]


def test_scene_migration_handles_empty_and_mixed_legacy_scenes() -> None:
    load_logger()
    original = {
        "virtuals": [{"id": "v1"}],
        "scenes": {
            "empty": {"name": "Empty"},
            "old": {"name": "Old", "displays": {"v1": dict[str, object]()}},
            "current": {"name": "Current", "virtuals": {"v1": dict[str, object]()}},
        },
    }
    with patch("ledfx.effects.Effects") as effects:
        effects.return_value.classes.return_value = dict[str, object]()
        result = migrate_config(original)
    assert result["scenes"]["empty"] == {"name": "Empty", "virtuals": {}}
    assert result["scenes"]["old"]["virtuals"] == {"v1": {}}
    assert result["scenes"]["current"]["virtuals"] == {"v1": {}}


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
