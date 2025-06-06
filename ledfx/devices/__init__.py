import asyncio
import logging
import socket
import threading
from abc import abstractmethod
from functools import cached_property, partial

import numpy as np
import serial
import serial.tools.list_ports
import voluptuous as vol
from sacn.sending.sender_socket_base import DEFAULT_PORT

from ledfx.config import save_config
from ledfx.events import (
    DeviceCreatedEvent,
    DevicesUpdatedEvent,
    DeviceUpdateEvent,
    Event,
)
from ledfx.utils import (
    AVAILABLE_FPS,
    WLED,
    BaseRegistry,
    RegistryLoader,
    async_fire_and_forget,
    clean_ip,
    generate_id,
    get_icon_name,
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
        self.lock = threading.Lock()

    def __del__(self):
        if self._active:
            self.deactivate()

    def update_config(self, config):
        with self.lock:
            # TODO: Sync locks to ensure everything is thread safe
            # self.lock has been added, but is not used presently outside of
            # artnet
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

    def set_offline(self):
        self.deactivate()
        self._online = False
        self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))

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
        if self.priority_virtual:
            return self.priority_virtual.refresh_rate
        else:
            _LOGGER.warning(
                f"refresh_rate() set 30 as {self.id} has no priority_virtual"
            )
            return 30

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
        bool indicator of online status
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
        # We have added a segment, therefore the priority virtual may of changed
        self.invalidate_cached_props()

    def clear_virtual_segments(self, virtual_id):
        new_segments = []
        for segment in self._segments:
            if segment[0] != virtual_id:
                new_segments.append(segment)
            else:
                if self._pixels is not None:
                    if self._ledfx.config.get("flush_on_deactivate", False):
                        self._pixels[segment[1] : segment[2] + 1] = np.zeros(
                            (segment[2] - segment[1] + 1, 3)
                        )
        self._segments = new_segments

        if self.priority_virtual:
            if virtual_id == self.priority_virtual.id:
                self.invalidate_cached_props()

    def clear_segments(self):
        self._segments = []
        self.invalidate_cached_props()

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

            virtual.virtual_cfg["segments"] = virtual.segments

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
        icon_name = get_icon_name(compound_name)
        if icon_name == "wled" and icon is not None:
            icon_name = icon
        virtual_config = {
            "name": compound_name,
            "icon_name": icon_name,
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

        virtual.virtual_cfg = self._ledfx.config["virtuals"][-1]


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
                self._online = True

        except serial.SerialException:
            _LOGGER.warning(
                "Serial Error: Please ensure your device is connected, functioning and the correct COM port is selected."
            )
            self.set_offline()

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
            self.deactivate_devices()

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)

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
            device_config["ip_address"] = clean_ip(device_config["ip_address"])
            device_ip = device_config["ip_address"]
            try:
                resolved_dest = await resolve_destination(
                    self._ledfx.loop, self._ledfx.thread_executor, device_ip
                )
            except ValueError:
                _LOGGER.warning(
                    f"Discarding device {device_ip} as it could not be resolved."
                )
                return

            for existing_device in self._ledfx.devices.values():
                if "ip_address" in existing_device.config.keys() and (
                    existing_device.config["ip_address"] == device_ip
                    or existing_device.config["ip_address"] == resolved_dest
                ):
                    self.run_device_ip_tests(
                        device_type, device_config, existing_device
                    )

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

            icon_name = get_icon_name(wled_name)

            wled_config = {
                "name": wled_name,
                "pixel_count": wled_count,
                "icon_name": icon_name,
                "rgbw_led": wled_rgbmode,
                "sync_mode": sync_mode,
            }

            device_config.update(wled_config)

        device_id = generate_id(device_config["name"])

        # Create the device
        _LOGGER.info(
            f"Adding device of type {device_type} with config {device_config}"
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
            "rows": device_config.get("rows", 1),
        }

        if device_type == "wled":
            if "matrix" in led_info.keys():
                if "h" in led_info["matrix"].keys():
                    virtual_config["rows"] = led_info["matrix"]["h"]

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

        virtual.virtual_cfg = self._ledfx.config["virtuals"][-1]

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

    def generate_device_ip_tests(self, new_type, new_config, pre_device):
        """
        Generate tests to check if the devices are compatible with each other on a common IP

        There are various scenarios where devices can coexist on the same IP address
        1) device types with different port numbers or other access methods
        2) common device types that have secondary checks that must be performed
           for example e131 / artnet universe or openrgb openrgb_id
           port number could also be considered here

        Explicit device approval tests should be added prior to the final is_general_port_separated test
        which is a catch-all for any device type that does not have a specific test

        Args:
            new_type (_type_): new_config does not carry device type so must be explicit
            new_config (_type_): config from creation of new device
            pre_device (_type_): config from pre-existing device

        Yields:
            bool: True if the devices can explicity coexist, False if there is no rejection
            ValueError: if the devices cannot coexist due to a hard failure
        """
        for test in [
            self.is_universe_separated,
            self.is_openrgb_id_separated,
            self.is_osc_port_path_separated,
            self.is_general_port_separated,
        ]:
            yield test(new_type, new_config, pre_device)

    def run_device_ip_tests(self, new_type, new_config, pre_device):
        """
        Run tests to check if the devices are compatible with each other on a common IP
        This function will reach the end and return if no tests hard succeeded or hard failed
        Individual tests with will
            return False for a soft fail = coexistance was not covered by the test for success or hard fail
            return True for success = coexistance is viable and device should be created
            raise ValueError with suitable message for hard fail = coexistance is not viable and device should not be created

        Args:
            new_type (_type_): new_config does not carry device type so must be explicit
            new_config (_type_): config from creation of new device
            pre_device (_type_): config from pre-existing device
        """

        for result in self.generate_device_ip_tests(
            new_type, new_config, pre_device
        ):
            if result:
                return

    def is_universe_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is universe separated from the pre-existing device
        """
        if new_type in ["e131", "artnet"] and pre_device.type in [
            "e131",
            "artnet",
        ]:
            if new_config["universe"] == pre_device.config["universe"]:
                msg = f'Ignoring {new_config["ip_address"]}: Shares IP and port {new_config["port"]} and starting universe with existing device {pre_device.name}'
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_openrgb_id_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is openrgb_id separated from the pre-existing device
        """
        if new_type == "openrgb" and pre_device.type == "openrgb":
            if new_config["openrgb_id"] == pre_device.config["openrgb_id"]:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and OpenRGB ID with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False

    def is_osc_port_path_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is osc port and path separated from the pre-existing device
        """
        if new_type == "osc" and pre_device.type == "osc":
            if new_config["port"] == pre_device.config["port"]:
                if new_config["path"] == pre_device.config["path"]:
                    if (
                        new_config["starting_addr"]
                        == pre_device.config["starting_addr"]
                    ):
                        msg = f"Ignoring {new_config['ip_address']}: Shares IP, Port, Path and starting address with existing device {pre_device.name}"
                        _LOGGER.info(msg)
                        raise ValueError(msg)
            return True
        return False

    def is_general_port_separated(self, new_type, new_config, pre_device):
        """
        Check if the new device is port separated from the pre-existing device
        """
        # e131 is a special case as its port number is not in the config, but in the library
        new_port = None
        pre_port = None
        if new_type == "e131":
            new_port = DEFAULT_PORT
        if pre_device.type == "e131":
            pre_port = DEFAULT_PORT
        if "port" in new_config:
            new_port = new_config["port"]
        if "port" in pre_device.config:
            pre_port = pre_device.config["port"]

        if new_port is not None and pre_port is not None:
            if new_port == pre_port:
                msg = f"Ignoring {new_config['ip_address']}: Shares IP and port with existing device {pre_device.name}"
                _LOGGER.info(msg)
                raise ValueError(msg)
            return True
        return False
