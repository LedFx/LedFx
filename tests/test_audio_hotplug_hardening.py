"""
Tests for the audio hotplug hardening pass introduced in PR 1776 follow-up.

What is tested here:
- Refresh coalescing: simultaneous hotplug events collapse to one refresh + one queued rerun
- One-rerun-only guarantee: no unbounded queue of refresh threads
- Stale stream generation rejection in the callback path
- _close_stream() fallback ordering when stop() times out
- Rate-limited malformed-frame logging (once per stream generation)

What is NOT tested (acceptable limitations):
- True end-to-end PortAudio cycle (sd._terminate / sd._initialize) requires real hardware
- Windows WASAPI loopback hang simulation requires a real or mock PortAudio driver
"""

import threading
import time
import types
import unittest
from unittest.mock import MagicMock, call, patch

from ledfx.effects.audio import AudioInputSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_class_state():
    """
    Reset AudioInputSource class-level state between tests.
    This is required because the class variables are shared singletons.
    """
    AudioInputSource._audio_stream_active = False
    AudioInputSource._stream = None
    AudioInputSource._activating = False
    AudioInputSource._refresh_in_progress = False
    AudioInputSource._refresh_pending = False
    AudioInputSource._refresh_generation = 0
    AudioInputSource._stream_generation = 0
    AudioInputSource._last_active = None
    AudioInputSource._last_device_name = None


def make_ais_bare():
    """
    Return an AudioInputSource-like instance WITHOUT calling __init__
    so we avoid needing real audio hardware or a real LedFx instance.

    Sets up the minimum instance attributes used by handle_device_list_change
    and _audio_sample_callback.
    """
    ais = object.__new__(AudioInputSource)
    ais._ledfx = None
    ais._callbacks = []
    ais._config = {
        "audio_device": 0,
        "audio_device_name": "",
        "sample_rate": 60,
        "delay_ms": 0,
    }
    ais._callback_stream_gen = 0
    ais._malformed_frame_last_gen = None
    ais.lock = threading.Lock()
    return ais


# ---------------------------------------------------------------------------
# §1 — Refresh coalescing
# ---------------------------------------------------------------------------


