import asyncio
import concurrent.futures
import importlib
import inspect
import ipaddress
import logging
import os
import pkgutil
import re
import socket
import sys
import time
from abc import ABC
from collections.abc import MutableMapping
from functools import lru_cache
from itertools import chain

# from asyncio import coroutines, ensure_future
from subprocess import PIPE, Popen

import numpy as np
import requests
import voluptuous as vol

from ledfx.config import save_config

# from asyncio import coroutines, ensure_future


_LOGGER = logging.getLogger(__name__)


def calc_available_fps():
    monotonic_res = time.get_clock_info("monotonic").resolution

    if monotonic_res < 0.001:
        mult = int(0.001 / monotonic_res)
    else:
        mult = 1

    max_fps_target = 126
    min_fps_target = 10

    max_fps_ticks = np.ceil(
        (1 / max_fps_target) / (monotonic_res * mult)
    ).astype(int)
    min_fps_ticks = np.ceil(
        (1 / min_fps_target) / (monotonic_res * mult)
    ).astype(int)
    tick_range = reversed(range(max_fps_ticks, min_fps_ticks))
    return {int(1 / (monotonic_res * mult * i)): i * mult for i in tick_range}


AVAILABLE_FPS = calc_available_fps()


@lru_cache(maxsize=32)
def fps_to_sleep_interval(fps):
    monotonic_res = time.get_clock_info("monotonic").resolution
    monotonic_ticks = next(
        (t for f, t in AVAILABLE_FPS.items() if f >= fps),
        list(AVAILABLE_FPS.values())[-1],
    )
    return max(0.001, monotonic_res * (monotonic_ticks - 1))


def install_package(package):
    _LOGGER.debug(f"Installed package: {package}")
    env = os.environ.copy()
    args = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        package,
    ]
    process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
    _, stderr = process.communicate()
    if process.returncode != 0:
        _LOGGER.error(
            "Failed to install package %s: %s",
            package,
            stderr.decode("utf-8").lstrip().strip(),
        )
        return False
    return True


def import_or_install(package):
    try:
        _LOGGER.debug(f"Imported package: {package}")
        return importlib.import_module(package)

    except ImportError:
        install_package(package)
        try:
            return importlib.import_module(package)
        except ImportError:
            return False
    return False


def async_fire_and_forget(coro, loop, exc_handler=None):
    """Run some code in the core event loop without a result"""

    if not asyncio.coroutines.iscoroutine(coro):
        raise TypeError(("A coroutine object is required: {}").format(coro))

    def callback():
        """Handle the firing of a coroutine."""
        task = asyncio.create_task(coro)
        if exc_handler is not None:
            task.add_done_callback(exc_handler)

    loop.call_soon_threadsafe(callback)
    return


