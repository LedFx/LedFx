"""Tests for the Web Audio "WebSocket v1" (audio_stream_data) handler."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ledfx.api import websocket
from ledfx.api.websocket import WebAudioStream, websocket_handlers


@pytest.mark.parametrize(
    "payload",
    [
        [0.5, -0.25, 1.0],  # current frontend: Array.from(Float32Array)
        {"0": 0.5, "1": -0.25, "2": 1.0},  # older frontends: raw Float32Array
    ],
)
def test_audio_stream_data_accepts_list_and_dict(payload: object) -> None:
    callback = MagicMock()
    stream = WebAudioStream("client-1", callback)
    stream.start()
    message = {"type": "audio_stream_data", "client": "client-1", "data": payload}

    with patch.object(websocket, "ACTIVE_AUDIO_STREAM", stream):
        websocket_handlers["audio_stream_data"](MagicMock(), message)

    np.testing.assert_array_equal(
        callback.call_args.args[0],
        np.array([0.5, -0.25, 1.0], dtype=np.float32),
    )


@pytest.mark.parametrize(
    "payload",
    [None, 3, "123", "", ["a", "b"], ["0.25", "0.5"], [[1.0], [2.0]], [10**400]],
)
def test_audio_stream_data_rejects_malformed_payload(payload: object) -> None:
    callback = MagicMock()
    stream = WebAudioStream("client-1", callback)
    stream.start()
    message = {"type": "audio_stream_data", "client": "client-1", "data": payload}

    with patch.object(websocket, "ACTIVE_AUDIO_STREAM", stream):
        # Must not raise: an exception here ends the websocket receive loop
        websocket_handlers["audio_stream_data"](MagicMock(), message)

    callback.assert_not_called()
