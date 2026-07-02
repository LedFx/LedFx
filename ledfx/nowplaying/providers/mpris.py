"""MPRIS (Media Player Remote Interfacing Specification) Now Playing provider.

Linux-only. Connects to the D-Bus session bus, discovers running MPRIS players,
and tracks the best active player for metadata subscription.
"""

import asyncio
import logging
import sys

try:
    from dbus_fast import MessageType
    from dbus_fast.aio import MessageBus
    from dbus_fast.message import Message
except (
    ImportError
):  # pragma: no cover - exercised on non-linux/no-dbus-fast envs
    MessageType = None
    MessageBus = None
    Message = None

from ledfx.nowplaying.models import TrackMetadata

_LOGGER = logging.getLogger(__name__)

SOURCE_ID = "mpris"
_DBUS_DEST = "org.freedesktop.DBus"
_DBUS_PATH = "/org/freedesktop/DBus"
_DBUS_IFACE = "org.freedesktop.DBus"
_PROPS_IFACE = "org.freedesktop.DBus.Properties"
_MPRIS_PREFIX = "org.mpris.MediaPlayer2."
_MPRIS_PATH = "/org/mpris/MediaPlayer2"
_MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
_PLAYBACK_STATUS_RANK = {
    "Playing": 3,
    "Paused": 2,
    "Stopped": 1,
}


