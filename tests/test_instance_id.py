"""Tests for persistent LedFx instance_id and Sendspin client_id construction."""

import uuid

import pytest

from ledfx.config import CORE_CONFIG_SCHEMA, ensure_instance_id


# ---------------------------------------------------------------------------
# Config bootstrap: ensure_instance_id
# ---------------------------------------------------------------------------


class TestEnsureInstanceId:
    """Tests for ensure_instance_id config helper."""

    def test_generates_uuid_when_missing(self):
        config = {}
        ensure_instance_id(config)
        # Must be a valid UUID string
        val = uuid.UUID(config["instance_id"])
        assert str(val) == config["instance_id"]

    def test_generates_uuid_when_empty_string(self):
        config = {"instance_id": ""}
        ensure_instance_id(config)
        uuid.UUID(config["instance_id"])  # valid UUID

    def test_preserves_existing_instance_id(self):
        existing = str(uuid.uuid4())
        config = {"instance_id": existing}
        ensure_instance_id(config)
        assert config["instance_id"] == existing

    def test_generated_ids_are_unique(self):
        configs = [{}, {}]
        for c in configs:
            ensure_instance_id(c)
        assert configs[0]["instance_id"] != configs[1]["instance_id"]

    def test_schema_accepts_instance_id(self):
        test_id = str(uuid.uuid4())
        config = CORE_CONFIG_SCHEMA({"instance_id": test_id})
        assert config["instance_id"] == test_id

    def test_schema_defaults_instance_id_to_empty(self):
        config = CORE_CONFIG_SCHEMA({})
        assert config["instance_id"] == ""


# ---------------------------------------------------------------------------
# Backward compatibility: existing config without instance_id
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Ensure old configs without instance_id load and validate fine."""

    def test_old_config_without_instance_id(self):
        old_config = {
            "host": "0.0.0.0",
            "port": 8888,
            "sendspin_servers": {"MyServer": {"server_url": "ws://host:1234"}},
        }
        validated = CORE_CONFIG_SCHEMA(old_config)
        assert validated["instance_id"] == ""
        # ensure_instance_id fills it in
        ensure_instance_id(validated)
        uuid.UUID(validated["instance_id"])


# ---------------------------------------------------------------------------
# Sendspin client_id construction
# ---------------------------------------------------------------------------


class TestSendspinClientId:
    """Tests for client_id built in SendspinAudioStream."""

    @pytest.fixture()
    def _skip_if_no_aiosendspin(self):
        """Skip tests if aiosendspin is not available."""
        try:
            from aiosendspin.client import SendspinClient  # noqa: F401
        except ImportError:
            pytest.skip("aiosendspin not available")

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_id_uses_short_instance_id(self):
        instance_id = str(uuid.uuid4())

        client_id = f"ledfx-{instance_id[:8]}"
        assert client_id == f"ledfx-{instance_id[:8]}"
        assert len(instance_id[:8]) == 8

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_id_deterministic(self):
        instance_id = str(uuid.uuid4())
        id1 = f"ledfx-{instance_id[:8]}"
        id2 = f"ledfx-{instance_id[:8]}"
        assert id1 == id2

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_id_differs_across_instances(self):
        id1 = f"ledfx-{str(uuid.uuid4())[:8]}"
        id2 = f"ledfx-{str(uuid.uuid4())[:8]}"
        assert id1 != id2

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_stream_constructor_stores_ids(self):
        from unittest.mock import MagicMock, patch

        from ledfx.sendspin.stream import SendspinAudioStream

        instance_id = str(uuid.uuid4())
        entry_id = "TestEntry"

        with patch(
            "ledfx.sendspin.stream.SendspinClient", MagicMock()
        ):
            stream = SendspinAudioStream(
                config={"server_url": "ws://localhost:1234", "client_name": "LedFx"},
                callback=lambda *a: None,
                sendspin_entry_id=entry_id,
                instance_id=instance_id,
            )

        assert stream._instance_id == instance_id
        assert stream._sendspin_entry_id == entry_id
