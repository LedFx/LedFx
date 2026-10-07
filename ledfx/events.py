from __future__ import annotations

import asyncio
import inspect
import logging
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from copy import copy, deepcopy
from dataclasses import dataclass
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

_LOGGER = logging.getLogger(__name__)


class Event:
    """Base for events"""

    BASE_CONFIG_UPDATE = "base_config_update"
    LEDFX_SHUTDOWN = "shutdown"
    DEVICE_CREATED = "device_created"
    DEVICE_UPDATE = "device_update"
    DEVICES_UPDATED = "devices_updated"
    VIRTUAL_UPDATE = "virtual_update"
    VISUALISATION_UPDATE = "visualisation_update"
    FRONTEND_VISUALISER_DATA = "frontend_visualiser_data"
    GRAPH_UPDATE = "graph_update"
    EFFECT_SET = "effect_set"
    EFFECT_UPDATED = "effect_updated"
    EFFECT_CLEARED = "effect_cleared"
    SCENE_ACTIVATED = "scene_activated"
    SCENE_DELETED = "scene_deleted"
    PRESET_ACTIVATED = "preset_activated"
    VIRTUAL_CONFIG_UPDATE = "virtual_config_update"
    GLOBAL_PAUSE = "global_pause"
    VIRTUAL_PAUSE = "virtual_pause"
    AUDIO_INPUT_DEVICE_CHANGED = "audio_input_device_changed"
    AUDIO_DEVICE_LIST_CHANGED = "audio_device_list_changed"
    VIRTUAL_DIAG = "virtual_diag"
    GENERAL_DIAG = "general_diag"
    CLIENT_CONNECTED = "client_connected"
    CLIENT_DISCONNECTED = "client_disconnected"
    CLIENT_SYNC = "client_sync"
    CLIENTS_UPDATED = "clients_updated"
    CLIENT_BROADCAST = "client_broadcast"
    PLAYLIST_STARTED = "playlist_started"
    PLAYLIST_ADVANCED = "playlist_advanced"
    PLAYLIST_STOPPED = "playlist_stopped"
    PLAYLIST_PAUSED = "playlist_paused"
    PLAYLIST_RESUMED = "playlist_resumed"
    COLORS_UPDATED = "colors_updated"
    SONG_DETECTED = "song_detected"
    NOW_PLAYING_TRACK_CHANGED = "now_playing_track_changed"
    NOW_PLAYING_METADATA_CHANGED = "now_playing_metadata_changed"
    NOW_PLAYING_ARTWORK_CHANGED = "now_playing_artwork_changed"
    NOW_PLAYING_GRADIENT_CHANGED = "now_playing_gradient_changed"
    NOW_PLAYING_CLEARED = "now_playing_cleared"
    AUDIO_SOURCE_ERROR = "audio_source_error"

    def __init__(self, type: str):
        """
        Initializes an event with the specified event type.

        Args:
            type: The string identifier representing the event type.
        """
        self.event_type = type

    def to_dict(self):
        """
        Returns a dictionary representation of the event's attributes.
        """
        return self.__dict__


class SongDetectedEvent(Event):
    """Event emitted when media/song info is detected"""

    def __init__(
        self,
        title: str,
        artist: str,
        album: str = "",
        thumbnail: str | None = None,
        position: float | None = None,
        duration: float | None = None,
        playing: bool = False,
        timestamp: float | None = None,
    ):
        """
        Initializes a SongDetectedEvent with media information.

        Args:
            title: The title of the song/track.
            artist: The artist name.
            album: The album name (optional).
            thumbnail: Path or URL to album artwork (optional).
            position: Current playback position in seconds (optional).
            duration: Total duration in seconds (optional).
            playing: Whether the media is currently playing.
            timestamp: Unix timestamp of when the info was captured.
        """
        super().__init__(Event.SONG_DETECTED)
        self.title = title
        self.artist = artist
        self.album = album
        self.thumbnail = thumbnail
        self.position = position
        self.duration = duration
        self.playing = playing
        self.timestamp = timestamp