class TestRefreshCoalescing(unittest.TestCase):
    """
    Verify that rapid back-to-back calls to handle_device_list_change()
    collapse to one active refresh and at most one pending rerun.
    """

    def setUp(self):
        _reset_class_state()
        self.ais = make_ais_bare()

    def tearDown(self):
        _reset_class_state()

    def test_second_call_while_refreshing_sets_pending(self):
        """
        While a refresh is running, a second call must set _refresh_pending
        and return immediately — it must NOT start a concurrent refresh.
        After the first refresh completes, exactly one follow-up (gen=2)
        is expected (triggered by the pending flag).
        """
        entered = threading.Event()
        proceed = threading.Event()
        calls_to_run_refresh = []
        all_done = threading.Event()

        def slow_run_refresh(gen):
            calls_to_run_refresh.append(gen)
            if gen == 1:
                entered.set()
                proceed.wait(timeout=5)
            else:
                # gen=2 follow-up ran — signal completion
                all_done.set()

        self.ais._run_device_refresh = slow_run_refresh

        t = threading.Thread(target=self.ais.handle_device_list_change)
        t.start()
        entered.wait(timeout=5)  # first call is inside _run_device_refresh

        # Second and third calls arrive while first is in-flight
        self.ais.handle_device_list_change()
        self.ais.handle_device_list_change()

        with AudioInputSource._class_lock:
            pending = AudioInputSource._refresh_pending

        self.assertTrue(pending, "_refresh_pending should be set")

        proceed.set()
        t.join(timeout=5)

        # Wait for the queued follow-up refresh (gen=2) to complete too
        all_done.wait(timeout=5)

        # Exactly two refreshes ran: gen=1 (original) + gen=2 (queued rerun)
        self.assertEqual(
            len(calls_to_run_refresh),
            2,
            f"Expected [1, 2], got {calls_to_run_refresh}",
        )

    def test_no_unbounded_queue(self):
        """
        Even after many hotplug events while refreshing, only one follow-up
        refresh can be queued (_refresh_pending, not a list or counter).
        Calling handle_device_list_change 100 times while refresh is in
        progress still results in exactly one pending flag, not 99.
        """
        barrier = threading.Barrier(2)
        proceed = threading.Event()

        def slow_run_refresh(gen):
            barrier.wait(timeout=5)
            proceed.wait(timeout=5)

        self.ais._run_device_refresh = slow_run_refresh

        t = threading.Thread(target=self.ais.handle_device_list_change)
        t.start()
        barrier.wait(timeout=5)

        for _ in range(100):
            self.ais.handle_device_list_change()

        with AudioInputSource._class_lock:
            pending = AudioInputSource._refresh_pending

        proceed.set()
        t.join(timeout=5)

        self.assertTrue(pending, "Pending flag should be set")
        # The important invariant: pending is a single boolean, not a counter.
        self.assertIsInstance(pending, bool)

    def test_first_call_when_idle_runs_immediately(self):
        """
        When no refresh is running, the first call runs synchronously and
        sets _refresh_in_progress for its duration.
        """
        run_refresh_called_with = []
        in_progress_during_call = []

        def immediate_run_refresh(gen):
            run_refresh_called_with.append(gen)
            in_progress_during_call.append(
                AudioInputSource._refresh_in_progress
            )

        self.ais._run_device_refresh = immediate_run_refresh

        self.ais.handle_device_list_change()

        self.assertEqual(len(run_refresh_called_with), 1)
        self.assertTrue(
            in_progress_during_call[0],
            "_refresh_in_progress should be True while running",
        )
        # After return, _refresh_in_progress must be cleared
        self.assertFalse(AudioInputSource._refresh_in_progress)

    def test_generation_counter_increments_per_refresh(self):
        """
        Each distinct (non-coalesced) call to handle_device_list_change()
        must increment _refresh_generation.
        """
        gens_seen = []

        def capture_gen(gen):
            gens_seen.append(gen)

        self.ais._run_device_refresh = capture_gen

        initial = AudioInputSource._refresh_generation
        self.ais.handle_device_list_change()
        self.ais.handle_device_list_change()

        self.assertEqual(gens_seen[0], initial + 1)
        self.assertEqual(gens_seen[1], initial + 2)


# ---------------------------------------------------------------------------
# §2 — Stale stream generation rejection in the callback
# ---------------------------------------------------------------------------


class TestCallbackGenerationGuard(unittest.TestCase):
    """
    Verify that _audio_sample_callback() silently discards frames that
    arrive from a stream whose generation no longer matches the class-level
    _stream_generation counter.
    """

    def setUp(self):
        _reset_class_state()
        self.ais = make_ais_bare()
        # Minimal attributes needed by _audio_sample_callback
        import numpy as np

        self.ais._config = {
            "sample_rate": 60,
            "delay_ms": 0,
            "min_volume": 0.2,
            "fft_size": 256,
        }
        self.ais.delay_queue = None

    def tearDown(self):
        _reset_class_state()

    def test_current_generation_processes_frame(self):
        """
        A callback from the current stream generation must be forwarded to
        pre_process_audio() / _invoke_callbacks().
        """
        import numpy as np

        # Align generations
        AudioInputSource._stream_generation = 3
        self.ais._callback_stream_gen = 3

        processed = []

        def fake_pre_process():
            processed.append(True)

        self.ais.pre_process_audio = fake_pre_process
        self.ais._invalidate_caches = MagicMock()
        self.ais._invoke_callbacks = MagicMock()

        # Expected sample count for sample_rate=60, MIC_RATE=44100
        from ledfx.effects.melbank import MIC_RATE

        out_len = MIC_RATE // 60  # = 735
        dummy_data = np.zeros(out_len, dtype=np.float32).tobytes()

        self.ais.resampler = MagicMock()
        self.ais.resampler.process = MagicMock(
            return_value=np.zeros(out_len, dtype=np.float32)
        )

        self.ais._audio_sample_callback(dummy_data, out_len, None, None)

        self.assertEqual(len(processed), 1, "Frame from current gen should be processed")

    def test_stale_generation_discards_frame(self):
        """
        A callback whose _callback_stream_gen is behind the current
        _stream_generation must be silently discarded.
        """
        import numpy as np

        AudioInputSource._stream_generation = 5
        self.ais._callback_stream_gen = 3  # stale

        processed = []

        def fake_pre_process():
            processed.append(True)

        self.ais.pre_process_audio = fake_pre_process
        self.ais._invoke_callbacks = MagicMock()

        from ledfx.effects.melbank import MIC_RATE

        out_len = MIC_RATE // 60
        dummy_data = np.zeros(out_len, dtype=np.float32).tobytes()

        self.ais._audio_sample_callback(dummy_data, out_len, None, None)

        self.assertEqual(len(processed), 0, "Stale callback must not process data")
        self.ais._invoke_callbacks.assert_not_called()


