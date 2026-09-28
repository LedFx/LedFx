"""Runtime regressions found while reviewing the Sendspin type annotations."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ledfx.sendspin.config import is_always_on, validate_sendspin_server_url

if TYPE_CHECKING:
    from aiosendspin.noise import Identity

    from ledfx.sendspin.stream import SendspinAudioStream


@pytest.mark.parametrize("port", ["not-a-port", "65536", "-1"])
def test_invalid_port_is_a_validation_error(port: str) -> None:
    valid, reason = validate_sendspin_server_url(f"ws://localhost:{port}/sendspin")
    assert not valid
    assert reason


def test_negative_hostapi_does_not_select_last_entry() -> None:
    assert not is_always_on(
        0, lambda: [{"hostapi": -1}], lambda: [{"name": "SENDSPIN"}]
    )


@pytest.fixture
def stream() -> SendspinAudioStream:
    pytest.importorskip("aiosendspin")
    from ledfx.sendspin.stream import SendspinAudioStream

    return SendspinAudioStream(
        config={"server_url": "ws://localhost:1234"},
        callback=lambda *_: None,
        instance_id="test-instance",
    )


def test_signed_24_bit_pcm_extremes(stream: SendspinAudioStream) -> None:
    samples = [-8388608, -1, 0, 1, 8388607]
    raw = b"".join((sample & 0xFFFFFF).to_bytes(3, "little") for sample in samples)
    decoded = stream._unpack_int24(raw)
    np.testing.assert_array_equal(decoded, np.array(samples, dtype=np.int32))


def test_new_stream_discards_queued_audio(stream: SendspinAudioStream) -> None:
    stream._leftover = np.ones(20, dtype=np.float32)
    stream._leftover_ts = 100
    stream._chunk_buffer.append((100, 1, np.ones(800, dtype=np.float32)))
    message = MagicMock()
    message.payload.player = None

    stream._stream_start_handler(message)

    assert not stream._chunk_buffer
    assert stream._leftover.size == 0
    assert stream._leftover_ts == 0


async def test_failed_connection_discards_partial_audio(
    stream: SendspinAudioStream,
) -> None:
    stream._leftover = np.ones(20, dtype=np.float32)
    stream._leftover_ts = 100
    client = MagicMock()
    client.connect = AsyncMock(side_effect=ConnectionError("offline"))
    client.disconnect = AsyncMock()
    with (
        patch("ledfx.sendspin.stream.SendspinClient", return_value=client),
        pytest.raises(ConnectionError, match="offline"),
    ):
        await stream._connect_and_receive()

    assert stream._leftover.size == 0
    assert stream._leftover_ts == 0
    client.disconnect.assert_awaited_once()


def test_concurrent_streams_share_one_complete_identity(tmp_path: Path) -> None:
    pytest.importorskip("aiosendspin")
    from aiosendspin.noise import Identity

    from ledfx.sendspin.identity import load_or_create_identity

    barrier = Barrier(2)
    generate = Identity.generate

    def generate_together() -> Identity:
        identity = generate()
        barrier.wait(timeout=5)
        return identity

    with (
        patch.object(Identity, "generate", side_effect=generate_together),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        identities = list(executor.map(load_or_create_identity, [tmp_path] * 2))

    assert identities[0].peer_id == identities[1].peer_id
    assert load_or_create_identity(tmp_path).peer_id == identities[0].peer_id
    assert sorted(path.name for path in tmp_path.iterdir()) == ["sendspin_identity"]
    if os.name == "posix":
        assert (tmp_path / "sendspin_identity").stat().st_mode & 0o777 == 0o600


async def test_reconnect_reuses_identity_and_pairing_store(
    stream: SendspinAudioStream,
) -> None:
    first = await stream._get_identity_and_pairing_store()
    second = await stream._get_identity_and_pairing_store()
    assert first[0] is second[0]
    assert first[1] is second[1]


def test_close_without_live_thread_clears_playback_state(
    stream: SendspinAudioStream,
) -> None:
    provider = MagicMock()
    stream._now_playing_provider = provider
    stream._leftover = np.ones(20, dtype=np.float32)
    stream._leftover_ts = 100
    stream._chunk_buffer.append((100, 1, np.ones(800, dtype=np.float32)))

    stream.close()
    stream.close()

    assert stream._leftover.size == 0
    assert stream._leftover_ts == 0
    assert not stream._chunk_buffer
    assert stream._client is None
    assert provider.clear.call_count == 2