class GeneralDiagEvent(Event):
    """Event emitted with arbitrary test diagnostics"""

    def __init__(self, debug: str, scroll: bool = False):
        """
        Initializes a GeneralDiagEvent with diagnostic text and an optional scroll flag.

        Args:
            debug: The diagnostic message to emit.
            scroll: If True, indicates the message should be scrolled.
        """
        super().__init__(Event.GENERAL_DIAG)
        self.debug = debug
        self.scroll = scroll


class _DiagnosticDropSummary(GeneralDiagEvent):
    """Carry trusted loss accounting without adding fields to the wire event."""

    __slots__ = ("dropped",)

    def __init__(self, dropped: int) -> None:
        super().__init__(f"Dropped {dropped} diagnostic messages", scroll=True)
        self.dropped = dropped


class VirtualDiagEvent(Event):
    """Event emitted when a virtual's diagnostics are updated"""

    def __init__(
        self,
        virtual_id: str,
        fps: int,
        r_avg: float,
        r_min: float,
        r_max: float,
        cycle: float,
        sleep: float,
        phy: dict[str, object],
    ):
        """
        Initializes a VirtualDiagEvent with diagnostic metrics for a virtual entity.

        Args:
            virtual_id: Identifier of the virtual entity.
            fps: Frames per second.
            r_avg: Average response time.
            r_min: Minimum response time.
            r_max: Maximum response time.
            cycle: Cycle time.
            sleep: Sleep time.
            phy: Phy dict containing physical device information.
        """
        super().__init__(Event.VIRTUAL_DIAG)
        self.virtual_id = virtual_id
        self.fps = fps
        self.r_avg = r_avg
        self.r_min = r_min
        self.r_max = r_max
        self.cycle = cycle
        self.sleep = sleep
        self.phy = phy


class ClientConnectedEvent(Event):
    """Event emitted when a client connects"""

    def __init__(self, client_id: str, client_ip: str):
        super().__init__(Event.CLIENT_CONNECTED)
        self.client_id = client_id
        self.client_ip = client_ip


class ClientDisconnectedEvent(Event):
    """Event emitted when a client disconnects"""

    def __init__(self, client_id: str, client_ip: str):
        super().__init__(Event.CLIENT_DISCONNECTED)
        self.client_id = client_id
        self.client_ip = client_ip


class ClientSyncEvent(Event):
    """Event emitted when a client advises sync with the server"""

    def __init__(self, client_id: str):
        super().__init__(Event.CLIENT_SYNC)
        self.client_id = client_id


class ClientsUpdatedEvent(Event):
    """Event emitted when client list/metadata changes"""

    def __init__(self):
        super().__init__(Event.CLIENTS_UPDATED)


class ClientBroadcastEvent(Event):
    """Event emitted when a client broadcasts a message"""

    def __init__(
        self,
        broadcast_type: str,
        broadcast_id: str,
        sender_uuid: str,
        sender_name: str | None,
        sender_type: str,
        target_uuids: list[str],
        payload: dict,
    ):
        super().__init__(Event.CLIENT_BROADCAST)
        self.broadcast_type = broadcast_type
        self.broadcast_id = broadcast_id
        self.sender_uuid = sender_uuid
        self.sender_name = sender_name
        self.sender_type = sender_type
        self.target_uuids = target_uuids
        self.payload = payload


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
    """
    Event emitted when a device changes status due to something outside the users control - this is used to update the frontend
    """

    def __init__(self, device_id: str):
        super().__init__(Event.DEVICES_UPDATED)
        self.device_id = device_id


class VirtualUpdateEvent(Event):
    """Event emitted when a virtual's pixels are updated"""

    def __init__(self, virtual_id: str, pixels: np.ndarray):
        super().__init__(Event.VIRTUAL_UPDATE)
        self.virtual_id = virtual_id
        self.pixels = pixels


class GlobalPauseEvent(Event):
    """Event emitted when all virtuals are paused"""

    def __init__(self, paused: bool):
        super().__init__(Event.GLOBAL_PAUSE)
        self.paused = paused


