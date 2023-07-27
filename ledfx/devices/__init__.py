import asyncio
import logging
import socket
from abc import abstractmethod
from functools import cached_property, partial

import numpy as np
import serial
import serial.tools.list_ports
import voluptuous as vol
import zeroconf

from ledfx.config import save_config
from ledfx.events import DeviceCreatedEvent, DeviceUpdateEvent, Event
from ledfx.utils import (
    AVAILABLE_FPS,
    WLED,
    BaseRegistry,
    RegistryLoader,
    async_fire_and_forget,
    generate_id,
    resolve_destination,
    wled_support_DDP,
)

_LOGGER = logging.getLogger(__name__)


def fps_validator(value):
    if not isinstance(value, int):
        raise ValueError("fps must be an integer")
    return next(
        (f for f in AVAILABLE_FPS.keys() if f >= value),
        list(AVAILABLE_FPS.keys())[-1],
    )


@BaseRegistry.no_registration
class Device(BaseRegistry):
    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "name", description="Friendly name for the device"
                ): str,
                vol.Optional(
                    "icon_name",
                    description="https://material-ui.com/components/material-icons/",
                    default="mdi:led-strip",
                ): str,
                vol.Optional(
                    "center_offset",
                    description="Number of pixels from the perceived center of the device",
                    default=0,
                ): int,
                vol.Optional(
                    "refresh_rate",
                    description="Target rate that pixels are sent to the device",
                    default=next(
                        (f for f in AVAILABLE_FPS if f >= 60),
                        list(AVAILABLE_FPS)[-1],
                    ),
                ): fps_validator,
            }
        )

    _active = False

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = config
        self._segments = []
        self._pixels = None
        self._silence_start = None
        self._device_type = ""
        self._online = True

    def __del__(self):
        if self._active:
            self.deactivate()

    def update_config(self, config):
        # TODO: Sync locks to ensure everything is thread safe
        if self._config is not None:
            config = {**self._config, **config}

        validated_config = type(self).schema()(config)
        self._config = validated_config

        # Iterate all the base classes and check to see if there is a custom
        # implementation of config updates. If to notify the base class.
        valid_classes = list(type(self).__bases__)
        valid_classes.append(type(self))
        for base in valid_classes:
            if hasattr(base, "config_updated"):
                if base.config_updated != super(base, base).config_updated:
                    base.config_updated(self, validated_config)

        _LOGGER.info(
            f"Device {self.name} config updated to {validated_config}."
        )

        for virtual_id in self._ledfx.virtuals:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if virtual.is_device == self.id:
                segments = [[self.id, 0, self.pixel_count - 1, False]]
                virtual.update_segments(segments)
                virtual.invalidate_cached_props()

        for virtual in self._virtuals_objs:
            virtual.deactivate_segments()
            virtual.activate_segments(virtual._segments)

    def config_updated(self, config):
        """
        to be reimplemented by child classes
        """
        pass

    @property
    def pixel_count(self):
        return int(self._config["pixel_count"])

    def is_active(self):
        return self._active

    def is_online(self):
        return self._online

    def update_pixels(self, virtual_id, data):
        # update each segment from this virtual
        if not self._active:
            _LOGGER.warning(
                f"Cannot update pixels of inactive device {self.name}"
            )
            return

        for pixels, start, end in data:
            # protect against an empty race condition
            if pixels.shape[0] != 0:
                if np.shape(pixels) == (3,) or np.shape(
                    self._pixels[start : end + 1]
                ) == np.shape(pixels):
                    self._pixels[start : end + 1] = pixels

        if self.priority_virtual:
            if virtual_id == self.priority_virtual.id:
                frame = self.assemble_frame()
                self.flush(frame)
                # _LOGGER.debug(f"Device {self.id} flushed by Virtual {virtual_id}")

                self._ledfx.events.fire_event(
                    DeviceUpdateEvent(self.id, frame)
                )
        else:
            _LOGGER.warning(
                f"Flush skipped as {self.id} has no priority_virtual"
            )

    def assemble_frame(self):
        """
        Assembles the frame to be flushed. Currently this will just return
        the active channels pixels, but will eventually handle things like
        merging multiple segments segments and alpha blending channels
        """
        frame = self._pixels

        if self._config["center_offset"]:
            frame = np.roll(frame, self._config["center_offset"], axis=0)
        return frame

    def activate(self):
        self._pixels = np.zeros((self.pixel_count, 3))
        self._active = True

    def deactivate(self):
        self._pixels = None
        self._active = False
        # self.flush(np.zeros((self.pixel_count, 3)))

    @abstractmethod
    def flush(self, data):
        """
        Flushes the provided data to the device. This abstract method must be
        overwritten by the device implementation.
        """

    @property
    def name(self):
        return self._config["name"]

    @property
    def max_refresh_rate(self):
        return self._config["refresh_rate"]

    @property
    def refresh_rate(self):
        return self.priority_virtual.refresh_rate

    @cached_property
    def priority_virtual(self):
        """
        Returns the first virtual that has the highest refresh rate of all virtuals
        associated with this device
        """
        if not any(virtual.active for virtual in self._virtuals_objs):
            return None

        refresh_rate = max(
            virtual.refresh_rate
            for virtual in self._virtuals_objs
            if virtual.active
        )
        return next(
            virtual
            for virtual in self._virtuals_objs
            if virtual.refresh_rate == refresh_rate
        )

    @cached_property
    def _virtuals_objs(self):
        return list(
            self._ledfx.virtuals.get(virtual_id)
            for virtual_id in self.virtuals
        )

    @property
    def active_virtuals(self):
        """
        list of id of the virtuals active on this device.
        it's a list bc there can be more than one virtual streaming
        to a device.
        """
        return list(
            virtual.id for virtual in self._virtuals_objs if virtual.active
        )

    @property
    def online(self):
        """
        list of id of the virtuals active on this device.
        it's a list bc there can be more than one virtual streaming
        to a device.
        """
        return self._online

    @cached_property
    def virtuals(self):
        return list(segment[0] for segment in self._segments)

    def add_segment(self, virtual_id, start_pixel, end_pixel, force=False):
        # make sure this segment doesn't overlap with any others
        for _virtual_id, segment_start, segment_end in self._segments:
            if virtual_id == _virtual_id:
                continue
            overlap = (
                min(segment_end, end_pixel)
                - max(segment_start, start_pixel)
                + 1
            )
            if overlap > 0:
                virtual_name = self._ledfx.virtuals.get(virtual_id).name
                blocking_virtual = self._ledfx.virtuals.get(_virtual_id)
                if force:
                    blocking_virtual.deactivate()
                else:
                    msg = f"Failed to activate effect! '{virtual_name}' overlaps with active virtual '{blocking_virtual.name}'"
                    _LOGGER.warning(msg)
                    raise ValueError(msg)

        # if the segment is from a new device, we need to recheck our priority virtual
        if virtual_id not in (segment[0] for segment in self._segments):
            self.invalidate_cached_props()
        self._segments.append((virtual_id, start_pixel, end_pixel))
        _LOGGER.debug(
            f"Device {self.id}: Added segment {virtual_id, start_pixel, end_pixel}"
        )

    def clear_virtual_segments(self, virtual_id):
        self._segments = [
            segment for segment in self._segments if segment[0] != virtual_id
        ]
        if self.priority_virtual:
            if virtual_id == self.priority_virtual.id:
                self.invalidate_cached_props()

    def clear_segments(self):
        self._segments = []

    def invalidate_cached_props(self):
        # invalidate cached properties
        for prop in ["priority_virtual", "_virtuals_objs", "virtuals"]:
            if hasattr(self, prop):
                delattr(self, prop)

    async def remove_from_virtuals(self):
        # delete segments for this device in any virtuals

        # list of ids to destroy after iterating
        auto_generated_virtuals_to_destroy = []
        for virtual in self._ledfx.virtuals.values():
            if not any(segment[0] == self.id for segment in virtual._segments):
                continue

            active = virtual.active
            if active:
                virtual.deactivate()
            virtual._segments = list(
                segment
                for segment in virtual._segments
                if segment[0] != self.id
            )
            # If the virtual is auto generated and has no segments left, nuke it
            if len(virtual._segments) == 0 and virtual.auto_generated:
                virtual.clear_effect()
                # cleanup this virtual from any scenes
                ledfx_scenes = self._ledfx.config["scenes"].copy()
                for scene_id, scene_config in ledfx_scenes.items():
                    self._ledfx.config["scenes"][scene_id]["virtuals"] = {
                        _virtual_id: effect
                        for _virtual_id, effect in scene_config[
                            "virtuals"
                        ].items()
                        if _virtual_id != virtual.id
                    }
                # add it to the list to be destroyed
                auto_generated_virtuals_to_destroy.append(virtual.id)
                continue

            # Update ledfx's config
            for idx, item in enumerate(self._ledfx.config["virtuals"]):
                if item["id"] == virtual.id:
                    item["segments"] = virtual.segments
                    self._ledfx.config["virtuals"][idx] = item
                    break

            if active:
                virtual.activate()

        for id in auto_generated_virtuals_to_destroy:
            virtual = self._ledfx.virtuals.get(id)
            virtual.clear_effect()
            device_id = virtual.is_device
            device = self._ledfx.devices.get(device_id)
            if device is not None:
                await device.remove_from_virtuals()
                self._ledfx.devices.destroy(device_id)

                # Update and save the configuration
                self._ledfx.config["devices"] = [
                    _device
                    for _device in self._ledfx.config["devices"]
                    if _device["id"] != device_id
                ]

            # cleanup this virtual from any scenes
            ledfx_scenes = self._ledfx.config["scenes"].copy()
            for scene_id, scene_config in ledfx_scenes.items():
                self._ledfx.config["scenes"][scene_id]["virtuals"] = {
                    _virtual_id: effect
                    for _virtual_id, effect in scene_config["virtuals"].items()
                    if _virtual_id != id
                }

            self._ledfx.virtuals.destroy(id)

            # Update and save the configuration
            self._ledfx.config["virtuals"] = [
                virtual
                for virtual in self._ledfx.config["virtuals"]
                if virtual["id"] != id
            ]
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

    async def add_postamble(self):
        # over ride in child classes for device specific behaviours
        pass

    def sub_v(self, name, icon, segs, rows):
        compound_name = f"{self.name}-{name}"
        _LOGGER.info(f"Creating a virtual for device {compound_name}")
        virtual_id = generate_id(compound_name)
        virtual_config = {
            "name": compound_name,
            "icon_name": icon,
            "transition_time": 0,
            "rows": rows,
        }

        segments = []
        for seg in segs:
            segments.append([self.id, seg[0], seg[1], False])

        # Create the virtual
        virtual = self._ledfx.virtuals.create(
            id=virtual_id,
            config=virtual_config,
            ledfx=self._ledfx,
            auto_generated=True,
        )

        # Create segment on the virtual
        virtual.update_segments(segments)

        # Update the configuration
        self._ledfx.config["virtuals"].append(
            {
                "id": virtual.id,
                "config": virtual.config,
                "segments": virtual.segments,
                "is_device": False,
                "auto_generated": True,
            }
        )


