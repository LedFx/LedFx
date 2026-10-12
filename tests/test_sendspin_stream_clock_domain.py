"""Regression tests: Sendspin scheduling must use the client's clock.

aiosendspin's ``compute_play_time()`` returns times in the client's clock
domain (CLOCK_MONOTONIC_RAW on Linux), while ``loop.time()`` is
CLOCK_MONOTONIC.  On long-running hosts these drift apart by seconds; mixing
them silently dropped every audio sub-chunk (effects froze after a few
seconds) or released chunks far too late.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

if TYPE_CHECKING:
    from aiosendspin.client import SendspinClient

    from ledfx.sendspin.stream import SendspinAudioStream

# Simulated offset between the event-loop clock and the client clock.
_SKEW_US = 21_000_000


@pytest.fixture()
def _skip_if_no_aiosendspin():
    try:
        from aiosendspin.client import SendspinClient  # noqa: F401
    except ImportError:
        pytest.skip("aiosendspin not available")


class _FakeClient:
    """Stand-in for SendspinClient exposing only the client clock."""

    def __init__(self, now_us: int) -> None:
        self.now_us_value = now_us

    def now_us(self) -> int:
        return self.now_us_value


def _as_client(fake: _FakeClient) -> "SendspinClient":
    return cast("SendspinClient", fake)


def _discard(*_args: object) -> None:
    pass


def _make_stream(
    callback: Callable[..., None] = _discard,
) -> "SendspinAudioStream":
    from ledfx.sendspin.stream import SendspinAudioStream

    with patch("ledfx.sendspin.stream.SendspinClient", MagicMock()):
        return SendspinAudioStream(
            config={"server_url": "ws://localhost:1234", "client_name": "LedFx"},
            callback=callback,
            instance_id=str(uuid.uuid4()),
        )


def _loop_at(time_us: int) -> MagicMock:
    loop = MagicMock()
    loop.time.return_value = time_us / 1_000_000
    return loop


@pytest.mark.usefixtures("_skip_if_no_aiosendspin")
class TestScheduleUsesClientClock:
    def test_loop_clock_ahead_does_not_drop_chunks(self):
        """Loop clock 21 s ahead of the client clock: nothing is dropped."""
        from ledfx.sendspin.stream import _SUB_CHUNK_SAMPLES

        client_now = 1_000_000_000
        stream = _make_stream()
        stream._client = _as_client(_FakeClient(client_now))
        stream._loop = _loop_at(client_now + _SKEW_US)

        # 500 ms ahead of the client clock, but 20.5 s "late" for the loop.
        samples = np.zeros(_SUB_CHUNK_SAMPLES * 4, dtype=np.float32)
        stream._schedule_mono_samples(samples, client_now + 500_000, 48000)

        assert len(stream._chunk_buffer) == 4

    def test_truly_late_chunks_are_dropped_and_warned(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Chunks late in the client clock are dropped with a throttled warning."""
        from ledfx.sendspin.stream import _SUB_CHUNK_SAMPLES

        client_now = 1_000_000_000
        stream = _make_stream()
        stream._client = _as_client(_FakeClient(client_now))
        stream._loop = _loop_at(client_now)

        samples = np.zeros(_SUB_CHUNK_SAMPLES * 3, dtype=np.float32)
        with caplog.at_level(logging.WARNING, logger="ledfx.sendspin.stream"):
            stream._schedule_mono_samples(samples, client_now - 5_000_000, 48000)
            stream._schedule_mono_samples(samples, client_now - 5_000_000, 48000)

        assert stream._chunk_buffer == []
        warnings = [r for r in caplog.records if "late sub-chunks" in r.message]
        assert len(warnings) == 1

    def test_slightly_late_chunks_do_not_warn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from ledfx.sendspin.stream import _SUB_CHUNK_SAMPLES

        client_now = 1_000_000_000
        stream = _make_stream()
        stream._client = _as_client(_FakeClient(client_now))
        stream._loop = _loop_at(client_now)

        samples = np.zeros(_SUB_CHUNK_SAMPLES, dtype=np.float32)
        with caplog.at_level(logging.WARNING, logger="ledfx.sendspin.stream"):
            stream._schedule_mono_samples(samples, client_now - 50_000, 48000)

        assert stream._chunk_buffer == []
        assert not [r for r in caplog.records if "late sub-chunks" in r.message]

    def test_falls_back_to_loop_clock_without_client(self):
        stream = _make_stream()
        stream._client = None
        assert stream._now_us(_loop_at(123_000_000)) == 123_000_000


@pytest.mark.usefixtures("_skip_if_no_aiosendspin")
class TestPlaybackSchedulerUsesClientClock:
    def test_loop_clock_behind_releases_on_client_time(self):
        """Loop clock 21 s behind: chunks due on the client clock are released."""
        from ledfx.sendspin.stream import _SUB_CHUNK_SAMPLES

        released: list[np.ndarray] = []

        async def run() -> None:
            loop = asyncio.get_running_loop()

            def capture(chunk: np.ndarray, *_args: object) -> None:
                released.append(chunk)

            stream = _make_stream(capture)
            client = _FakeClient(int(loop.time() * 1_000_000) + _SKEW_US)
            stream._client = _as_client(client)
            stream._loop = loop
            stream._active = True

            due = np.ones(_SUB_CHUNK_SAMPLES, dtype=np.float32)
            future = np.zeros(_SUB_CHUNK_SAMPLES, dtype=np.float32)
            stream._chunk_buffer = [
                (client.now_us_value - 1_000, 1, due),
                (client.now_us_value + 60_000_000, 2, future),
            ]

            task = asyncio.create_task(stream._playback_scheduler())
            await asyncio.sleep(0.05)
            stream._active = False
            await task

            assert len(stream._chunk_buffer) == 1

        asyncio.run(run())

        assert len(released) == 1
        assert released[0][0] == 1.0