class VirtualPauseEvent(Event):
    """Event emitted when virtual updated paused"""

    def __init__(self, virtual_id: str, paused: bool):
        super().__init__(Event.VIRTUAL_PAUSE)
        self.virtual_id = virtual_id
        self.paused = paused


class AudioDeviceChangeEvent(Event):
    """Event emitted when the audio capture device is changed"""

    def __init__(self, audio_input_device_name: str):
        super().__init__(Event.AUDIO_INPUT_DEVICE_CHANGED)
        self.audio_input_device_name = audio_input_device_name


class AudioDeviceListChangedEvent(Event):
    """Event emitted when the system audio device list changes (devices added/removed)"""

    def __init__(self):
        super().__init__(Event.AUDIO_DEVICE_LIST_CHANGED)


class AudioSourceErrorEvent(Event):
    """Event emitted when the configured audio source cannot be opened.

    Used to notify the frontend when a Sendspin (or other virtual) audio device
    is unavailable so the user can choose to fix it rather than silently falling
    back to a different device.
    """

    def __init__(self, error_type: str, message: str, device_name: str = ""):
        super().__init__(Event.AUDIO_SOURCE_ERROR)
        self.error_type = error_type
        self.message = message
        self.device_name = device_name


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
        pixels: str | list[list[int]],
        shape: tuple,
    ):
        super().__init__(Event.VISUALISATION_UPDATE)
        self.is_device = is_device
        self.vis_id = vis_id
        self.pixels = pixels
        self.shape = shape


class FrontendVisualiserDataEvent(Event):
    """Event fired when frontend sends captured visualiser pixel data to backend
    Used for frontend-driven effects (opposite direction of VisualisationUpdateEvent)
    """

    def __init__(
        self,
        vis_id: str,  # identifier for the visualiser source
        pixels: np.ndarray,  # RGB pixel array
        shape: tuple,  # (rows, cols) shape of the pixel data
        client_id: str,  # UUID of the client that sent the data
    ):
        super().__init__(Event.FRONTEND_VISUALISER_DATA)
        self.vis_id = vis_id
        self.pixels = pixels
        self.shape = shape
        self.client_id = client_id


class EffectSetEvent(Event):
    """Event emitted when an effect is set"""

    def __init__(
        self,
        effect_name: str,
        effect_id: str,
        virtual_id: str,
        effect_type: str,
        active: bool,
        streaming: bool,
    ):
        super().__init__(Event.EFFECT_SET)
        self.effect_name = effect_name
        self.effect_id = effect_id
        self.virtual_id = virtual_id
        self.effect_type = effect_type
        self.active = active
        self.streaming = streaming


class EffectUpdatedEvent(Event):
    """Event emitted when an effect is updated"""

    def __init__(
        self,
        effect_id: str,
        virtual_id: str,
    ):
        super().__init__(Event.EFFECT_UPDATED)
        self.effect_id = effect_id
        self.virtual_id = virtual_id


class EffectClearedEvent(Event):
    """Event emitted when an effect is cleared"""

    def __init__(self, virtual_id: str):
        super().__init__(Event.EFFECT_CLEARED)
        self.virtual_id = virtual_id


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


class PlaylistStartedEvent(Event):
    """Event emitted when a playlist starts

    Includes optional scene_id describing which scene was activated when the
    playlist started.
    """

    def __init__(
        self,
        playlist_id: str,
        index: int,
        scene_id: str | None = None,
        effective_duration_ms: int | None = None,
        remaining_ms: int | None = None,
    ):
        super().__init__(Event.PLAYLIST_STARTED)
        self.playlist_id = playlist_id
        self.index = index
        self.scene_id = scene_id
        # Duration after jitter/clamping applied for the current item
        self.effective_duration_ms = effective_duration_ms
        # Remaining ms when paused/cancelled (if available)
        self.remaining_ms = remaining_ms


class PlaylistAdvancedEvent(Event):
    """Event emitted when the playlist advances to the next item

    Includes the scene_id that was activated for the advanced index.
    """

    def __init__(
        self,
        playlist_id: str,
        index: int,
        scene_id: str | None = None,
        effective_duration_ms: int | None = None,
    ):
        super().__init__(Event.PLAYLIST_ADVANCED)
        self.playlist_id = playlist_id
        self.index = index
        self.scene_id = scene_id
        self.effective_duration_ms = effective_duration_ms


