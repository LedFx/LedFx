"""Regressions for device lifecycle and render-loop fixes."""

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    virtual._output_lock = threading.RLock()
    virtual._retired_effects = []
    virtual._render_token = 0
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


async def test_device_put_invalid_config_returns_structured_400() -> None:
    ledfx = fake_ledfx()
    device = WLEDDevice(
        ledfx,
        WLEDDevice.Config.model_validate(
            {"name": "wled", "ip_address": "10.0.0.2", "sync_mode": "DDP"}
        ),
    )
    ledfx.devices.get.return_value = device
    request = MagicMock()
    request.json = AsyncMock(return_value={"config": {"sync_mode": "bogus"}})
    response = await DeviceEndpoint(ledfx).put("d", request)
    body = json.loads(response.text or "")
    assert response.status == 400 and body["errors"][0]["loc"] == ["sync_mode"]
    assert device.config.sync_mode == "DDP"
    ledfx.config_store.request_save.assert_not_called()


def test_ip_change_forces_address_re_resolution() -> None:
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = DDPDevice(
        core,
        DDPDevice.config_model().model_validate(
            {"name": "DDP", "ip_address": "10.0.0.1"}
        ),
    )
    device._virtuals_objs = []
    device._destination = "10.0.0.1"
    device.update_config({"pixel_count": 10})
    assert device._destination == "10.0.0.1"
    device.update_config({"ip_address": "10.0.0.2"})
    assert device._destination is None


def test_update_config_merges_into_model_and_keeps_stored_extras() -> None:
    device = WLEDDevice(
        MagicMock(),
        WLEDDevice.Config.model_validate(
            {"name": "wled", "ip_address": "10.0.0.2", "pixel_count": 20}
        ),
    )
    device._destination = "10.0.0.2"
    with patch.object(WLEDDevice, "setup_subdevice"):
        device.update_config({"sync_mode": "UDP"})
    assert device.config.sync_mode == "UDP"
    assert device.config.name == "wled"
    assert device.config.model_extra == {"pixel_count": 20}
    assert device._destination == "10.0.0.2"


def test_wled_rebuilds_subdevice_on_pixel_count_change() -> None:
    device = WLEDDevice(
        MagicMock(),
        WLEDDevice.Config.model_validate(
            {
                "sync_mode": "UDP",
                "name": "wled",
                "ip_address": "10.0.0.2",
                "pixel_count": 20,
                "refresh_rate": 60,
            }
        ),
    )
    device._destination = "10.0.0.2"
    device.device_configs = {"UDP": {}}
    device._built_settings = ("UDP", "wled", "10.0.0.2", 10, 60)
    old = MagicMock()
    device.subdevice = old
    sender = MagicMock()
    sender.Config.model_validate.side_effect = dict
    with patch.dict(WLEDDevice.SYNC_MODES, {"UDP": sender}):
        device.config_updated(device._config)
    old.deactivate.assert_called_once()
    assert sender.call_args.args[1]["pixel_count"] == 20


def test_wled_keeps_its_sender_when_only_the_icon_changes() -> None:
    settings = {
        "sync_mode": "E131",
        "name": "wled",
        "ip_address": "10.0.0.2",
        "pixel_count": 20,
        "refresh_rate": 60,
    }
    device = WLEDDevice(
        MagicMock(), WLEDDevice.Config.model_validate(settings | {"icon_name": "wled"})
    )
    device._built_settings = device._output_settings()
    live = MagicMock()
    device.subdevice = live
    device._config = device.config.model_copy(update={"icon_name": "mdi:lamp"})
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
    config = cls.config_model().model_validate({"name": "strip", **settings})
    with patch.object(cls, "activate"):  # rpi_ws281x starts its strip in __init__
        device = cls(ledfx, config)
    activate, deactivate = MagicMock(), MagicMock()
    vars(device).update(activate=activate, deactivate=deactivate)
    return device, activate, deactivate


@pytest.mark.parametrize(("cls", "settings"), OUTPUT_DEVICES)
def test_cosmetic_change_keeps_the_output_running(
    cls: type[Device], settings: dict[str, object]
) -> None:
    device, activate, deactivate = _output_device(cls, settings)
    device.update_config({"name": "renamed", "icon_name": "mdi:lamp"})
    assert device.config.name == "renamed"
    deactivate.assert_not_called()
    activate.assert_not_called()


def test_output_change_replaces_the_artnet_sender() -> None:
    device, activate, deactivate = _output_device(*OUTPUT_DEVICES[3])
    assert isinstance(device, ArtNetDevice)
    live, candidate = MagicMock(), MagicMock()
    device._sender = live
    device._requested = True
    device._destination = "127.0.0.1"
    with patch.object(device, "_make_sender", return_value=candidate) as make:
        device.update_config({"packet_size": 512})
        make.assert_called_once()
    assert device._sender is candidate
    live.close.assert_called_once()
    device.update_config({"icon_name": "mdi:lamp"})
    candidate.close.assert_not_called()
    deactivate.assert_not_called()
    activate.assert_not_called()


