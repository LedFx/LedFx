"""QLC+ integration connection lifecycle, with aiohttp mocked out."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import WSServerHandshakeError

from ledfx.integrations import Status
from ledfx.integrations.qlc import QLC, QLCWebsocketClient


def make_qlc() -> QLC:
    ledfx = MagicMock()
    ledfx.loop = asyncio.get_running_loop()
    return QLC(ledfx, QLC.Config(), False, None)


async def test_client_disconnect_closes_its_session() -> None:
    with patch("ledfx.integrations.qlc.aiohttp.ClientSession") as session_cls:
        session_cls.return_value.close = AsyncMock()
        client = QLCWebsocketClient("http://127.0.0.1:9999/qlcplusWS", "x")
    client.websocket = AsyncMock()

    await client.disconnect()

    client.websocket.close.assert_awaited_once()
    session_cls.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("teardown", ["disconnect", "on_delete"])
async def test_teardown_disconnects_and_drops_the_client(teardown: str) -> None:
    integration = make_qlc()
    client = MagicMock(disconnect=AsyncMock())
    integration._client = client

    await getattr(integration, teardown)()
    for _ in range(3):  # let the fire-and-forget disconnect run
        await asyncio.sleep(0)

    client.disconnect.assert_awaited_once()
    assert integration._client is None
    assert integration.status == Status.DISCONNECTED


async def test_send_payload_without_a_client_is_a_noop() -> None:
    integration = make_qlc()
    await integration._send_payload({"1": 255})


async def test_client_connect_retries_after_a_handshake_error() -> None:
    websocket = MagicMock()
    with patch("ledfx.integrations.qlc.aiohttp.ClientSession") as session_cls:
        session_cls.return_value.ws_connect = AsyncMock(
            side_effect=[
                WSServerHandshakeError(
                    MagicMock(), (), message="Invalid response status"
                ),
                websocket,
            ]
        )
        client = QLCWebsocketClient("http://127.0.0.1:9999/qlcplusWS", "x")

    with patch("ledfx.integrations.qlc.asyncio.sleep", AsyncMock()):
        assert await client.connect() is True

    assert client.websocket is websocket
    assert session_cls.return_value.ws_connect.await_count == 2


async def test_unresolvable_host_warns_and_leaves_the_integration_disconnected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    integration = make_qlc()
    integration._status = Status.CONNECTING
    failure = ValueError("Failed to resolve destination not-a-host")

    with patch(
        "ledfx.integrations.qlc.resolve_destination", AsyncMock(side_effect=failure)
    ):
        await integration.connect()

    assert integration.status == Status.DISCONNECTED
    assert integration._client is None
    assert [
        r.levelname for r in caplog.records if r.name == "ledfx.integrations.qlc"
    ] == ["WARNING"]


async def test_disconnect_during_a_widget_query_stops_the_query() -> None:
    integration = make_qlc()
    client = MagicMock(disconnect=AsyncMock())

    async def query(message: str) -> str:
        if message.endswith("getWidgetsList"):
            return "getWidgetsList|1|Fader|2|Button"
        await integration.disconnect()  # the integration is torn down mid-query
        return "getWidgetType|Slider"

    client.query = AsyncMock(side_effect=query)
    integration._client = client

    assert await integration.get_widgets() == []
    assert client.query.await_count == 2


async def test_delete_during_host_resolution_does_not_connect() -> None:
    integration = make_qlc()
    resolving = asyncio.Event()
    release = asyncio.Event()

    async def resolve(*_: object) -> str:
        resolving.set()
        await release.wait()
        return "127.0.0.1"

    with (
        patch("ledfx.integrations.qlc.resolve_destination", resolve),
        patch("ledfx.integrations.qlc.QLCWebsocketClient") as client_cls,
    ):
        connecting = asyncio.create_task(integration.connect())
        await resolving.wait()
        await integration.on_delete()
        release.set()
        await connecting

    client_cls.assert_not_called()
    assert integration._client is None
    assert integration.status == Status.DISCONNECTED


async def test_client_disconnect_closes_the_session_when_close_hangs() -> None:
    with patch("ledfx.integrations.qlc.aiohttp.ClientSession") as session_cls:
        session_cls.return_value.close = AsyncMock()
        client = QLCWebsocketClient("http://127.0.0.1:9999/qlcplusWS", "x")
    client.websocket = MagicMock(close=AsyncMock(side_effect=asyncio.Event().wait))

    real_timeout = asyncio.timeout

    def expire_now(_: float) -> asyncio.Timeout:
        return real_timeout(0)

    with patch("asyncio.timeout", expire_now):
        await client.disconnect()

    session_cls.return_value.close.assert_awaited_once()