class PlaylistStoppedEvent(Event):
    """Event emitted when a playlist stops

    May include the scene_id that was active when the playlist stopped.
    """

    def __init__(
        self,
        playlist_id: str,
        scene_id: str | None = None,
        effective_duration_ms: int | None = None,
        remaining_ms: int | None = None,
    ):
        super().__init__(Event.PLAYLIST_STOPPED)
        self.playlist_id = playlist_id
        self.scene_id = scene_id
        self.effective_duration_ms = effective_duration_ms
        self.remaining_ms = remaining_ms


class PlaylistPausedEvent(Event):
    """Event emitted when a playlist is paused

    Includes index and the scene_id currently active when paused.
    """

    def __init__(
        self,
        playlist_id: str,
        index: int,
        scene_id: str | None = None,
        effective_duration_ms: int | None = None,
        remaining_ms: int | None = None,
    ):
        super().__init__(Event.PLAYLIST_PAUSED)
        self.playlist_id = playlist_id
        self.index = index
        self.scene_id = scene_id
        self.effective_duration_ms = effective_duration_ms
        self.remaining_ms = remaining_ms


class PlaylistResumedEvent(Event):
    """Event emitted when a playlist is resumed

    Includes index and the scene_id that will be active after resuming.
    """

    def __init__(
        self,
        playlist_id: str,
        index: int,
        scene_id: str | None = None,
        effective_duration_ms: int | None = None,
        remaining_ms: int | None = None,
    ):
        super().__init__(Event.PLAYLIST_RESUMED)
        self.playlist_id = playlist_id
        self.index = index
        self.scene_id = scene_id
        self.effective_duration_ms = effective_duration_ms
        self.remaining_ms = remaining_ms


class VirtualConfigUpdateEvent(Event):
    """Event emitted when a virtual is updated, including effect changes"""

    def __init__(self, virtual_id, config):
        super().__init__(Event.VIRTUAL_CONFIG_UPDATE)
        self.virtual_id = virtual_id
        self.config = config


class BaseConfigUpdateEvent(Event):
    """
    Event emitted when an item in the base configuration is updated.
    """

    def __init__(self, config):
        super().__init__(Event.BASE_CONFIG_UPDATE)
        self.config = config


class ColorsUpdatedEvent(Event):
    """
    Event emitted when user-defined colors or gradients are added, modified, or deleted.
    """

    def __init__(self):
        super().__init__(Event.COLORS_UPDATED)


class NowPlayingTrackChangedEvent(Event):
    """Event emitted when the current track changes."""

    def __init__(
        self,
        source_id: str,
        title: str | None,
        artist: str | None,
        album: str | None,
    ):
        super().__init__(Event.NOW_PLAYING_TRACK_CHANGED)
        self.source_id = source_id
        self.title = title
        self.artist = artist
        self.album = album


class NowPlayingMetadataChangedEvent(Event):
    """Event emitted when metadata is updated (including position-only changes)."""

    def __init__(self, source_id: str, metadata: dict):
        super().__init__(Event.NOW_PLAYING_METADATA_CHANGED)
        self.source_id = source_id
        self.metadata = metadata


class NowPlayingArtworkChangedEvent(Event):
    """Event emitted when artwork reference changes."""

    def __init__(self, source_id: str, artwork: dict):
        super().__init__(Event.NOW_PLAYING_ARTWORK_CHANGED)
        self.source_id = source_id
        self.artwork = artwork


class NowPlayingGradientChangedEvent(Event):
    """Event emitted when the current track gradient is updated."""

    def __init__(self, source_id: str, gradient: str | None, variant: str):
        super().__init__(Event.NOW_PLAYING_GRADIENT_CHANGED)
        self.source_id = source_id
        self.gradient = gradient
        self.variant = variant