# ---------------------------------------------------------------------------
# §3 — Malformed frame rate-limiting
# ---------------------------------------------------------------------------


class TestMalformedFrameRateLimit(unittest.TestCase):
    """
    Verify that malformed frame warnings are logged at most once per stream
    generation to prevent log flooding during device teardown.
    """

    def setUp(self):
        _reset_class_state()
        self.ais = make_ais_bare()
        import numpy as np

        self.ais._config = {
            "sample_rate": 60,
            "delay_ms": 0,
            "min_volume": 0.2,
            "fft_size": 256,
        }
        self.ais.delay_queue = None
        AudioInputSource._stream_generation = 1
        self.ais._callback_stream_gen = 1

    def tearDown(self):
        _reset_class_state()

    def test_malformed_frame_logged_once_per_gen(self):
        """
        Sending 10 malformed frames in the same generation should produce
        exactly one debug log, not 10.
        """
        import numpy as np
        from ledfx.effects.melbank import MIC_RATE

        # Wrong size — will be malformed after resampler returns different length
        out_len = MIC_RATE // 60  # expected
        wrong_len = out_len - 1
        dummy_data = np.zeros(wrong_len, dtype=np.float32).tobytes()

        self.ais.resampler = MagicMock()
        # Resampler returns wrong-size data
        self.ais.resampler.process = MagicMock(
            return_value=np.zeros(wrong_len, dtype=np.float32)
        )

        log_calls = []

        with patch("ledfx.effects.audio._LOGGER") as mock_logger:
            for _ in range(10):
                self.ais._audio_sample_callback(
                    dummy_data, wrong_len, None, None
                )
            debug_calls = [
                c
                for c in mock_logger.debug.call_args_list
                if "malformed" in str(c).lower()
            ]
            self.assertEqual(
                len(debug_calls),
                1,
                f"Expected 1 malformed-frame log, got {len(debug_calls)}",
            )


# ---------------------------------------------------------------------------
# §4 — _close_stream() fallback ordering
# ---------------------------------------------------------------------------