@BaseRegistry.no_registration
class MidiDevice(Device):
    pass


@BaseRegistry.no_registration
class NetworkedDevice(Device):
    """
    Networked device, handles resolving IP
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
        }
    )

    async def async_initialize(self):
        self._destination = None
        await self.resolve_address()

    async def resolve_address(self, success_callback=None):
        try:
            self._destination = await resolve_destination(
                self._ledfx.loop,
                self._ledfx.thread_executor,
                self._config["ip_address"],
            )
            _LOGGER.info(
                f"Device {self.name}: Resolved destination to {self._destination}"
            )
            self._online = True
            if success_callback:
                success_callback()
        except ValueError as msg:
            self._online = False
            _LOGGER.warning(f"Device {self.name}: {msg}")

    def activate(self, *args, **kwargs):
        if self._destination is None:
            msg = f"Device {self.name}: Failed to activate, is it online?"
            _LOGGER.warning(msg)
            callback = partial(self.activate, *args, **kwargs)
            async_fire_and_forget(
                self.resolve_address(success_callback=callback),
                loop=self._ledfx.loop,
            )
        else:
            self._online = True
            super().activate(*args, **kwargs)

    @property
    def destination(self):
        if self._destination is None:
            _LOGGER.warning(
                f"Device {self.name}: Searching for device... Is it online?"
            )
            async_fire_and_forget(
                self.resolve_address(), loop=self._ledfx.loop
            )
            return
        else:
            return self._destination


@BaseRegistry.no_registration
class UDPDevice(NetworkedDevice):
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "port",
                description="Port for the UDP device",
            ): vol.All(int, vol.Range(min=1, max=65535)),
        }
    )

    def activate(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} started."
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} stopped."
        )
        self._sock = None


class AvailableCOMPorts:
    ports = serial.tools.list_ports.comports()

    available_ports = [""]

    for p in ports:
        available_ports.append(p.device)


@BaseRegistry.no_registration
class SerialDevice(Device):
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "com_port",
                description="COM port for Adalight compatible device",
                default="",
            ): vol.In(list(AvailableCOMPorts.available_ports)),
            vol.Required(
                "baudrate", description="baudrate", default=500000
            ): vol.All(int, vol.Range(min=115200)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.serial = None
        self.baudrate = self._config["baudrate"]
        self.com_port = self._config["com_port"]

    def activate(self):
        try:
            if self.serial and self.serial.isOpen:
                return

            self.serial = serial.Serial(self.com_port, self.baudrate)
            if self.serial.isOpen:
                super().activate()

        except serial.SerialException:
            _LOGGER.critical(
                "Serial Error: Please ensure your device is connected, functioning and the correct COM port is selected."
            )
            # Todo: Trigger the UI to refresh after the clear effect call. Currently it still shows as active.
            self.deactivate()

    def deactivate(self):
        super().deactivate()
        if self.serial:
            self.serial.close()


class Devices(RegistryLoader):
    """Thin wrapper around the device registry that manages devices"""

    PACKAGE_NAME = "ledfx.devices"

    def __init__(self, ledfx):
        super().__init__(ledfx, Device, self.PACKAGE_NAME)

        def on_shutdown(e):
            self._zeroconf.close()
            self.deactivate_devices()

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)
        self._zeroconf = zeroconf.Zeroconf()

    def create_from_config(self, config):
        for device in config:
            _LOGGER.info(f"Loading device from config: {device}")
            try:
                self._ledfx.devices.create(
                    id=device["id"],
                    type=device["type"],
                    config=device["config"],
                    ledfx=self._ledfx,
                )
            except vol.MultipleInvalid as e:
                _LOGGER.exception(e)

    def deactivate_devices(self):
        for device in self.values():
            device.deactivate()

    def get_device(self, device_id):
        for device in self.values():
            if device_id == device.id:
                return device
        return None

    async def async_initialize_devices(self):
        tasks = [
            device.async_initialize()
            for device in self.values()
            if hasattr(device, "async_initialize")
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if type(result) is ValueError:
                _LOGGER.warning(result)

    async def add_new_device(self, device_type, device_config):
        """
        Creates a new device.
        """
        # First, we try to make sure this device doesn't share a destination with any existing device
        if "ip_address" in device_config.keys():
            device_ip = device_config["ip_address"]
            try:
                resolved_dest = await resolve_destination(
                    self._ledfx.loop, self._ledfx.thread_executor, device_ip
                )
            except ValueError:
                _LOGGER.error(f"Discarding device {device_ip}")
                return

            for existing_device in self._ledfx.devices.values():
                if "ip_address" in existing_device.config.keys() and (
                    existing_device.config["ip_address"] == device_ip
                    or existing_device.config["ip_address"] == resolved_dest
                ):
                    if device_type == "e131":
                        # check the universes for e131, it might still be okay at a shared ip_address
                        # eg. for multi output controllers
                        if (
                            device_config["universe"]
                            == existing_device.config["universe"]
                        ):
                            msg = f"Ignoring {device_ip}: Shares IP and starting universe with existing device {existing_device.name}"
                            _LOGGER.info(msg)
                            raise ValueError(msg)
                    elif device_type == "openrgb":
                        # check the OpenRGB ID for OpenRGB device, it might still be okay at a shared ip_address
                        # eg. for multi OpenRGB devices
                        if (
                            device_config["openrgb_id"]
                            == existing_device.config["openrgb_id"]
                        ):
                            msg = f"Ignoring {device_ip}: Shares IP and OpenRGB ID with existing device {existing_device.name}"
                            _LOGGER.info(msg)
                            raise ValueError(msg)
                    else:
                        msg = f"Ignoring {device_ip}: Shares destination with existing device {existing_device.name}"
                        _LOGGER.info(msg)
                        raise ValueError(msg)

        # If WLED device, get all the necessary config from the device itself
        if device_type == "wled":
            wled = WLED(resolved_dest)
            wled_config = await wled.get_config()

            led_info = wled_config["leds"]
            # If we've found the device via WLED scan, it won't have a custom name from the frontend
            # However if it's "WLED" (i.e, Default) then we will name the device exactly how WLED does, by using the second half of it's MAC address
            # This allows us to respect the users choice of names if adding a WLED device via frontend
            # I turned black off as this logic is clearer on one line
            # fmt: off
            if "name" in device_config.keys() and device_config["name"] is not None:
                wled_name = device_config["name"]
            elif wled_config["name"] == "WLED":
                wled_name = f"{wled_config['name']}-{wled_config['mac'][6:]}".upper()
            else:
                wled_name = wled_config['name']
            # fmt: on
            wled_count = led_info["count"]
            wled_rgbmode = led_info["rgbw"]
            wled_build = wled_config["vid"]

            if wled_support_DDP(wled_build):
                _LOGGER.info(f"WLED build Supports DDP: {wled_build}")
                sync_mode = "DDP"
            else:
                _LOGGER.info(
                    f"WLED build pre DDP, default to UDP: {wled_build}"
                )
                sync_mode = "UDP"

            wled_config = {
                "name": wled_name,
                "pixel_count": wled_count,
                "icon_name": "wled",
                "rgbw_led": wled_rgbmode,
                "sync_mode": sync_mode,
            }

            device_config.update(wled_config)

        device_id = generate_id(device_config["name"])

        # Create the device
        _LOGGER.info(
            "Adding device of type {} with config {}".format(
                device_type, device_config
            )
        )
        device = self._ledfx.devices.create(
            id=device_id,
            type=device_type,
            config=device_config,
            ledfx=self._ledfx,
        )

        if hasattr(device, "async_initialize"):
            await device.async_initialize()

        device_config = device.config
        if device_type == "wled":
            device_config["name"] = wled_name
        # Update and save the configuration
        self._ledfx.config["devices"].append(
            {
                "id": device.id,
                "type": device.type,
                "config": device_config,
            }
        )

        # Generate virtual configuration for the device
        _LOGGER.info(f"Creating a virtual for device {device.name}")
        virtual_id = generate_id(device.name)
        virtual_config = {
            "name": device.name,
            "icon_name": device_config["icon_name"],
        }
        segments = [[device.id, 0, device_config["pixel_count"] - 1, False]]

        # Create the virtual
        virtual = self._ledfx.virtuals.create(
            id=virtual_id,
            config=virtual_config,
            ledfx=self._ledfx,
            is_device=device.id,
            auto_generated=False,
        )

        # Create the device as a single segment on the virtual
        virtual.update_segments(segments)

        # Update the configuration
        self._ledfx.config["virtuals"].append(
            {
                "id": virtual.id,
                "config": virtual.config,
                "segments": virtual.segments,
                "is_device": device.id,
                "auto_generated": virtual.auto_generated,
            }
        )
        self._ledfx.events.fire_event(DeviceCreatedEvent(device.name))
        await device.add_postamble()

        # Finally, save the config to file!
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return device

    async def set_wleds_sync_mode(self, mode):
        for device in self.values():
            if (
                device.type == "wled"
                and device.pixel_count > 480
                and device.config["sync_mode"] != mode
            ):
                device.wled.set_sync_mode(mode)
                await device.wled.flush_sync_settings()
                device.update_config({"sync_mode": mode})

    async def find_wled_devices(self):
        # Scan the LAN network that match WLED using zeroconf - Multicast DNS
        # Service Discovery Library
        _LOGGER.info("Scanning for WLED devices...")
        wled_listener = WLEDListener(self._ledfx)
        wledbrowser = self._zeroconf.add_service_listener(
            "_wled._tcp.local.", wled_listener
        )
        try:
            await asyncio.sleep(30)
        finally:
            _LOGGER.info("Scan Finished")
            self._zeroconf.remove_service_listener(wled_listener)


class WLEDListener(zeroconf.ServiceBrowser):
    def __init__(self, _ledfx):
        self._ledfx = _ledfx

    def remove_service(self, zeroconf_obj, type, name):
        _LOGGER.info(f"Service {name} removed")

    def add_service(self, zeroconf_obj, type, name):
        info = zeroconf_obj.get_service_info(type, name)

        if info:
            hostname = str(info.server).rstrip(".")
            _LOGGER.info(f"Found device: {hostname}")

            device_type = "wled"
            device_config = {"ip_address": hostname}

            def handle_exception(future):
                # Ignore exceptions, these will be raised when a device is found that already exists
                exc = future.exception()

            async_fire_and_forget(
                self._ledfx.devices.add_new_device(device_type, device_config),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

    def update_service(self, zeroconf_obj, type, name):
        """Callback when a service is updated."""
        pass
