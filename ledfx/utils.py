from asyncio import coroutines, ensure_future
from subprocess import PIPE, Popen
import concurrent.futures
import voluptuous as vol
from abc import ABC
import threading
import logging
import inspect
import importlib
import pkgutil
import re
import imp
import sys
import os

_LOGGER = logging.getLogger(__name__)

from subprocess import PIPE, Popen

def install_package(package):
    _LOGGER.info('Installing package %s', package)
    env = os.environ.copy()
    args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
    process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
    _, stderr = process.communicate()
    if process.returncode != 0:
        _LOGGER.error("Failed to install package %s: %s",
                      package, stderr.decode('utf-8').lstrip().strip())
        return False
    return True

def import_or_install(package):
    try:
        return importlib.import_module(package)
        print("imported package")
    except ImportError:
        install_package(package)
        try:
            return importlib.import_module(package)
        except ImportError:
            return False
    return False

def async_fire_and_forget(coro, loop):
    """Run some code in the core event loop without a result"""

    if not coroutines.iscoroutine(coro):
        raise TypeError(('A coroutine object is required: {}').format(coro))

    def callback():
        """Handle the firing of a coroutine."""
        ensure_future(coro, loop=loop)

    loop.call_soon_threadsafe(callback)
    return


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

    loop.call_soon_threadsafe(run_callback)
    return future

def generate_id(name):
    """Converts a name to a id"""
    part1 = re.sub('[^a-zA-Z0-9]', ' ', name).lower()
    return re.sub(' +', ' ', part1).strip().replace(' ', '-')

def generate_title(id):
    """Converts an id to a more human readable title"""
    return re.sub('[^a-zA-Z0-9]', ' ', id).title()

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
                len(default) + 2))

    if hasattr_explicit(cls, attr):
        return getattr(cls, attr, default)
    if default:
        return default[0]

    raise AttributeError("type object '{}' has no attribute '{}'.".format(
        cls.__name__, attr))


class BaseRegistry(ABC):
    """
    Base registry class used for effects and devices. This maintains a
    list of automatically registered base classes and assembles schema
    information

    The prevent registration for classes that are intended to serve as
    base classes (i.e. GradientEffect) add the following declarator:
        @Effect.no_registration
    """
    _schema_attr = 'CONFIG_SCHEMA'

    def __init_subclass__(cls, **kwargs):
        """Automatically register the class"""
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, '_registry'):
            cls._registry = {}

        name = cls.__module__.split('.')[-1]
        cls._registry[name] = cls

    @classmethod
    def no_registration(self, cls):
        """Clear registration entiry based on special declarator"""

        name = cls.__module__.split('.')[-1]
        del cls._registry[name]
        return cls

    @classmethod
    def schema(self, extended=True, extra=vol.ALLOW_EXTRA):
        """Returns the extended schema of the class"""

        if extended is False:
            return getattr_explicit(
                type(self), self._schema_attr, vol.Schema({}))

        schema = vol.Schema({}, extra=extra)
        classes = inspect.getmro(self)[::-1]
        for c in classes:
            c_schema = getattr_explicit(c, self._schema_attr, None)
            if c_schema is not None:
                schema = schema.extend(c_schema.schema)

        return schema

    @classmethod
    def registry(self):
        """Returns all the subclasses in the registry"""

        return self._registry

    @property
    def id(self) -> str:
        """Returns the id for the object"""
        return getattr(self, '_id', None)

    @property
    def type(self) -> str:
        """Returns the id for the object"""
        return getattr(self, '_type', None)

    @property
    def config(self) -> dict:
        """Returns the config for the object"""
        return getattr(self, '_config', None)


class RegistryLoader(object):
    """Manages loading of compoents for a given registry"""

    def __init__(self, ledfx, cls, package):
        self._package = package
        self._cls = cls
        self._objects = {}
        self._object_id = 1

        self._ledfx = ledfx
        self.import_registry(package)

        # If running in developer mode autoreload the registry when any file
        # within the package changes.
        # Check ledfx is not running as a single exe built using pyinstaller (sys frozen flag).
        if ledfx.dev_enabled() and import_or_install("watchdog") and not getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):

            watchdog_events = import_or_install("watchdog.events")
            watchdog_observers = import_or_install("watchdog.observers")

            class RegistryReloadHandler(watchdog_events.FileSystemEventHandler):
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
                recursive=True)
            self.observer.start()

    def import_registry(self, package):
        """
        Imports all the modules in the package thus hydrating
        the registry for the class
        """

        found = self.discover_modules(package)
        _LOGGER.info("Importing {} from {}".format(found, package))
        for name in found:
            importlib.import_module(name)

    def discover_modules(self, package):
        """Discovers all modules in the package"""
        module = importlib.import_module(package)

        found = []
        for _, name, _ in pkgutil.iter_modules(module.__path__, package + '.'):
            found.append(name)

        return found

    def __iter__(self):
        return iter(self._objects)

    def types(self):
        """Returns all the type strings in the registry"""
        return list(self._cls.registry().keys())

    def classes(self):
        """Returns all the classes in the regsitry"""
        return self._cls.registry()

    def get_class(self, type):
        return self._cls.registry()[type]

    def values(self):
        """Returns all the created objects"""
        return self._objects.values()

    def reload_module(self, name):
        if name in sys.modules.keys():
            path = sys.modules[name].__file__
            if path.endswith('.pyc') or path.endswith('.pyo'):
                path = path[:-1]

            try:
                module = imp.load_source(name, path)
                sys.modules[name] = module
            except SyntaxError as e:
                _LOGGER.error("Failed to reload {}: {}".format(name, e))
        else:
            pass

    def reload(self, force=False):
        """Reloads the registry"""

        found = self.discover_modules(self._package)
        _LOGGER.info("Reloading {} from {}".format(found, self._package))
        for name in found:
            self.reload_module(name)


    def create(self, type, id = None, *args, **kwargs):
        """Loads and creates a object from the registry by type"""

        if type not in self._cls.registry():
            raise AttributeError(
                ("Couldn't find '{}' in the {} registry").format(
                    type, self._cls.__name__.lower()))

        id = id or type

        # Find the first valid id based on what is already in the registry
        dupe_id = id
        dupe_index = 1
        while id in self._objects:
            id = "{}-{}".format(dupe_id, dupe_index)
            dupe_index = dupe_index + 1

        # Create the new object based on the registry entires and
        # validate the schema.
        _cls = self._cls.registry().get(type)
        _config = kwargs.pop('config', None)
        if _config != None:
            _config = _cls.schema()(_config)
            obj = _cls(config = _config, *args, **kwargs)
        else:
            obj = _cls(*args, **kwargs)

        # Attach some common properties
        setattr(obj, '_id', id)
        setattr(obj, '_type', type)

        # Store the object into the internal list and return it
        self._objects[id] = obj
        return obj

    def destroy(self, id):

        if id not in self._objects:
            raise AttributeError(
                ("Object with id '{}' does not exist.").format(id))
        del self._objects[id]

    def get(self, id):
        return self._objects.get(id)