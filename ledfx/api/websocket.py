import asyncio
import binascii
import json
import logging
import struct
import time
import uuid
from concurrent import futures
from typing import Any, ClassVar

import numpy as np
import pybase64
import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.dedupequeue import VisDeduplicateQ
from ledfx.events import (
    ClientBroadcastEvent,
    ClientConnectedEvent,
    ClientDisconnectedEvent,
    ClientsUpdatedEvent,
    Event,
    SongDetectedEvent,
)
from ledfx.utils import empty_queue

_LOGGER = logging.getLogger(__name__)
MAX_PENDING_MESSAGES = 256
MAX_VAL = 32767

# Phase 2: Client metadata constants
VALID_CLIENT_TYPES = [
    "controller",
    "visualiser",
    "mobile",
    "display",
    "api",
    "unknown",
]

# Phase 3: Broadcasting constants
BROADCAST_TYPES = [
    "visualiser_control",
    "scene_sync",
    "color_palette",
    "custom",
]
TARGET_MODES = ["all", "type", "names", "uuids"]
MAX_PAYLOAD_SIZE = 2048

BASE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.Coerce(int),
        vol.Required("type"): str,
    },
    extra=vol.ALLOW_EXTRA,
)

# Phase 3: Broadcast message schema
BROADCAST_SCHEMA = vol.Schema(
    {
        vol.Required("broadcast_type"): vol.In(BROADCAST_TYPES),
        vol.Required("target"): vol.Schema(
            {
                vol.Required("mode"): vol.In(TARGET_MODES),
                vol.Optional("value"): str,  # For mode="type"
                vol.Optional("names"): [
                    vol.All(str, vol.Length(min=1))
                ],  # For mode="names"
                vol.Optional("uuids"): [
                    vol.All(str, vol.Length(min=1))
                ],  # For mode="uuids"
            },
            extra=vol.PREVENT_EXTRA,
        ),
        vol.Required("payload"): dict,
    },
    extra=vol.PREVENT_EXTRA,
)
# Not all events are able to be subscribed to by the websocket
# This dict show the events that are not subscribable and what event should be used instead
NON_SUBSCRIBABLE_EVENTS = {
    "device_update": "Use visualisation_update instead",
}

# TODO: Have a more well defined registration and a more componetized solution.
# Could do something like have Device actually provide the handler for Device
# related functionality. This would allow easy access to internal workings and
# events.
websocket_handlers = {}


def websocket_handler(type):
    def function(func):
        websocket_handlers[type] = func
        return func

    return function


WEB_AUDIO_CLIENTS = set()
ACTIVE_AUDIO_STREAM = None


class WebsocketEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/websocket"

    async def get(self, request) -> web.Response:
        try:
            return await WebsocketConnection(self._ledfx).handle(request)
        except ConnectionResetError:
            _LOGGER.debug("Connection Reset Error on Websocket Connection.")
            return await self.internal_error("Connection Reset Error.")