class MPRISNowPlayingProvider:
    """Linux MPRIS Now Playing provider."""

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._loop = None
        self._bus = None
        self._init_task = None
        self._select_task = None
        self._push_task = None
        self._select_lock = asyncio.Lock()
        self._name_owner_handler = None
        self._properties_handler = None
        self._active_player_name = None
        self._active_player_owner = None
        self._known_players = set()

    def start(self):
        """Start provider initialization on Linux."""
        if sys.platform != "linux":
            return
        if self._init_task is not None:
            return

        self._loop = asyncio.get_running_loop()
        self._init_task = asyncio.ensure_future(self._initialize())

    def stop(self):
        """Stop provider and disconnect from D-Bus if connected."""
        if self._select_task is not None:
            self._select_task.cancel()
            self._select_task = None

        if self._push_task is not None:
            self._push_task.cancel()
            self._push_task = None

        if self._init_task is not None:
            self._init_task.cancel()
            self._init_task = None

        if self._bus is not None and self._name_owner_handler is not None:
            try:
                self._bus.remove_message_handler(self._name_owner_handler)
            except Exception:
                pass
        if self._bus is not None and self._properties_handler is not None:
            try:
                self._bus.remove_message_handler(self._properties_handler)
            except Exception:
                pass
        self._name_owner_handler = None
        self._properties_handler = None

        self._known_players = set()
        self._active_player_name = None
        self._active_player_owner = None

        if self._bus is not None:
            try:
                self._bus.disconnect()
            except Exception as exc:
                _LOGGER.debug("MPRIS: error while disconnecting bus: %s", exc)
            self._bus = None

    def clear(self):
        """Explicitly reset provider state and notify the service."""
        self._active_player_name = None
        self._active_player_owner = None
        self._known_players = set()
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)

    async def _initialize(self):
        """Connect to session D-Bus and set up player discovery hooks."""
        if MessageBus is None:
            _LOGGER.debug("MPRIS: dbus-fast not installed; provider disabled")
            return

        try:
            self._bus = await MessageBus().connect()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "MPRIS: failed to connect to session D-Bus: %s", exc
            )
            return

        _LOGGER.info("MPRIS: connected to session D-Bus")

        await self._install_name_owner_subscription()
        await self._install_properties_subscription()
        await self._select_best_player()

    async def _install_name_owner_subscription(self):
        """Subscribe to DBus NameOwnerChanged and attach message handler."""
        if self._bus is None:
            return

        rule = (
            "type='signal',"
            f"sender='{_DBUS_DEST}',"
            f"interface='{_DBUS_IFACE}',"
            "member='NameOwnerChanged'"
        )

        _reply = await self._call_method(
            destination=_DBUS_DEST,
            path=_DBUS_PATH,
            interface=_DBUS_IFACE,
            member="AddMatch",
            signature="s",
            body=[rule],
        )

        if _reply is None:
            _LOGGER.warning(
                "MPRIS: failed to register DBus NameOwnerChanged match rule: %s",
                rule,
            )
            return

        def _on_message(message):
            if (
                message.message_type != MessageType.SIGNAL
                or message.interface != _DBUS_IFACE
                or message.member != "NameOwnerChanged"
                or message.path != _DBUS_PATH
            ):
                return

            if not message.body or len(message.body) != 3:
                return

            name = message.body[0]
            if not isinstance(name, str) or not name.startswith(_MPRIS_PREFIX):
                return

            self._schedule_select_best_player()

        self._name_owner_handler = _on_message
        self._bus.add_message_handler(self._name_owner_handler)

    def _schedule_select_best_player(self):
        if self._loop is None:
            return

        if self._select_task is not None and not self._select_task.done():
            return

        self._select_task = asyncio.ensure_future(self._select_best_player())

    async def _install_properties_subscription(self):
        """Subscribe to MPRIS PropertiesChanged events."""
        if self._bus is None:
            return

        rule = (
            "type='signal',"
            f"interface='{_PROPS_IFACE}',"
            "member='PropertiesChanged',"
            f"path='{_MPRIS_PATH}'"
        )

        _reply = await self._call_method(
            destination=_DBUS_DEST,
            path=_DBUS_PATH,
            interface=_DBUS_IFACE,
            member="AddMatch",
            signature="s",
            body=[rule],
        )

        if _reply is None:
            _LOGGER.warning(
                "MPRIS: failed to register DBus PropertiesChanged match rule: %s",
                rule,
            )
            return

        def _on_message(message):
            if (
                message.message_type != MessageType.SIGNAL
                or message.interface != _PROPS_IFACE
                or message.member != "PropertiesChanged"
                or message.path != _MPRIS_PATH
            ):
                return

            if self._active_player_owner is None:
                return

            # Signals are emitted by the unique-name owner (e.g. :1.42).
            if message.sender != self._active_player_owner:
                return

            if not message.body or len(message.body) < 1:
                return

            iface_name = message.body[0]
            if iface_name != _MPRIS_PLAYER_IFACE:
                return

            self._schedule_push_metadata()

        self._properties_handler = _on_message
        self._bus.add_message_handler(self._properties_handler)

    def _schedule_push_metadata(self):
        if self._loop is None:
            return

        if self._push_task is not None and not self._push_task.done():
            return

        self._push_task = asyncio.ensure_future(self._push_metadata())

    async def _select_best_player(self):
        """Discover MPRIS players and select the highest-priority one."""
        async with self._select_lock:
            names = await self._list_mpris_players()
            self._known_players = set(names)

            if not names:
                if self._active_player_name is not None:
                    _LOGGER.info(
                        "MPRIS: no players found; clearing active source"
                    )
                    self._active_player_name = None
                    self.clear()
                return

            ranked = []
            for name in names:
                status = await self._get_playback_status(name)
                rank = _PLAYBACK_STATUS_RANK.get(status, 0)
                ranked.append((rank, name, status))

            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            _rank, best_name, best_status = ranked[0]

            if best_name != self._active_player_name:
                prev = self._active_player_name or "none"
                _LOGGER.info(
                    "MPRIS active player changed: %s -> %s (%s)",
                    prev,
                    best_name,
                    best_status or "unknown",
                )
                self._active_player_name = best_name
                self._active_player_owner = await self._get_name_owner(
                    best_name
                )
                self._schedule_push_metadata()
            elif self._active_player_owner is None:
                self._active_player_owner = await self._get_name_owner(
                    best_name
                )
                self._schedule_push_metadata()

    async def _list_mpris_players(self):
        """Return all running bus names that implement MPRIS."""
        reply = await self._call_method(
            destination=_DBUS_DEST,
            path=_DBUS_PATH,
            interface=_DBUS_IFACE,
            member="ListNames",
        )
        if reply is None or not reply.body:
            return []

        names = reply.body[0]
        if not isinstance(names, list):
            return []

        return [
            name
            for name in names
            if isinstance(name, str) and name.startswith(_MPRIS_PREFIX)
        ]

    async def _get_playback_status(self, player_bus_name):
        """Read PlaybackStatus from a single MPRIS player."""
        reply = await self._call_method(
            destination=player_bus_name,
            path=_MPRIS_PATH,
            interface=_PROPS_IFACE,
            member="Get",
            signature="ss",
            body=[_MPRIS_PLAYER_IFACE, "PlaybackStatus"],
        )
        if reply is None or not reply.body:
            return None

        variant = reply.body[0]
        return getattr(variant, "value", None)

    async def _get_name_owner(self, bus_name):
        """Resolve a well-known bus name to its unique owner name."""
        reply = await self._call_method(
            destination=_DBUS_DEST,
            path=_DBUS_PATH,
            interface=_DBUS_IFACE,
            member="GetNameOwner",
            signature="s",
            body=[bus_name],
        )
        if reply is None or not reply.body:
            return None

        owner = reply.body[0]
        return owner if isinstance(owner, str) else None

    async def _push_metadata(self):
        """Fetch and forward active-player metadata to the service."""
        if self._active_player_name is None:
            return

        reply = await self._call_method(
            destination=self._active_player_name,
            path=_MPRIS_PATH,
            interface=_PROPS_IFACE,
            member="GetAll",
            signature="s",
            body=[_MPRIS_PLAYER_IFACE],
        )
        if reply is None or not reply.body:
            return

        props = reply.body[0]
        if not isinstance(props, dict):
            return

        status = self._variant_value(props.get("PlaybackStatus"))
        metadata = self._variant_value(props.get("Metadata")) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        title = self._as_text(self._variant_value(metadata.get("xesam:title")))

        artists = self._variant_value(metadata.get("xesam:artist"))
        artist = None
        if isinstance(artists, list) and artists:
            artist = self._as_text(artists[0])
        elif isinstance(artists, str):
            artist = self._as_text(artists)

        album = self._as_text(self._variant_value(metadata.get("xesam:album")))
        track_id_raw = self._variant_value(metadata.get("mpris:trackid"))
        track_id = self._as_text(track_id_raw)

        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is None:
            return

        # A stopped player with no content should clear active mpris state.
        if status == "Stopped" and not any((title, artist, album)):
            now_playing.clear(SOURCE_ID)
            return

        now_playing.set_metadata(
            SOURCE_ID,
            TrackMetadata(
                source_id=SOURCE_ID,
                title=title,
                artist=artist,
                album=album,
                track_id=track_id,
            ),
        )

    @staticmethod
    def _variant_value(value):
        """Return dbus-fast Variant.value if present, else the input value."""
        return getattr(value, "value", value)

    @staticmethod
    def _as_text(value):
        """Convert value to trimmed text or None."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    async def _call_method(
        self,
        destination,
        path,
        interface,
        member,
        signature="",
        body=None,
    ):
        """Issue a low-level D-Bus method call and return the reply message."""
        if self._bus is None:
            return None

        if Message is None:
            return None

        if body is None:
            body = []

        try:
            reply = await self._bus.call(
                Message(
                    destination=destination,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return None

        if reply.message_type == MessageType.ERROR:
            return None

        return reply
