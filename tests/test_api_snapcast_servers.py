"""Unit tests for Snapcast server management API endpoints and device listing."""

import json
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.snapcast_server import SnapcastServerEndpoint
from ledfx.api.snapcast_servers import SnapcastServersEndpoint
from ledfx.effects.audio import (
    SNAPCAST_SERVERS,
    AudioInputSource,
    network_audio_source,
)


class MockLedFx:
    def __init__(self, servers=None):
        self.config = {"snapcast_servers": servers or {}}
        self.config_dir = "/tmp/test_snapcast"
        self._load_snapcast_servers = MagicMock()


LIVING_ROOM = {"host": "192.168.1.20", "port": 1704, "client_name": "LedFx"}


@pytest.fixture
async def api():
    """Serve both endpoints against a MockLedFx with one server configured."""
    mock_ledfx = MockLedFx({"living-room": dict(LIVING_ROOM)})
    app = web.Application()
    app.router.add_route(
        "*",
        "/api/snapcast/servers",
        SnapcastServersEndpoint(mock_ledfx).handler,
    )
    app.router.add_route(
        "*",
        "/api/snapcast/servers/{server_id}",
        SnapcastServerEndpoint(mock_ledfx).handler,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    with (
        patch("ledfx.api.snapcast_servers.save_config") as save_new,
        patch("ledfx.api.snapcast_server.save_config") as save_existing,
    ):
        yield client, mock_ledfx, save_new, save_existing
    await client.close()


async def send(client, method, path, payload):
    resp = await getattr(client, method)(
        path,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 200
    return await resp.json()


class TestListAndAdd:
    async def test_get(self, api):
        client, *_ = api
        resp = await client.get("/api/snapcast/servers")
        data = await resp.json()
        assert data == {"servers": {"living-room": LIVING_ROOM}}

    async def test_add_with_defaults(self, api):
        client, ledfx, save, _ = api
        data = await send(
            client,
            "post",
            "/api/snapcast/servers",
            {"id": "Kitchen", "host": " snapserver.local "},
        )
        assert data["status"] == "success"
        assert ledfx.config["snapcast_servers"]["kitchen"] == {
            "host": "snapserver.local",
            "port": 1704,
            "client_name": "LedFx",
        }
        save.assert_called_once()
        ledfx._load_snapcast_servers.assert_called_once()

    async def test_add_with_all_fields(self, api):
        client, ledfx, *_ = api
        await send(
            client,
            "post",
            "/api/snapcast/servers",
            {
                "id": "garage",
                "host": "10.0.0.5",
                "port": 1705,
                "client_name": "Garage LEDs",
            },
        )
        assert ledfx.config["snapcast_servers"]["garage"] == {
            "host": "10.0.0.5",
            "port": 1705,
            "client_name": "Garage LEDs",
        }

    @pytest.mark.parametrize(
        "payload, reason",
        [
            ({"host": "10.0.0.5"}, "'id'"),
            ({"id": "x"}, "'host'"),
            ({"id": "x", "host": ""}, "empty"),
            ({"id": "x", "host": "tcp://10.0.0.5"}, "not a URL"),
            ({"id": "x", "host": "bad host"}, "invalid characters"),
            ({"id": "x", "host": "h", "port": 70000}, "out of range"),
            ({"id": "x", "host": "h", "port": "1704"}, "integer"),
            ({"id": "x", "host": "h", "client_name": " "}, "client_name"),
        ],
    )
    async def test_add_rejects_invalid(self, api, payload, reason):
        client, ledfx, save, _ = api
        data = await send(client, "post", "/api/snapcast/servers", payload)
        assert data["status"] == "failed"
        assert reason in data["payload"]["reason"]
        assert list(ledfx.config["snapcast_servers"]) == ["living-room"]
        save.assert_not_called()

    async def test_add_duplicate(self, api):
        client, *_ = api
        data = await send(
            client,
            "post",
            "/api/snapcast/servers",
            {"id": "living-room", "host": "10.0.0.9"},
        )
        assert data["status"] == "failed"
        assert "already exists" in data["payload"]["reason"]

    async def test_add_invalid_json(self, api):
        client, *_ = api
        resp = await client.post("/api/snapcast/servers", data="{nope")
        data = await resp.json()
        assert data["status"] == "failed"


class TestUpdateAndDelete:
    async def test_update(self, api):
        client, ledfx, _, save = api
        with patch("ledfx.api.snapcast_server._sync_active_stream") as sync:
            data = await send(
                client,
                "put",
                "/api/snapcast/servers/living-room",
                {"port": 1800},
            )
        assert data["status"] == "success"
        assert ledfx.config["snapcast_servers"]["living-room"] == {
            **LIVING_ROOM,
            "port": 1800,
        }
        save.assert_called_once()
        sync.assert_called_once_with(ledfx, "living-room", restart=True)

    async def test_update_without_change_keeps_stream(self, api):
        client, *_ = api
        with patch("ledfx.api.snapcast_server._sync_active_stream") as sync:
            await send(
                client,
                "put",
                "/api/snapcast/servers/living-room",
                {"host": "192.168.1.20"},
            )
        sync.assert_not_called()

    async def test_update_rejects_invalid(self, api):
        client, ledfx, _, save = api
        data = await send(
            client,
            "put",
            "/api/snapcast/servers/living-room",
            {"host": "a b"},
        )
        assert data["status"] == "failed"
        assert ledfx.config["snapcast_servers"]["living-room"] == LIVING_ROOM
        save.assert_not_called()

    async def test_update_unknown(self, api):
        client, *_ = api
        data = await send(
            client, "put", "/api/snapcast/servers/nope", {"port": 1}
        )
        assert data["status"] == "failed"
        assert "not found" in data["payload"]["reason"]

    async def test_delete(self, api):
        client, ledfx, _, save = api
        with patch("ledfx.api.snapcast_server._sync_active_stream") as sync:
            resp = await client.delete("/api/snapcast/servers/living-room")
        data = await resp.json()
        assert data["status"] == "success"
        assert ledfx.config["snapcast_servers"] == {}
        save.assert_called_once()
        sync.assert_called_once_with(ledfx, "living-room", restart=False)

    async def test_delete_unknown(self, api):
        client, *_ = api
        resp = await client.delete("/api/snapcast/servers/nope")
        data = await resp.json()
        assert data["status"] == "failed"


class TestDeviceListing:
    @pytest.fixture(autouse=True)
    def servers(self):
        saved = dict(SNAPCAST_SERVERS)
        SNAPCAST_SERVERS.clear()
        SNAPCAST_SERVERS["living-room"] = dict(LIVING_ROOM)
        yield
        SNAPCAST_SERVERS.clear()
        SNAPCAST_SERVERS.update(saved)

    def test_configured_server_is_an_input_device(self):
        devices = AudioInputSource.input_devices()
        matches = [
            idx
            for idx, name in devices.items()
            if name == "SNAPCAST: living-room"
        ]
        assert len(matches) == 1
        device = AudioInputSource.query_devices()[matches[0]]
        assert device["snapcast_config"] == LIVING_ROOM

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("SNAPCAST: living-room", ("Snapcast", "living-room")),
            ("SENDSPIN: kitchen", ("Sendspin", "kitchen")),
            ("ALSA: hw:0", None),
            (None, None),
        ],
    )
    def test_network_audio_source(self, name, expected):
        assert network_audio_source(name) == expected


class TestSelectDevice:
    async def test_selecting_device_reconciles_always_on(self):
        """PUT /api/audio/devices starts an always-on network source even when
        no effect is using audio yet (ledfx.audio is None)."""
        from ledfx.api.audio_devices import AudioDevicesEndpoint

        ledfx = MagicMock()
        ledfx.audio = None
        ledfx.config = {"audio": {}}
        app = web.Application()
        app.router.add_route(
            "*", "/api/audio/devices", AudioDevicesEndpoint(ledfx).handler
        )
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            with (
                patch("ledfx.api.audio_devices.save_config"),
                patch.object(
                    AudioInputSource, "valid_device_indexes", return_value=(3,)
                ),
                patch.object(
                    AudioInputSource,
                    "input_devices",
                    return_value={3: "SNAPCAST: living-room"},
                ),
            ):
                data = await send(
                    client, "put", "/api/audio/devices", {"audio_device": 3}
                )
        finally:
            await client.close()

        assert data["status"] == "success"
        assert ledfx.config["audio"]["audio_device_name"] == (
            "SNAPCAST: living-room"
        )
        ledfx.reconcile_snapcast_always_on_runtime.assert_called_once()
        ledfx.reconcile_sendspin_always_on_runtime.assert_called_once()
