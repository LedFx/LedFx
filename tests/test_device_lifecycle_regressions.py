"""Regressions for device lifecycle and render-loop fixes."""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

from ledfx.api.device import DeviceEndpoint
from ledfx.devices import Device
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.govee import Govee
from ledfx.devices.hue import HueDevice
from ledfx.devices.wled import WLEDDevice
from ledfx.effects.fire import Fire
from ledfx.mdns_manager import ZeroConfRunner
from ledfx.virtuals import Virtual


def test_render_thread_survives_frame_exception() -> None:
    virtual = object.__new__(Virtual)
    virtual._active = True
    virtual.fallback_fire = False
    virtual.lock = threading.Lock()
    virtual._active_effect = MagicMock(is_active=True, pixels=None)
    frames: list[int] = []

    def assemble() -> None:
        frames.append(1)
        if len(frames) == 1:
            raise RuntimeError("effect bug")
        virtual._active = False

    virtual.assemble_frame = assemble
    with (
        patch.object(Virtual, "refresh_rate", 1000),
        patch.object(Virtual, "id", "v"),
    ):
        virtual.thread_function()
    assert len(frames) == 2


async def test_device_put_persists_merged_config() -> None:
    ledfx = MagicMock()
    device = ledfx.devices.get.return_value
    device.config = {"ip_address": "10.0.0.5", "sync_mode": "E131"}
    ledfx.config = {"devices": [{"id": "d", "config": {"ip_address": "10.0.0.5"}}]}
    request = MagicMock()
    request.json = AsyncMock(return_value={"config": {"sync_mode": "E131"}})
    with patch("ledfx.api.device.save_config"):
        await DeviceEndpoint(ledfx).put("d", request)
    assert ledfx.config["devices"][0]["config"] == device.config


def test_ip_change_forces_address_re_resolution() -> None:
    device = object.__new__(DDPDevice)
    device._config = {"ip_address": "10.0.0.1"}
    device._destination = "10.0.0.1"
    with patch.object(Device, "update_config"):
        device.update_config({"pixel_count": 10})
        assert device._destination == "10.0.0.1"
        device.update_config({"ip_address": "10.0.0.2"})
    assert device._destination is None


def test_wled_rebuilds_subdevice_on_pixel_count_change() -> None:
    device = object.__new__(WLEDDevice)
    device._ledfx = MagicMock()
    device._active = False
    device._destination = "10.0.0.2"
    device._config = {
        "sync_mode": "UDP",
        "name": "wled",
        "ip_address": "10.0.0.2",
        "pixel_count": 20,
        "refresh_rate": 60,
    }
    device.device_configs = {"UDP": {}}
    old = MagicMock()
    device.subdevice = old
    sender = MagicMock()
    with patch.dict(WLEDDevice.SYNC_MODES, {"UDP": sender}):
        device.config_updated(device._config)
    old.deactivate.assert_called_once()
    assert sender.call_args.args[1]["pixel_count"] == 20


async def test_mdns_skips_unresolved_services() -> None:
    runner = ZeroConfRunner(MagicMock())
    with (
        patch("ledfx.mdns_manager.AsyncServiceInfo") as info,
        patch("ledfx.mdns_manager.async_fire_and_forget") as fire,
    ):
        info.return_value.async_request = AsyncMock(return_value=False)
        await runner.add_wled_device(MagicMock(), "_wled._tcp.local.", "x")
    fire.assert_not_called()


def test_hue_stops_handshaking_after_success() -> None:
    device = object.__new__(HueDevice)
    device._config = {"entertainment_id": "e", "ip_address": "10.0.0.4", "udp_port": 2100}
    device._dtls_client_context = MagicMock()
    with (
        patch.object(HueDevice, "_hue_request"),
        patch("ledfx.devices.hue.socket.socket"),
        patch("ledfx.devices.hue.time.sleep"),
        patch("ledfx.devices.NetworkedDevice.activate"),
    ):
        device.activate()
    wrapped = device._dtls_client_context.wrap_socket.return_value
    assert wrapped.do_handshake.call_count == 1


def test_govee_second_deactivate_does_not_release_socket_again() -> None:
    device = object.__new__(Govee)
    device._config = {"name": "govee"}
    server = MagicMock()
    device.udp_server = server
    with (
        patch.object(Govee, "send_deactivate"),
        patch.object(Device, "deactivate"),
    ):
        device.deactivate()
        device.deactivate()
    server.close.assert_called_once()


def test_unextended_schema_returns_own_schema() -> None:
    assert Fire.schema(extended=False) is Fire.CONFIG_SCHEMA