class NowPlayingClearedEvent(Event):
    """Event emitted when Now Playing state is cleared."""

    def __init__(self, source_id: str):
        super().__init__(Event.NOW_PLAYING_CLEARED)
        self.source_id = source_id


class LedFxShutdownEvent(Event):
    """Event emitted when LedFx is shutting down"""

    def __init__(self):
        super().__init__(Event.LEDFX_SHUTDOWN)


def copy_filter_value(value: object) -> object:
    """Copy only JSON equality values, accepting tuples as sequence input."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(cast(float, value)):
        return value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        if not all(type(key) is str for key in mapping):
            raise ValueError("filter keys must be strings")
        return {
            cast(str, key): copy_filter_value(item) for key, item in mapping.items()
        }
    if type(value) in (list, tuple):
        return tuple(
            copy_filter_value(item)
            for item in cast(list[object] | tuple[object, ...], value)
        )
    raise ValueError("filter values must be JSON-compatible")


def equal_filter_value(left: object, right: object) -> bool:
    """Compare JSON values structurally without invoking array equality."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return False
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        left_mapping = cast(Mapping[object, object], left)
        right_mapping = cast(Mapping[object, object], right)
        return left_mapping.keys() == right_mapping.keys() and all(
            equal_filter_value(left_mapping[key], right_mapping[key])
            for key in left_mapping
        )
    if type(left) in (list, tuple) and type(right) in (list, tuple):
        left_sequence = cast(list[object] | tuple[object, ...], left)
        right_sequence = cast(list[object] | tuple[object, ...], right)
        return len(left_sequence) == len(right_sequence) and all(
            equal_filter_value(a, b)
            for a, b in zip(left_sequence, right_sequence, strict=True)
        )
    scalar_types = (str, bool, int, float, type(None))
    return type(left) in scalar_types and type(right) in scalar_types and left == right


def _validate_callback(callback: object) -> None:
    if not callable(callback):
        raise TypeError("event callbacks must be callable")
    if inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(
        callback.__call__
    ):
        raise TypeError("event callbacks must be synchronous")


def _observe_future_result(future: asyncio.Future[object]) -> None:
    if not future.cancelled():
        future.exception()


def _reject_awaitable(result: object) -> None:
    if not inspect.isawaitable(result):
        return
    if inspect.iscoroutine(result):
        result.close()
    elif isinstance(result, asyncio.Future):
        future = cast(asyncio.Future[object], result)
        future.cancel()
        future.add_done_callback(_observe_future_result)
    raise TypeError("event callbacks must be synchronous")


class EventListener:
    def __init__(
        self,
        callback: Callable[[Event], object],
        event_filter: Mapping[str, object] | None = None,
        *,
        generation: int = 0,
        event_type: str = "",
    ) -> None:
        _validate_callback(callback)
        if event_filter is not None and not isinstance(event_filter, Mapping):
            raise ValueError("event filter must be a mapping")
        self.callback = callback
        self.filter = cast(
            dict[str, object],
            copy_filter_value(event_filter if event_filter is not None else {}),
        )
        for key in ("vis_id", "device_id", "virtual_id", "graph_id", "scene_id"):
            if key in self.filter and type(self.filter[key]) is not str:
                raise ValueError(f"{key} filter must be a string")
        if "is_device" in self.filter and type(self.filter["is_device"]) is not bool:
            raise ValueError("is_device filter must be a boolean")
        self.generation = generation
        self.active = True
        self.event_type = event_type

    def revoke(self) -> bool:
        """Revoke once; the caller holds the owning bus lock."""
        if not self.active:
            return False
        self.active = False
        return True

    def filter_event(self, event: Event) -> bool:
        """Return whether this registration excludes the event."""
        event_dict = event.to_dict()
        return any(
            key not in event_dict or not equal_filter_value(value, event_dict[key])
            for key, value in self.filter.items()
        )


class _EventLoop(Protocol):
    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> object: ...


class _EventHost(Protocol):
    @property
    def loop(self) -> _EventLoop: ...


