"""
Test audio cleanup and resource management to prevent memory leaks.

This test validates the fix for issue #1712 where Pipewire resets
caused rapid memory consumption due to improper stream error handling
and resource cleanup.
"""

from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from ledfx.effects.audio import AudioInputSource


class TestAudioInputSourceCleanup:
    """Test proper cleanup and error handling in AudioInputSource"""

    @pytest.fixture
    def mock_ledfx(self):
        """Create a mock LedFx instance"""
        ledfx = MagicMock()
        ledfx.config = {
            "audio": {
                "sample_rate": 60,
                "mic_rate": 44100,
                "fft_size": 2048,
                "min_volume": 0.2,
                "delay_ms": 0,
            },
            "melbanks": {},
        }
        ledfx.events = MagicMock()
        ledfx.events.add_listener = MagicMock()
        return ledfx

    @pytest.fixture
    def audio_source(self, mock_ledfx):
        """Create an AudioInputSource instance"""
        with patch("ledfx.effects.audio.sd"):
            source = AudioInputSource(mock_ledfx, mock_ledfx.config["audio"])
            return source

    def test_instance_variables_initialized(self, audio_source):
        """Test that all instance variables are properly initialized per-instance"""
        assert hasattr(audio_source, "_audio_stream_active")
        assert hasattr(audio_source, "_callbacks")
        assert hasattr(audio_source, "_stream")
        assert hasattr(audio_source, "_timer")
        assert hasattr(audio_source, "_stream_error_count")
        assert hasattr(audio_source, "resampler")
        assert hasattr(audio_source, "delay_queue")

        # Verify they're instance-specific
        assert audio_source._callbacks == []
        assert audio_source._stream is None
        assert audio_source._stream_error_count == 0

    def test_multiple_instances_have_separate_state(self, mock_ledfx):
        """Test that multiple instances don't share state"""
        with patch("ledfx.effects.audio.sd"):
            source1 = AudioInputSource(mock_ledfx, mock_ledfx.config["audio"])
            source2 = AudioInputSource(mock_ledfx, mock_ledfx.config["audio"])

            # Add callback to source1
            callback1 = Mock()
            source1._callbacks.append(callback1)

            # Verify source2 doesn't have the callback
            assert len(source1._callbacks) == 1
            assert len(source2._callbacks) == 0

    def test_callback_exception_handling(self, audio_source):
        """Test that exceptions in callbacks don't crash the system"""
        # Add a callback that raises an exception
        error_callback = Mock(side_effect=Exception("Test error"))
        success_callback = Mock()

        audio_source._callbacks = [error_callback, success_callback]

        # Invoke callbacks - should not raise
        audio_source._invoke_callbacks()

        # Both callbacks should have been called
        error_callback.assert_called_once()
        success_callback.assert_called_once()

    def test_stream_error_detection(self, audio_source, mock_ledfx):
        """Test that stream errors are detected and trigger cleanup"""
        # Mock a stream
        audio_source._audio_stream_active = True
        audio_source._stream = Mock()
        audio_source.resampler = Mock()
        audio_source.resampler.process = Mock(
            return_value=np.zeros(733, dtype=np.float32)
        )
        audio_source._config = {
            "sample_rate": 60,
            "min_volume": 0.2,
        }

        # Mock methods to prevent full callback execution after error detection
        audio_source.pre_process_audio = Mock()
        audio_source._invalidate_caches = Mock()
        audio_source._invoke_callbacks = Mock()
        audio_source.delay_queue = None
        
        # Mock threading to prevent actual deactivation thread from running
        # This allows us to check the error count before it gets reset
        deactivate_called = []
        def mock_deactivate_and_schedule():
            deactivate_called.append(True)
        
        audio_source._deactivate_and_schedule_recovery = mock_deactivate_and_schedule

        # Create mock audio data
        in_data = np.zeros(733, dtype=np.float32).tobytes()

        # Simulate multiple errors to trigger cleanup
        for i in range(12):
            # Create a mock status with error
            status = Mock()
            # Use a long string to trigger the len > 50 check as well
            status.__str__ = Mock(
                return_value="PrimeOutputBuffersPartialInvalidBlockSize"
                + "X" * 40
            )

            audio_source._audio_sample_callback(in_data, 733, None, status)

        # Verify that deactivation was triggered at least once
        assert len(deactivate_called) > 0
        # Error count should have reached or exceeded threshold before deactivation
        assert audio_source._stream_error_count >= 10

    def test_malformed_data_handling(self, audio_source):
        """Test that malformed audio data doesn't cause memory leaks"""
        audio_source._audio_stream_active = True
        audio_source.resampler = Mock()
        audio_source._config = {
            "sample_rate": 60,
            "min_volume": 0.2,
        }

        # Test with invalid data
        invalid_data = b"invalid"
        audio_source._audio_sample_callback(invalid_data, 0, None, None)

        # Should not crash, just log warning

    def test_deactivate_cleans_all_resources(self, audio_source):
        """Test that deactivate properly cleans up all resources"""
        # Setup mock resources
        mock_stream = Mock()
        mock_resampler = Mock()
        mock_queue = Mock()
        mock_queue.empty = Mock(return_value=True)

        audio_source._stream = mock_stream
        audio_source._audio_stream_active = True
        audio_source.resampler = mock_resampler
        audio_source.delay_queue = mock_queue

        # Deactivate
        audio_source.deactivate()

        # Verify cleanup
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert audio_source._stream is None
        assert audio_source.resampler is None
        assert audio_source.delay_queue is None
        assert audio_source._audio_stream_active is False
        assert audio_source._stream_error_count == 0

    def test_deactivate_handles_stream_errors(self, audio_source):
        """Test that deactivate handles errors during stream cleanup"""
        # Setup mock stream that raises on stop
        mock_stream = Mock()
        mock_stream.stop = Mock(side_effect=Exception("Stream error"))
        mock_stream.close = Mock()

        audio_source._stream = mock_stream
        audio_source._audio_stream_active = True

        # Should not raise exception
        audio_source.deactivate()

        # Verify cleanup attempted and stream cleared
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert audio_source._stream is None

    def test_timer_cleanup_in_subscribe(self, audio_source):
        """Test that timers are properly cancelled in subscribe"""
        # Create a mock timer
        mock_timer = Mock()
        audio_source._timer = mock_timer
        audio_source._audio_stream_active = True  # Prevent activation attempt

        # Subscribe
        callback = Mock()
        audio_source.subscribe(callback)

        # Timer should be cancelled
        mock_timer.cancel.assert_called_once()

    def test_timer_cleanup_in_unsubscribe(self, audio_source):
        """Test that timers are properly managed in unsubscribe"""
        callback = Mock()
        audio_source._callbacks = [callback]
        audio_source._audio_stream_active = True
        audio_source._subscriber_threshold = 0

        # Unsubscribe
        audio_source.unsubscribe(callback)

        # Verify new timer was created
        assert audio_source._timer is not None

    def test_check_and_deactivate_cancels_timer(self, audio_source):
        """Test that check_and_deactivate properly cancels timer"""
        mock_timer = Mock()
        audio_source._timer = mock_timer
        audio_source._audio_stream_active = False

        audio_source.check_and_deactivate()

        # Timer should be cancelled
        mock_timer.cancel.assert_called()
        assert audio_source._timer is None

    def test_preprocessing_with_invalid_state(self, audio_source):
        """Test that preprocessing handles invalid state gracefully"""
        # Test with None sample
        audio_source._raw_audio_sample = None
        audio_source.pre_process_audio()  # Should not crash

        # Test with empty sample
        audio_source._raw_audio_sample = np.array([])
        audio_source.pre_process_audio()  # Should not crash

    def test_resampler_error_recovery(self, audio_source):
        """Test that resampler errors increment error counter"""
        audio_source._audio_stream_active = True
        audio_source.resampler = Mock()
        audio_source.resampler.process = Mock(
            side_effect=Exception("Resampler error")
        )
        audio_source._config = {
            "sample_rate": 60,
            "min_volume": 0.2,
        }

        # Create audio data that would trigger resampling
        in_data = np.zeros(1000, dtype=np.float32).tobytes()

        # Call callback
        audio_source._audio_sample_callback(in_data, 1000, None, None)

        # Error counter should have increased
        assert audio_source._stream_error_count > 0

    def test_successful_processing_decrements_error_count(self, audio_source):
        """Test that successful processing decrements error counter"""
        from ledfx.effects.melbank import MIC_RATE

        audio_source._audio_stream_active = True
        audio_source._stream_error_count = 5
        audio_source.resampler = Mock()

        # Calculate expected output sample length
        out_sample_len = MIC_RATE // 60  # 30000 // 60 = 500

        # Return correct size to ensure successful processing
        audio_source.resampler.process = Mock(
            return_value=np.zeros(out_sample_len, dtype=np.float32)
        )
        audio_source._config = {
            "sample_rate": 60,
            "min_volume": 0.2,
        }
        audio_source.delay_queue = None
        audio_source._raw_audio_sample = np.zeros(
            out_sample_len, dtype=np.float32
        )

        # Mock required methods
        audio_source.pre_process_audio = Mock()
        audio_source._invalidate_caches = Mock()
        audio_source._invoke_callbacks = Mock()

        # Create audio data with different size to trigger resampling
        in_sample_len = (
            735  # Different from out_sample_len to force resampling
        )
        in_data = np.zeros(in_sample_len, dtype=np.float32).tobytes()

        # Call callback successfully - should trigger resampling then success
        audio_source._audio_sample_callback(in_data, in_sample_len, None, None)

        # Error counter should have decreased
        assert audio_source._stream_error_count == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
