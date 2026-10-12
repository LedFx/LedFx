"""Tests for FLAC decoder lifecycle in SendspinAudioStream.

Verifies that _finish_flac_decoder is called in all required code paths
(stream/clear, stream/start, close) and that PCM-only sessions never
touch the decoder.
"""

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

if TYPE_CHECKING:
    from ledfx.sendspin.stream import SendspinAudioStream


@pytest.fixture()
def _skip_if_no_aiosendspin():
    try:
        from aiosendspin.client import SendspinClient  # noqa: F401
    except ImportError:
        pytest.skip("aiosendspin not available")


@pytest.fixture()
def stream(_skip_if_no_aiosendspin) -> "SendspinAudioStream":
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

    def test_noop_when_no_decoder(self, stream: "SendspinAudioStream"):
        """Calling _finish_flac_decoder with no active decoder is a no-op."""
        assert stream._flac_decoder is None
        stream._finish_flac_decoder("test")  # should not raise
        assert stream._flac_decoder is None

    def test_finishes_and_nulls_decoder(self, stream: "SendspinAudioStream"):
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

    def test_exception_in_finish_is_swallowed(self, stream: "SendspinAudioStream"):
        mock_decoder = MagicMock()
        mock_decoder.finish.side_effect = RuntimeError("libFLAC error")
        stream._flac_decoder = mock_decoder

        stream._finish_flac_decoder("error test")  # should not raise

        assert stream._flac_decoder is None
        mock_decoder.finish.assert_called_once()


class TestStreamClearFinishesDecoder:
    """_stream_clear_handler must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_stream_clear(self, stream: "SendspinAudioStream"):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        stream._stream_clear_handler(roles=["player"])

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None

    def test_buffers_cleared_on_stream_clear(self, stream: "SendspinAudioStream"):
        stream._leftover = np.ones(100, dtype=np.float32)
        stream._leftover_ts = 12345
        with stream._buffer_lock:
            stream._chunk_buffer.append((0, 0, np.zeros(10, dtype=np.float32)))

        stream._stream_clear_handler(roles=["player"])

        assert len(stream._leftover) == 0
        assert stream._leftover_ts == 0
        assert len(stream._chunk_buffer) == 0


class TestStreamStartFinishesDecoder:
    """_stream_start_handler must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_stream_start(self, stream: "SendspinAudioStream"):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        msg = MagicMock()
        msg.payload.player = None
        stream._stream_start_handler(msg)

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None


class _SilenceSceneStub:
    def __init__(self, calls: list[tuple[str, str]]) -> None:
        self.calls = calls

    def report_source_silence(self, reason: str) -> None:
        self.calls.append(("silence", reason))

    def report_source_unknown(self, reason: str) -> None:
        self.calls.append(("unknown", reason))

    def report_source_active(self, reason: str) -> None:
        self.calls.append(("active", reason))


class TestSendspinSilenceClassification:
    def test_missing_server_volume_preserves_previous_value_and_state(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        stream._ledfx = SimpleNamespace(silence_scene=_SilenceSceneStub(calls))
        stream._sendspin_volume = 75

        stream._handle_sendspin_volume(None)

        assert stream._sendspin_volume == 75
        assert calls == []

    def test_explicit_zero_server_volume_reports_silence(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        stream._ledfx = SimpleNamespace(silence_scene=_SilenceSceneStub(calls))
        stream._sendspin_volume = 75

        stream._handle_sendspin_volume(0)

        assert stream._sendspin_volume == 0
        assert calls == [("silence", "sendspin_volume_changed")]

    def test_stream_start_reports_unknown_until_volume_is_measured(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        controller = _SilenceSceneStub(calls)
        stream._ledfx = SimpleNamespace(silence_scene=controller)
        stream._expecting_audio = True

        msg = MagicMock()
        msg.payload.player = None
        stream._stream_start_handler(msg)

        assert calls == [("unknown", "sendspin_stream_started")]

    def test_pause_then_stream_resume_reports_silence_then_unknown(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        controller = _SilenceSceneStub(calls)
        stream._ledfx = SimpleNamespace(silence_scene=controller)
        stream._expecting_audio = True

        stream._stream_end_handler(roles=None)
        msg = MagicMock()
        msg.payload.player = None
        stream._stream_start_handler(msg)

        assert calls == [
            ("silence", "sendspin_stream_ended"),
            ("unknown", "sendspin_stream_started"),
        ]

    def test_idle_connection_and_unmute_without_stream_report_silence(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        controller = _SilenceSceneStub(calls)
        stream._ledfx = SimpleNamespace(silence_scene=controller)
        stream._sendspin_disconnected = False
        stream._expecting_audio = False
        stream._report_sendspin_state("sendspin_connected")
        stream._sendspin_muted = False
        stream._report_sendspin_state("sendspin_unmuted")

        assert calls == [
            ("silence", "sendspin_connected"),
            ("silence", "sendspin_unmuted"),
        ]

    def test_explicit_pause_mute_zero_volume_and_disconnect_report_silence(
        self, stream: "SendspinAudioStream"
    ):
        calls: list[tuple[str, str]] = []
        controller = _SilenceSceneStub(calls)
        stream._ledfx = SimpleNamespace(silence_scene=controller)
        stream._expecting_audio = True
        for attribute, value, reason in (
            ("_sendspin_paused", True, "paused"),
            ("_sendspin_paused", False, "unpaused"),
            ("_sendspin_muted", True, "muted"),
            ("_sendspin_muted", False, "unmuted"),
            ("_sendspin_volume", 0, "zero_volume"),
            ("_sendspin_disconnected", True, "disconnected"),
        ):
            setattr(stream, attribute, value)
            stream._report_sendspin_state(reason)

        stream._sendspin_disconnected = False
        stream._sendspin_volume = 100
        stream._sendspin_paused = False
        stream._report_sendspin_state("sendspin_playback_resumed")
        stream._sendspin_muted = False
        stream._report_sendspin_state("sendspin_unmuted")

        assert calls == [
            ("silence", "paused"),
            ("unknown", "unpaused"),
            ("silence", "muted"),
            ("unknown", "unmuted"),
            ("silence", "zero_volume"),
            ("silence", "disconnected"),
            ("unknown", "sendspin_playback_resumed"),
            ("unknown", "sendspin_unmuted"),
        ]


class TestCloseFinishesDecoder:
    """close() must finish the FLAC decoder."""

    def test_flac_decoder_finished_on_close(self, stream: "SendspinAudioStream"):
        mock_decoder = MagicMock()
        stream._flac_decoder = mock_decoder

        stream.close()

        mock_decoder.finish.assert_called_once()
        assert stream._flac_decoder is None


class TestPcmPathNoDecoderCleanup:
    """PCM path should only clear buffers, never touch FLAC decoder."""

    def test_stream_clear_pcm_only(self, stream: "SendspinAudioStream"):
        """When no decoder exists, stream/clear just clears buffers."""
        assert stream._flac_decoder is None
        stream._leftover = np.ones(50, dtype=np.float32)
        with stream._buffer_lock:
            stream._chunk_buffer.append((0, 0, np.zeros(10, dtype=np.float32)))

        stream._stream_clear_handler(roles=["player"])

        assert stream._flac_decoder is None
        assert len(stream._leftover) == 0
        assert len(stream._chunk_buffer) == 0

    def test_stream_start_pcm_only(self, stream: "SendspinAudioStream"):
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
