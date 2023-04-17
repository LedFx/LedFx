import logging
from typing import Callable

import numpy as np

_LOGGER = logging.getLogger(__name__)


class Event:
    """Base for events"""

    LEDFX_SHUTDOWN = "shutdown"
    DEVICE_CREATED = "device_created"
    DEVICE_UPDATE = "device_update"
    DEVICES_UPDATED = "devices_updated"
    VIRTUAL_UPDATE = "virtual_update"
    VISUALISATION_UPDATE = "visualisation_update"
    GRAPH_UPDATE = "graph_update"
    EFFECT_SET = "effect_set"
    EFFECT_CLEARED = "effect_cleared"
    SCENE_ACTIVATED = "scene_activated"
    SCENE_DELETED = "scene_deleted"
    PRESET_ACTIVATED = "preset_activated"
    VIRTUAL_CONFIG_UPDATE = "virtual_config_update"
    GLOBAL_PAUSE = "global_pause"
    VIRTUAL_PAUSE = "virtual_pause"
    AUDIO_INPUT_DEVICE_CHANGED = "audio_input_device_changed"

    def __init__(self, type: str):
        self.event_type = type

    def to_dict(self):
        return self.__dict__


class DeviceUpdateEvent(Event):
    """Event emitted when a device's pixels are updated"""

    def __init__(self, device_id: str, pixels: np.ndarray):
        super().__init__(Event.DEVICE_UPDATE)
        self.device_id = device_id
        # self.pixels = pixels.astype(np.uint8).T.tolist()
        self.pixels = pixels


class DeviceCreatedEvent(Event):
    """Event emitted when a device is created"""

    def __init__(self, device_name):
        self.device_name = device_name
        super().__init__(Event.DEVICE_CREATED)


class DevicesUpdatedEvent(Event):
    """Weird event emitted when OpenRGB device fails to connect"""

    def __init__(self, device_id: str):
        super().__init__(Event.DEVICES_UPDATED)
        self.device_id = device_id


class VirtualUpdateEvent(Event):
    """Event emitted when a virtual's pixels are updated"""

    def __init__(self, virtual_id: str, pixels: np.ndarray):
        super().__init__(Event.VIRTUAL_UPDATE)
        self.virtual_id = virtual_id
        # self.pixels = pixels.astype(np.uint8).T.tolist()
        self.pixels = pixels


class GlobalPauseEvent(Event):
    """Event emitted when all virtuals are paused"""

    def __init__(self):
        super().__init__(Event.GLOBAL_PAUSE)


class VirtualPauseEvent(Event):
    """Event emitted when virtual updated paused"""

    def __init__(self, virtual_id: str):
        super().__init__(Event.VIRTUAL_PAUSE)
        self.virtual_id = virtual_id


class AudioDeviceChangeEvent(Event):
    """Event emitted when the audio capture device is changed"""

    def __init__(self, audio_input_device_name: str):
        super().__init__(Event.AUDIO_INPUT_DEVICE_CHANGED)
        self.audio_input_device_name = audio_input_device_name


class GraphUpdateEvent(Event):
    """Event emitted when an audio graph is updated"""

    def __init__(
        self,
        graph_id: str,
        melbank: np.ndarray,
        frequencies: np.ndarray,
    ):
        super().__init__(Event.GRAPH_UPDATE)
        self.graph_id = graph_id
        self.melbank = melbank.tolist()
        self.frequencies = frequencies.tolist()


class VisualisationUpdateEvent(Event):
    """Event that encompasses DeviceUpdateEvent and VirtualUpdateEvent
    used to send pixel data to frontend at a constant rate"""

    def __init__(
        self,
        is_device: bool,  # true if device, false if virtual
        vis_id: str,  # id of device/virtual
        pixels: np.ndarray,
    ):
        super().__init__(Event.VISUALISATION_UPDATE)
        self.is_device = is_device
        self.vis_id = vis_id
        self.pixels = pixels.astype(np.uint8).T.tolist()


class EffectSetEvent(Event):
    """Event emitted when an effect is set or updated"""

    def __init__(self, effect_name, effect_id, effect_config, virtual_id):
        super().__init__(Event.EFFECT_SET)
        self.effect_name = effect_name
        self.effect_id = effect_id
        self.effect_config = effect_config
        self.virtual_id = virtual_id


class EffectClearedEvent(Event):
    """Event emitted when an effect is cleared"""

    def __init__(self):
        super().__init__(Event.EFFECT_CLEARED)


class SceneActivatedEvent(Event):
    """Event emitted when a scene is set"""

    def __init__(self, scene_id):
        super().__init__(Event.SCENE_ACTIVATED)
        self.scene_id = scene_id


class SceneDeletedEvent(Event):
    """Event emitted when a scene is set"""

    def __init__(self, scene_id):
        super().__init__(Event.SCENE_DELETED)
        self.scene_id = scene_id


class VirtualConfigUpdateEvent(Event):
    """Event emitted when a virtual is updated, including effect changes"""

    def __init__(self, virtual_id, config):
        super().__init__(Event.VIRTUAL_CONFIG_UPDATE)
        self.virtual_id = virtual_id
        self.config = config


class LedFxShutdownEvent(Event):
    """Event emitted when LedFx is shutting down"""

    def __init__(self):
        super().__init__(Event.LEDFX_SHUTDOWN)


class EventListener:
    def __init__(self, callback: Callable, event_filter: dict = {}):
        self.callback = callback
        self.filter = event_filter

    def filter_event(self, event):
        event_dict = event.to_dict()
        for filter_key in self.filter:
            if event_dict.get(filter_key) != self.filter[filter_key]:
                return True

        return False


class Events:
    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._listeners = {}

    def fire_event(self, event: Event) -> None:
        listeners = self._listeners.get(event.event_type, [])
        if not listeners:
            return

        for listener in listeners:
            if not listener.filter_event(event):
                self._ledfx.loop.call_soon_threadsafe(listener.callback, event)

    def add_listener(
        self,
        callback: Callable,
        event_type: str,
        event_filter: dict = {},
    ) -> None:
        listener = EventListener(callback, event_filter)
        if event_type in self._listeners:
            self._listeners[event_type].append(listener)
        else:
            self._listeners[event_type] = [listener]

        def remove_listener() -> None:
            self._remove_listener(event_type, listener)

        return remove_listener

    def _remove_listener(self, event_type: str, listener: Callable) -> None:
        try:
            self._listeners[event_type].remove(listener)
            if not self._listeners[event_type]:
                self._listeners.pop(event_type)
        except (KeyError, ValueError):
            _LOGGER.warning("Failed to remove event listener %s", listener)


# def get_event_types():
#     """Get a list of the types of events available"""
#     return [event for event in vars(Event) if (not event.startswith('__')) and (event.isupper())]

# print(get_event_types())
