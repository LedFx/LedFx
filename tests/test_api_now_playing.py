"""Integration tests for the GET /api/now-playing endpoint."""

from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.now_playing import NowPlayingEndpoint
from ledfx.nowplaying.models import NowPlayingState, NowPlayingTrack

ENDPOINT_PATH = NowPlayingEndpoint.ENDPOINT_PATH


class TestNowPlayingUninitialized:
    """Manager not attached to _ledfx (now_playing attribute missing)."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.mock_ledfx = MagicMock(spec=[])  # no attributes at all
        app = web.Application()
        endpoint = NowPlayingEndpoint(self.mock_ledfx)
        app.router.add_route("*", ENDPOINT_PATH, endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    async def test_returns_unavailable(self):
        resp = await self.client.get(ENDPOINT_PATH)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "unavailable"
        assert "message" in data


class TestNowPlayingInitialized:
    """Manager attached and returning a known state dict."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        state = NowPlayingState(
            enabled=True,
            status="running",
            provider_name="platform_media",
            active_track=NowPlayingTrack(
                provider="platform_media",
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                is_playing=True,
            ),
            active_art_url="https://example.com/art.jpg",
            palette_applied=False,
            last_track_signature="abc123",
        )
        self.expected = state.to_dict()

        self.mock_ledfx = MagicMock()
        self.mock_ledfx.now_playing.state.to_dict.return_value = self.expected

        app = web.Application()
        endpoint = NowPlayingEndpoint(self.mock_ledfx)
        app.router.add_route("*", ENDPOINT_PATH, endpoint.handler)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        yield
        await self.client.close()

    async def test_returns_state(self):
        resp = await self.client.get(ENDPOINT_PATH)
        assert resp.status == 200
        data = await resp.json()
        assert data == self.expected
