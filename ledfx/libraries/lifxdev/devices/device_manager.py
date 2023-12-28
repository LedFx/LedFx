#!/usr/bin/env python3

from __future__ import annotations

import collections
import dataclasses
import enum
import functools
import logging
import pathlib
from collections.abc import Callable
from typing import Any

import yaml

from ledfx.libraries.lifxdev.colors import color
from ledfx.libraries.lifxdev.devices import device, light, multizone, tile
from ledfx.libraries.lifxdev.messages import device_messages, packet

CONFIG_PATH = pathlib.Path.home() / ".lifx" / "devices.yaml"


class DeviceConfigError(Exception):
    pass


class DeviceDiscoveryError(Exception):
    pass


@dataclasses.dataclass
class ProductInfo:
    ip: str
    port: int
    label: str
    product_name: str
    device: light.LifxLight


class DeviceGroup:
    """Class for managing groups of devices"""

    def __init__(self, devices_and_groups: dict[str, Any]):
        """Create a device group.

        Args:
            devices_and_groups: (dict) Dictionary containing devices and subgroups.
        """
        self._devices_and_groups = devices_and_groups

        # Get easy access to all devices in the device group
        self._all_devices: dict[str, Any] = {}
        self._all_groups: dict[str, Any] = {}
        for name, device_or_group in self._devices_and_groups.items():
            if isinstance(device_or_group, type(self)):
                self._all_groups[name] = device_or_group
                for (
                    sub_name,
                    sub_device,
                ) in device_or_group.get_all_devices().items():
                    self._all_devices[sub_name] = sub_device
                for (
                    sub_name,
                    sub_group,
                ) in device_or_group.get_all_groups().items():
                    self._all_groups[sub_name] = sub_group
            else:
                self._all_devices[name] = device_or_group

        # Organizing devices by type is useful for setting colormaps
        self._devices_by_type = collections.defaultdict(list)
        for lifx_device in self._all_devices.values():
            device_type = DeviceType[
                _DEVICE_TYPES_R[type(lifx_device).__name__]
            ]
            self._devices_by_type[device_type].append(lifx_device)

    def get_all_devices(self) -> dict[str, Any]:
        return self._all_devices

    def get_all_groups(self) -> dict[str, DeviceGroup]:
        return self._all_groups

    def get_device(self, name: str) -> Any:
        return self._all_devices[name]

    def get_group(self, name: str) -> DeviceGroup:
        return self._all_groups[name]

    def has_device(self, name: str) -> bool:
        return name in self._all_devices

    def has_group(self, name: str) -> bool:
        return name in self._all_groups

    def set_color(
        self, hsbk: color.Hsbk | light.COLOR_T, *, duration: float = 0.0
    ) -> None:
        """Set the color of all lights in the device group.

        Args:
            hsbk: (color.Hsbk) Human-readable HSBK tuple.
            duration: (float) The time in seconds to make the color transition.
        """

        for target in self._all_devices.values():
            target.set_color(hsbk, duration=duration, ack_required=False)

    def set_power(self, state: bool, *, duration: float = 0.0) -> None:
        """Set power state on all lights in the device group.

        Args:
            state: (bool) True powers on the light. False powers it off.
            duration: (float) The time in seconds to make the color transition.
        """
        for target in self._all_devices.values():
            target.set_power(state, duration=duration, ack_required=False)


# Convienence for validating type names in config files
class DeviceType(enum.Enum):
    group = 0
    light = 1
    infrared = 2
    multizone = 3
    tile = 4


# Mapping and reverse mapping from config file type name to class
_DEVICE_TYPES = {
    "group": DeviceGroup,
    "light": light.LifxLight,
    "infrared": light.LifxInfraredLight,
    "multizone": multizone.LifxMultiZone,
    "tile": tile.LifxTile,
}
_DEVICE_TYPES_R = {value.__name__: key for key, value in _DEVICE_TYPES.items()}


def _require_config_loaded(function: Callable) -> Callable:
    """Require configuration to be loaded before calling a class method"""

    @functools.wraps(function)
    def _run(self, *args, **kwargs) -> Any:
        if not self._root_device_group:
            raise DeviceConfigError("Device config not loaded.")
        return function(self, *args, **kwargs)

    return _run


