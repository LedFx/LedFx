"""Device publication must not block rendering behind a virtual callback."""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from unittest.mock import MagicMock, patch

import numpy as np

from ledfx.configuration.models import VirtualConfig
from ledfx.devices.artnet import ArtNetDevice
from ledfx.virtuals import Virtual


def test_artnet_render_sends_while_configuration_waits_for_virtual() -> None:
    core = MagicMock()
    rendering, callback = threading.Event(), threading.Event()

    class BoundedLock:
        def __init__(self) -> None:
            self.lock = threading.Lock()

        def __enter__(self) -> None:
            assert self.lock.acquire(timeout=2), "configuration/render lock cycle"

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self.lock.release()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        device = ArtNetDevice(
            core,
            ArtNetDevice.config_model().model_validate(
                {
                    "name": "Art-Net",
                    "ip_address": "127.0.0.1",
                    "port": receiver.getsockname()[1],
                    "pixel_count": 1,
                    "packet_size": 6,
                }
            ),
        )
        device.__dict__["_id"] = "device"
        device._destination = "127.0.0.1"
        device._virtuals_objs = []
        virtual = Virtual(core, VirtualConfig.model_validate({"name": "attached"}))
        virtual.__dict__["_id"] = "attached"
        virtual.is_device = device.id
        virtual._segments = [[device.id, 0, 0, False]]
        core.devices.get.return_value = device
        core.config_store.virtual_entry.return_value = None
        core.virtuals.__iter__.return_value = (virtual.id,)
        core.virtuals.get.return_value = virtual
        original_update = virtual.update_segments
        lock = BoundedLock()

        def update(segments: list[list[object]]) -> None:
            callback.set()
            original_update(segments)

        def render() -> None:
            with lock:
                rendering.set()
                assert callback.wait(2)
                # Match the renderer: it owns Virtual.lock while sending pixels.
                # The new configuration has committed before its callback starts.
                device.flush(np.full((2, 3), 73, dtype=np.uint8))

        device.activate()
        try:
            with (
                patch.object(virtual, "lock", lock),
                patch.object(virtual, "update_segments", side_effect=update),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                rendered = executor.submit(render)
                assert rendering.wait(2)
                configured = executor.submit(device.update_config, {"pixel_count": 2})
                configured.result(timeout=4)
                rendered.result(timeout=4)
            assert virtual.segments == [[device.id, 0, 1, False]]
            # Replacing Art-Net emits a blackout first. Require the rendered frame,
            # not just that the workers completed without deadlocking.
            while True:
                packet = receiver.recv(1024)
                if packet[18:] == bytes([73] * 6):
                    break
            assert packet[:8] == b"Art-Net\x00"
        finally:
            device.deactivate()


def test_artnet_contended_frame_defers_layout_initialization() -> None:
    device = ArtNetDevice(
        MagicMock(),
        ArtNetDevice.config_model().model_validate(
            {"name": "Art-Net", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    # Configuration owns this lock while changing output settings. A dropped
    # frame must not initialize a layout from partially published settings.
    with device.lock:
        device.flush(np.ones((1, 3), dtype=np.uint8))
        assert device.init
    device.flush(np.ones((1, 3), dtype=np.uint8))
    assert not device.init
    assert device.channel_count == 3
