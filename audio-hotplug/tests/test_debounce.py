"""Test the debouncer implementation."""

import threading
import time
import pytest

from audio_hotplug._debounce import Debouncer


class TestDebouncer:
    """Test cases for the Debouncer class."""

    def test_single_trigger(self):
        """Test that single trigger invokes callback once."""
        callback_count = {"count": 0}
        
        def callback():
            callback_count["count"] += 1
        
        debouncer = Debouncer(callback, delay_ms=50)
        debouncer.trigger()
        
        # Wait for debounce period + buffer
        time.sleep(0.1)
        
        assert callback_count["count"] == 1
    
    def test_multiple_rapid_triggers_coalesced(self):
        """Test that rapid triggers result in single callback."""
        callback_count = {"count": 0}
        
        def callback():
            callback_count["count"] += 1
        
        debouncer = Debouncer(callback, delay_ms=100)
        
        # Trigger 10 times rapidly
        for _ in range(10):
            debouncer.trigger()
            time.sleep(0.01)  # 10ms between triggers
        
        # Wait for debounce period + buffer
        time.sleep(0.15)
        
        # Should only fire once despite 10 triggers
        assert callback_count["count"] == 1
    
    def test_separate_bursts(self):
        """Test that separated bursts each result in callbacks."""
        callback_count = {"count": 0}
        
        def callback():
            callback_count["count"] += 1
        
        debouncer = Debouncer(callback, delay_ms=50)
        
        # First burst
        debouncer.trigger()
        debouncer.trigger()
        time.sleep(0.1)  # Wait for first callback
        
        # Second burst
        debouncer.trigger()
        debouncer.trigger()
        time.sleep(0.1)  # Wait for second callback
        
        assert callback_count["count"] == 2
    
    def test_thread_safety(self):
        """Test that debouncer is thread-safe."""
        callback_count = {"count": 0}
        lock = threading.Lock()
        
        def callback():
            with lock:
                callback_count["count"] += 1
        
        debouncer = Debouncer(callback, delay_ms=50)
        
        # Trigger from multiple threads simultaneously
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=lambda: [debouncer.trigger() for _ in range(10)])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Wait for debounce
        time.sleep(0.1)
        
        # Should still only fire once despite multi-threaded triggers
        assert callback_count["count"] == 1
    
    def test_cancel(self):
        """Test that cancel prevents callback."""
        callback_count = {"count": 0}
        
        def callback():
            callback_count["count"] += 1
        
        debouncer = Debouncer(callback, delay_ms=100)
        debouncer.trigger()
        
        # Cancel before debounce period expires
        time.sleep(0.02)
        debouncer.cancel()
        
        # Wait past debounce period
        time.sleep(0.15)
        
        assert callback_count["count"] == 0
    
    def test_callback_exception_handled(self):
        """Test that exceptions in callback don't crash debouncer."""
        callback_count = {"count": 0}
        
        def failing_callback():
            callback_count["count"] += 1
            raise ValueError("Test exception")
        
        debouncer = Debouncer(failing_callback, delay_ms=50)
        
        # Should not raise despite callback exception
        debouncer.trigger()
        time.sleep(0.1)
        
        # Verify callback was called
        assert callback_count["count"] == 1
    
    def test_varying_delays(self):
        """Test different debounce delays."""
        for delay_ms in [10, 50, 100, 200]:
            callback_count = {"count": 0}
            
            def callback():
                callback_count["count"] += 1
            
            debouncer = Debouncer(callback, delay_ms=delay_ms)
            debouncer.trigger()
            
            # Wait for delay + buffer
            time.sleep((delay_ms / 1000.0) + 0.05)
            
            assert callback_count["count"] == 1, f"Failed for delay_ms={delay_ms}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
