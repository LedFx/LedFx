import asyncio
import binascii
import inspect
import json
import logging
import struct
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from concurrent import futures
from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, cast, get_args

import numpy as np
import pybase64
from aiohttp import WSMsgType, web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ledfx.api import RestEndpoint
from ledfx.api.jsonutil import default, dumps
from ledfx.configuration.fields import coerce
from ledfx.events import (
    ClientBroadcastEvent,
    ClientConnectedEvent,
    ClientDisconnectedEvent,
    ClientsUpdatedEvent,
    Event,
    EventListener,
    FrontendVisualiserDataEvent,
    SongDetectedEvent,
)

_LOGGER = logging.getLogger(__name__)
MAX_PENDING_MESSAGES = 256
MAX_LATEST_KEYS = 256
MAX_PENDING_TEXT = 100
MAX_CONTROL_BATCH = 32
FINAL_ERROR_REPLY_TIMEOUT = 1.0
MAX_VAL = 32767

# Phase 2: Client metadata constants
VALID_CLIENT_TYPES = [
    "controller",
    "visualiser",
    "mobile",
    "display",
    "api",
    "not-set",
    "unknown",
]

# Phase 3: Broadcasting constants and message models
BroadcastType = Literal["visualiser_control", "scene_sync", "color_palette", "custom"]
TargetMode = Literal["all", "type", "names", "uuids"]
BROADCAST_TYPES: list[str] = list(get_args(BroadcastType))
TARGET_MODES: list[str] = list(get_args(TargetMode))
MAX_PAYLOAD_SIZE = 2048
NonEmptyStr = Annotated[str, Field(min_length=1)]


class BaseMessage(BaseModel):
    """Every websocket message: an int id (coerced, as before) and a type."""

    model_config = ConfigDict(extra="allow")

    id: Annotated[int, coerce(int)]
    type: str


class BroadcastTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TargetMode
    value: str | None = None  # For mode="type"
    names: list[NonEmptyStr] | None = None  # For mode="names"
    uuids: list[NonEmptyStr] | None = None  # For mode="uuids"


class BroadcastData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    broadcast_type: BroadcastType
    target: BroadcastTarget
    payload: dict[str, object]