class DeviceManager(device.LifxDevice):
    """Device manager

    Class for device discovery and loading configs.
    """

    def __init__(
        self,
        config_path: str | pathlib.Path = CONFIG_PATH,
        *,
        buffer_size: int = packet.BUFFER_SIZE,
        timeout: float = packet.TIMEOUT_S,
        verbose: bool = False,
        comm_init: Callable | None = None,
    ):
        """Create a LIFX device manager.

        Args:
            config_path: (str) Path to the device config. If non-existant, do not load.
            buffer_size: (int) Buffer size for receiving UDP responses.
            timeout: (float) UDP response timeout.
            nonblock_delay: (float) Delay time to wait for messages when nonblocking.
            verbose: (bool) Use logging.info instead of logging.debug.
            comm_init: (function) This function (no args) creates a socket object.
        """
        super().__init__(
            ip="255.255.255.255",
            buffer_size=buffer_size,
            timeout=timeout,
            verbose=verbose,
            comm_init=comm_init,
        )

        self._timeout = timeout
        self._comm_init = comm_init

        # Load product identification
        products = pathlib.Path(__file__).parent / "products.yaml"
        with products.open() as f:
            product_list = yaml.safe_load(f).pop().get("products", [])

        # For easily recovering product info via get_product_class
        self._products: dict[str, Any] = {}
        for product in product_list:
            self._products[product["pid"]] = product

        # Load config sets the self._root_device_group variable
        self._discovered_device_group: DeviceGroup | None = None
        self._root_device_group: DeviceGroup | None = None
        self._config_path = pathlib.Path(config_path)
        if self._config_path.exists():
            self.load_config()

    @property
    def discovered(self) -> DeviceGroup:
        """The discovered group"""
        if not self._discovered_device_group:
            raise DeviceDiscoveryError(
                "Device discovery has not been performed."
            )
        return self._discovered_device_group

    @property
    @_require_config_loaded
    def root(self) -> DeviceGroup:
        """The root device group"""
        assert self._root_device_group
        return self._root_device_group

    def discover(self, num_retries: int = 10) -> dict[str, ProductInfo]:
        """Discover devices on the network

        Args:
            num_retries: (int) Number of GetService calls made.
        """

        logging.info("Scanning for LIFX devices.")
        state_service_dict: dict[str, packet.LifxResponse] = {}
        # Disabling the timeout speeds up discovery
        for _ in range(num_retries):
            search_responses = self.get_devices_on_network() or []
            for response in search_responses:
                ip = response.addr[0]
                state_service_dict[ip] = response

        logging.info("Getting device info for discovered devices.")
        device_dict: dict[str, ProductInfo] = {}
        for ip, state_service in state_service_dict.items():
            port = state_service.payload["port"]
            try:
                label = self.get_label(ip, port=port)
                product_dict = self.get_product_info(ip, port=port)
            except packet.NoResponsesError as e:
                logging.error(e)
                continue

            product_name = product_dict["name"]
            device_klass = product_dict["class"]

            product_info = ProductInfo(
                ip=ip,
                port=port,
                label=label,
                product_name=product_name,
                device=device_klass(
                    ip,
                    port=port,
                    label=label,
                    comm_init=self._comm_init,
                    timeout=self._timeout,
                    verbose=self._verbose,
                ),
            )
            device_dict[label] = product_info

        return device_dict

    def get_devices_on_network(self) -> list[packet.LifxResponse] | None:
        """Get device info from one or more devices.

        Returns:
            A list of StateService responses.
        """
        return self.send_recv(
            device_messages.GetService(), res_required=True, retry_recv=True
        )

    def get_label(
        self,
        ip: str,
        *,
        port: int = packet.LIFX_PORT,
        mac_addr: str | None = None,
        verbose: bool = False,
    ) -> str:
        """Get the label of a device

        Args:
            ip: (str) Override the IP address.
            port: (int) Override the UDP port.
            mac_addr: (str) Override the MAC address.
            verbose: (bool) Use logging.info instead of logging.debug.
        """
        response = self.send_recv(
            device_messages.GetLabel(),
            res_required=True,
            ip=ip,
            port=port,
            mac_addr=mac_addr,
            verbose=verbose,
        )
        assert response
        return response.pop().payload["label"]

    def get_product_info(
        self,
        ip: str,
        *,
        port: int = packet.LIFX_PORT,
        mac_addr: str | None = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Get the Python class needed to control a LIFX product.

        Args:
            ip: (str) Override the IP address.
            port: (int) Override the UDP port.
            mac_addr: (str) Override the MAC address.
            verbose: (bool) Use logging.info instead of logging.debug.
        """
        response = self.send_recv(
            device_messages.GetVersion(),
            res_required=True,
            ip=ip,
            port=port,
            mac_addr=mac_addr,
            verbose=verbose,
        )
        assert response
        product_id = response.pop().payload["product"]

        # Get the class definition from the product info
        product = self._products[product_id]
        features = product["features"]
        if features["multizone"]:
            klass = multizone.LifxMultiZone
        elif features["matrix"]:
            klass = tile.LifxTile
        elif features["infrared"]:
            klass = light.LifxInfraredLight
        else:
            klass = light.LifxLight

        product["class"] = klass
        return product

    def load_config(
        self, config_path: str | pathlib.Path | None = None
    ) -> None:
        """Load a config and populate device groups.

        Args:
            config_path: (str) Path to the device config.
        """
        config_path = pathlib.Path(config_path or self._config_path)
        with config_path.open() as f:
            config_dict = yaml.safe_load(f)

        self._root_device_group = self._load_device_group(config_dict)

    def _load_device_group(
        self, config_dict: dict[str, Any], max_brightness: float = 1.0
    ) -> DeviceGroup:
        """Recursively load a device group from a config dict."""
        devices_and_groups: dict[str, Any] = {}
        for name, conf in config_dict.items():
            # Validate the type name
            type_name = conf.get("type")
            if not type_name:
                raise DeviceConfigError(
                    f"Device/group {name!r} missing 'type' field."
                )
            try:
                device_type = DeviceType[type_name]
            except KeyError:
                raise DeviceConfigError(
                    f"Invalid type for device {name!r}: {type_name}"
                )

            # Check that the IP address is present
            ip = conf.get("ip")
            if not (ip or device_type == DeviceType.group):
                raise DeviceConfigError(f"Device {name!r} has no IP address.")

            mb_key = "max-brightness"
            conf_mb = conf.get(mb_key)
            if conf_mb is not None:
                if conf_mb <= 0:
                    raise ValueError(
                        f"{name}:{mb_key}: must be greater than zero."
                    )
                elif conf_mb > 1:
                    raise ValueError(
                        f"{name}:{mb_key}: must be less than or equal to one."
                    )
                elif conf_mb < max_brightness:
                    max_brightness = conf_mb

            kwargs = {}
            if device_type in [DeviceType.multizone, DeviceType.tile]:
                length_key = "length"
                length = conf.get(length_key)
                if not isinstance(length, int):
                    raise ValueError(
                        f"{name}:{length_key}: must be an integer."
                    )
                if length <= 0:
                    raise ValueError(
                        f"{name}:{length_key}: must be greater than zero."
                    )
                kwargs[length_key] = length

            # Recurse through group listing
            if device_type == DeviceType.group:
                group_devices = conf.get("devices")
                devices_and_groups[name] = self._load_device_group(
                    group_devices, max_brightness
                )

            else:
                port = conf.get("port", packet.LIFX_PORT)
                klass = _DEVICE_TYPES[device_type.name]
                devices_and_groups[name] = klass(
                    ip,
                    port=port,
                    label=name,
                    max_brightness=max_brightness,
                    comm_init=self._comm_init,
                    verbose=self._verbose,
                    **kwargs,
                )

        return DeviceGroup(devices_and_groups)

    @_require_config_loaded
    def get_all_devices(self) -> dict[str, Any]:
        assert self._root_device_group is not None
        return self._root_device_group.get_all_devices()

    @_require_config_loaded
    def get_all_groups(self) -> dict[str, DeviceGroup]:
        assert self._root_device_group is not None
        return self._root_device_group.get_all_groups()

    @_require_config_loaded
    def get_device(self, name: str) -> Any:
        """Get a device by its label."""
        assert self._root_device_group is not None
        return self._root_device_group.get_device(name)

    @_require_config_loaded
    def get_group(self, name: str) -> DeviceGroup:
        """Get a group by its label."""
        assert self._root_device_group is not None
        return self._root_device_group.get_group(name)

    @_require_config_loaded
    def has_device(self, name: str) -> bool:
        """Check if a device exists."""
        assert self._root_device_group is not None
        return self._root_device_group.has_device(name)

    @_require_config_loaded
    def has_group(self, name: str) -> bool:
        """Check if a group exists."""
        assert self._root_device_group is not None
        return self._root_device_group.has_group(name)