@dataclass(eq=False)
class _RegistrationObserver:
    callback: Callable[[str, int], object]
    active: bool = True

    def revoke(self) -> bool:
        """Revoke once; the caller holds the owning bus lock."""
        if not self.active:
            return False
        self.active = False
        return True


@dataclass
class _PendingGraph:
    graph_id: str
    melbank: NDArray[np.generic]
    frequencies: NDArray[np.generic]


class Events:
    """Dispatch shared read-only events through revocable registrations."""

    def __init__(self, ledfx: _EventHost) -> None:
        self._ledfx = ledfx
        self._lock = threading.Lock()
        self._listeners: dict[str, tuple[EventListener, ...]] = {}
        self._revisions: dict[str, int] = {}
        self._generation = 0
        self._registration_observers: tuple[_RegistrationObserver, ...] = ()
        self._listener_errors: dict[str, tuple[float, int]] = {}
        self._telemetry_lock = threading.Lock()
        self._latest: dict[tuple[str, str], Event | _PendingGraph] = {}
        self._draining_latest: dict[tuple[str, str], Event | _PendingGraph] = {}
        self._text_queue: deque[Event] = deque()
        self._draining_text: deque[Event] = deque()
        self._text_dropped = 0
        self._telemetry_scheduled = False

    def registration_snapshot(
        self, event_type: str
    ) -> tuple[int, tuple[EventListener, ...]]:
        with self._lock:
            return self._revisions.get(event_type, 0), self._listeners.get(
                event_type, ()
            )

    def has_listeners(self, event_type: str) -> bool:
        """Whether an event has consumers, before preparing an expensive payload."""
        return bool(self.registration_snapshot(event_type)[1])

    def may_have_listeners(
        self, event_type: str, metadata: Mapping[str, object]
    ) -> bool:
        """Exclude registrations only when supplied metadata proves a mismatch."""
        _, listeners = self.registration_snapshot(event_type)
        for listener in listeners:
            try:
                if all(
                    key not in metadata or equal_filter_value(value, metadata[key])
                    for key, value in listener.filter.items()
                ):
                    return True
            except Exception as error:  # noqa: BLE001 - isolate consumer code
                self._report_listener_error(listener, error)
                # A failed comparison cannot conclusively exclude this listener.
                return True
        return False

    def fire_event(self, event: Event) -> None:
        if event.event_type in (Event.GRAPH_UPDATE, Event.VIRTUAL_DIAG):
            field = (
                "graph_id" if event.event_type == Event.GRAPH_UPDATE else "virtual_id"
            )
            entity_id = getattr(event, field, None)
            if type(entity_id) is not str:
                return
            metadata: dict[str, object] = {
                "event_type": event.event_type,
                field: entity_id,
            }
            if not self.may_have_listeners(event.event_type, metadata):
                return
            # Only these fixed producer channels own mutable admission payloads.
            snapshot = copy(event)
            snapshot.__dict__ = deepcopy(event.__dict__)
            self._admit_latest(event.event_type, entity_id, snapshot, metadata)
        elif event.event_type == Event.GENERAL_DIAG:
            if not self.has_listeners(Event.GENERAL_DIAG):
                return
            snapshot = copy(event)
            snapshot.__dict__ = deepcopy(event.__dict__)
            with self._telemetry_lock:
                if not self.has_listeners(Event.GENERAL_DIAG):
                    return
                if len(self._text_queue) == 100:
                    self._text_queue.popleft()
                    self._text_dropped += 1
                self._text_queue.append(snapshot)
                wake = not self._telemetry_scheduled
                self._telemetry_scheduled = True
            if wake:
                self._ledfx.loop.call_soon_threadsafe(self._drain_telemetry)
        else:
            self._dispatch(event)

    def publish_graph(
        self,
        graph_id: str,
        melbank: NDArray[np.generic],
        frequencies: NDArray[np.generic],
    ) -> None:
        """Own an interested graph sample; convert only the selected latest.

        Publishers use stable live-source IDs and purge pending samples when
        disposing/rebuilding those sources. This map is not a historical cache.
        """
        metadata: dict[str, object] = {
            "event_type": Event.GRAPH_UPDATE,
            "graph_id": graph_id,
        }
        if not self.may_have_listeners(Event.GRAPH_UPDATE, metadata):
            return
        pending = _PendingGraph(graph_id, melbank.copy(), frequencies.copy())
        self._admit_latest(Event.GRAPH_UPDATE, graph_id, pending, metadata)

    def _admit_latest(
        self,
        event_type: str,
        entity_id: str,
        pending: Event | _PendingGraph,
        metadata: Mapping[str, object],
    ) -> None:
        with self._telemetry_lock:
            # Recheck after copying: a revoked last registration must not leave
            # a retained sample behind its synchronous prune.
            if not self.may_have_listeners(event_type, metadata):
                return
            self._latest[event_type, entity_id] = pending
            wake = not self._telemetry_scheduled
            self._telemetry_scheduled = True
        if wake:
            self._ledfx.loop.call_soon_threadsafe(self._drain_telemetry)

    def _materialize_graph(self, pending: _PendingGraph) -> GraphUpdateEvent:
        return GraphUpdateEvent(pending.graph_id, pending.melbank, pending.frequencies)

    def purge_pending(self, event_type: str, entity_id: str) -> None:
        """Release the current source sample without retaining a tombstone."""
        with self._telemetry_lock:
            self._latest.pop((event_type, entity_id), None)
            self._draining_latest.pop((event_type, entity_id), None)

    def _drain_telemetry(self) -> None:
        with self._telemetry_lock:
            self._draining_latest = self._latest
            self._latest = {}
            self._draining_text = self._text_queue
            self._text_queue = deque()
            dropped = self._text_dropped
            keys = tuple(self._draining_latest)
        try:
            for event_type, entity_id in keys:
                key = (event_type, entity_id)
                with self._telemetry_lock:
                    pending = self._draining_latest.get(key)
                if pending is None:
                    continue
                field = "graph_id" if event_type == Event.GRAPH_UPDATE else "virtual_id"
                if not self.may_have_listeners(
                    event_type, {"event_type": event_type, field: entity_id}
                ):
                    continue
                event = (
                    self._materialize_graph(pending)
                    if isinstance(pending, _PendingGraph)
                    else pending
                )
                with self._telemetry_lock:
                    # A deletion/revocation during materialization invalidates
                    # this sample. Claim dispatch before releasing the lock.
                    if self._draining_latest.pop(key, None) is not pending:
                        continue
                self._dispatch(event)
            with self._telemetry_lock:
                has_text = bool(self._draining_text)
            if has_text and dropped and self._dispatch(_DiagnosticDropSummary(dropped)):
                with self._telemetry_lock:
                    self._text_dropped -= dropped
            while True:
                with self._telemetry_lock:
                    if not self._draining_text:
                        break
                    event = self._draining_text.popleft()
                self._dispatch(event)
        finally:
            with self._telemetry_lock:
                self._draining_latest.clear()
                self._draining_text.clear()
                wake = bool(self._latest or self._text_queue)
                self._telemetry_scheduled = wake
            if wake:
                self._ledfx.loop.call_soon_threadsafe(self._drain_telemetry)

    def _dispatch(self, event: Event) -> bool:
        """Queue guarded ordinary observer invocations; report admission."""
        _, listeners = self.registration_snapshot(event.event_type)
        admitted = False
        for listener in listeners:
            try:
                filtered = listener.filter_event(event)
            except Exception as error:  # noqa: BLE001 - isolate consumer code
                self._report_listener_error(listener, error)
                continue
            if not filtered:
                with self._lock:
                    active = listener.active
                try:
                    self._ledfx.loop.call_soon_threadsafe(self._invoke, listener, event)
                    admitted = admitted or active
                except Exception as error:  # noqa: BLE001 - isolate scheduling failures
                    self._report_listener_error(listener, error)
        return admitted

    def _invoke(self, listener: EventListener, event: Event) -> None:
        with self._lock:
            if not listener.active:
                return
            # This is the invocation claim: a callback claimed here may finish
            # after disposal. No user code runs while holding the bus mutex.
        try:
            result = listener.callback(event)
            _reject_awaitable(result)
        except Exception as error:  # noqa: BLE001 - isolate consumer code
            self._report_listener_error(listener, error)

    def _report_listener_error(self, listener: EventListener, exc: Exception) -> None:
        self._report_error(listener.event_type, exc)

    def _report_error(self, event_type: str, exc: Exception) -> None:
        category = type(exc).__name__
        now = time.monotonic()
        with self._lock:
            last_report, suppressed = self._listener_errors.get(
                category, (-math.inf, 0)
            )
            count = suppressed + 1
            if now - last_report < 1.0:
                self._listener_errors[category] = (last_report, count)
                return
            self._listener_errors[category] = (now, 0)
        # Exception strings and tracebacks can contain whole pixel payloads.
        _LOGGER.warning(
            "Event listener failure for %s (%s; %d errors since last report)",
            event_type,
            category,
            count,
        )

    def add_listener(
        self,
        callback: Callable[[Event], None],
        event_type: str,
        event_filter: Mapping[str, object] | None = None,
    ) -> Callable[[], None]:
        listener = EventListener(callback, event_filter, event_type=event_type)
        with self._lock:
            self._generation += 1
            listener.generation = self._generation
            self._listeners[event_type] = self._listeners.get(event_type, ()) + (
                listener,
            )
            revision = self._revisions.get(event_type, 0) + 1
            self._revisions[event_type] = revision
            observers = self._registration_observers
        self._notify_registration_observers(observers, event_type, revision)

        def remove_listener() -> None:
            self._remove_listener(event_type, listener)

        return remove_listener

    def _prune_telemetry(self, event_type: str) -> None:
        if event_type not in (
            Event.GRAPH_UPDATE,
            Event.VIRTUAL_DIAG,
            Event.GENERAL_DIAG,
        ):
            return
        with self._telemetry_lock:
            field = "graph_id" if event_type == Event.GRAPH_UPDATE else "virtual_id"
            for pending in (self._latest, self._draining_latest):
                for key in tuple(pending):
                    if key[0] == event_type and not self.may_have_listeners(
                        event_type, {"event_type": event_type, field: key[1]}
                    ):
                        del pending[key]
            if event_type == Event.GENERAL_DIAG and not self.has_listeners(event_type):
                self._text_queue.clear()
                self._draining_text.clear()

    def _remove_listener(self, event_type: str, listener: EventListener) -> None:
        with self._lock:
            if not listener.revoke():
                return
            remaining = tuple(
                item
                for item in self._listeners.get(event_type, ())
                if item is not listener
            )
            if remaining:
                self._listeners[event_type] = remaining
            else:
                self._listeners.pop(event_type, None)
            revision = self._revisions.get(event_type, 0) + 1
            self._revisions[event_type] = revision
            observers = self._registration_observers
        self._prune_telemetry(event_type)
        self._notify_registration_observers(observers, event_type, revision)

    def add_registration_observer(
        self, callback: Callable[[str, int], None]
    ) -> Callable[[], None]:
        _validate_callback(callback)
        observer = _RegistrationObserver(callback)
        with self._lock:
            self._registration_observers += (observer,)

        def remove_observer() -> None:
            with self._lock:
                if not observer.revoke():
                    return
                self._registration_observers = tuple(
                    item
                    for item in self._registration_observers
                    if item is not observer
                )

        return remove_observer

    def _notify_registration_observers(
        self,
        observers: tuple[_RegistrationObserver, ...],
        event_type: str,
        revision: int,
    ) -> None:
        for observer in observers:
            self._ledfx.loop.call_soon_threadsafe(
                self._invoke_registration_observer, observer, event_type, revision
            )

    def _invoke_registration_observer(
        self, observer: _RegistrationObserver, event_type: str, revision: int
    ) -> None:
        with self._lock:
            if not observer.active:
                return
            # Observer disposal has the same invocation claim as event disposal.
        try:
            result = observer.callback(event_type, revision)
            _reject_awaitable(result)
        except Exception as error:  # noqa: BLE001 - isolate consumer code
            self._report_error(event_type, error)
