"""Unit tests for Sendspin server management API endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.sendspin_discover import SendspinDiscoverEndpoint
from ledfx.api.sendspin_server import SendspinServerEndpoint
from ledfx.api.sendspin_servers import SendspinServersEndpoint


class MockLedFx:
    """Minimal LedFx mock for Sendspin API tests."""

    def __init__(self):
        self.config = {"sendspin_servers": {}}
        self.config_dir = "/tmp/test_sendspin"
        self._load_sendspin_servers = MagicMock()


# ---------------------------------------------------------------------------
# GET /api/sendspin/servers
# ---------------------------------------------------------------------------


class TestGetSendspinServers:
    """Test GET /api/sendspin/servers."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MockLedFx()
        app = web.Application()
        endpoint = SendspinServersEndpoint(self.mock_ledfx)
        app.router.add_route("*", "/api/sendspin/servers", endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_get_empty(self, _):
        """Returns empty dict when no servers configured."""
        resp = await self.client.get("/api/sendspin/servers")
        assert resp.status == 200
        data = await resp.json()
        assert data == {"servers": {}}

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_get_with_servers(self, _):
        """Returns all configured servers."""
        self.mock_ledfx.config["sendspin_servers"] = {
            "living-room": {
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "client_name": "LedFx",
            }
        }
        resp = await self.client.get("/api/sendspin/servers")
        assert resp.status == 200
        data = await resp.json()
        assert "living-room" in data["servers"]
        assert data["servers"]["living-room"]["server_url"] == "ws://192.168.1.12:8927/sendspin"

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=False)
    async def test_get_unavailable(self, _):
        """Returns error when Sendspin is not available."""
        resp = await self.client.get("/api/sendspin/servers")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "failed"
        assert "aiosendspin" in data["payload"]["reason"] or "3.12" in data["payload"]["reason"]


# ---------------------------------------------------------------------------
# POST /api/sendspin/servers
# ---------------------------------------------------------------------------