def test_failed_config_hook_keeps_the_running_config() -> None:
    device, _, _ = _output_device(*OUTPUT_DEVICES[3])
    assert isinstance(device, ArtNetDevice)
    before = device._config
    live = MagicMock()
    device._sender = live
    device._requested = True
    device._destination = "127.0.0.1"
    with patch.object(
        device, "_make_sender", side_effect=OSError("socket unavailable")
    ) as make:
        with pytest.raises(OSError):
            device.update_config({"packet_size": 512})
        assert device._config is before
        assert device._sender is live
        live.close.assert_not_called()
        make.side_effect = None
        device.update_config({"packet_size": 512})
        assert make.call_count == 2


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
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = DDPDevice(
        core,
        DDPDevice.config_model().model_validate(
            {"name": "DDP", "ip_address": "10.0.0.1"}
        ),
    )
    device._destination = "10.0.0.1"
    original = device._config

    def reject(configured_device: DDPDevice, config: object) -> None:
        assert configured_device is device
        assert device._destination is None
        raise ValueError("bad ip")

    with (
        patch.object(DDPDevice, "config_updated", side_effect=reject),
        pytest.raises(ValueError),
    ):
        device.update_config({"ip_address": "not an address"})
    assert device._destination == "10.0.0.1" and device._config is original


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


async def test_mdns_rescan_closes_the_previous_zeroconf() -> None:
    runner = ZeroConfRunner(MagicMock())
    with (
        patch("ledfx.mdns_manager.AsyncZeroconf") as zeroconf,
        patch("ledfx.mdns_manager.AsyncServiceBrowser") as browser,
    ):
        first_zc, second_zc = MagicMock(), MagicMock()
        first_browser, second_browser = MagicMock(), MagicMock()
        for mock in (first_zc, second_zc):
            mock.async_close = AsyncMock()
        for mock in (first_browser, second_browser):
            mock.async_cancel = AsyncMock()
        zeroconf.side_effect = [first_zc, second_zc]
        browser.side_effect = [first_browser, second_browser]
        await runner.discover_wled_devices()
        await runner.discover_wled_devices()
    first_browser.async_cancel.assert_awaited_once()
    first_zc.async_close.assert_awaited_once()
    second_zc.async_close.assert_not_awaited()
    assert runner.aiozc is second_zc


def test_hue_stops_handshaking_after_success() -> None:
    device = object.__new__(HueDevice)
    device._output_lock = threading.RLock()
    device._config = HueDevice.config_model().model_construct(
        entertainment_id="e",
        ip_address="10.0.0.4",
        udp_port=2100,
    )
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
    device._output_lock = threading.RLock()
    device._config = Govee.config_model().model_construct(name="govee")
    server = MagicMock()
    device.udp_server = server
    with (
        patch.object(Govee, "send_deactivate"),
        patch.object(Device, "deactivate"),
    ):
        device.deactivate()
        device.deactivate()
    server.close.assert_called_once()


async def test_mdns_rescan_close_survives_cancellation() -> None:
    runner = ZeroConfRunner(MagicMock())
    old_zc = MagicMock(async_close=AsyncMock())
    cancelling = asyncio.Event()
    release = asyncio.Event()

    async def slow_cancel() -> None:
        cancelling.set()
        await release.wait()

    runner.aiozc = old_zc
    runner.aiobrowser = MagicMock(async_cancel=slow_cancel)
    with (
        patch("ledfx.mdns_manager.AsyncZeroconf"),
        patch("ledfx.mdns_manager.AsyncServiceBrowser"),
    ):
        scan = asyncio.create_task(runner.discover_wled_devices())
        await cancelling.wait()
        scan.cancel()  # e.g. the client went away mid-scan
        with pytest.raises(asyncio.CancelledError):
            await scan
        release.set()
        await asyncio.gather(*runner._closing)
    old_zc.async_close.assert_awaited_once()


async def test_mdns_close_still_closes_zeroconf_if_cancel_fails() -> None:
    zc = MagicMock(async_close=AsyncMock())
    browser = MagicMock(async_cancel=AsyncMock(side_effect=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        await ZeroConfRunner._close(browser, zc)
    zc.async_close.assert_awaited_once()


def test_e131_sender_does_not_need_the_sacn_port() -> None:
    import socket

    from ledfx.devices.e131 import E131Device

    device = E131Device(
        MagicMock(),
        E131Device.config_model().model_validate(
            {"name": "e131", "ip_address": "127.0.0.1"}
        ),
    )
    device._destination = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as holder:
        holder.bind(("127.0.0.1", 5568))
        device.activate()
        assert device._sender is not None
        # No frame was sent: cleanup emits no data/control traffic.
        device.deactivate()
