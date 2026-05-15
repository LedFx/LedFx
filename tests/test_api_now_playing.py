"""Unit tests for the Now Playing REST API endpoint (Phase 2)."""

import io
import json
from unittest.mock import patch

import pytest
from PIL import Image

from ledfx.api.now_playing import NowPlayingEndpoint
from ledfx.nowplaying.models import TrackMetadata
from ledfx.nowplaying.service import NowPlayingService


def _make_test_png():
    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _DummyLedFx:
    """Minimal LedFx core stub with Now Playing service."""

    def __init__(self, config_dir):
        self.config = {}
        self.config_dir = config_dir
        self.now_playing = NowPlayingService(self)


@pytest.fixture
def ledfx(tmp_path):
    return _DummyLedFx(config_dir=str(tmp_path))


@pytest.fixture
def endpoint(ledfx):
    return NowPlayingEndpoint(ledfx)


@pytest.mark.asyncio
async def test_get_empty_state(endpoint):
    """GET with no state returns null fields."""
    response = await endpoint.get()
    assert response.status == 200

    data = json.loads(response.body.decode())
    assert data["active_source_id"] is None
    assert data["metadata"] is None
    assert data["artwork"] is None
    assert data["selected_gradient_variant"] == "led_punchy"
    assert data["current_gradient"] is None


@pytest.mark.asyncio
async def test_get_with_metadata(endpoint, ledfx):
    """GET after set_metadata returns expected data."""
    meta = TrackMetadata(
        source_id="sendspin",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=200.0,
        track_id="track-1",
    )
    ledfx.now_playing.set_metadata("sendspin", meta)

    response = await endpoint.get()
    assert response.status == 200

    data = json.loads(response.body.decode())
    assert data["active_source_id"] == "sendspin"
    assert data["metadata"]["title"] == "Test Song"
    assert data["metadata"]["artist"] == "Test Artist"
    assert data["metadata"]["album"] == "Test Album"
    assert data["metadata"]["duration"] == 200.0
    assert data["metadata"]["source_id"] == "sendspin"


@pytest.mark.asyncio
async def test_get_with_artwork_url(endpoint, ledfx):
    """GET after set_artwork_url includes artwork reference."""
    meta = TrackMetadata(source_id="sendspin", title="Song")
    ledfx.now_playing.set_metadata("sendspin", meta)

    png_data = _make_test_png()
    with patch.object(
        ledfx.now_playing,
        "_download_image",
        return_value=(png_data, "image/png"),
    ):
        ledfx.now_playing.set_artwork_url(
            "sendspin",
            "https://example.com/art.png",
            content_type="image/png",
            artwork_hash="abc123",
        )

    response = await endpoint.get()
    data = json.loads(response.body.decode())

    assert data["artwork"]["url"] == "https://example.com/art.png"
    assert data["artwork"]["content_type"] == "image/png"
    assert data["artwork"]["hash"] == "abc123"
    assert data["artwork"]["width"] == 4
    assert data["artwork"]["height"] == 4


@pytest.mark.asyncio
async def test_get_after_clear(endpoint, ledfx):
    """GET after clear returns empty state."""
    meta = TrackMetadata(source_id="sendspin", title="Song")
    ledfx.now_playing.set_metadata("sendspin", meta)
    ledfx.now_playing.clear("sendspin")

    response = await endpoint.get()
    data = json.loads(response.body.decode())

    assert data["active_source_id"] is None
    assert data["metadata"] is None
