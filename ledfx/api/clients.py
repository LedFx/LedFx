import logging
import time
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.websocket import WebsocketConnection
from ledfx.events import (
    ClientBroadcastEvent,
    ClientsUpdatedEvent,
    ClientSyncEvent,
)

_LOGGER = logging.getLogger(__name__)

ACTIONS = ["sync", "broadcast"]
BROADCAST_TYPES = [
    "visualiser_control",
    "scene_sync",
    "color_palette",
    "custom",
]
TARGET_MODES = ["all", "type", "names", "uuids"]
MAX_PAYLOAD_SIZE = 2048  # 2KB

BROADCAST_SCHEMA = vol.Schema(
    {
        vol.Required("action"): "broadcast",
        vol.Required("broadcast_type"): vol.In(BROADCAST_TYPES),
        vol.Required("sender_id"): str,
        vol.Required("target"): {
            vol.Required("mode"): vol.In(TARGET_MODES),
            vol.Optional("value"): str,
            vol.Optional("names"): [str],
            vol.Optional("uuids"): [str],
        },
        vol.Required("payload"): dict,
    }
)


class ClientEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/clients"

    async def get(self) -> web.Response:
        """Get the list of clients with full metadata"""
        clients = await WebsocketConnection.get_all_clients_metadata()
        return await self.bare_request_success(clients)

    async def post(self, request: web.Request) -> web.Response:
        """Perform action for client"""
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        action = data.get("action")

        if action is None:
            return await self.invalid_request(
                'Required attribute "action" was not provided'
            )

        if action not in ACTIONS:
            return await self.invalid_request(
                f"Action {action} is not in {ACTIONS}"
            )

        if action == "sync":
            client_id = data.get("client_id", "unknown")
            self._ledfx.events.fire_event(ClientSyncEvent(client_id))
            response = {"status": "success", "action": action}
            return await self.bare_request_success(response)

        if action == "broadcast":
            return await self._handle_broadcast(data)

    async def _handle_broadcast(self, data):
        """Handle broadcast action"""
        # Validate schema
        try:
            validated = BROADCAST_SCHEMA(data)
        except vol.Invalid as e:
            return await self.invalid_request(f"Invalid broadcast schema: {e}")

        # Check payload size
        import json

        payload_size = len(json.dumps(validated["payload"]))
        if payload_size > MAX_PAYLOAD_SIZE:
            return await self.invalid_request(
                f"Payload too large: {payload_size} bytes (max {MAX_PAYLOAD_SIZE})"
            )

        # Get sender info
        sender_id = validated["sender_id"]
        clients = await WebsocketConnection.get_all_clients_metadata()
        sender_name = clients.get(sender_id, {}).get("name", "Unknown")

        # Filter target clients
        target_uuids = self._filter_targets(validated["target"], clients)

        if not target_uuids:
            return await self.invalid_request("No targets matched filters")

        # Fire broadcast event
        self._ledfx.events.fire_event(
            ClientBroadcastEvent(
                broadcast_type=validated["broadcast_type"],
                sender_id=sender_id,
                sender_name=sender_name,
                target_uuids=target_uuids,
                payload=validated["payload"],
            )
        )

        response = {
            "status": "success",
            "broadcast_id": f"b-{int(time.time() * 1000)}",
            "targets_matched": len(target_uuids),
            "targets": target_uuids,
        }
        return await self.bare_request_success(response)

    def _filter_targets(self, target_config, clients):
        """Filter clients based on target configuration"""
        mode = target_config["mode"]

        if mode == "all":
            return list(clients.keys())

        if mode == "type":
            client_type = target_config.get("value")
            return [
                uuid
                for uuid, meta in clients.items()
                if meta.get("type") == client_type
            ]

        if mode == "names":
            target_names = target_config.get("names", [])
            return [
                uuid
                for uuid, meta in clients.items()
                if meta.get("name") in target_names
            ]

        if mode == "uuids":
            return target_config.get("uuids", [])

        return []
