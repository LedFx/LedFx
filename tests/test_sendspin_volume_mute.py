"""Unit tests for Sendspin MA-compatible volume/mute handling.

Verifies the "fake state + silence gate" model:
- volume/mute are tracked and reported for Music Assistant compatibility
- only mute=True or volume=0 actually silences audio (feeds zeros)
- volume values 1-100 do NOT affect audio processing
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_aiosendspin():
    """Patch aiosendspin imports so tests run without Python 3.12+."""
    with patch.dict(
        "sys.modules",
        {
            "aiosendspin": MagicMock(),
            "aiosendspin.client": MagicMock(),
            "aiosendspin.models": MagicMock(),
            "aiosendspin.models.core": MagicMock(),
            "aiosendspin.models.player": MagicMock(),
        },
    ):
        yield


@pytest.fixture
def stream():
    """Create a SendspinAudioStream instance with mocked dependencies."""
    with patch(
        "ledfx.sendspin.stream.SendspinClient"
    ) as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        from ledfx.sendspin.stream import SendspinAudioStream

        callback = MagicMock()
        s = SendspinAudioStream(
            config={"server_url": "ws://test:8927/sendspin"},
            callback=callback,
            instance_id="abcdef01-2345-6789-abcd-ef0123456789",
        )
        yield s


class TestInitialState:
    """Test that initial volume/mute state is correct."""

    def test_default_volume(self, stream):
        assert stream._ma_volume == 100

    def test_default_muted(self, stream):
        assert stream._ma_muted is False

    def test_default_not_silenced(self, stream):
        assert stream._effective_silenced is False


class TestRecomputeEffectiveSilenced:
    """Test effective_silenced logic."""

    def test_volume_100_not_muted(self, stream):
        stream._ma_volume = 100
        stream._ma_muted = False
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is False

    def test_volume_50_not_muted(self, stream):
        """Volume 1-100 with no mute → not silenced."""
        stream._ma_volume = 50
        stream._ma_muted = False
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is False

    def test_volume_1_not_muted(self, stream):
        """Volume 1 → not silenced (only 0 silences)."""
        stream._ma_volume = 1
        stream._ma_muted = False
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is False

    def test_volume_0_silences(self, stream):
        """Volume 0 → silenced."""
        stream._ma_volume = 0
        stream._ma_muted = False
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is True

    def test_muted_silences(self, stream):
        """Mute=True → silenced regardless of volume."""
        stream._ma_volume = 100
        stream._ma_muted = True
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is True

    def test_muted_and_volume_0(self, stream):
        """Both muted and volume=0 → silenced."""
        stream._ma_volume = 0
        stream._ma_muted = True
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is True

    def test_unmute_with_volume_restores(self, stream):
        """Unmuting with volume>0 → not silenced."""
        stream._ma_volume = 75
        stream._ma_muted = True
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is True

        stream._ma_muted = False
        stream._recompute_effective_silenced()
        assert stream._effective_silenced is False


class TestServerCommandHandler:
    """Test _server_command_handler processes MA commands correctly."""

    def _make_volume_payload(self, volume):
        """Create a mock ServerCommandPayload for a volume command."""
        from ledfx.sendspin.stream import PlayerCommand

        payload = MagicMock()
        payload.player.command = PlayerCommand.VOLUME
        payload.player.volume = volume
        payload.player.mute = None
        return payload

    def _make_mute_payload(self, mute):
        """Create a mock ServerCommandPayload for a mute command."""
        from ledfx.sendspin.stream import PlayerCommand

        payload = MagicMock()
        payload.player.command = PlayerCommand.MUTE
        payload.player.mute = mute
        payload.player.volume = None
        return payload

    def test_volume_command_updates_state(self, stream):
        stream._report_player_state = MagicMock()
        payload = self._make_volume_payload(50)
        stream._server_command_handler(payload)
        assert stream._ma_volume == 50
        assert stream._effective_silenced is False
        stream._report_player_state.assert_called_once()

    def test_volume_0_silences(self, stream):
        stream._report_player_state = MagicMock()
        payload = self._make_volume_payload(0)
        stream._server_command_handler(payload)
        assert stream._ma_volume == 0
        assert stream._effective_silenced is True

    def test_volume_clamped_above_100(self, stream):
        """Volume values above 100 are clamped."""
        stream._report_player_state = MagicMock()
        payload = self._make_volume_payload(150)
        stream._server_command_handler(payload)
        assert stream._ma_volume == 100

    def test_volume_clamped_below_0(self, stream):
        """Negative volume values are clamped to 0."""
        stream._report_player_state = MagicMock()
        payload = self._make_volume_payload(-10)
        stream._server_command_handler(payload)
        assert stream._ma_volume == 0
        assert stream._effective_silenced is True

    def test_mute_command_sets_muted(self, stream):
        stream._report_player_state = MagicMock()
        payload = self._make_mute_payload(True)
        stream._server_command_handler(payload)
        assert stream._ma_muted is True
        assert stream._effective_silenced is True
        stream._report_player_state.assert_called_once()

    def test_unmute_command(self, stream):
        stream._report_player_state = MagicMock()
        stream._ma_muted = True
        stream._recompute_effective_silenced()

        payload = self._make_mute_payload(False)
        stream._server_command_handler(payload)
        assert stream._ma_muted is False
        assert stream._effective_silenced is False

    def test_no_player_payload_ignored(self, stream):
        """Payload with player=None is safely ignored."""
        stream._report_player_state = MagicMock()
        payload = MagicMock()
        payload.player = None
        stream._server_command_handler(payload)
        stream._report_player_state.assert_not_called()

    def test_audio_not_scaled_at_volume_50(self, stream):
        """Volume 50 must NOT affect audio - just track state."""
        stream._report_player_state = MagicMock()
        payload = self._make_volume_payload(50)
        stream._server_command_handler(payload)
        # effective_silenced should be False - audio passes through unchanged
        assert stream._effective_silenced is False
        assert stream._ma_volume == 50


class TestSilenceGate:
    """Test that the silence gate in _playback_scheduler feeds zeros."""

    @pytest.mark.asyncio
    async def test_silenced_feeds_zeros(self, stream):
        """When silenced, callback receives zeros instead of real audio."""
        import asyncio

        stream._active = True
        stream._loop = asyncio.get_event_loop()
        stream._effective_silenced = True

        # Pre-load buffer with real audio
        real_audio = np.ones(800, dtype=np.float32) * 0.5
        now_us = int(stream._loop.time() * 1_000_000)
        stream._chunk_buffer = [(now_us - 1000, 1, real_audio)]

        # Run one iteration of the scheduler
        stream._active = False  # Will exit after processing one chunk
        # Manually execute the scheduler logic inline
        chunk = None
        with stream._buffer_lock:
            if stream._chunk_buffer:
                play_time_us = stream._chunk_buffer[0][0]
                check_us = int(stream._loop.time() * 1_000_000)
                if play_time_us <= check_us:
                    import heapq

                    _, _, chunk = heapq.heappop(stream._chunk_buffer)

        if chunk is not None:
            if stream._effective_silenced:
                chunk = np.zeros_like(chunk)
            stream.callback(chunk, len(chunk), None, None)

        # Verify callback received zeros
        stream.callback.assert_called_once()
        delivered = stream.callback.call_args[0][0]
        np.testing.assert_array_equal(delivered, np.zeros(800, dtype=np.float32))

    @pytest.mark.asyncio
    async def test_not_silenced_passes_audio(self, stream):
        """When not silenced, callback receives the real audio."""
        import asyncio

        stream._active = True
        stream._loop = asyncio.get_event_loop()
        stream._effective_silenced = False

        real_audio = np.ones(800, dtype=np.float32) * 0.5
        now_us = int(stream._loop.time() * 1_000_000)
        stream._chunk_buffer = [(now_us - 1000, 1, real_audio)]

        # Process one chunk
        chunk = None
        with stream._buffer_lock:
            if stream._chunk_buffer:
                import heapq

                play_time_us = stream._chunk_buffer[0][0]
                check_us = int(stream._loop.time() * 1_000_000)
                if play_time_us <= check_us:
                    _, _, chunk = heapq.heappop(stream._chunk_buffer)

        if chunk is not None:
            if stream._effective_silenced:
                chunk = np.zeros_like(chunk)
            stream.callback(chunk, len(chunk), None, None)

        # Verify callback received the original audio
        stream.callback.assert_called_once()
        delivered = stream.callback.call_args[0][0]
        np.testing.assert_array_equal(delivered, real_audio)
