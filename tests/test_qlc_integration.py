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
