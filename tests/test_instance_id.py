"""Tests for persistent LedFx instance_id and Sendspin client_id construction."""

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.configuration.models import LedFxConfig

# ---------------------------------------------------------------------------
# Config model: instance_id (LedFxCore fills an empty one with a UUID at start)
# ---------------------------------------------------------------------------


class TestInstanceIdField:
    def test_model_accepts_instance_id(self) -> None:
        test_id = str(uuid.uuid4())
        assert LedFxConfig(instance_id=test_id).instance_id == test_id

    def test_model_defaults_instance_id_to_empty(self) -> None:
        assert LedFxConfig().instance_id == ""

    def test_old_config_without_instance_id_loads(self) -> None:
        old_config = {
            "host": "127.0.0.1",
            "port": 8888,
            "sendspin_servers": {"MyServer": {"server_url": "ws://host:1234"}},
        }
        assert LedFxConfig.model_validate(old_config).instance_id == ""


# ---------------------------------------------------------------------------
# Sendspin persistent identity construction
# ---------------------------------------------------------------------------


class TestSendspinIdentity:
    """Tests for the persistent identity passed to SendspinClient."""

    @pytest.fixture()
    def _skip_if_no_aiosendspin(self):
        """Skip tests if aiosendspin is not available."""
        try:
            from aiosendspin.client import SendspinClient  # noqa: F401
        except ImportError:
            pytest.skip("aiosendspin not available")

    def _run_connect_and_capture(self, instance_id: str, config_dir: Path) -> MagicMock:
        """Run _connect_and_receive with a mocked SendspinClient, return the mock class."""
        from types import SimpleNamespace

        from ledfx.sendspin.stream import SendspinAudioStream

        mock_client_cls = MagicMock()
        mock_inst = mock_client_cls.return_value
        mock_inst.connect = AsyncMock(side_effect=Exception("stop"))
        mock_inst.add_audio_chunk_listener = MagicMock()
        mock_inst.add_stream_start_listener = MagicMock()
        mock_inst.add_stream_clear_listener = MagicMock()

        with patch("ledfx.sendspin.stream.SendspinClient", mock_client_cls):
            stream = SendspinAudioStream(
                config={
                    "server_url": "ws://localhost:1234",
                    "client_name": "LedFx",
                },
                callback=lambda *a: None,
                instance_id=instance_id,
                ledfx=SimpleNamespace(
                    config_dir=str(config_dir),
                    now_playing=None,
                ),
            )
            with pytest.raises(Exception, match="stop"):
                asyncio.run(stream._connect_and_receive())

        return mock_client_cls

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_identity_is_stable_for_config_directory(
        self, tmp_path: Path
    ) -> None:
        instance_id = str(uuid.uuid4())
        mock_cls = self._run_connect_and_capture(instance_id, tmp_path)
        identity = mock_cls.call_args.kwargs["identity"]
        assert identity.peer_id
        assert (tmp_path / "sendspin_identity").exists()

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_identity_persists_across_streams(self, tmp_path: Path) -> None:
        instance_id = str(uuid.uuid4())
        mock1 = self._run_connect_and_capture(instance_id, tmp_path)
        mock2 = self._run_connect_and_capture(instance_id, tmp_path)
        assert (
            mock1.call_args.kwargs["identity"].peer_id
            == mock2.call_args.kwargs["identity"].peer_id
        )

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_client_identity_differs_across_config_directories(
        self, tmp_path: Path
    ) -> None:
        mock1 = self._run_connect_and_capture(str(uuid.uuid4()), tmp_path / "one")
        mock2 = self._run_connect_and_capture(str(uuid.uuid4()), tmp_path / "two")
        assert (
            mock1.call_args.kwargs["identity"].peer_id
            != mock2.call_args.kwargs["identity"].peer_id
        )

    @pytest.mark.usefixtures("_skip_if_no_aiosendspin")
    def test_stream_constructor_stores_ids(self):
        from unittest.mock import MagicMock, patch

        from ledfx.sendspin.stream import SendspinAudioStream

        instance_id = str(uuid.uuid4())

        with patch("ledfx.sendspin.stream.SendspinClient", MagicMock()):
            stream = SendspinAudioStream(
                config={
                    "server_url": "ws://localhost:1234",
                    "client_name": "LedFx",
                },
                callback=lambda *a: None,
                instance_id=instance_id,
            )

        assert stream._instance_id == instance_id
