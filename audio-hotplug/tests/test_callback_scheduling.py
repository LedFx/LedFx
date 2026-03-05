"""Test callback scheduling (sync and async)."""

import asyncio
import threading
import time
import pytest

from audio_hotplug._base import AudioDeviceMonitor


class MockMonitor(AudioDeviceMonitor):
    """Mock monitor for testing base class functionality."""
    
    def start(self, on_change):
        self._callback = on_change
    
    def stop(self):
        pass
    
    def trigger_from_thread(self):
        """Simulate triggering callback from background thread."""
        if self._callback:
            self._notify(self._callback)


class TestCallbackScheduling:
    """Test cases for callback scheduling in AudioDeviceMonitor."""
    
    def test_sync_callback_with_loop(self):
        """Test sync callback invoked on event loop."""
        loop = asyncio.new_event_loop()
        callback_invoked = {"value": False}
        
        def callback():
            callback_invoked["value"] = True
        
        monitor = MockMonitor(loop=loop)
        monitor.start(callback)
        
        # Trigger from different thread
        thread = threading.Thread(target=monitor.trigger_from_thread)
        thread.start()
        thread.join()
        
        # Run loop briefly to process callback
        loop.run_until_complete(asyncio.sleep(0.01))
        
        assert callback_invoked["value"]
        loop.close()
    
    def test_async_callback_with_loop(self):
        """Test async callback scheduled on event loop."""
        loop = asyncio.new_event_loop()
        callback_invoked = {"value": False}
        
        async def async_callback():
            await asyncio.sleep(0.01)
            callback_invoked["value"] = True
        
        monitor = MockMonitor(loop=loop)
        monitor.start(async_callback)
        
        # Trigger from different thread
        thread = threading.Thread(target=monitor.trigger_from_thread)
        thread.start()
        thread.join()
        
        # Run loop to completion
        loop.run_until_complete(asyncio.sleep(0.05))
        
        assert callback_invoked["value"]
        loop.close()
    
    def test_sync_callback_no_loop_direct_call(self):
        """Test sync callback without loop calls directly."""
        callback_invoked = {"value": False}
        
        def callback():
            callback_invoked["value"] = True
        
        monitor = MockMonitor(loop=None)
        monitor.start(callback)
        monitor.trigger_from_thread()
        
        # Give it a moment
        time.sleep(0.01)
        
        assert callback_invoked["value"]
    
    def test_async_callback_no_loop_error(self):
        """Test async callback without loop logs error."""
        async def async_callback():
            pass
        
        monitor = MockMonitor(loop=None)
        monitor.start(async_callback)
        
        # Should not raise, but should log error
        monitor.trigger_from_thread()
        time.sleep(0.01)
        # No assertion - just verify no crash
    
    def test_sync_callback_exception_caught(self):
        """Test exceptions in sync callback are caught and logged."""
        callback_invoked = {"value": False}
        
        def failing_callback():
            callback_invoked["value"] = True
            raise ValueError("Test exception")
        
        loop = asyncio.new_event_loop()
        monitor = MockMonitor(loop=loop)
        monitor.start(failing_callback)
        
        # Should not propagate exception
        thread = threading.Thread(target=monitor.trigger_from_thread)
        thread.start()
        thread.join()
        
        loop.run_until_complete(asyncio.sleep(0.01))
        
        assert callback_invoked["value"]
        loop.close()
    
    def test_async_callback_exception_caught(self):
        """Test exceptions in async callback are caught and logged."""
        callback_invoked = {"value": False}
        
        async def failing_async_callback():
            callback_invoked["value"] = True
            raise ValueError("Test exception")
        
        loop = asyncio.new_event_loop()
        monitor = MockMonitor(loop=loop)
        monitor.start(failing_async_callback)
        
        thread = threading.Thread(target=monitor.trigger_from_thread)
        thread.start()
        thread.join()
        
        loop.run_until_complete(asyncio.sleep(0.05))
        
        assert callback_invoked["value"]
        loop.close()
    
    def test_running_loop_detection(self):
        """Test that running loop is detected when none provided."""
        callback_invoked = {"value": False}
        
        async def test_with_running_loop():
            def callback():
                callback_invoked["value"] = True
            
            # Don't pass loop, should detect running loop
            monitor = MockMonitor(loop=None)
            monitor.start(callback)
            
            # Trigger from different thread
            thread = threading.Thread(target=monitor.trigger_from_thread)
            thread.start()
            thread.join()
            
            await asyncio.sleep(0.01)
        
        asyncio.run(test_with_running_loop())
        assert callback_invoked["value"]
    
    def test_multiple_rapid_callbacks(self):
        """Test multiple rapid callback invocations."""
        loop = asyncio.new_event_loop()
        callback_count = {"count": 0}
        
        def callback():
            callback_count["count"] += 1
        
        monitor = MockMonitor(loop=loop)
        monitor.start(callback)
        
        # Trigger multiple times
        for _ in range(10):
            thread = threading.Thread(target=monitor.trigger_from_thread)
            thread.start()
            thread.join(timeout=0.01)
        
        loop.run_until_complete(asyncio.sleep(0.05))
        
        # All callbacks should be invoked
        assert callback_count["count"] == 10
        loop.close()


@pytest.mark.asyncio
async def test_async_context():
    """Test callback within async context using pytest-asyncio."""
    callback_invoked = {"value": False}
    
    async def async_callback():
        await asyncio.sleep(0.01)
        callback_invoked["value"] = True
    
    loop = asyncio.get_event_loop()
    monitor = MockMonitor(loop=loop)
    monitor.start(async_callback)
    
    thread = threading.Thread(target=monitor.trigger_from_thread)
    thread.start()
    thread.join()
    
    await asyncio.sleep(0.05)
    
    assert callback_invoked["value"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
