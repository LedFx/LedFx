"""Regressions for device lifecycle and render-loop fixes."""

import threading
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from ledfx.api.device import DeviceEndpoint
from ledfx.configuration.plugin import PluginConfig
from ledfx.devices import Device
from ledfx.devices.artnet import ArtNetDevice
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.govee import Govee
from ledfx.devices.hue import HueDevice
from ledfx.devices.nanoleaf import NanoleafDevice
from ledfx.devices.osc import OSCServerDevice
from ledfx.devices.rpi_ws281x import RPI_WS281X
from ledfx.devices.wled import WLEDDevice
from ledfx.effects.fire import Fire
from ledfx.mdns_manager import ZeroConfRunner
from ledfx.virtuals import Virtual
from tests.test_utilities.fake_ledfx import fake_ledfx


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
    ledfx = fake_ledfx(
        {"devices": [{"id": "d", "type": "ddp", "config": {"ip_address": "10.0.0.5"}}]}
    )
    device = ledfx.devices.get.return_value
    device.config = PluginConfig.model_validate(
        {"ip_address": "10.0.0.5", "sync_mode": "E131"}
    )
    request = MagicMock()
    request.json = AsyncMock(return_value={"config": {"sync_mode": "E131"}})
    await DeviceEndpoint(ledfx).put("d", request)
    assert ledfx.config.devices[0].config == device.config.as_dict()
    ledfx.config_store.request_save.assert_called_once()


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
    device._built_settings = ("UDP", "wled", "10.0.0.2", 10, 60)
    old = MagicMock()
    device.subdevice = old
    sender = MagicMock()
    sender.config_model.return_value.model_validate.side_effect = dict
    with patch.dict(WLEDDevice.SYNC_MODES, {"UDP": sender}):
        device.config_updated(device._config)
    old.deactivate.assert_called_once()
    assert sender.call_args.args[1]["pixel_count"] == 20


def test_wled_keeps_its_sender_when_only_the_icon_changes() -> None:
    device = object.__new__(WLEDDevice)
    device._config = {
        "sync_mode": "E131",
        "name": "wled",
        "ip_address": "10.0.0.2",
        "pixel_count": 20,
        "refresh_rate": 60,
        "icon_name": "wled",
    }
    device._built_settings = device._output_settings()
    live = MagicMock()
    device.subdevice = live
    device._config = {**device._config, "icon_name": "mdi:lamp"}
    device.config_updated(device._config)
    live.deactivate.assert_not_called()
    assert device.subdevice is live


OUTPUT_DEVICES: list[tuple[type[Device], dict[str, object]]] = [
    (NanoleafDevice, {"ip_address": "10.0.0.3", "auth_token": "t"}),
    (OSCServerDevice, {"ip_address": "10.0.0.3", "port": 9000, "pixel_count": 4}),
    (RPI_WS281X, {"pixel_count": 4, "gpio_pin": 18}),
    (ArtNetDevice, {"ip_address": "10.0.0.3", "pixel_count": 4}),
]


def _output_device(
    cls: type[Device], settings: dict[str, object]
) -> tuple[Device, MagicMock, MagicMock]:
    """A device of cls with its output start/stop replaced by mocks."""
    ledfx = MagicMock()
    validate = cast(vol.Schema, cls.schema())
    with patch.object(cls, "activate"):  # rpi_ws281x starts its strip in __init__
        device = cls(ledfx, validate({"name": "strip", **settings}))
    activate, deactivate = MagicMock(), MagicMock()
    vars(device).update(activate=activate, deactivate=deactivate)
    return device, activate, deactivate


@pytest.mark.parametrize(("cls", "settings"), OUTPUT_DEVICES)
def test_cosmetic_change_keeps_the_output_running(
    cls: type[Device], settings: dict[str, object]
) -> None:
    device, activate, deactivate = _output_device(cls, settings)
    device.update_config({"name": "renamed", "icon_name": "mdi:lamp"})
    assert device._config["name"] == "renamed"
    deactivate.assert_not_called()
    activate.assert_not_called()


def test_output_change_restarts_the_output() -> None:
    device, activate, deactivate = _output_device(*OUTPUT_DEVICES[1])
    device.update_config({"port": 9001})
    deactivate.assert_called_once()
    activate.assert_called_once()
    device.update_config({"icon_name": "mdi:lamp"})  # now built from port 9001
    deactivate.assert_called_once()


def test_failed_config_hook_keeps_the_running_config() -> None:
    device, activate, _ = _output_device(*OUTPUT_DEVICES[1])
    before = device._config
    activate.side_effect = OSError("port in use")
    with pytest.raises(OSError):
        device.update_config({"port": 9001})
    assert device._config is before
    activate.side_effect = None
    device.update_config({"port": 9001})  # retried: still differs from the build
    assert activate.call_count == 2


def test_failed_effect_hook_keeps_the_running_config() -> None:
    effect = Fire(MagicMock(), {})
    before, flip = effect._config, effect.flip
    with (
        patch.object(Fire, "config_updated", side_effect=ValueError("bad")),
        pytest.raises(ValueError),
    ):
        effect.update_config({"flip": not flip})
    assert effect._config is before
    assert effect.flip is flip


def test_rejected_update_keeps_the_resolved_address() -> None:
    device = object.__new__(DDPDevice)
    device._config = {"ip_address": "10.0.0.1"}
    device._destination = "10.0.0.1"
    with (
        patch.object(Device, "update_config", side_effect=vol.Invalid("bad ip")),
        pytest.raises(vol.Invalid),
    ):
        device.update_config({"ip_address": "not an address"})
    assert device._destination == "10.0.0.1"


async def test_mdns_skips_unresolved_services() -> None:
    runner = ZeroConfRunner(MagicMock())
    with (
        patch("ledfx.mdns_manager.AsyncServiceInfo") as info,
        patch("ledfx.mdns_manager.async_fire_and_forget") as fire,
    ):
        info.return_value.async_request = AsyncMock(return_value=False)
        info.return_value.server = None
        await runner.add_wled_device(MagicMock(), "_wled._tcp.local.", "x")
    fire.assert_not_called()


async def test_mdns_keeps_a_service_known_only_by_hostname() -> None:
    runner = ZeroConfRunner(MagicMock())
    with (
        patch("ledfx.mdns_manager.AsyncServiceInfo") as info,
        patch("ledfx.mdns_manager.async_fire_and_forget") as fire,
    ):
        # SRV answered, address records timed out: the hostname still resolves.
        info.return_value.async_request = AsyncMock(return_value=False)
        info.return_value.server = "wled-kitchen.local."
        await runner.add_wled_device(MagicMock(), "_wled._tcp.local.", "x")
    fire.assert_called_once()
    fire.call_args.args[0].close()  # the add_new_device coroutine was never awaited


def test_hue_stops_handshaking_after_success() -> None:
    device = object.__new__(HueDevice)
    device._config = {
        "entertainment_id": "e",
        "ip_address": "10.0.0.4",
        "udp_port": 2100,
    }
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
