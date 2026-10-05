"""Regressions for changing a device's pixel count while LedFx runs."""

from unittest.mock import MagicMock, patch

import numpy as np
from ledfx_senders.e131 import ChannelLayout

from ledfx.configuration.models import VirtualConfig
from ledfx.devices import Device
from ledfx.devices.e131 import E131Device
from ledfx.transitions import Transitions
from ledfx.virtuals import Virtual


def _e131(pixel_count: int) -> E131Device:
    ledfx = MagicMock()
    ledfx.virtuals = dict[str, object]()
    config = E131Device.config_model().model_validate(
        {"name": "e131", "ip_address": "10.0.0.1", "pixel_count": pixel_count}
    )
    device = E131Device(ledfx, config)
    device._destination = "10.0.0.1"
    device._virtuals_objs = []
    return device


def test_e131_pixel_count_change_resizes_channels() -> None:
    from ledfx_senders import E131Sender

    device = _e131(100)

    def capture(
        layout: ChannelLayout,
        *,
        destination: str,
        source_name: str,
        priority: int = 100,
    ) -> E131Sender:
        return E131Sender._test_sender(
            layout,
            mode="capture",
            destination=destination,
            source_name=source_name,
            priority=priority,
        )

    with patch("ledfx.devices.e131.E131Sender", side_effect=capture) as factory:
        device.activate()
        old = device._sender
        assert old is not None
        device.update_config({"pixel_count": 200})
        assert getattr(device.config, "channel_count") == 600  # noqa: B009 - stored extra
        assert getattr(device.config, "universe_end") == 2  # noqa: B009 - stored extra
        assert factory.call_count == 2 and old.closed
        assert device._sender is not None
        assert device._sender.layout.universes == (1, 2)
        device.flush(np.zeros((200, 3)))
        device.deactivate()


def test_pixel_count_change_resizes_device_buffer() -> None:
    # LEDFX-V2-REL-1WD: _pixels kept its old length, so clearing a segment
    # sized for the new count raised a broadcast error.
    device = _e131(1)
    Device.activate(device)  # the buffer only; no sACN sender
    device.update_config({"pixel_count": 4})

    assert device._pixels is not None
    assert device._pixels.shape == (4, 3)
    device._segments = [["v", 0, 3]]
    device.clear_virtual_segments("v")


def test_transition_follows_effective_pixel_count() -> None:
    # LEDFX-V2-REL-4SD: the dissolve mask kept the old length after the
    # effective pixel count changed, so every transition frame raised.
    virtual = object.__new__(Virtual)
    virtual._ledfx = MagicMock()
    virtual._ledfx.config.global_brightness = 1
    virtual._config = VirtualConfig.model_validate({"name": "v"})
    virtual._active_effect = MagicMock()
    virtual._active_effect.get_pixels.return_value = np.zeros((1, 3))
    virtual._transition_effect = MagicMock(is_active=True)
    virtual._transition_effect.get_pixels.return_value = np.zeros((1, 3))
    virtual.transitions = Transitions(2)
    virtual.frame_transitions = virtual.transitions["Dissolve"]
    virtual.transition_frame_counter = 0
    virtual.transition_frame_total = 10

    virtual.assemble_frame()
    assert virtual.transitions.pixel_count == 1


def test_shrinking_an_active_device_clears_its_old_segment() -> None:
    # Shrinking resizes the buffer before the old segment is cleared.
    device = _e131(4)
    device._ledfx.config.flush_on_deactivate = True
    Device.activate(device)  # the buffer only; no sACN sender
    device._segments = [["v", 0, 3]]
    device.update_config({"pixel_count": 2})
    device.clear_virtual_segments("v")

    assert device._pixels is not None
    assert device._pixels.shape == (2, 3)


def test_e131_ip_address_change_rebuilds_the_sender() -> None:
    from ledfx_senders import E131Sender

    device = _e131(100)

    def capture(
        layout: ChannelLayout,
        *,
        destination: str,
        source_name: str,
        priority: int = 100,
    ) -> E131Sender:
        return E131Sender._test_sender(
            layout,
            mode="capture",
            destination=destination,
            source_name=source_name,
            priority=priority,
        )

    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        device.activate()
        old = device._sender
        assert old is not None
        device.update_config({"ip_address": "10.0.0.2"})
        assert old.closed and device._sender is None
        assert device._destination is None
        assert device._ledfx.loop.call_soon_threadsafe.called
        device.deactivate()


def test_e131_layout_ending_on_a_universe_boundary_sends_every_channel() -> None:
    from ledfx_senders import E131Sender

    device = _e131(170)
    device.update_config({"channel_offset": 1})

    def capture(
        layout: ChannelLayout,
        *,
        destination: str,
        source_name: str,
        priority: int = 100,
    ) -> E131Sender:
        return E131Sender._test_sender(
            layout,
            mode="capture",
            destination=destination,
            source_name=source_name,
            priority=priority,
        )

    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        device.activate()
        device.flush(np.full((170, 3), 255))
        assert device._sender is not None
        packets = device._sender._engine.captures()
        assert packets[1][0][126] == 255
        assert getattr(device.config, "universe_end") == 2  # noqa: B009 - stored extra
        device.deactivate()


def test_networked_device_virtual_callbacks_run_after_publication_unlocks() -> None:
    from ledfx.devices.ddp import DDPDevice

    core = MagicMock()
    d = DDPDevice(
        core,
        DDPDevice.config_model().model_validate(
            {"name": "DDP", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    d.__dict__["_id"] = "ddp"
    d._destination = "127.0.0.1"
    attached, segmented = MagicMock(), MagicMock()
    attached.is_device = d.id
    core.virtuals = {"attached": attached}
    d._virtuals_objs = [segmented]
    Device.activate(d)

    def assert_published_and_unlocked(*args: object) -> None:
        assert d.lock.acquire(blocking=False), "base lock leaked into virtual callbacks"
        try:
            assert d.pixel_count == 2
            assert d._destination is None
            assert d._pixels is not None and d._pixels.shape == (2, 3)
        finally:
            d.lock.release()

    attached.update_segments.side_effect = assert_published_and_unlocked
    segmented.deactivate_segments.side_effect = assert_published_and_unlocked
    segmented.activate_segments.side_effect = assert_published_and_unlocked
    d.update_config({"pixel_count": 2, "ip_address": "127.0.0.2"})
    attached.update_segments.assert_called_once_with([[d.id, 0, 1, False]])
    segmented.deactivate_segments.assert_called_once()
    segmented.activate_segments.assert_called_once()
    Device.deactivate(d)


def test_networked_device_failed_publication_restores_destination_and_config() -> None:
    import pytest

    from ledfx.devices.ddp import DDPDevice

    core = MagicMock()
    core.virtuals = dict[str, object]()
    d = DDPDevice(
        core,
        DDPDevice.config_model().model_validate(
            {"name": "DDP", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    d._destination = "127.0.0.1"
    d._virtuals_objs = []
    original = d._config
    with pytest.raises(ValueError):
        d.update_config({"pixel_count": 0, "ip_address": "127.0.0.2"})
    assert d._destination == "127.0.0.1" and d._config is original
    with (
        patch.object(DDPDevice, "config_updated", side_effect=OSError("setup failed")),
        pytest.raises(OSError),
    ):
        d.update_config({"pixel_count": 2, "ip_address": "127.0.0.2"})
    assert d._destination == "127.0.0.1" and d._config is original
    d.update_config({"pixel_count": 2})
    assert d._destination == "127.0.0.1" and d.pixel_count == 2
