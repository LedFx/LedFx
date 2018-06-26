from asyncio import coroutines, ensure_future
import concurrent.futures
import voluptuous as vol
import threading
import logging
import inspect

_LOGGER = logging.getLogger(__name__)

def async_fire_and_forget(coro, loop):

    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError('Cannot be called from within the event loop')

    if not coroutines.iscoroutine(coro):
        raise TypeError('A coroutine object is required: %s' % coro)

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

class MetaRegistry(type):
    """
    Meta-class to manage registry and schema merging
    """

    def __init__(cls, name, bases, cls_dict):
        type.__init__(cls, name, bases, cls_dict)

        # Register all leaf most subclasses such that the effect manager
        # can properly iterate over the effects
        if not hasattr(cls, 'registry'):
            cls.registry = set()
        cls.registry.add(cls)
        cls.registry -= set(bases)
        
        # Combine all the schema starting at the base most class and
        # working back to the current class. This will allow subclasses
        # to override base class configuration and defaults
        cls.schema = vol.Schema({})
        base_classes = inspect.getmro(cls)[::-1]
        for base in inspect.getmro(cls):
            if hasattr(base, 'CONFIG_SCHEMA'):
                cls.schema = cls.schema.extend(base.CONFIG_SCHEMA.schema)

        # Finally combine the current class schema
        if hasattr(cls, 'CONFIG_SCHEMA'):
            cls.schema.extend(cls.CONFIG_SCHEMA.schema)

    def get_schema(cls):
        return cls.schema

    def get_registry(cls):
        return cls.registry