class TestPostSendspinServers:
    """Test POST /api/sendspin/servers."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MockLedFx()
        app = web.Application()
        endpoint = SendspinServersEndpoint(self.mock_ledfx)
        app.router.add_route("*", "/api/sendspin/servers", endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    @patch("ledfx.api.sendspin_servers.save_config")
    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server(self, _, mock_save):
        """Successfully adds a new server."""
        payload = {
            "id": "living-room",
            "server_url": "ws://192.168.1.12:8927/sendspin",
        }
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert "living-room" in self.mock_ledfx.config["sendspin_servers"]
        mock_save.assert_called_once()
        self.mock_ledfx._load_sendspin_servers.assert_called_once()

    @patch("ledfx.api.sendspin_servers.save_config")
    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server_with_client_name(self, _, mock_save):
        """Stores custom client_name when provided."""
        payload = {
            "id": "office",
            "server_url": "wss://192.168.1.55:8927/sendspin",
            "client_name": "LedFx-Office",
        }
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        stored = self.mock_ledfx.config["sendspin_servers"]["office"]
        assert stored["client_name"] == "LedFx-Office"
        assert stored["server_url"] == "wss://192.168.1.55:8927/sendspin"

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server_missing_id(self, _):
        """Rejects request missing 'id'."""
        payload = {"server_url": "ws://192.168.1.12:8927/sendspin"}
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "failed"
        assert "id" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server_missing_url(self, _):
        """Rejects request missing 'server_url'."""
        payload = {"id": "living-room"}
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "failed"
        assert "server_url" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server_invalid_url_scheme(self, _):
        """Rejects URLs that do not start with ws:// or wss://."""
        for bad_url in ["http://example.com", "ftp://example.com", "wss_example"]:
            payload = {"id": "bad", "server_url": bad_url}
            resp = await self.client.post(
                "/api/sendspin/servers",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            data = await resp.json()
            assert data["status"] == "failed", f"Expected failure for url: {bad_url}"
            assert "ws://" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_duplicate_server(self, _):
        """Rejects adding a server with an ID that already exists."""
        self.mock_ledfx.config["sendspin_servers"]["living-room"] = {
            "server_url": "ws://192.168.1.12:8927/sendspin",
            "client_name": "LedFx",
        }
        payload = {"id": "living-room", "server_url": "ws://192.168.1.99:8927/sendspin"}
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        data = await resp.json()
        assert data["status"] == "failed"
        assert "already exists" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=True)
    async def test_add_server_id_is_slugified(self, _):
        """The 'id' field is run through generate_id (slugified)."""
        with patch("ledfx.api.sendspin_servers.save_config"):
            payload = {
                "id": "Living Room Server!",
                "server_url": "ws://192.168.1.12:8927/sendspin",
            }
            await self.client.post(
                "/api/sendspin/servers",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            # generate_id("Living Room Server!") => "living-room-server"
            assert "living-room-server" in self.mock_ledfx.config["sendspin_servers"]

    @patch("ledfx.api.sendspin_servers._sendspin_available", return_value=False)
    async def test_post_unavailable(self, _):
        """Returns error when Sendspin is not available."""
        payload = {"id": "test", "server_url": "ws://192.168.1.1:8927/sendspin"}
        resp = await self.client.post(
            "/api/sendspin/servers",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        data = await resp.json()
        assert data["status"] == "failed"


# ---------------------------------------------------------------------------
# PUT /api/sendspin/servers/{server_id}
# ---------------------------------------------------------------------------


class TestPutSendspinServer:
    """Test PUT /api/sendspin/servers/{server_id}."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MockLedFx()
        self.mock_ledfx.config["sendspin_servers"] = {
            "living-room": {
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "client_name": "LedFx",
            }
        }
        app = web.Application()
        endpoint = SendspinServerEndpoint(self.mock_ledfx)
        app.router.add_route("*", "/api/sendspin/servers/{server_id}", endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    @patch("ledfx.api.sendspin_server.save_config")
    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_update_url(self, _, mock_save):
        """Updates server_url on an existing server."""
        payload = {"server_url": "ws://192.168.1.20:8927/sendspin"}
        resp = await self.client.put(
            "/api/sendspin/servers/living-room",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert (
            self.mock_ledfx.config["sendspin_servers"]["living-room"]["server_url"]
            == "ws://192.168.1.20:8927/sendspin"
        )
        mock_save.assert_called_once()
        self.mock_ledfx._load_sendspin_servers.assert_called_once()

    @patch("ledfx.api.sendspin_server.save_config")
    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_update_client_name(self, _, mock_save):
        """Updates client_name without touching server_url."""
        payload = {"client_name": "LedFx-Updated"}
        await self.client.put(
            "/api/sendspin/servers/living-room",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        server = self.mock_ledfx.config["sendspin_servers"]["living-room"]
        assert server["client_name"] == "LedFx-Updated"
        assert server["server_url"] == "ws://192.168.1.12:8927/sendspin"

    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_update_not_found(self, _):
        """Returns error when server_id does not exist."""
        payload = {"server_url": "ws://192.168.1.99:8927/sendspin"}
        resp = await self.client.put(
            "/api/sendspin/servers/nonexistent",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        data = await resp.json()
        assert data["status"] == "failed"
        assert "not found" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_update_invalid_url_scheme(self, _):
        """Rejects invalid URL scheme on update."""
        payload = {"server_url": "http://192.168.1.20:8927/sendspin"}
        resp = await self.client.put(
            "/api/sendspin/servers/living-room",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        data = await resp.json()
        assert data["status"] == "failed"
        assert "ws://" in data["payload"]["reason"]


# ---------------------------------------------------------------------------
# DELETE /api/sendspin/servers/{server_id}
# ---------------------------------------------------------------------------


class TestDeleteSendspinServer:
    """Test DELETE /api/sendspin/servers/{server_id}."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MockLedFx()
        self.mock_ledfx.config["sendspin_servers"] = {
            "living-room": {
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "client_name": "LedFx",
            }
        }
        app = web.Application()
        endpoint = SendspinServerEndpoint(self.mock_ledfx)
        app.router.add_route("*", "/api/sendspin/servers/{server_id}", endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    @patch("ledfx.api.sendspin_server.save_config")
    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_delete_server(self, _, mock_save):
        """Successfully removes an existing server."""
        resp = await self.client.delete("/api/sendspin/servers/living-room")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert "living-room" not in self.mock_ledfx.config["sendspin_servers"]
        mock_save.assert_called_once()
        self.mock_ledfx._load_sendspin_servers.assert_called_once()

    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=True)
    async def test_delete_not_found(self, _):
        """Returns error when server_id does not exist."""
        resp = await self.client.delete("/api/sendspin/servers/nonexistent")
        data = await resp.json()
        assert data["status"] == "failed"
        assert "not found" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_server._sendspin_available", return_value=False)
    async def test_delete_unavailable(self, _):
        """Returns error when Sendspin is not available."""
        resp = await self.client.delete("/api/sendspin/servers/living-room")
        data = await resp.json()
        assert data["status"] == "failed"


# ---------------------------------------------------------------------------
# GET /api/sendspin/discover
# ---------------------------------------------------------------------------


class TestGetSendspinDiscover:
    """Test GET /api/sendspin/discover."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MockLedFx()
        app = web.Application()
        endpoint = SendspinDiscoverEndpoint(self.mock_ledfx)
        app.router.add_route("*", "/api/sendspin/discover", endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    @patch.object(SendspinDiscoverEndpoint, "_discover", new_callable=AsyncMock)
    async def test_discover_no_servers(self, mock_discover, _):
        """Returns empty list when no servers found."""
        mock_discover.return_value = []
        resp = await self.client.get("/api/sendspin/discover")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert data["data"]["servers"] == []
        assert "No Sendspin servers" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    @patch.object(SendspinDiscoverEndpoint, "_discover", new_callable=AsyncMock)
    async def test_discover_finds_server(self, mock_discover, _):
        """Returns discovered servers with already_configured flag."""
        mock_discover.return_value = [
            {
                "name": "Sendspin Living Room",
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "host": "192.168.1.12",
                "port": 8927,
            }
        ]
        resp = await self.client.get("/api/sendspin/discover")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        servers = data["data"]["servers"]
        assert len(servers) == 1
        assert servers[0]["server_url"] == "ws://192.168.1.12:8927/sendspin"
        assert servers[0]["already_configured"] is False
        assert "1 server(s) found" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    @patch.object(SendspinDiscoverEndpoint, "_discover", new_callable=AsyncMock)
    async def test_discover_already_configured(self, mock_discover, _):
        """Marks already-configured servers with already_configured=True."""
        self.mock_ledfx.config["sendspin_servers"] = {
            "living-room": {
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "client_name": "LedFx",
            }
        }
        mock_discover.return_value = [
            {
                "name": "Sendspin Living Room",
                "server_url": "ws://192.168.1.12:8927/sendspin",
                "host": "192.168.1.12",
                "port": 8927,
            }
        ]
        resp = await self.client.get("/api/sendspin/discover")
        data = await resp.json()
        assert data["data"]["servers"][0]["already_configured"] is True

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    @patch.object(SendspinDiscoverEndpoint, "_discover", new_callable=AsyncMock)
    async def test_discover_respects_timeout_param(self, mock_discover, _):
        """Passes timeout query param to _discover."""
        mock_discover.return_value = []
        await self.client.get("/api/sendspin/discover?timeout=5.0")
        mock_discover.assert_called_once_with(5.0)

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    async def test_discover_timeout_too_large(self, _):
        """Rejects timeout above maximum."""
        resp = await self.client.get("/api/sendspin/discover?timeout=999")
        data = await resp.json()
        assert data["status"] == "failed"
        assert "30.0" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=True)
    async def test_discover_invalid_timeout(self, _):
        """Rejects non-numeric timeout."""
        resp = await self.client.get("/api/sendspin/discover?timeout=abc")
        data = await resp.json()
        assert data["status"] == "failed"
        assert "number" in data["payload"]["reason"]

    @patch("ledfx.api.sendspin_discover._sendspin_available", return_value=False)
    async def test_discover_unavailable(self, _):
        """Returns error when Sendspin is not available."""
        resp = await self.client.get("/api/sendspin/discover")
        data = await resp.json()
        assert data["status"] == "failed"