def get_local_ip():
    """Uses a socket to find the first non-loopback ip address

    Returns:
        string: Either the first non-loopback ip address or hostname, or localhost
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use Google Public DNS server to determine own IP
        sock.connect(("8.8.8.8", 80))

        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return "127.0.0.1"
    finally:
        sock.close()


def async_fire_and_return(coro, callback, timeout=10):
    """Run some async code in the core event loop with a callback to handle result"""

    if not asyncio.coroutines.iscoroutine(coro):
        raise TypeError(("A coroutine object is required: {}").format(coro))

    def _callback(future):
        exc = future.exception()
        if exc:
            # Handle wonderful empty TimeoutError exception
            if type(exc) == TimeoutError:
                _LOGGER.warning(f"Coroutine {future} timed out.")
            else:
                _LOGGER.error(exc)
        else:
            callback(future.result())

    future = asyncio.create_task(asyncio.wait_for(coro, timeout=timeout))
    future.add_done_callback(_callback)


def async_callback(loop, callback, *args):
    """Run a callback in the event loop with access to the result"""

    future = concurrent.futures.Future()

    def run_callback():
        try:
            future.set_result(callback(*args))
        # pylint: disable=broad-except
        except Exception as e:
            if future.set_running_or_notify_cancel():
                future.set_exception(e)
            else:
                _LOGGER.warning("Exception on lost future: ", exc_info=True)

    loop.call_soon(run_callback)
    return future


class WLED:
    """
    A collection of WLED helper functions
    """

    SYNC_MODES = {"DDP": 4048, "E131": 5568, "ARTNET": 6454}

    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.reboot_flag = False

    async def get_sync_settings(self):
        self.sync_settings = await WLED._get_sync_settings(self.ip_address)

    @staticmethod
    async def _wled_request(
        method, ip_address, endpoint, timeout=0.5, **kwargs
    ):
        url = f"http://{ip_address}/{endpoint}"

        try:
            response = method(url, timeout=timeout, **kwargs)

        except requests.exceptions.RequestException:
            msg = f"WLED {ip_address}: Failed to connect"
            raise ValueError(msg)

        if not response.ok:
            msg = f"WLED {ip_address}: API Error - {response.status_code}"
            raise ValueError(msg)

        return response

    @staticmethod
    async def _get_sync_settings(ip_address):

        response = await WLED._wled_request(
            requests.get, ip_address, "json/cfg"
        )
        return response.json()

    async def flush_sync_settings(self):
        """
        JSON API call to flush wled sync settings to the device. Will reboot if required.
        """
        # {'rb': True} must be sent to the '/state' endpoint
        # if self.reboot_flag:
        #     self.sync_settings["rb"] = True
        await WLED._wled_request(
            requests.post,
            self.ip_address,
            "json/cfg",
            data=self.sync_settings,
        )
        self.reboot_flag = False

    async def get_config(self):
        """
            Uses a JSON API call to determine if the device is WLED or WLED compatible
            and return its config.
            Specifically searches for "WLED" in the brand json - currently all major
            branches/forks of WLED contain WLED in the branch data.
        Returns:
            config: dict, with all wled configuration info
        """
        _LOGGER.info(
            f"WLED {self.ip_address}: Attempting to contact device..."
        )
        response = await WLED._wled_request(
            requests.get, self.ip_address, "json/info"
        )

        wled_config = response.json()

        if not wled_config["brand"] in "WLED":
            msg = f"WLED {self.ip_address}: Not a compatible WLED brand '{wled_config['brand']}'"
            raise ValueError(msg)

        _LOGGER.info(f"WLED {self.ip_address}: Received config")

        return wled_config

    async def get_state(self):
        """
            Uses a JSON API call to determine the full WLED device state

        Returns:
            state, dict. Full device state
        """
        response = await WLED._wled_request(
            requests.get, self.ip_address, "json/state"
        )

        return response.json()

    async def get_power_state(self):
        """
            Uses a JSON API call to determine the WLED device power state (on/off)

        Args:
            ip_address (string): The device IP to be queried
        Returns:
            boolean: True is "On", False is "Off"
        """
        return await self.get_state()["on"]

    async def get_segments(self):
        """
            Uses a JSON API call to determine the WLED segment setup

        Args:
            ip_address (string): The device IP to be queried
        Returns:
            dict: array of segments
        """
        return await self.get_state()["seg"]

    async def set_power_state(self, state):
        """
            Uses a JSON API post call to set the power of a WLED compatible device on/off

        Args:
            state (bool): on/off
        """
        power = {"on": True if state else False}
        await WLED._wled_request(
            requests.post, self.ip_address, "/json/state", data=power
        )

        _LOGGER.info(
            f"WLED {self.ip_address}: Turned {'on' if state else 'off'}."
        )

    async def set_brightness(self, brightness):
        """
            Uses a JSON API post call to adjust a WLED compatible device's
            brightness

        Args:
            brightness (int): The brightness value between 0-255
        """
        # cast to int and clamp to range
        brightness = max(0, max(int(brightness), 255))
        bri = {"bri": brightness}

        await WLED._wled_request(
            requests.post, self.ip_address, "/json/state", data=bri
        )

        _LOGGER.info(
            f"WLED {self.ip_address}: Set brightness to {brightness}."
        )

    def enable_realtime_gamma(self):
        """
        Updates internal sync settings to enable realtime gamma

        {"if": {"live": {"no-gc": True|False}}}
        """

        self.sync_settings["if"]["live"]["no-gc"] = False

        _LOGGER.info(
            f"WLED {self.ip_address}: Enabled realtime gamma correction"
        )

    def force_max_brightness(self):
        """
        Updates internal sync settings to enable "Force Max Brightness"

        {"if": {"live": {"maxbri": True|False}}}
        """
        self.sync_settings["if"]["live"]["maxbri"] = True

        _LOGGER.info(f"WLED {self.ip_address}: Enabled force max brightness")

    def multirgb_dmx_mode(self):
        """
        Updates DMX mode to "Multi RGB"

        {"if": {"live": {"dmx": {"mode": 0-6}}}}
        """
        self.sync_settings["if"]["live"]["dmx"]["mode"] = 4

        _LOGGER.info(f"WLED {self.ip_address}: Enabled Multi RGB")

    def first_universe(self):
        """
        Updates first universe to "1"

        {"if": {"live": {"dmx": {"uni": 1}}}}
        """
        self.sync_settings["if"]["live"]["dmx"]["uni"] = 1

        _LOGGER.info(f"WLED {self.ip_address}: Set first Universe = 1")

    def first_dmx_address(self):
        """
        Updates first dmx address to "1"

        {"if": {"live": {"dmx": {"addr": 1}}}}
        """
        self.sync_settings["if"]["live"]["dmx"]["addr"] = 1

        _LOGGER.info(f"WLED {self.ip_address}: Set first DMX address = 1")

    def get_inactivity_timeout(self):
        """
        Get inactivity timeout from internal sync settings

        {"if": {"live": {"timeout": 25(2.5s)}}}
        """
        return self.sync_settings["if"]["live"]["timeout"]

    def set_inactivity_timeout(self, timeout=2.5):
        """
        Updates internal sync settings to set timeout for wled effect virtual after ledfx streaming finishes

        Args:
            timeout: int/float, seconds
        """
        tout = self.sync_settings["if"]["live"]["timeout"]
        if tout * 10 == timeout:
            return

        self.sync_settings["if"]["live"]["timeout"] = timeout * 10

        _LOGGER.info(
            f"Set WLED device at {self.ip_address} timeout to {timeout}s"
        )

    def set_sync_mode(self, mode):
        """
        Updates internal sync settings to set sync mode

        Args:
            mode: str, in ["ddp", "e131", "artnet" or "udp"]
        """
        mode = mode.upper()

        assert mode in WLED.SYNC_MODES.keys()

        if mode == "udp":
            # if realtime udp is already enabled, we're good to go
            if self.sync_settings["if"]["live"]["en"]:
                return
            else:
                self.sync_settings["if"]["live"]["en"] = True

        else:
            # make sure the mode isn't already set, if so no need to go on.
            # for clarity, this is a reverse dict lookup
            if mode == self.get_sync_mode():
                return
            port = WLED.SYNC_MODES[mode]
            self.sync_settings["if"]["live"]["port"] = port

        self.reboot_flag = True

        _LOGGER.info(
            f"Set WLED device at {self.ip_address} to sync mode '{mode}'"
        )

    def get_sync_mode(self):
        """
        Reverse dict lookup of current sync mode by port

        {"if": {"live": {"port": 5568|6454|4048}}}
        """
        sync_port = self.sync_settings["if"]["live"]["port"]

        return next(
            key for key, value in WLED.SYNC_MODES.items() if value == sync_port
        )

    async def reboot(self):
        """
        JSON API Post to reboot wled device
        """
        reboot = {"rb": True}
        await WLED._wled_request(
            requests.post,
            self.ip_address,
            "/json/state",
            timeout=3,
            data=reboot,
        )


def empty_queue(queue: asyncio.Queue):
    """Empty an asyncio queue

    Args:
        queue (asyncio.Queue): The asyncio queue to empty
    """
    for _ in range(queue.qsize()):
        queue.get_nowait()
        queue.task_done()


async def resolve_destination(
    loop, executor, destination, port=7777, timeout=3
):
    """Uses asyncio's non blocking DNS funcs to attempt domain lookup

    Args:
        loop: ledfx event loop (ledfx.loop)
        executor: ledfx executor (ledfx.thread_executor)
        destination (string): The domain name to be resolved.
        timeout, optional (int/float): timeout for the operation

    Returns:
        On success: string containing the resolved IP address.
        On failure: boolean false.
    """
    try:
        ipaddress.ip_address(destination)
        return destination

    except ValueError:
        cleaned_dest = destination.rstrip(".")
        try:
            dest = await loop.run_in_executor(
                executor, socket.gethostbyname, cleaned_dest
            )
            _LOGGER.debug(f"Resolved {cleaned_dest} to {dest}")
            return dest
            # dest = await loop.getaddrinfo(cleaned_dest, port)
            # return dest[0][4][0]
        except socket.gaierror as e:
            raise ValueError(f"Failed to resolve destination {cleaned_dest}")


def currently_frozen():
    """Checks to see if running in a frozen environment such as pyinstaller or pyupdater package
    Args:
        Nil

    Returns:
        boolean
    """
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def generate_id(name):
    """Converts a name to a id"""
    part1 = re.sub("[^a-zA-Z0-9]", " ", name).lower()
    return re.sub(" +", " ", part1).strip().replace(" ", "-")


def generate_title(id):
    """Converts an id to a more human readable title"""
    return re.sub("[^a-zA-Z0-9]", " ", id).title()


def hasattr_explicit(cls, attr):
    """Returns if the given object has explicitly declared an attribute"""
    try:
        return getattr(cls, attr) != getattr(super(cls, cls), attr, None)
    except AttributeError:
        return False


def getattr_explicit(cls, attr, *default):
    """Gets an explicit attribute from an object"""

    if len(default) > 1:
        raise TypeError(
            "getattr_explicit expected at most 3 arguments, got {}".format(
                len(default) + 2
            )
        )

    if hasattr_explicit(cls, attr):
        return getattr(cls, attr, default)
    if default:
        return default[0]

    raise AttributeError(
        f"type object '{cls.__name__}' has no attribute '{attr}'."
    )


class UserDefaultCollection(MutableMapping):
    """
    A collection of default values and user defined values.
    User defined values are saved automatically in LedFx config.
    Items can be retrieved by name as if user and default values are a single dictionary.
    Validator is a callable that returns sanitised value or raises ValueError if there's a problem
    Parser is a callable that translates config values into a valid form for ledfx to use
    """

    def __init__(
        self,
        ledfx,
        collection_name: str,
        defaults: dict,
        user: str,
        validator: callable = lambda x: x,
        parser: callable = lambda x: x,
    ):
        """
        collection_name: friendly description of the collection
        defaults: dict of default values
        user: ledfx config key for user values
        """
        self._ledfx = ledfx
        self._collection_name = collection_name
        self._default_vals = defaults
        self._user_vals = self._ledfx.config[user]
        self._validator = validator
        self._parser = parser

    def get_all(self, merged=False):
        if merged:
            return self._default_vals | self._user_vals
        else:
            return self._default_vals, self._user_vals

    def __getitem__(self, key):
        val = self._default_vals.get(key) or self._user_vals.get(key)
        if val:
            return self._parser(val)
        raise KeyError(f"Unknown {self._collection_name}: {key}")
        # _LOGGER.error(f"Unknown {self._collection_name}: {name}")

    def __delitem__(self, key):
        if key in self._default_vals:
            _LOGGER.error(
                f"Cannot delete LedFx {self._collection_name}: {key}"
            )
            return
        if key in self._user_vals:
            del self._user_vals[key]
        _LOGGER.info(
            f"Deleted {self._collection_name.lower().rstrip('s')}: {key}"
        )
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    def __setitem__(self, key, value):
        if key in self._default_vals:
            _LOGGER.error(
                f"Cannot overwrite LedFx {self._collection_name}: {key}"
            )
            return
        self._user_vals[key] = self._validator(value)
        _LOGGER.info(
            f"Saved {self._collection_name.lower().rstrip('s')}: {key}"
        )
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    def __iter__(self):
        return chain(self._default_vals, self._user_vals)

    def __len__(self):
        return len(self._default_vals) + len(self._user_vals)


class RollingQueueHandler(logging.handlers.QueueHandler):
    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except asyncio.QueueFull:
            self.queue.get_nowait()
            self.enqueue(record)


class BaseRegistry(ABC):
    """
    Base registry class used for effects and devices. This maintains a
    list of automatically registered base classes and assembles schema
    information

    The prevent registration for classes that are intended to serve as
    base classes (i.e. GradientEffect) add the following declarator:
        @Effect.no_registration
    """

    _schema_attr = "CONFIG_SCHEMA"

    def __init_subclass__(cls, **kwargs):
        """Automatically register the class"""
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "_registry"):
            cls._registry = {}

        name = cls.__module__.split(".")[-1]
        cls._registry[name] = cls

    @classmethod
    def no_registration(self, cls):
        """Clear registration entity based on special declarator"""

        name = cls.__module__.split(".")[-1]
        del cls._registry[name]
        return cls

    # currently this permanently overwrites Device.CONFIG_SCHEMA instead of just for a wrapper device
    # @classmethod
    # def designate_wrapper_device(self, cls):
    #     """Designate Wrapper device to ignore pixel_count in schema"""
    #     # replace base Device classes schema with Wrapper devices schema
    #     setattr(inspect.getmro(cls)[2], self._schema_attr, getattr_explicit(inspect.getmro(cls)[0], self._schema_attr, None))
    #     return cls

    @classmethod
    def schema(self, extended=True, extra=vol.ALLOW_EXTRA):
        """Returns the extended schema of the class"""

        if extended is False:
            return getattr_explicit(
                type(self), self._schema_attr, vol.Schema({})
            )

        schema = vol.Schema({}, extra=extra)
        classes = inspect.getmro(self)[::-1]
        for c in classes:
            c_schema = getattr_explicit(c, self._schema_attr, None)
            if c_schema is not None:
                if type(c_schema) is property:
                    schema = schema.extend(c_schema.fget().schema)
                else:
                    schema = schema.extend(c_schema.schema)

        return schema

    @classmethod
    def registry(self):
        """Returns all the subclasses in the registry"""

        return self._registry

    @property
    def id(self) -> str:
        """Returns the id for the object"""
        return getattr(self, "_id", None)

    @property
    def type(self) -> str:
        """Returns the type for the object"""
        return getattr(self, "_type", None)

    @property
    def config(self) -> dict:
        """Returns the config for the object"""
        return getattr(self, "_config", None)

    @config.setter
    def config(self, _config):
        """Updates the config for an object"""
        _config = self.schema()(_config)
        return setattr(self, "_config", _config)


class RegistryLoader:
    """Manages loading of components for a given registry"""

    def __init__(self, ledfx, cls, package):
        self._package = package
        self._cls = cls
        self._objects = {}
        self._object_id = 1

        self._ledfx = ledfx
        self.import_registry(package)

        # If running in developer mode autoreload the registry when any file
        # within the package changes.
        # Check ledfx is not running as a single exe built using pyinstaller
        # (sys frozen flag).
        if ledfx.dev_enabled() and not currently_frozen():
            import_or_install("watchdog")
            watchdog_events = import_or_install("watchdog.events")
            watchdog_observers = import_or_install("watchdog.observers")

            class RegistryReloadHandler(
                watchdog_events.FileSystemEventHandler
            ):
                def __init__(self, registry):
                    self.registry = registry

                def on_modified(self, event):
                    (_, extension) = os.path.splitext(event.src_path)
                    if extension == ".py":
                        self.registry.reload()

            self.auto_reload_handler = RegistryReloadHandler(self)

            self.observer = watchdog_observers.Observer()
            self.observer.schedule(
                self.auto_reload_handler,
                os.path.dirname(sys.modules[package].__file__),
                recursive=True,
            )
            self.observer.start()

    def import_registry(self, package):
        """
        Imports all the modules in the package thus hydrating
        the registry for the class
        """

        found = self.discover_modules(package)
        _LOGGER.debug(f"Importing {found} from {package}")
        for name in found:
            importlib.import_module(name)

    def discover_modules(self, package):
        """Discovers all modules in the package"""
        module = importlib.import_module(package)

        found = []
        for _, name, _ in pkgutil.iter_modules(module.__path__, package + "."):
            found.append(name)

        return found

    def __iter__(self):
        return iter(self._objects)

    def types(self):
        """Returns all the type strings in the registry"""
        return list(self._cls.registry().keys())

    def classes(self):
        """Returns all the classes in the registry"""
        return self._cls.registry()

    def get_class(self, type):
        return self._cls.registry()[type]

    def values(self):
        """Returns all the created objects"""
        return self._objects.values()

    def reload_module(self, name):
        if name in sys.modules.keys():
            path = sys.modules[name].__file__
            if path.endswith(".pyc") or path.endswith(".pyo"):
                path = path[:-1]

            try:
                module = importlib.import_module(name, path)
                sys.modules[name] = module
            except SyntaxError as e:
                _LOGGER.error(f"Failed to reload {name}: {e}")
        else:
            pass

    def reload(self, force=False):
        """Reloads the registry"""
        found = self.discover_modules(self._package)
        _LOGGER.debug(f"Reloading {found} from {self._package}")
        for name in found:
            self.reload_module(name)

    def create(self, type, id=None, *args, **kwargs):
        """Loads and creates a object from the registry by type"""

        if type not in self._cls.registry():
            raise AttributeError(
                ("Couldn't find '{}' in the {} registry").format(
                    type, self._cls.__name__.lower()
                )
            )

        id = id or type

        # Find the first valid id based on what is already in the registry
        dupe_id = id
        dupe_index = 1
        while id in self._objects:
            id = f"{dupe_id}-{dupe_index}"
            dupe_index = dupe_index + 1

        # Create the new object based on the registry entires and
        # validate the schema.
        _cls = self._cls.registry().get(type)
        _config = kwargs.pop("config", None)
        if _config is not None:
            _config = _cls.schema()(_config)
            obj = _cls(config=_config, *args, **kwargs)
        else:
            obj = _cls(*args, **kwargs)

        # Attach some common properties
        setattr(obj, "_id", id)
        setattr(obj, "_type", type)

        # Store the object into the internal list and return it
        self._objects[id] = obj
        return obj

    def destroy(self, id):

        if id not in self._objects:
            raise AttributeError(
                ("Object with id '{}' does not exist.").format(id)
            )
        del self._objects[id]

    def get(self, *args):
        return self._objects.get(*args)
