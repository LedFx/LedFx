"""Tests for WebSocket client management features (Phase 1-3)

Comprehensive test suite for client metadata, broadcasting, and connection management.
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from ledfx.api.websocket import (
    BROADCAST_SCHEMA,
    BROADCAST_TYPES,
    MAX_PAYLOAD_SIZE,
    TARGET_MODES,
    VALID_CLIENT_TYPES,
    WebsocketConnection,
)
from ledfx.events import ClientBroadcastEvent, ClientsUpdatedEvent


@pytest.fixture
def mock_ledfx():
    """Create a mock LedFx instance with proper event loop cleanup"""
    ledfx = MagicMock()
    loop = asyncio.new_event_loop()
    ledfx.loop = loop
    ledfx.events = MagicMock()
    ledfx.events.fire_event = MagicMock()

    yield ledfx

    # Clean up event loop resources
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture
def websocket_connection(mock_ledfx):
    """Create a WebsocketConnection instance"""
    conn = WebsocketConnection(mock_ledfx)
    conn.uid = "test-uuid-1234"
    conn.client_ip = "192.168.1.100"
    conn.connected_at = time.time()
    return conn


@pytest.fixture(autouse=True)
def clear_class_state():
    """Clear class-level state before each test"""
    WebsocketConnection.client_metadata.clear()
    WebsocketConnection.ip_uid_map.clear()
    yield
    WebsocketConnection.client_metadata.clear()
    WebsocketConnection.ip_uid_map.clear()


class TestPhase1Infrastructure:
    """Test Phase 1: Infrastructure components"""

    @pytest.mark.asyncio
    async def test_metadata_storage_initialization(self):
        """Test that class-level metadata storage is initialized"""
        assert hasattr(WebsocketConnection, "client_metadata")
        assert hasattr(WebsocketConnection, "metadata_lock")
        assert isinstance(WebsocketConnection.client_metadata, dict)
        assert isinstance(WebsocketConnection.metadata_lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_instance_attributes(self, websocket_connection):
        """Test that instance attributes are initialized"""
        assert websocket_connection.device_id is None
        assert websocket_connection.client_name is None
        assert websocket_connection.client_type == "unknown"
        assert websocket_connection.connected_at is not None

    @pytest.mark.asyncio
    async def test_name_exists_empty(self, websocket_connection):
        """Test _name_exists returns False when no clients exist"""
        result = await websocket_connection._name_exists("TestName")
        assert result is False

    @pytest.mark.asyncio
    async def test_name_exists_found(self, websocket_connection):
        """Test _name_exists returns True when name exists"""
        # Pre-populate metadata
        WebsocketConnection.client_metadata["other-uuid"] = {
            "name": "ExistingName"
        }

        result = await websocket_connection._name_exists("ExistingName")
        assert result is True

    @pytest.mark.asyncio
    async def test_name_exists_exclude_self(self, websocket_connection):
        """Test _name_exists ignores excluded UUID"""
        # Pre-populate with own name
        WebsocketConnection.client_metadata[websocket_connection.uid] = {
            "name": "MyName"
        }

        result = await websocket_connection._name_exists(
            "MyName", exclude_uuid=websocket_connection.uid
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_update_metadata(self, websocket_connection):
        """Test _update_metadata stores metadata correctly"""
        websocket_connection.client_name = "TestClient"
        websocket_connection.client_type = "controller"
        websocket_connection.device_id = "device-123"

        await websocket_connection._update_metadata()

        metadata = WebsocketConnection.client_metadata[
            websocket_connection.uid
        ]
        assert metadata["name"] == "TestClient"
        assert metadata["type"] == "controller"
        assert metadata["device_id"] == "device-123"
        assert metadata["ip"] == "192.168.1.100"
        assert "connected_at" in metadata

    @pytest.mark.asyncio
    async def test_get_all_clients_metadata(self):
        """Test get_all_clients_metadata returns deep copy"""
        # Pre-populate metadata
        WebsocketConnection.client_metadata["uuid-1"] = {
            "name": "Client1",
            "type": "controller",
        }
        WebsocketConnection.client_metadata["uuid-2"] = {
            "name": "Client2",
            "type": "visualiser",
        }

        result = await WebsocketConnection.get_all_clients_metadata()

        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-2" in result
        # Verify it's a copy (mutating result doesn't affect class storage)
        result["uuid-1"]["name"] = "Modified"
        assert (
            WebsocketConnection.client_metadata["uuid-1"]["name"] == "Client1"
        )


class TestPhase2ClientMetadata:
    """Test Phase 2: Client metadata features"""

    @pytest.mark.asyncio
    async def test_set_client_info_basic(
        self, websocket_connection, mock_ledfx
    ):
        """Test set_client_info with valid data"""
        message = {
            "id": 1,
            "type": "set_client_info",
            "data": {
                "name": "TestClient",
                "type": "controller",
                "device_id": "dev-1",
            },
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.set_client_info_handler(message)

        # Verify instance attributes
        assert websocket_connection.client_name == "TestClient"
        assert websocket_connection.client_type == "controller"
        assert websocket_connection.device_id == "dev-1"

        # Verify metadata stored
        metadata = WebsocketConnection.client_metadata[
            websocket_connection.uid
        ]
        assert metadata["name"] == "TestClient"
        assert metadata["type"] == "controller"

        # Verify event fired
        mock_ledfx.events.fire_event.assert_called()
        event = mock_ledfx.events.fire_event.call_args[0][0]
        assert isinstance(event, ClientsUpdatedEvent)

        # Verify response sent
        websocket_connection.send.assert_called_once()
        response = websocket_connection.send.call_args[0][0]
        assert response["event_type"] == "client_info_updated"
        assert response["name"] == "TestClient"
        assert response["type"] == "controller"
        assert response["name_conflict"] is False

    @pytest.mark.asyncio
    async def test_set_client_info_default_name(self, websocket_connection):
        """Test set_client_info generates default name when not provided"""
        message = {"id": 1, "type": "set_client_info", "data": {}}

        websocket_connection.send = MagicMock()
        await websocket_connection.set_client_info_handler(message)

        # Should generate name from UUID
        assert websocket_connection.client_name.startswith("Client-")
        assert (
            websocket_connection.client_name
            == f"Client-{websocket_connection.uid[:8]}"
        )

    @pytest.mark.asyncio
    async def test_set_client_info_invalid_type(self, websocket_connection):
        """Test set_client_info defaults to 'unknown' for invalid type"""
        message = {
            "id": 1,
            "type": "set_client_info",
            "data": {"type": "invalid_type"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.set_client_info_handler(message)

        # Should default to 'unknown'
        assert websocket_connection.client_type == "unknown"

    @pytest.mark.asyncio
    async def test_set_client_info_name_conflict(self, websocket_connection):
        """Test set_client_info handles name conflicts with counter"""
        # Pre-populate with existing name
        WebsocketConnection.client_metadata["other-uuid"] = {
            "name": "TestClient"
        }

        message = {
            "id": 1,
            "type": "set_client_info",
            "data": {"name": "TestClient"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.set_client_info_handler(message)

        # Should append (2) to name
        assert websocket_connection.client_name == "TestClient (2)"

        # Verify name_conflict flag
        response = websocket_connection.send.call_args[0][0]
        assert response["name_conflict"] is True

    @pytest.mark.asyncio
    async def test_set_client_info_multiple_conflicts(
        self, websocket_connection
    ):
        """Test set_client_info handles multiple name conflicts"""
        # Pre-populate with existing names
        WebsocketConnection.client_metadata["uuid-1"] = {"name": "TestClient"}
        WebsocketConnection.client_metadata["uuid-2"] = {
            "name": "TestClient (2)"
        }
        WebsocketConnection.client_metadata["uuid-3"] = {
            "name": "TestClient (3)"
        }

        message = {
            "id": 1,
            "type": "set_client_info",
            "data": {"name": "TestClient"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.set_client_info_handler(message)

        # Should append (4) to name
        assert websocket_connection.client_name == "TestClient (4)"

    @pytest.mark.asyncio
    async def test_update_client_info_name_only(
        self, websocket_connection, mock_ledfx
    ):
        """Test update_client_info updates name only"""
        # Pre-set initial metadata
        websocket_connection.client_name = "OldName"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        message = {
            "id": 1,
            "type": "update_client_info",
            "data": {"name": "NewName"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Verify name updated
        assert websocket_connection.client_name == "NewName"
        # Verify type unchanged
        assert websocket_connection.client_type == "controller"

        # Verify event fired
        mock_ledfx.events.fire_event.assert_called()

    @pytest.mark.asyncio
    async def test_update_client_info_name_conflict(
        self, websocket_connection
    ):
        """Test update_client_info rejects name conflict"""
        # Pre-populate with existing name
        WebsocketConnection.client_metadata["other-uuid"] = {
            "name": "TakenName"
        }

        message = {
            "id": 1,
            "type": "update_client_info",
            "data": {"name": "TakenName"},
        }

        websocket_connection.send_error = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Should send error
        websocket_connection.send_error.assert_called_once()
        error_message = websocket_connection.send_error.call_args[0][1]
        assert "already taken" in error_message

    @pytest.mark.asyncio
    async def test_update_client_info_type_update(self, websocket_connection):
        """Test that update_client_info can change type"""
        # Pre-set initial metadata
        websocket_connection.client_name = "TestClient"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        message = {
            "id": 1,
            "type": "update_client_info",
            "data": {"type": "visualiser"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Type should be updated
        assert websocket_connection.client_type == "visualiser"

        # Verify metadata was persisted
        metadata = WebsocketConnection.client_metadata[
            websocket_connection.uid
        ]
        assert metadata["type"] == "visualiser"

        # Verify response
        response = websocket_connection.send.call_args[0][0]
        assert response["event_type"] == "client_info_updated"
        assert response["type"] == "visualiser"

    @pytest.mark.asyncio
    async def test_update_client_info_invalid_type(self, websocket_connection):
        """Test that update_client_info defaults invalid types to unknown"""
        websocket_connection.client_name = "TestClient"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        message = {
            "id": 1,
            "type": "update_client_info",
            "data": {"type": "invalid_type"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Invalid type should default to unknown
        assert websocket_connection.client_type == "unknown"

        # Verify response
        response = websocket_connection.send.call_args[0][0]
        assert response["type"] == "unknown"

    @pytest.mark.asyncio
    async def test_update_client_info_name_and_type(
        self, websocket_connection
    ):
        """Test that update_client_info can update both name and type"""
        websocket_connection.client_name = "TestClient"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        message = {
            "id": 1,
            "type": "update_client_info",
            "data": {"name": "NewName", "type": "display"},
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Both should be updated
        assert websocket_connection.client_name == "NewName"
        assert websocket_connection.client_type == "display"

        # Verify metadata was persisted
        metadata = WebsocketConnection.client_metadata[
            websocket_connection.uid
        ]
        assert metadata["name"] == "NewName"
        assert metadata["type"] == "display"

        # Verify response
        response = websocket_connection.send.call_args[0][0]
        assert response["name"] == "NewName"
        assert response["type"] == "display"

    @pytest.mark.asyncio
    async def test_update_client_info_no_updates(self, websocket_connection):
        """Test update_client_info with no data"""
        message = {"id": 1, "type": "update_client_info", "data": {}}

        websocket_connection.send = MagicMock()
        await websocket_connection.update_client_info_handler(message)

        # Should send error response with "No valid updates" message
        response = websocket_connection.send.call_args[0][0]
        assert response["success"] is False
        assert "No valid updates" in response.get("error", {}).get(
            "message", ""
        )


class TestPhase3Broadcasting:
    """Test Phase 3: Broadcasting features"""

    @pytest.mark.asyncio
    async def test_filter_targets_mode_all(self, websocket_connection):
        """Test _filter_targets with mode='all' excludes sender"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
            "uuid-1": {"name": "Client1", "type": "controller"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
        }

        target_config = {"mode": "all"}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender should be excluded from mode='all' to prevent self-echo
        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-2" in result
        assert "uuid-sender" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_type(self, websocket_connection):
        """Test _filter_targets with mode='type'"""
        clients = {
            "uuid-1": {"name": "Client1", "type": "controller"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
            "uuid-3": {"name": "Client3", "type": "visualiser"},
        }

        target_config = {"mode": "type", "value": "visualiser"}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-1"
        )

        assert len(result) == 2
        assert "uuid-2" in result
        assert "uuid-3" in result
        assert "uuid-1" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_type_missing_value(
        self, websocket_connection
    ):
        """Test _filter_targets rejects type mode without value (fail-closed)"""
        clients = {"uuid-1": {"name": "Client1", "type": "controller"}}

        target_config = {"mode": "type"}  # Missing 'value'
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        assert len(result) == 0  # Fail-closed: return empty list

    @pytest.mark.asyncio
    async def test_filter_targets_mode_type_includes_sender(
        self, websocket_connection
    ):
        """Test _filter_targets with mode='type' includes sender if sender matches type"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "visualiser"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
            "uuid-3": {"name": "Client3", "type": "controller"},
        }

        target_config = {"mode": "type", "value": "visualiser"}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender included because they match type="visualiser"
        assert len(result) == 2
        assert "uuid-2" in result
        assert "uuid-sender" in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_names(self, websocket_connection):
        """Test _filter_targets with mode='names'"""
        clients = {
            "uuid-1": {"name": "Client1", "type": "controller"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
            "uuid-3": {"name": "Client3", "type": "mobile"},
        }

        target_config = {"mode": "names", "names": ["Client1", "Client3"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-3" in result
        assert "uuid-2" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_names_missing_list(
        self, websocket_connection
    ):
        """Test _filter_targets rejects names mode without list (fail-closed)"""
        clients = {"uuid-1": {"name": "Client1", "type": "controller"}}

        target_config = {"mode": "names"}  # Missing 'names' list
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        assert len(result) == 0  # Fail-closed: return empty list

    @pytest.mark.asyncio
    async def test_filter_targets_mode_uuids(self, websocket_connection):
        """Test _filter_targets with mode='uuids' (lenient filtering)"""
        clients = {
            "uuid-1": {"name": "Client1", "type": "controller"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
            "uuid-3": {"name": "Client3", "type": "mobile"},
        }

        target_config = {"mode": "uuids", "uuids": ["uuid-1", "uuid-999"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Lenient filtering: non-existent UUIDs silently ignored
        assert len(result) == 1
        assert "uuid-1" in result
        assert "uuid-999" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_uuids_missing_list(
        self, websocket_connection
    ):
        """Test _filter_targets rejects uuids mode without list (fail-closed)"""
        clients = {"uuid-1": {"name": "Client1", "type": "controller"}}

        target_config = {"mode": "uuids"}  # Missing 'uuids' list
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        assert len(result) == 0  # Fail-closed: return empty list

    @pytest.mark.asyncio
    async def test_filter_targets_invalid_mode(self, websocket_connection):
        """Test _filter_targets rejects invalid mode (fail-closed)"""
        clients = {"uuid-1": {"name": "Client1", "type": "controller"}}

        target_config = {"mode": "invalid_mode"}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        assert len(result) == 0  # Fail-closed: return empty list

    @pytest.mark.asyncio
    async def test_filter_targets_mode_names_lenient(
        self, websocket_connection
    ):
        """Test _filter_targets with mode='names' uses lenient filtering"""
        clients = {
            "uuid-1": {"name": "Client1", "type": "controller"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
        }

        # Request includes non-existent name "Client999"
        target_config = {
            "mode": "names",
            "names": ["Client1", "Client999"],
        }
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Lenient: broadcasts to Client1, silently ignores Client999
        assert len(result) == 1
        assert "uuid-1" in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_names_sender_included(
        self, websocket_connection
    ):
        """Test mode='names' includes sender only if explicitly listed in the names array"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
            "uuid-1": {"name": "Client1", "type": "visualiser"},
        }

        # Explicitly target sender via name
        target_config = {"mode": "names", "names": ["Sender", "Client1"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender included because explicitly targeted by name
        assert len(result) == 2
        assert "uuid-sender" in result
        assert "uuid-1" in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_names_sender_excluded(
        self, websocket_connection
    ):
        """Test mode='names' excludes sender when sender's name is not in the list"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
            "uuid-1": {"name": "Client1", "type": "visualiser"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
        }

        # Target specific names, NOT including sender
        target_config = {"mode": "names", "names": ["Client1", "Client2"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender excluded because not in the names list
        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-2" in result
        assert "uuid-sender" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_uuids_sender_included(
        self, websocket_connection
    ):
        """Test mode='uuids' includes sender only if explicitly listed in the uuids array"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
            "uuid-1": {"name": "Client1", "type": "visualiser"},
        }

        # Explicitly target sender via UUID
        target_config = {"mode": "uuids", "uuids": ["uuid-sender", "uuid-1"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender included because explicitly targeted by UUID
        assert len(result) == 2
        assert "uuid-sender" in result
        assert "uuid-1" in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_uuids_sender_excluded(
        self, websocket_connection
    ):
        """Test mode='uuids' excludes sender when sender's UUID is not in the list"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
            "uuid-1": {"name": "Client1", "type": "visualiser"},
            "uuid-2": {"name": "Client2", "type": "visualiser"},
        }

        # Target specific UUIDs, NOT including sender
        target_config = {"mode": "uuids", "uuids": ["uuid-1", "uuid-2"]}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender excluded because not in the uuids list
        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-2" in result
        assert "uuid-sender" not in result

    @pytest.mark.asyncio
    async def test_filter_targets_mode_all_sender_only(
        self, websocket_connection
    ):
        """Test mode='all' returns empty when sender is the only client"""
        clients = {
            "uuid-sender": {"name": "Sender", "type": "controller"},
        }

        target_config = {"mode": "all"}
        result = websocket_connection._filter_targets(
            target_config, clients, "uuid-sender"
        )

        # Sender excluded, no other clients, result is empty
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_broadcast_handler_success(
        self, websocket_connection, mock_ledfx
    ):
        """Test broadcast_handler with valid data"""
        # Set up connection metadata
        websocket_connection.client_name = "Sender"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        # Add target client
        WebsocketConnection.client_metadata["target-uuid"] = {
            "name": "Target",
            "type": "visualiser",
        }

        message = {
            "id": 1,
            "type": "broadcast",
            "data": {
                "broadcast_type": "scene_sync",
                "target": {"mode": "all"},
                "payload": {"scene_id": "scene-123"},
            },
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.broadcast_handler(message)

        # Verify event fired
        mock_ledfx.events.fire_event.assert_called()
        event = mock_ledfx.events.fire_event.call_args[0][0]
        assert isinstance(event, ClientBroadcastEvent)
        assert event.broadcast_type == "scene_sync"
        assert event.sender_uuid == websocket_connection.uid
        assert event.sender_name == "Sender"
        assert event.sender_type == "controller"
        assert len(event.target_uuids) == 1  # Only target (sender excluded)
        assert "target-uuid" in event.target_uuids
        assert websocket_connection.uid not in event.target_uuids
        assert event.payload == {"scene_id": "scene-123"}

        # Verify success response
        websocket_connection.send.assert_called_once()
        response = websocket_connection.send.call_args[0][0]
        assert response["event_type"] == "broadcast_sent"
        assert "broadcast_id" in response
        assert (
            response["targets_matched"] == 1
        )  # Only target (sender excluded)

    @pytest.mark.asyncio
    async def test_broadcast_handler_no_sender_id_field(
        self, websocket_connection
    ):
        """Test that broadcast_handler derives sender from connection (security)"""
        websocket_connection.client_name = "RealSender"
        websocket_connection.client_type = "controller"
        await websocket_connection._update_metadata()

        # Add target client
        WebsocketConnection.client_metadata["target-uuid"] = {
            "name": "Target",
            "type": "visualiser",
        }

        message = {
            "id": 1,
            "type": "broadcast",
            "data": {
                "broadcast_type": "custom",
                "target": {"mode": "all"},
                "payload": {"data": "test"},
                # Note: No sender_id field - should be ignored even if present
            },
        }

        websocket_connection.send = MagicMock()
        await websocket_connection.broadcast_handler(message)

        # Verify sender derived from connection, not request
        event = websocket_connection._ledfx.events.fire_event.call_args[0][0]
        assert event.sender_uuid == websocket_connection.uid
        assert event.sender_name == "RealSender"

    @pytest.mark.asyncio
    async def test_broadcast_handler_invalid_schema(
        self, websocket_connection
    ):
        """Test broadcast_handler rejects invalid schema"""
        message = {
            "id": 1,
            "type": "broadcast",
            "data": {
                "broadcast_type": "invalid_type",  # Not in BROADCAST_TYPES
                "target": {"mode": "all"},
                "payload": {},
            },
        }

        websocket_connection.send_error = MagicMock()
        await websocket_connection.broadcast_handler(message)

        # Should send error
        websocket_connection.send_error.assert_called_once()
        error_message = websocket_connection.send_error.call_args[0][1]
        assert "Invalid broadcast data" in error_message

    @pytest.mark.asyncio
    async def test_broadcast_handler_payload_too_large(
        self, websocket_connection
    ):
        """Test broadcast_handler rejects oversized payload"""
        # Create payload larger than MAX_PAYLOAD_SIZE
        large_payload = {"data": "x" * (MAX_PAYLOAD_SIZE + 100)}

        message = {
            "id": 1,
            "type": "broadcast",
            "data": {
                "broadcast_type": "custom",
                "target": {"mode": "all"},
                "payload": large_payload,
            },
        }

        websocket_connection.send_error = MagicMock()
        await websocket_connection.broadcast_handler(message)

        # Should send error about payload size
        websocket_connection.send_error.assert_called_once()
        error_message = websocket_connection.send_error.call_args[0][1]
        assert "Payload size" in error_message
        assert "exceeds maximum" in error_message

    @pytest.mark.asyncio
    async def test_broadcast_handler_no_targets_matched(
        self, websocket_connection
    ):
        """Test broadcast_handler rejects when no targets match"""
        await websocket_connection._update_metadata()

        message = {
            "id": 1,
            "type": "broadcast",
            "data": {
                "broadcast_type": "custom",
                "target": {"mode": "type", "value": "nonexistent_type"},
                "payload": {},
            },
        }

        websocket_connection.send_error = MagicMock()
        await websocket_connection.broadcast_handler(message)

        # Should send error about no targets
        websocket_connection.send_error.assert_called_once()
        error_message = websocket_connection.send_error.call_args[0][1]
        assert "No clients matched" in error_message


class TestSchemaValidation:
    """Test Voluptuous schema validation"""

    def test_broadcast_schema_valid(self):
        """Test BROADCAST_SCHEMA accepts valid data"""
        valid_data = {
            "broadcast_type": "scene_sync",
            "target": {"mode": "all"},
            "payload": {"scene_id": "test"},
        }

        result = BROADCAST_SCHEMA(valid_data)
        assert result["broadcast_type"] == "scene_sync"

    def test_broadcast_schema_missing_required(self):
        """Test BROADCAST_SCHEMA rejects missing required fields"""
        invalid_data = {
            "broadcast_type": "scene_sync",
            # Missing 'target' and 'payload'
        }

        with pytest.raises(vol.Invalid):
            BROADCAST_SCHEMA(invalid_data)

    def test_broadcast_schema_invalid_broadcast_type(self):
        """Test BROADCAST_SCHEMA rejects invalid broadcast_type"""
        invalid_data = {
            "broadcast_type": "invalid_type",
            "target": {"mode": "all"},
            "payload": {},
        }

        with pytest.raises(vol.Invalid):
            BROADCAST_SCHEMA(invalid_data)

    def test_broadcast_schema_invalid_target_mode(self):
        """Test BROADCAST_SCHEMA rejects invalid target mode"""
        invalid_data = {
            "broadcast_type": "custom",
            "target": {"mode": "invalid_mode"},
            "payload": {},
        }

        with pytest.raises(vol.Invalid):
            BROADCAST_SCHEMA(invalid_data)

    def test_broadcast_schema_prevents_extra_fields(self):
        """Test BROADCAST_SCHEMA rejects extra fields (PREVENT_EXTRA)"""
        invalid_data = {
            "broadcast_type": "custom",
            "target": {"mode": "all"},
            "payload": {},
            "sender_id": "fake-uuid",  # Should be rejected
        }

        with pytest.raises(vol.Invalid):
            BROADCAST_SCHEMA(invalid_data)


class TestConstants:
    """Test that constants are defined correctly"""

    def test_valid_client_types(self):
        """Test VALID_CLIENT_TYPES contains expected types"""
        assert "controller" in VALID_CLIENT_TYPES
        assert "visualiser" in VALID_CLIENT_TYPES
        assert "mobile" in VALID_CLIENT_TYPES
        assert "display" in VALID_CLIENT_TYPES
        assert "api" in VALID_CLIENT_TYPES
        assert "unknown" in VALID_CLIENT_TYPES

    def test_broadcast_types(self):
        """Test BROADCAST_TYPES contains expected types"""
        assert "visualiser_control" in BROADCAST_TYPES
        assert "scene_sync" in BROADCAST_TYPES
        assert "color_palette" in BROADCAST_TYPES
        assert "custom" in BROADCAST_TYPES

    def test_target_modes(self):
        """Test TARGET_MODES contains expected modes"""
        assert "all" in TARGET_MODES
        assert "type" in TARGET_MODES
        assert "names" in TARGET_MODES
        assert "uuids" in TARGET_MODES

    def test_max_payload_size(self):
        """Test MAX_PAYLOAD_SIZE is reasonable"""
        assert MAX_PAYLOAD_SIZE == 2048
        assert MAX_PAYLOAD_SIZE > 0


class TestConcurrency:
    """Test thread-safety of metadata operations"""

    @pytest.mark.asyncio
    async def test_concurrent_metadata_updates(self, mock_ledfx):
        """Test that concurrent metadata updates are thread-safe"""
        connections = [WebsocketConnection(mock_ledfx) for _ in range(10)]

        # Set unique UIDs
        for i, conn in enumerate(connections):
            conn.uid = f"uuid-{i}"
            conn.client_ip = f"192.168.1.{i}"
            conn.connected_at = time.time()
            conn.client_name = f"Client-{i}"
            conn.client_type = "controller"

        # Update all metadata concurrently
        await asyncio.gather(
            *[conn._update_metadata() for conn in connections]
        )

        # Verify all metadata stored correctly
        assert len(WebsocketConnection.client_metadata) == 10
        for i in range(10):
            assert f"uuid-{i}" in WebsocketConnection.client_metadata
            assert (
                WebsocketConnection.client_metadata[f"uuid-{i}"]["name"]
                == f"Client-{i}"
            )

    @pytest.mark.asyncio
    async def test_concurrent_name_checks(self, mock_ledfx):
        """Test that concurrent name existence checks are thread-safe"""
        conn = WebsocketConnection(mock_ledfx)
        conn.uid = "test-uuid"

        # Pre-populate with a name
        WebsocketConnection.client_metadata["other-uuid"] = {
            "name": "ExistingName"
        }

        # Check name existence concurrently
        results = await asyncio.gather(
            *[conn._name_exists("ExistingName") for _ in range(100)]
        )

        # All should return True
        assert all(results)