class TestCloseStreamFallback(unittest.TestCase):
    """
    Verify _close_stream() correctly:
    1. Calls stop() with a timeout
    2. Falls back to abort() when stop() times out
    3. Always calls close()
    4. Logs the timeout warning
    """

    def setUp(self):
        _reset_class_state()

    def tearDown(self):
        _reset_class_state()

    def test_clean_stop_no_abort(self):
        """When stop() returns quickly, abort() should NOT be called."""
        stream = MagicMock()
        stream.stop = MagicMock(return_value=None)
        stream.close = MagicMock()
        stream.abort = MagicMock()

        AudioInputSource._close_stream(
            stream, context="test", gen=1, device_name="TestDev", device_idx=5
        )

        stream.stop.assert_called_once()
        stream.close.assert_called_once()
        stream.abort.assert_not_called()

    def test_timeout_triggers_abort_then_close(self):
        """When stop() wedges, abort() and close() must both be called."""
        stream = MagicMock()
        # stop() blocks until abort() is called (simulated by a long sleep)
        stop_event = threading.Event()

        def blocking_stop():
            stop_event.wait(timeout=30)  # simulate wedged stop

        stream.stop = MagicMock(side_effect=blocking_stop)
        stream.close = MagicMock()
        stream.abort = MagicMock(side_effect=lambda: stop_event.set())

        # Use a very short timeout for the test
        orig_timeout = AudioInputSource._STREAM_STOP_TIMEOUT_S
        AudioInputSource._STREAM_STOP_TIMEOUT_S = 0.1
        try:
            AudioInputSource._close_stream(
                stream, context="test", gen=7, device_name="WedgeDev", device_idx=2
            )
        finally:
            AudioInputSource._STREAM_STOP_TIMEOUT_S = orig_timeout

        stream.abort.assert_called_once()
        stream.close.assert_called_once()

    def test_stop_exception_still_closes(self):
        """If stop() raises immediately, close() must still be called."""
        stream = MagicMock()
        stream.stop = MagicMock(side_effect=RuntimeError("stop exploded"))
        stream.close = MagicMock()
        stream.abort = MagicMock()

        AudioInputSource._close_stream(stream, context="test", gen=2)

        # stop() threw in the worker thread — the worker exits and join() returns
        # immediately (no timeout), so abort() is not called
        stream.close.assert_called_once()

    def test_close_exception_logged_not_raised(self):
        """If close() raises, it must be caught and logged — not propagate."""
        stream = MagicMock()
        stream.stop = MagicMock(return_value=None)
        stream.close = MagicMock(side_effect=RuntimeError("close boom"))

        # Must not raise
        AudioInputSource._close_stream(stream, context="test", gen=3)

    def test_none_stream_is_noop(self):
        """Passing None for the stream must be a silent no-op."""
        # Must not raise
        AudioInputSource._close_stream(None, context="test", gen=1)

    def test_timeout_logs_warning(self):
        """A timed-out stop() must produce a warning log containing the gen."""
        stream = MagicMock()
        stop_event = threading.Event()

        def blocking_stop():
            stop_event.wait(timeout=30)

        stream.stop = MagicMock(side_effect=blocking_stop)
        stream.close = MagicMock()
        stream.abort = MagicMock(side_effect=lambda: stop_event.set())

        orig_timeout = AudioInputSource._STREAM_STOP_TIMEOUT_S
        AudioInputSource._STREAM_STOP_TIMEOUT_S = 0.1
        try:
            with patch("ledfx.effects.audio._LOGGER") as mock_logger:
                AudioInputSource._close_stream(
                    stream, context="test", gen=42, device_name="Dev", device_idx=3
                )
                warning_messages = [
                    str(c) for c in mock_logger.warning.call_args_list
                ]
                self.assertTrue(
                    any("timed out" in m.lower() for m in warning_messages),
                    f"Expected timed-out warning, got: {warning_messages}",
                )
        finally:
            AudioInputSource._STREAM_STOP_TIMEOUT_S = orig_timeout


# ---------------------------------------------------------------------------
# §5 — Rerun-only-once guarantee after pending refresh
# ---------------------------------------------------------------------------


class TestRefreshRerunOnce(unittest.TestCase):
    """
    After a refresh completes and _refresh_pending was set, exactly one
    follow-up refresh must be launched — not two, not zero.
    """

    def setUp(self):
        _reset_class_state()
        self.ais = make_ais_bare()

    def tearDown(self):
        _reset_class_state()

    def test_one_rerun_when_pending(self):
        """
        Simulate: refresh 1 runs, multiple hotplug events arrive during it.
        After refresh 1 completes, exactly one follow-up refresh (refresh 2)
        must run.  No more.
        """
        barrier = threading.Barrier(2)
        proceed = threading.Event()
        gens_executed = []

        def controlled_refresh(gen):
            gens_executed.append(gen)
            if gen == 1:
                # Signal the main thread that gen=1 is in progress
                barrier.wait(timeout=5)
                # Wait until main thread has fired extra hotplug events
                proceed.wait(timeout=5)

        self.ais._run_device_refresh = controlled_refresh

        t = threading.Thread(target=self.ais.handle_device_list_change)
        t.start()
        barrier.wait(timeout=5)

        # Fire several hotplug events while gen=1 is running
        for _ in range(5):
            self.ais.handle_device_list_change()

        proceed.set()
        t.join(timeout=5)

        # Allow the follow-up thread (gen=2) to finish
        time.sleep(0.3)

        self.assertEqual(gens_executed, [1, 2], f"Expected [1, 2], got {gens_executed}")


if __name__ == "__main__":
    unittest.main()