class WebsocketConnection:
    ip_uid_map = {}
    map_lock = asyncio.Lock()
    # Phase 1: Class-level metadata storage
    client_metadata: ClassVar[dict[str, dict[str, Any]]] = (
        {}
    )  # UUID -> metadata dict
    metadata_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._socket = None
        self._listeners = {}
        self._receiver_task = None
        self._sender_task = None
        self._sender_queue = VisDeduplicateQ(maxsize=MAX_PENDING_MESSAGES)
        self.client_ip = None
        self.uid = None
        # Phase 1: Instance attributes for client metadata
        self.device_id = None
        self.client_name = None
        self.client_type = "unknown"
        self.connected_at = None  # Set in handle() method

    def close(self):
        """
        Closes the websocket connection.

        This method cancels the receiver and sender tasks, if they exist, to close the websocket connection.
        """
        if self._receiver_task:
            self._receiver_task.cancel()
        if self._sender_task:
            self._sender_task.cancel()

    def clear_subscriptions(self):
        """
        Clears all the subscriptions by calling the registered listener functions.
        """
        for func in self._listeners.values():
            func()

    @classmethod
    async def get_all_clients(cls):
        async with cls.map_lock:
            return cls.ip_uid_map.copy()

    def send(self, message):
        """Sends a message to the websocket connection

        Args:
            message (str): The message to be sent
        """

        # If the queue is full, dump it and start again
        if self._sender_queue.qsize() == MAX_PENDING_MESSAGES:
            empty_queue(self._sender_queue)

        try:
            self._sender_queue.put_nowait(message)
        except asyncio.QueueFull:
            _LOGGER.error(
                f"Client sender queue size exceeded {MAX_PENDING_MESSAGES}"
            )
            self.close()

    def send_error(self, id, message):
        """Sends an error string to the websocket connection.

        Args:
            id (int): The ID of the error message.
            message (str): The error message to be sent.


        """

        return self.send(
            {
                "id": id,
                "success": False,
                "error": {"message": message},
            }
        )

    def send_event(self, id, event):
        """
        Sends an event notification to the websocket connection.

        Args:
            id (str): The ID of the event.
            event (Event): The event object to be sent.

        """

        return self.send({"id": id, "type": "event", **event.to_dict()})

    async def _sender(self):
        """
        Async write loop to pull from the queue and send

        This method is an asynchronous write loop that pulls messages from the sender queue and sends them over the websocket connection.
        It continuously checks for new messages in the queue until the websocket connection is closed.
        If there is an error serializing the message to JSON, it logs an error message.
        If the websocket connection is closed by the client, it logs a message and breaks the loop.
        """
        _LOGGER.info("Starting websocket sender")
        while not self._socket.closed:
            message = await self._sender_queue.get()
            try:
                # _LOGGER.debug("Sending websocket message")
                await self._socket.send_json(message, dumps=json.dumps)
            except TypeError as err:
                _LOGGER.error(
                    "Unable to serialize to JSON: %s\n%s",
                    err,
                    message,
                )
            except ConnectionResetError:
                _LOGGER.info("Websocket connection closed by the client.")
                break

        _LOGGER.info("Stopped websocket sender.")

    async def handle(self, request):
        """Handle the websocket connection"""

        self.client_ip = request.remote
        self.connected_at = time.time()

        async with WebsocketConnection.map_lock:
            self.uid = str(uuid.uuid4())
            WebsocketConnection.ip_uid_map[self.uid] = self.client_ip

        socket = self._socket = web.WebSocketResponse(
            protocols=("http", "https", "ws", "wss")
        )

        # print(request.protocol)
        # print(socket._protocols)
        # headers = request.headers
        # from aiohttp import hdrs
        # protocol = None
        # print(headers)
        # print("SEC_WEBSOCKET_PROTOCOL", hdrs.SEC_WEBSOCKET_PROTOCOL)
        # print(hdrs.SEC_WEBSOCKET_PROTOCOL in headers)
        # if hdrs.SEC_WEBSOCKET_PROTOCOL in headers:
        #     req_protocols = [
        #         str(proto.strip())
        #         for proto in headers[hdrs.SEC_WEBSOCKET_PROTOCOL].split(",")
        #     ]
        #     print("req",req_protocols)
        #     for proto in req_protocols:
        #         if proto in socket._protocols:
        #             protocol = proto
        #             break
        #     else:
        #         # No overlap found: Return no protocol as per spec
        #         _LOGGER.warning(
        #             "Client protocols %r don’t overlap server-known ones %r",
        #             req_protocols,
        #             socket._protocols,
        #         )
        # print(protocol)
        # print(socket.can_prepare(request))
        # print(socket._protocols)
        # print(socket.ws_protocol)

        await socket.prepare(request)

        _LOGGER.info("Websocket connected.")

        # Send UID to the client
        await self._socket.send_json(
            {"event_type": "client_id", "client_id": self.uid}
        )

        self._receiver_task = asyncio.current_task(loop=self._ledfx.loop)
        self._sender_task = self._ledfx.loop.create_task(self._sender())

        self._ledfx.events.fire_event(
            ClientConnectedEvent(self.uid, self.client_ip)
        )

        def shutdown_handler(e):
            self.close()

        remove_listeners = self._ledfx.events.add_listener(
            shutdown_handler, Event.LEDFX_SHUTDOWN
        )

        try:
            message = await socket.receive_json()
            while message:
                message = BASE_MESSAGE_SCHEMA(message)

                if message["type"] in websocket_handlers:
                    # Phase 1: Support async handlers
                    handler = websocket_handlers[message["type"]]
                    if asyncio.iscoroutinefunction(handler):
                        await handler(self, message)
                    else:
                        handler(self, message)
                else:
                    _LOGGER.error(
                        f"Received unknown command {message['type']}"
                    )
                    self.send_error(message["id"], "Unknown command type.")

                message = await socket.receive_json()

        except (vol.Invalid, ValueError):
            _LOGGER.info("Invalid message format.")
            self.send_error(message["id"], "Invalid message format.")

        except TypeError as e:
            if socket.closed:
                _LOGGER.info("Connection closed by client.")
            else:
                _LOGGER.exception(f"Unexpected TypeError: {e}")

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:
            async with WebsocketConnection.map_lock:
                if self.uid in WebsocketConnection.ip_uid_map:
                    del WebsocketConnection.ip_uid_map[self.uid]
            # Phase 1: Clean up client metadata on disconnect
            async with WebsocketConnection.metadata_lock:
                if self.uid in WebsocketConnection.client_metadata:
                    del WebsocketConnection.client_metadata[self.uid]
            remove_listeners()
            self.clear_subscriptions()

            # Gracefully stop the sender ensuring all messages get flushed
            self.send(None)
            await self._sender_task

            # Close the connection
            await socket.close()
            _LOGGER.info("Closed connection")

            self._ledfx.events.fire_event(
                ClientDisconnectedEvent(self.uid, self.client_ip)
            )
            self._ledfx.events.fire_event(ClientsUpdatedEvent())

        return socket

    # Phase 1: Metadata utility methods
    async def _name_exists(self, name, exclude_uuid=None):
        """Check if a client name already exists (thread-safe)"""
        async with WebsocketConnection.metadata_lock:
            for (
                client_uuid,
                meta,
            ) in WebsocketConnection.client_metadata.items():
                if client_uuid != exclude_uuid and meta.get("name") == name:
                    return True
            return False

    async def _reserve_and_set_client_name(
        self, desired_name: str
    ) -> tuple[str, bool]:
        """Atomically check for name conflicts, resolve them, and persist metadata.

        This method acquires metadata_lock once and holds it throughout the entire
        operation to prevent TOCTOU race conditions where multiple clients could
        end up with the same name.

        Args:
            desired_name: The name the client wants to use

        Returns:
            Tuple of (resolved_name, name_conflict_flag)
            - resolved_name: The actual name assigned (may have " (N)" suffix)
            - name_conflict_flag: True if the name was modified due to conflict
        """
        async with WebsocketConnection.metadata_lock:
            # Check uniqueness and resolve conflicts while holding lock
            original_name = desired_name
            resolved_name = desired_name
            counter = 1
            name_conflict = False

            while True:
                # Check if name exists (exclude self)
                name_taken = False
                for (
                    client_uuid,
                    meta,
                ) in WebsocketConnection.client_metadata.items():
                    if (
                        client_uuid != self.uid
                        and meta.get("name") == resolved_name
                    ):
                        name_taken = True
                        break

                if not name_taken:
                    break

                # Name conflict - increment counter
                name_conflict = True
                counter += 1
                resolved_name = f"{original_name} ({counter})"

            # Update instance attribute
            self.client_name = resolved_name

            # Persist metadata (still holding lock)
            WebsocketConnection.client_metadata[self.uid] = {
                "ip": self.client_ip,
                "name": self.client_name,
                "type": self.client_type,
                "device_id": self.device_id,
                "connected_at": self.connected_at,
            }

            return resolved_name, name_conflict

    async def _update_metadata(self):
        """Update class-level metadata storage (thread-safe)"""
        async with WebsocketConnection.metadata_lock:
            WebsocketConnection.client_metadata[self.uid] = {
                "ip": self.client_ip,
                "name": self.client_name,
                "type": self.client_type,
                "device_id": self.device_id,
                "connected_at": self.connected_at,
            }

    @classmethod
    async def get_all_clients_metadata(cls):
        """Get deep copy of all client metadata (thread-safe)"""
        async with cls.metadata_lock:
            return {
                uuid: meta.copy() for uuid, meta in cls.client_metadata.items()
            }

    @websocket_handler("set_client_info")
    async def set_client_info_handler(self, message):
        """Handle client metadata initialization"""
        data = message.get("data", {})
        device_id = data.get("device_id")
        name = data.get("name")
        client_type = data.get("type", "unknown")

        # Validate client_type
        if client_type not in VALID_CLIENT_TYPES:
            _LOGGER.warning(
                f"Invalid client_type '{client_type}' from {self.uid}, defaulting to 'unknown'"
            )
            client_type = "unknown"

        # Generate default name if not provided
        if not name:
            name = f"Client-{self.uid[:8]}"

        # Store device_id and type before atomic name reservation
        self.device_id = device_id
        self.client_type = client_type

        # Atomically check, resolve conflicts, and persist metadata
        # This prevents TOCTOU race conditions
        resolved_name, name_conflict = await self._reserve_and_set_client_name(
            name
        )

        # Send confirmation (after atomic operation completes)
        self.send(
            {
                "id": message["id"],
                "event_type": "client_info_updated",
                "client_id": self.uid,
                "name": resolved_name,
                "type": self.client_type,
                "name_conflict": name_conflict,
            }
        )

        # Fire event (only after metadata is persisted)
        self._ledfx.events.fire_event(ClientsUpdatedEvent())
        _LOGGER.info(
            f"Client {self.uid} set info: name='{resolved_name}', type='{self.client_type}'"
        )

    @websocket_handler("update_client_info")
    async def update_client_info_handler(self, message):
        """Handle client metadata updates (name and type)"""
        data = message.get("data", {})
        name = data.get("name")
        client_type = data.get("type")

        # Validate and normalize type if provided
        if client_type is not None:
            if client_type not in VALID_CLIENT_TYPES:
                _LOGGER.warning(
                    f"Invalid client_type '{client_type}' from {self.uid}, defaulting to 'unknown'"
                )
                client_type = "unknown"

        # Check if any updates were provided
        if name is None and client_type is None:
            # No valid updates provided
            self.send_error(message["id"], "No valid updates provided")
            return

        # Atomically update name and/or type (prevents TOCTOU race)
        async with WebsocketConnection.metadata_lock:
            # Check if name is already taken by another client (if name update requested)
            if name is not None:
                for (
                    client_uuid,
                    meta,
                ) in WebsocketConnection.client_metadata.items():
                    if client_uuid != self.uid and meta.get("name") == name:
                        self.send_error(
                            message["id"],
                            f"Name '{name}' is already taken by another client",
                        )
                        return

                # Name is available - update instance attribute
                self.client_name = name

            # Update type if provided
            if client_type is not None:
                self.client_type = client_type

            # Persist metadata (still holding lock)
            WebsocketConnection.client_metadata[self.uid] = {
                "ip": self.client_ip,
                "name": self.client_name,
                "type": self.client_type,
                "device_id": self.device_id,
                "connected_at": self.connected_at,
            }

        # Send confirmation (after atomic operation completes)
        self.send(
            {
                "id": message["id"],
                "event_type": "client_info_updated",
                "client_id": self.uid,
                "name": self.client_name,
                "type": self.client_type,
            }
        )

        # Fire event
        self._ledfx.events.fire_event(ClientsUpdatedEvent())

        # Log what was updated
        updates = []
        if name is not None:
            updates.append(f"name='{self.client_name}'")
        if client_type is not None:
            updates.append(f"type='{self.client_type}'")
        _LOGGER.info(f"Client {self.uid} updated: {', '.join(updates)}")

    # Phase 3: Broadcasting methods
    def _filter_targets(
        self, target_config: dict, clients: dict, sender_uuid: str
    ) -> list[str]:
        """Filter clients based on target configuration (fail-closed validation).

        Args:
            target_config: Targeting specification with mode and parameters
            clients: Dictionary of connected clients {uuid: metadata}
            sender_uuid: UUID of sender (excluded from mode='all' to prevent self-echo)

        Returns:
            List of target client UUIDs (sender excluded from mode='all')
        """
        mode = target_config.get("mode")

        if mode == "all":
            # Exclude sender to prevent self-echo
            return [uuid for uuid in clients.keys() if uuid != sender_uuid]

        elif mode == "type":
            value = target_config.get("value")
            if not value:
                _LOGGER.warning("Target mode 'type' requires 'value' field")
                return []
            return [
                client_uuid
                for client_uuid, meta in clients.items()
                if meta.get("type") == value
            ]

        elif mode == "names":
            names = target_config.get("names")
            if not names or not isinstance(names, list):
                _LOGGER.warning("Target mode 'names' requires 'names' list")
                return []
            return [
                client_uuid
                for client_uuid, meta in clients.items()
                if meta.get("name") in names
            ]

        elif mode == "uuids":
            uuids = target_config.get("uuids")
            if not uuids or not isinstance(uuids, list):
                _LOGGER.warning("Target mode 'uuids' requires 'uuids' list")
                return []
            # Only return UUIDs that exist in connected clients
            return [
                client_uuid for client_uuid in uuids if client_uuid in clients
            ]

        else:
            _LOGGER.warning(f"Invalid target mode: {mode}")
            return []

    @websocket_handler("broadcast")
    async def broadcast_handler(self, message):
        """Handle client-to-client broadcast messages (WebSocket-only)"""
        try:
            data = message.get("data", {})
            # Validate against schema
            validated_data = BROADCAST_SCHEMA(data)
        except vol.Invalid as e:
            self.send_error(message["id"], f"Invalid broadcast data: {e}")
            return

        # Validate payload size
        payload = validated_data["payload"]
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        payload_size = len(payload_bytes)
        if payload_size > MAX_PAYLOAD_SIZE:
            self.send_error(
                message["id"],
                f"Payload size ({payload_size} bytes) exceeds maximum ({MAX_PAYLOAD_SIZE} bytes)",
            )
            return

        # Get all client metadata
        clients = await WebsocketConnection.get_all_clients_metadata()

        # Derive sender identity from WebSocket connection (server-side)
        sender_uuid = self.uid
        sender_name = self.client_name or f"Client-{sender_uuid[:8]}"
        sender_type = self.client_type

        # Filter targets based on target configuration
        target_config = validated_data["target"]
        target_uuids = self._filter_targets(
            target_config, clients, sender_uuid
        )

        # Reject if no targets matched
        if not target_uuids:
            self.send_error(
                message["id"],
                f"No clients matched target specification: {target_config}",
            )
            return

        # Generate unique broadcast ID
        broadcast_id = f"b-{uuid.uuid4()}"

        # Fire broadcast event (subscribers will receive it)
        self._ledfx.events.fire_event(
            ClientBroadcastEvent(
                broadcast_type=validated_data["broadcast_type"],
                broadcast_id=broadcast_id,
                sender_uuid=sender_uuid,
                sender_name=sender_name,
                sender_type=sender_type,
                target_uuids=target_uuids,
                payload=payload,
            )
        )

        # Log broadcast for audit
        _LOGGER.info(
            f"Broadcast {broadcast_id}: type={validated_data['broadcast_type']}, "
            f"sender={sender_name} ({sender_uuid[:8]}), "
            f"targets={len(target_uuids)} clients"
        )

        # Send success response
        self.send(
            {
                "id": message["id"],
                "event_type": "broadcast_sent",
                "broadcast_id": broadcast_id,
                "targets_matched": len(target_uuids),
                "target_uuids": target_uuids,
            }
        )

    @websocket_handler("subscribe_event")
    def subscribe_event_handler(self, message):
        def notify_websocket(event):
            self.send_event(message["id"], event)

        # Some events are not subscribable - send an error message if the user tries to subscribe to one with a hint on what to use instead
        if message.get("event_type") in NON_SUBSCRIBABLE_EVENTS.keys():
            msg = f"Websocket cannot subscribe to {message.get('event_type')} events - use {NON_SUBSCRIBABLE_EVENTS[message.get('event_type')]} instead"
            _LOGGER.warning(f"{msg}.")
            self.send_error(message["id"], msg)
            return

        _LOGGER.debug(f"  sub Q: {hex(id(self))} {str(message)[:80]}")
        _LOGGER.debug(
            f"Websocket subscribing to event {message.get('event_type')} with filter {message.get('event_filter')}"
        )
        self._listeners[message["id"]] = self._ledfx.events.add_listener(
            notify_websocket,
            message.get("event_type"),
            message.get("event_filter", {}),
        )

    @websocket_handler("unsubscribe_event")
    def unsubscribe_event_handler(self, message):
        _LOGGER.debug(f"unsub Q: {hex(id(self))} {str(message)[:80]}")
        subscription_id = message["id"]

        _LOGGER.debug(f"Websocket unsubscribing event id {subscription_id}")
        if subscription_id in self._listeners:
            self._listeners.pop(subscription_id)()
        else:
            _LOGGER.warning(
                f"Unsubscibe unknown subscription ID {subscription_id}"
            )

    @websocket_handler("audio_stream_start")
    def audio_stream_start_handler(self, message):
        client = message.get("client")

        if client in WEB_AUDIO_CLIENTS:
            _LOGGER.warning(f"Web audio client {client} already exists")
            return

        _LOGGER.info(f"Web audio stream opened by client {client}")
        WEB_AUDIO_CLIENTS.add(client)

    @websocket_handler("audio_stream_stop")
    def audio_stream_stop_handler(self, message):
        client = message.get("client")
        _LOGGER.info(f"Web audio stream closed by client {client}")
        WEB_AUDIO_CLIENTS.discard(client)

    @websocket_handler("audio_stream_config")
    def audio_stream_config_handler(self, message):
        _LOGGER.info(
            f"WebAudioConfig from {message.get('client')}: {message.get('data')}"
        )

    @websocket_handler("audio_stream_data")
    def audio_stream_data_handler(self, message):
        # _LOGGER.info(
        #     "Websocket: {} incoming from {} with type {}".format(
        #         message.get("event_type"),
        #         message.get("client"),
        #         type(message.get("data")),
        #     )
        # )

        if not ACTIVE_AUDIO_STREAM:
            return

        client = message.get("client")

        if ACTIVE_AUDIO_STREAM.client != client:
            return
        ACTIVE_AUDIO_STREAM.data = np.fromiter(
            message.get("data").values(), dtype=np.float32
        )

    @websocket_handler("audio_stream_data_v2")
    def audio_stream_data_base64_handler(self, message):
        # Max value for signed 16-bit values.
        if not ACTIVE_AUDIO_STREAM:
            return

        client = message.get("client")

        if ACTIVE_AUDIO_STREAM.client != client:
            return
        try:
            decoded = pybase64.b64decode(message.get("data"))
        except binascii.Error:
            _LOGGER.info("Incorrect base64 padding.")
        except Exception as err:
            _LOGGER.exception(
                "Unexpected Exception in base64 decoding: %s", err
            )
        else:
            fmt = "<%dh" % (len(decoded) // 2)
            data = list(struct.unpack(fmt, decoded))
            # Minimum value is -32768 for signed, so that's why if the number is negative,
            # it is divided by 32768 when converting to float.
            data = np.array(
                [d / MAX_VAL if d >= 0 else d / (MAX_VAL + 1) for d in data],
                dtype=np.float32,
            )
            ACTIVE_AUDIO_STREAM.data = data

    @websocket_handler("song_info")
    def song_info_handler(self, message):
        """
        Handle incoming song/media info and broadcast to all subscribed clients.

        Expected message format:
        {
            "id": int,
            "type": "song_info",
            "title": str,
            "artist": str,
            "album": str (optional),
            "thumbnail": str (optional),
            "position": float (optional),
            "duration": float (optional),
            "playing": bool (optional),
            "timestamp": float (optional)
        }
        """
        _LOGGER.info(
            f"Received song info: {message.get('artist')} - {message.get('title')}"
        )

        # Fire the event which will be broadcast to all subscribed clients
        self._ledfx.events.fire_event(
            SongDetectedEvent(
                title=message.get("title", "Unknown"),
                artist=message.get("artist", "Unknown"),
                album=message.get("album", ""),
                thumbnail=message.get("thumbnail"),
                position=message.get("position"),
                duration=message.get("duration"),
                playing=message.get("playing", False),
                timestamp=message.get("timestamp"),
            )
        )


class WebAudioStream:
    def __init__(self, client: str, callback: callable):
        self.client = client
        self.callback = callback
        self._data = None
        self._active = False

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    def close(self):
        self._active = False

    @property
    def data(self, x):
        return self._data

    @data.setter
    def data(self, x):
        self._data = x
        if self._active:
            try:
                self.callback(self._data, None, None, None)
            except Exception as e:
                _LOGGER.error(e)