# Not all events are able to be subscribed to by the websocket
# This dict show the events that are not subscribable and what event should be used instead
NON_SUBSCRIBABLE_EVENTS = {
    "device_update": "visualisation_update",
    "virtual_update": "visualisation_update",
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


@dataclass(frozen=True)
class Delivery:
    message: dict[str, object]
    connection_generation: int
    subscription_id: int | None = None
    subscription_generation: int | None = None


@dataclass(frozen=True)
class Subscription:
    dispose: Callable[[], None]
    generation: int
    event_type: str


LatestKey = tuple[int, int, str, str, bool | None]


class WebsocketConnection:
    ip_uid_map: ClassVar[dict[str, str]] = {}
    map_lock = asyncio.Lock()
    # Phase 1: Class-level metadata storage
    client_metadata: ClassVar[
        dict[str, dict[str, object]]
    ] = {}  # UUID -> metadata dict
    metadata_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._socket = None
        self._listeners: dict[int, Subscription] = {}
        self._receiver_task = None
        self._sender_task: asyncio.Task[None] | None = None
        self._receiver_error_reply: dict[str, object] | None = None
        self._control_queue: deque[Delivery] = deque()
        self._latest_slots: OrderedDict[LatestKey, Delivery] = OrderedDict()
        self._text_queue: deque[Delivery] = deque()
        self._text_dropped = 0
        self._text_summary_ready = True
        self._text_summary: tuple[Delivery, int] | None = None
        self._controls_selected = 0
        self._prefer_text = False
        self._connection_generation = 0
        self._subscription_generation = 0
        self._closed = False
        self._closing = False
        self._close_task: asyncio.Task[None] | None = None
        self._has_work = asyncio.Event()
        self.client_ip = None
        self.uid = None
        # Phase 1: Instance attributes for client metadata
        self.device_id = None
        self.client_name = None
        self.client_type = "unknown"
        self.connected_at = None  # Set in handle() method

    def _clear_delivery(self) -> None:
        self._control_queue.clear()
        self._latest_slots.clear()
        self._text_queue.clear()
        self._text_summary = None
        self._text_dropped = 0
        self._text_summary_ready = True

    def _invalidate_connection(self) -> None:
        if not self._closing:
            self._closing = True
            self._connection_generation += 1
            self.clear_subscriptions()
            self._clear_delivery()
        self._has_work.set()

    def close(self) -> None:
        """Idempotent forced teardown, independent of queue capacity."""
        if self._closed:
            return
        self._closed = True
        self._invalidate_connection()
        current = asyncio.current_task(loop=self._ledfx.loop)
        for task in (self._receiver_task, self._sender_task):
            if task is not None and task is not current:
                task.cancel()

    def clear_subscriptions(self) -> None:
        for subscription_id in tuple(self._listeners):
            self._revoke_subscription(subscription_id)

    @classmethod
    async def get_all_clients(cls):
        async with cls.map_lock:
            return cls.ip_uid_map.copy()

    def _revoke_subscription(self, subscription_id: int) -> None:
        previous = self._listeners.pop(subscription_id, None)
        if previous is not None:
            previous.dispose()
        self._control_queue = deque(
            item
            for item in self._control_queue
            if item.subscription_id != subscription_id
        )
        for key in tuple(self._latest_slots):
            if key[0] == subscription_id:
                del self._latest_slots[key]
        self._text_queue = deque(
            item for item in self._text_queue if item.subscription_id != subscription_id
        )
        # Loss is connection-wide. A revoked summary must be rebuilt with a
        # current owner; only a successfully written summary resets its count.
        if (
            self._text_summary is not None
            and self._text_summary[0].subscription_id == subscription_id
        ):
            self._text_summary = None

    def _delivery_current(self, item: Delivery) -> bool:
        if self._closing or item.connection_generation != self._connection_generation:
            return False
        if item.subscription_id is None:
            return True
        owner = self._listeners.get(item.subscription_id)
        return owner is not None and owner.generation == item.subscription_generation

    def _send_installation_result(self, message: dict[str, object]) -> None:
        self.send(message)

    def _initiate_close(self, code: int, reason: str) -> None:
        """Reject admission and revoke ownership before scheduling one close."""
        if self._closing:
            return
        self._invalidate_connection()
        # A terminal-error grace must be interruptible even if socket.close
        # stalls. Ordinary already-started writes may finish while closing.
        if self._receiver_error_reply is not None and self._sender_task is not None:
            self._sender_task.cancel()
        self._close_task = self._ledfx.loop.create_task(
            self._close_socket(code, reason)
        )
        self._close_task.add_done_callback(self._observe_close)

    async def _close_socket(self, code: int, reason: str) -> None:
        try:
            if self._socket is not None:
                await self._socket.close(code=code, message=reason.encode())
        finally:
            self.close()

    def _observe_close(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (error := task.exception()) is not None:
            _LOGGER.error("Unable to close websocket after backlog failure: %s", error)

    def _admit_control(self, item: Delivery) -> None:
        if not self._delivery_current(item):
            return
        if len(self._control_queue) >= MAX_PENDING_MESSAGES:
            self._initiate_close(1013, "control backlog; reconnect and resync")
            return
        self._control_queue.append(item)
        self._has_work.set()

    def send(self, message: dict[str, object]) -> None:
        """Admit connection-owned protocol controls in FIFO order."""
        self._admit_control(Delivery(message, self._connection_generation))

    def send_error(self, id: object, message: str) -> None:
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

    def send_event(
        self, id: int, event: Event, subscription_generation: int | None = None
    ) -> None:
        owner = self._listeners.get(id)
        if owner is None:
            return
        generation = (
            owner.generation
            if subscription_generation is None
            else subscription_generation
        )
        item = Delivery(
            {"id": id, "type": "event", **event.to_dict()},
            self._connection_generation,
            id,
            generation,
        )
        if not self._delivery_current(item):
            return
        category = event.event_type
        if category in (
            Event.VISUALISATION_UPDATE,
            Event.GRAPH_UPDATE,
            Event.VIRTUAL_DIAG,
        ):
            field = {
                Event.VISUALISATION_UPDATE: "vis_id",
                Event.GRAPH_UPDATE: "graph_id",
                Event.VIRTUAL_DIAG: "virtual_id",
            }[category]
            entity = item.message.get(field)
            kind = (
                item.message.get("is_device")
                if category == Event.VISUALISATION_UPDATE
                else None
            )
            # Only known scalar metadata participates in hashing/equality.
            if type(entity) is not str or (
                category == Event.VISUALISATION_UPDATE and type(kind) is not bool
            ):
                return
            key: LatestKey = (
                id,
                generation,
                category,
                cast(str, entity),
                cast(bool | None, kind),
            )
            if (
                key not in self._latest_slots
                and len(self._latest_slots) >= MAX_LATEST_KEYS
            ):
                self._initiate_close(1013, "stream backlog; reconnect and resync")
                return
            # Replacing in place preserves the pending key's turn. Popping a
            # selected key means a hot source re-enters at the rotation tail.
            self._latest_slots[key] = item
        elif category == Event.GENERAL_DIAG:
            if len(self._text_queue) >= MAX_PENDING_TEXT:
                self._text_queue.popleft()
                self._text_dropped += 1
            self._text_queue.append(item)
        else:
            self._admit_control(item)
            return
        self._has_work.set()

    def _select_lower_priority(self) -> Delivery | None:
        while self._text_queue and not self._delivery_current(self._text_queue[0]):
            self._text_queue.popleft()
        if self._text_queue and (self._prefer_text or not self._latest_slots):
            self._prefer_text = False
            if self._text_dropped and self._text_summary_ready:
                owner = self._text_queue[0]
                summary = Delivery(
                    {
                        "id": owner.subscription_id,
                        "type": "event",
                        "event_type": Event.GENERAL_DIAG,
                        "debug": f"Dropped {self._text_dropped} diagnostic messages",
                        "scroll": True,
                    },
                    owner.connection_generation,
                    owner.subscription_id,
                    owner.subscription_generation,
                )
                self._text_summary = (summary, self._text_dropped)
                return summary
            self._text_summary_ready = True
            return self._text_queue.popleft()
        if self._latest_slots:
            self._prefer_text = True
            return self._latest_slots.popitem(last=False)[1]
        return None

    def _select_delivery(self) -> Delivery | None:
        """Select only one item; control FIFO yields lower-priority progress."""
        if self._closing:
            return None
        while self._control_queue or self._latest_slots or self._text_queue:
            item = None
            if self._controls_selected >= MAX_CONTROL_BATCH or not self._control_queue:
                self._controls_selected = 0
                item = self._select_lower_priority()
            if item is None and self._control_queue:
                item = self._control_queue.popleft()
                self._controls_selected += 1
            if item is not None and self._delivery_current(item):
                return item
        return None

    async def _write_delivery(self, item: Delivery) -> None:
        socket = self._socket
        if socket is None or not self._delivery_current(item):
            return
        # The claim and writer invocation have no intervening await. A write
        # already invoked is allowed to finish after its subscription revokes.
        summary = self._text_summary
        await socket.send_json(item.message, dumps=dumps)
        if summary is not None and summary[0] is item:
            self._text_dropped = max(0, self._text_dropped - summary[1])
            self._text_summary_ready = False
            if self._text_summary is summary:
                self._text_summary = None

    async def _sender(self) -> None:
        socket = self._socket
        if socket is None:
            return
        _LOGGER.info("Starting websocket sender")
        writes = 0
        try:
            while not socket.closed and not self._closing:
                item = self._select_delivery()
                if item is None:
                    self._has_work.clear()
                    await self._has_work.wait()
                    continue
                try:
                    await self._write_delivery(item)
                except TypeError as err:
                    _LOGGER.error(
                        "Unable to serialize to JSON: %s\n%s", err, item.message
                    )
                except ConnectionResetError:
                    _LOGGER.info("Websocket connection closed by the client.")
                    return
                if item.message is self._receiver_error_reply:
                    return
                writes += 1
                if writes >= MAX_CONTROL_BATCH:
                    writes = 0
                    await asyncio.sleep(0)
        finally:
            # Preserve the overload close task and terminal-error grace.
            # Otherwise stop a receiver still waiting after writer failure.
            if self._closing or self._receiver_error_reply is not None:
                self._invalidate_connection()
            else:
                self.close()
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
        await self._socket.send_json({"event_type": "client_id", "client_id": self.uid})

        self._receiver_task = asyncio.current_task(loop=self._ledfx.loop)
        sender_task = self._sender_task = self._ledfx.loop.create_task(self._sender())

        self._ledfx.events.fire_event(ClientConnectedEvent(self.uid, self.client_ip))

        def shutdown_handler(e):
            self.close()

        remove_listeners = self._ledfx.events.add_listener(
            shutdown_handler, Event.LEDFX_SHUTDOWN
        )

        message: dict[str, object] | None = None
        try:
            ws_msg = await socket.receive()
            while ws_msg.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                if ws_msg.type == WSMsgType.BINARY:
                    self._handle_binary_message(ws_msg.data)
                    ws_msg = await socket.receive()
                    continue

                # A parse/validation failure must not reuse the preceding ID
                # or try to read dictionary keys from scalar/array JSON.
                message = None
                raw_message = ws_msg.json()
                if isinstance(raw_message, dict):
                    message = raw_message
                message = BaseMessage.model_validate(raw_message).model_dump()

                if message["type"] in websocket_handlers:
                    # Phase 1: Support async handlers
                    handler = websocket_handlers[message["type"]]
                    if inspect.iscoroutinefunction(handler):
                        await handler(self, message)
                    else:
                        handler(self, message)
                else:
                    _LOGGER.error("Received unknown command %s", message["type"])
                    self.send_error(message["id"], "Unknown command type.")

                ws_msg = await socket.receive()

        except ValueError:  # includes pydantic's ValidationError
            _LOGGER.info("Invalid message format.")
            if message is not None:
                msg_id = message.get("id")
                if msg_id is not None:
                    self._receiver_error_reply = {
                        "id": msg_id,
                        "success": False,
                        "error": {"message": "Invalid message format."},
                    }
                    self.send(self._receiver_error_reply)

        except TypeError:
            if socket.closed:
                _LOGGER.info("Connection closed by client.")
            else:
                _LOGGER.exception("Unexpected TypeError")

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Connection reset")

        except Exception:
            _LOGGER.exception("Unexpected Exception")

        finally:
            self.clear_subscriptions()
            if (
                self._receiver_error_reply is not None
                and not self._closed
                and not self._closing
                and not socket.closed
            ):
                # The one socket writer preserves FIFO and stops at this reply.
                # Keep shutdown listening active so forced close aborts the grace.
                try:
                    await asyncio.wait_for(
                        asyncio.gather(sender_task, return_exceptions=True),
                        timeout=FINAL_ERROR_REPLY_TIMEOUT,
                    )
                except (TimeoutError, asyncio.CancelledError):
                    pass
            async with WebsocketConnection.map_lock:
                if self.uid in WebsocketConnection.ip_uid_map:
                    del WebsocketConnection.ip_uid_map[self.uid]
            # Phase 1: Clean up client metadata on disconnect
            async with WebsocketConnection.metadata_lock:
                if self.uid in WebsocketConnection.client_metadata:
                    del WebsocketConnection.client_metadata[self.uid]
            remove_listeners()
            self._closed = True
            self._invalidate_connection()
            if self._close_task is not None:
                self._close_task.cancel()
                await asyncio.gather(self._close_task, return_exceptions=True)

            # Stop and await the sender even when the control FIFO is full.
            sender_task.cancel()
            await asyncio.gather(sender_task, return_exceptions=True)

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

    async def _reserve_and_set_client_name(self, desired_name: str) -> tuple[str, bool]:
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
                    if client_uuid != self.uid and meta.get("name") == resolved_name:
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
            return {uuid: meta.copy() for uuid, meta in cls.client_metadata.items()}

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
                "Invalid client_type '%s' from %s, defaulting to 'unknown'",
                client_type,
                self.uid,
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
        resolved_name, name_conflict = await self._reserve_and_set_client_name(name)

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
            "Client %s set info: name='%s', type='%s'",
            self.uid,
            resolved_name,
            self.client_type,
        )

    @websocket_handler("update_client_info")
    async def update_client_info_handler(self, message):
        """Handle client metadata updates (name and type)"""
        data = message.get("data", {})
        name = data.get("name")
        client_type = data.get("type")

        # Validate and normalize type if provided
        if client_type is not None and client_type not in VALID_CLIENT_TYPES:
            _LOGGER.warning(
                "Invalid client_type '%s' from %s, defaulting to 'unknown'",
                client_type,
                self.uid,
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
        _LOGGER.info("Client %s updated: %s", self.uid, ", ".join(updates))

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
            return [uuid for uuid in clients if uuid != sender_uuid]

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
            return [client_uuid for client_uuid in uuids if client_uuid in clients]

        else:
            _LOGGER.warning("Invalid target mode: %s", mode)
            return []

    @websocket_handler("broadcast")
    async def broadcast_handler(self, message):
        """Handle client-to-client broadcast messages (WebSocket-only)"""
        try:
            data = message.get("data", {})
            validated_data = BroadcastData.model_validate(data).model_dump(
                exclude_unset=True
            )
        except ValidationError as e:
            self.send_error(message["id"], f"Invalid broadcast data: {e}")
            return

        # Validate payload size
        payload = validated_data["payload"]
        payload_bytes = json.dumps(payload, ensure_ascii=False, default=default).encode(
            "utf-8"
        )
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
        target_uuids = self._filter_targets(target_config, clients, sender_uuid)

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
            "Broadcast %s: type=%s, sender=%s (%s), targets=%s clients",
            broadcast_id,
            validated_data["broadcast_type"],
            sender_name,
            sender_uuid[:8],
            len(target_uuids),
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

    @websocket_handler("get_event_capabilities")
    def get_event_capabilities_handler(self, message: dict[str, object]) -> None:
        self._send_installation_result(
            {
                "id": message["id"],
                "type": "result",
                "success": True,
                "result": {
                    "subscription_ack": 1,
                    "control_overflow": "close_1013_resync",
                },
            }
        )

    @websocket_handler("subscribe_event")
    def subscribe_event_handler(self, message: dict[str, object]) -> None:
        if self._closing:
            return
        ack = message.get("ack", False)
        if type(ack) is not bool:
            self.send_error(message["id"], "ack must be a boolean")
            return
        event_type = message.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            self.send_error(message["id"], "event_type must be a nonempty string")
            return
        event_filter = message.get("event_filter", {})
        if event_filter is not None and not isinstance(event_filter, Mapping):
            self.send_error(message["id"], "event_filter must be a mapping")
            return
        if event_type in NON_SUBSCRIBABLE_EVENTS:
            msg = (
                f"Websocket cannot subscribe to {event_type} events - "
                f"use {NON_SUBSCRIBABLE_EVENTS[event_type]} instead"
            )
            _LOGGER.warning("%s.", msg)
            self.send_error(message["id"], msg)
            return

        subscription_id = message["id"]
        if type(subscription_id) is not int:
            self.send_error(subscription_id, "subscription id must be an integer")
            return
        subscription_id = cast(int, subscription_id)
        self._subscription_generation += 1
        generation = self._subscription_generation

        def notify_websocket(event: Event) -> None:
            self.send_event(subscription_id, event, generation)

        try:
            # Validate all filter equality values/known metadata before revoke.
            # This temporary registration never enters the bus snapshot.
            validated = EventListener(
                notify_websocket,
                cast(Mapping[str, object] | None, event_filter),
            )
        except (TypeError, ValueError) as error:
            self.send_error(subscription_id, str(error))
            return
        self._revoke_subscription(subscription_id)
        try:
            disposer = self._ledfx.events.add_listener(
                notify_websocket, event_type, validated.filter
            )
        except (TypeError, ValueError) as error:
            self.send_error(subscription_id, str(error))
            return
        self._listeners[subscription_id] = Subscription(
            disposer, generation, event_type
        )
        if ack:
            self._send_installation_result(
                {
                    "id": subscription_id,
                    "type": "result",
                    "success": True,
                    "result": {
                        "subscription_id": subscription_id,
                        "event_type": event_type,
                        "installed": True,
                    },
                }
            )

    @websocket_handler("unsubscribe_event")
    def unsubscribe_event_handler(self, message: dict[str, object]) -> None:
        subscription_id = message["id"]
        _LOGGER.debug("Websocket unsubscribing event id %s", subscription_id)
        if subscription_id not in self._listeners:
            _LOGGER.warning("Unsubscribe unknown subscription ID %s", subscription_id)
        if type(subscription_id) is int:
            self._revoke_subscription(cast(int, subscription_id))

    @websocket_handler("audio_stream_start")
    def audio_stream_start_handler(self, message):
        client = message.get("client")

        if client in WEB_AUDIO_CLIENTS:
            _LOGGER.warning("Web audio client %s already exists", client)
            return

        _LOGGER.info("Web audio stream opened by client %s", client)
        WEB_AUDIO_CLIENTS.add(client)

    @websocket_handler("audio_stream_stop")
    def audio_stream_stop_handler(self, message):
        client = message.get("client")
        _LOGGER.info("Web audio stream closed by client %s", client)
        WEB_AUDIO_CLIENTS.discard(client)

    @websocket_handler("audio_stream_config")
    def audio_stream_config_handler(self, message):
        _LOGGER.info(
            "WebAudioConfig from %s: %s",
            message.get("client"),
            message.get("data"),
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
        data = message.get("data")
        # The frontend sends a list; older ones sent a {"0": ...} dict
        if isinstance(data, dict):
            data = list(data.values())
        try:
            # np.fromiter would also take a string, or numeric strings, as
            # samples; the frontend only ever sends a list of numbers.
            if not isinstance(data, list) or not all(
                isinstance(sample, (int, float)) for sample in data
            ):
                raise TypeError(type(data).__name__)
            samples = np.fromiter(data, dtype=np.float32)
        except (TypeError, ValueError, OverflowError):
            _LOGGER.warning("Malformed audio_stream_data from client %s", client)
            return
        ACTIVE_AUDIO_STREAM.data = samples

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
        except Exception:
            _LOGGER.exception("Unexpected Exception in base64 decoding")
        else:
            fmt = f"<{len(decoded) // 2}h"
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
            "Received song info: %s - %s",
            message.get("artist"),
            message.get("title"),
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

    _BINARY_MSG_FRONTEND_VIS = 0x01

    def _handle_binary_message(self, data: bytes) -> None:
        """Dispatch a raw binary WebSocket frame.

        Binary frame layout (all integers little-endian):
          [0]             uint8   message_type (0x01 = frontend_visualiser_data)
          [1-2]           uint16  width
          [3-4]           uint16  height
          [5]             uint8   vis_id byte length (N)
          [6 .. 6+N-1]   bytes   vis_id (UTF-8)
          [6+N]           uint8   client_id byte length (M)  -- ignored, self.uid used
          [7+N ..]        bytes   RGB pixels (width * height * 3)
        """
        try:
            if len(data) < 1:
                return
            msg_type = data[0]

            if msg_type == self._BINARY_MSG_FRONTEND_VIS:
                self._handle_frontend_vis(data)
            # Add additional binary message type handlers here following
            # the same pattern: elif msg_type == self._BINARY_MSG_XXX:
            #     self._handle_xxx(data)
            else:
                _LOGGER.warning(
                    "Unknown binary message type 0x%02x from %s",
                    msg_type,
                    self.uid,
                )

        except (ValueError, TypeError, struct.error) as e:
            _LOGGER.warning("Malformed binary frame from %s: %s", self.uid, e)

    def _handle_frontend_vis(self, data: bytes) -> None:
        """Parse and dispatch a frontend visualiser binary frame.

        Binary frame layout (after the 1-byte message type):
          [1-2]           uint16  width
          [3-4]           uint16  height
          [5]             uint8   vis_id byte length (N)
          [6 .. 6+N-1]   bytes   vis_id (UTF-8)
          [6+N]           uint8   client_id byte length (M)  -- ignored, self.uid used
          [7+N ..]        bytes   RGB pixels (width * height * 3)
        """
        if len(data) < 6:
            _LOGGER.warning(
                "Binary frontend_visualiser_data too short from %s",
                self.uid,
            )
            return

        width, height = struct.unpack_from("<HH", data, 1)
        vis_id_len = data[5]
        offset = 6

        if len(data) < offset + vis_id_len:
            _LOGGER.warning(
                "Binary frontend_visualiser_data truncated vis_id from %s",
                self.uid,
            )
            return

        vis_id = data[offset : offset + vis_id_len].decode("utf-8")
        offset += vis_id_len

        # Skip client_id length + bytes — identity comes from self.uid
        if len(data) < offset + 1:
            _LOGGER.warning(
                "Binary frontend_visualiser_data missing client_id length from %s",
                self.uid,
            )
            return
        client_id_len = data[offset]
        offset += 1 + client_id_len

        expected_pixel_bytes = width * height * 3
        pixel_data = data[offset:]
        if len(pixel_data) != expected_pixel_bytes:
            _LOGGER.warning(
                "Binary frontend_visualiser_data pixel size mismatch from %s: "
                "expected %d bytes for %dx%d, got %d",
                self.uid,
                expected_pixel_bytes,
                width,
                height,
                len(pixel_data),
            )
            return

        pixels = np.frombuffer(pixel_data, dtype=np.uint8).reshape(height, width, 3)
        self._ledfx.events.fire_event(
            FrontendVisualiserDataEvent(
                vis_id=vis_id,
                pixels=pixels,
                shape=[height, width],
                client_id=self.uid,
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
    def data(self, x):  # noqa: PLR0206
        return self._data

    @data.setter
    def data(self, x):
        self._data = x
        if self._active:
            try:
                self.callback(self._data, None, None, None)
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("%s", e)
