"""Unit tests for the Now Playing REST API endpoint (Phase 2 + Phase 7 config)."""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_request(body_dict=None, bad_json=False):
    """Create a minimal mock aiohttp request."""
    request = MagicMock()
    if bad_json:
        request.json = AsyncMock(side_effect=json.JSONDecodeError("", "", 0))
    elif body_dict is not None:
        request.json = AsyncMock(return_value=body_dict)
    else:
        request.json = AsyncMock(return_value={})
    return request


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
    # Phase 7: config section present
    assert "config" in data
    assert data["config"]["gradient"]["enabled"] is False
    assert data["config"]["gradient"]["variant"] == "led_punchy"


@pytest.mark.asyncio
async def test_get_with_metadata(endpoint, ledfx):
    """GET after set_metadata returns expected data."""
    meta = TrackMetadata(
        source_id="sendspin",
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
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


# ------------------------------------------------------------------
# Phase 7: PUT /api/now-playing tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_gradient_config(endpoint, ledfx):
    """PUT updates gradient configuration."""
    request = _make_request(
        {"gradient": {"enabled": False, "variant": "led_max"}}
    )
    with patch("ledfx.nowplaying.service.save_config"):
        response = await endpoint.put(request)

    assert response.status == 200
    body = json.loads(response.body.decode())
    assert body["status"] == "success"
    assert body["data"]["gradient"]["enabled"] is False
    assert body["data"]["gradient"]["variant"] == "led_max"


@pytest.mark.asyncio
async def test_put_track_text_config(endpoint, ledfx):
    """PUT updates track_text configuration."""
    request = _make_request(
        {
            "track_text": {
                "enabled": True,
                "duration": 5,
                "virtual_ids": ["m1"],
            }
        }
    )
    with patch("ledfx.nowplaying.service.save_config"):
        response = await endpoint.put(request)

    assert response.status == 200
    body = json.loads(response.body.decode())
    assert body["data"]["track_text"]["enabled"] is True
    assert body["data"]["track_text"]["duration"] == 5
    assert body["data"]["track_text"]["virtual_ids"] == ["m1"]


@pytest.mark.asyncio
async def test_put_album_art_config(endpoint, ledfx):
    """PUT updates album_art configuration."""
    request = _make_request(
        {"album_art": {"enabled": True, "virtual_ids": ["m2"]}}
    )
    with patch("ledfx.nowplaying.service.save_config"):
        response = await endpoint.put(request)

    assert response.status == 200
    body = json.loads(response.body.decode())
    assert body["data"]["album_art"]["enabled"] is True
    assert body["data"]["album_art"]["virtual_ids"] == ["m2"]


@pytest.mark.asyncio
async def test_put_invalid_variant(endpoint, ledfx):
    """PUT with invalid variant returns error."""
    request = _make_request({"gradient": {"variant": "not_valid"}})
    response = await endpoint.put(request)

    assert response.status == 200
    body = json.loads(response.body.decode())
    assert body["status"] == "failed"


@pytest.mark.asyncio
async def test_put_invalid_json(endpoint, ledfx):
    """PUT with bad JSON returns 400."""
    request = _make_request(bad_json=True)
    response = await endpoint.put(request)
    assert response.status == 400


@pytest.mark.asyncio
async def test_put_non_dict_body(endpoint, ledfx):
    """PUT with non-dict body returns error."""
    request = _make_request()
    request.json = AsyncMock(return_value="not a dict")
    response = await endpoint.put(request)

    body = json.loads(response.body.decode())
    assert body["status"] == "failed"


@pytest.mark.asyncio
async def test_put_reflects_in_get(endpoint, ledfx):
    """Config from PUT is visible in subsequent GET."""
    request = _make_request(
        {"gradient": {"enabled": False, "virtual_ids": ["v1", "v2"]}}
    )
    with patch("ledfx.nowplaying.service.save_config"):
        await endpoint.put(request)

    response = await endpoint.get()
    data = json.loads(response.body.decode())
    assert data["config"]["gradient"]["enabled"] is False
    assert data["config"]["gradient"]["virtual_ids"] == ["v1", "v2"]
