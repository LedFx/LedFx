"""Tests for FLAC decoder lifecycle in SendspinAudioStream.

Verifies that _finish_flac_decoder is called in all required code paths
(stream/clear, stream/start, close) and that PCM-only sessions never
touch the decoder.
"""

import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture()
def _skip_if_no_aiosendspin():
    try:
        from aiosendspin.client import SendspinClient  # noqa: F401
    except ImportError:
        pytest.skip("aiosendspin not available")


@pytest.fixture()
def stream(_skip_if_no_aiosendspin):
    """Create a SendspinAudioStream with mocked SendspinClient."""
    from ledfx.sendspin.stream import SendspinAudioStream

    with patch("ledfx.sendspin.stream.SendspinClient", MagicMock()):
        s = SendspinAudioStream(
            config={
                "server_url": "ws://localhost:1234",
                "client_name": "LedFx",
            },
            callback=lambda *a: None,
            instance_id=str(uuid.uuid4()),
        )
    return s


class TestFinishFlacDecoderHelper:
    """Tests for _finish_flac_decoder helper method."""

    def test_noop_when_no_decoder(self, stream):
        """Calling _finish_flac_decoder with no active decoder is a no-op."""
        assert stream._flac_decoder is None
        stream._finish_flac_decoder("test")  # should not raise
        assert stream._flac_decoder is None

    def test_finishes_and_nulls_decoder(self, stream):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder
        stream._flac_fmt_logged = True
        stream._flac_pending_play_time_us = 99999
        stream._flac_pending_sample_rate = 44100
        stream._flac_pending_samples_emitted = 500

        stream._finish_flac_decoder("test reason")

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None
        assert stream._flac_fmt_logged is False
        assert stream._flac_pending_play_time_us == 0
        assert stream._flac_pending_sample_rate == 48000
        assert stream._flac_pending_samples_emitted == 0

    def test_exception_in_finish_is_swallowed(self, stream):
        mock_decoder = MagicMock()
        mock_decoder.finish.side_effect = RuntimeError("libFLAC error")
        stream._flac_decoder = mock_decoder

        stream._finish_flac_decoder("error test")  # should not raise

        assert stream._flac_decoder is None
        mock_decoder.finish.assert_called_once()


class TestStreamClearFinishesDecoder:
    """_stream_clear_handler must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_stream_clear(self, stream):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        stream._stream_clear_handler(roles="player")

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None

    def test_buffers_cleared_on_stream_clear(self, stream):
        stream._leftover = np.ones(100, dtype=np.float32)
        stream._leftover_ts = 12345
        with stream._buffer_lock:
            stream._chunk_buffer.append((0, 0, np.zeros(10)))

        stream._stream_clear_handler(roles="player")

        assert len(stream._leftover) == 0
        assert stream._leftover_ts == 0
        assert len(stream._chunk_buffer) == 0


class TestStreamStartFinishesDecoder:
    """_stream_start_handler must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_stream_start(self, stream):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        msg = MagicMock()
        msg.payload.player = None
        stream._stream_start_handler(msg)

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None


class TestCloseFinishesDecoder:
    """close() must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_close(self, stream):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        stream.close()

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None


class TestPcmPathNoDecoderCleanup:
    """PCM path should only clear buffers, never touch FLAC decoder."""

    def test_stream_clear_pcm_only(self, stream):
        """When no decoder exists, stream/clear just clears buffers."""
        assert stream._flac_decoder is None
        stream._leftover = np.ones(50, dtype=np.float32)
        with stream._buffer_lock:
            stream._chunk_buffer.append((0, 0, np.zeros(10)))

        stream._stream_clear_handler(roles="player")

        assert stream._flac_decoder is None
        assert len(stream._leftover) == 0
        assert len(stream._chunk_buffer) == 0

    def test_stream_start_pcm_only(self, stream):
        """When no decoder exists, stream/start just resets leftover state."""
        assert stream._flac_decoder is None

        # Set up leftover state to verify it is cleared
        stream._leftover = np.ones(25, dtype=np.float32)
        stream._leftover_ts = 12345

        msg = MagicMock()
        msg.payload.player = None
        stream._stream_start_handler(msg)

        assert stream._flac_decoder is None
        assert len(stream._leftover) == 0
        assert stream._leftover_ts == 0
