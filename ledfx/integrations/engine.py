import asyncio
import logging
import time

import numpy as np
import voluptuous as vol

from ledfx.effects.melbank import MIC_RATE
from ledfx.events import MoodChangedEvent
from ledfx.integrations import Integration
from ledfx.integrations.librosa_worker.librosaEngineClient import (
    LibrosaEngineClient,
)
from ledfx.utils import Teleplot

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False


_LOGGER = logging.getLogger(__name__)


class Engine(Integration):
    """Engine Integration"""

    NAME = "Engine"
    DESCRIPTION = "Librosa based audio engine to drive scene changes"

    if LIBROSA_AVAILABLE:
        beta = False
    else:
        _LOGGER.error(
            f"{NAME} integration requires 'librosa' package. Please install it with 'uv sync --group=librosa' to use this integration."
        )
        beta = True

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default=NAME,
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default=DESCRIPTION,
            ): str,
            vol.Optional(
                "sample_window",
                description="Number of seconds to analyze",
                default=8,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=30)),
            vol.Optional(
                "ambient_threshold",
                description="Z-score threshold for ambient/breakdown mood states (very low energy). Default: -0.8, Range: -1.5 to -0.3",
                default=-0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=-1.5, max=-0.3)),
            vol.Optional(
                "peak_threshold",
                description="Z-score threshold for peak/intense mood states (higher = more extreme energy needed). Default: 0.7, Range: 0.3 to 1.5",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.3, max=1.5)),
            vol.Optional(
                "build_threshold",
                description="Z-score threshold for build mood state (energy/density rising). Default: 0.3, Range: 0.1 to 0.8",
                default=0.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=0.8)),
            vol.Optional(
                "chill_threshold",
                description="Z-score threshold below which energy is considered chill/relaxed. Default: -0.3, Range: -0.8 to 0.0",
                default=-0.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=-0.8, max=0.0)),
            vol.Optional(
                "diag",
                description="Enable basic diagnostic logging to teleplot",
                default=False,
            ): bool,
            vol.Optional(
                "debug",
                description="Enable debug logging to teleplot for tuning",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._data = {}

        # === New: IPC + async queue wiring ===
        self._librosa_client: LibrosaEngineClient | None = None
        self._audio_queue: asyncio.Queue | None = None
        self._audio_sender_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._previous_mood: str | None = None

    async def connect(self, msg=None):
        # TODO: why does editing an integration mark it as disabled?!?

        _LOGGER.warning(f"{self.NAME} integration connecting")
        if not LIBROSA_AVAILABLE:
            # Protecting here in case a config has been loaded with integration enabled.
            _LOGGER.error(
                f"{self.NAME} integration requires 'librosa' package. Please install it with 'uv sync --group=librosa' to use this integration."
            )
            # TODO: we need a more User facing way to handle failure to enable an extension
            return

        self._loop = asyncio.get_running_loop()

        # Set up IPC client and queue
        # LibrosaEngineClient will default to analysis_worker.py in its own directory
        self._librosa_client = LibrosaEngineClient(config=self._config)
        await self._librosa_client.start()
        self._librosa_client.add_callback(self._on_worker_features)

        self._audio_queue = asyncio.Queue()
        self._audio_sender_task = asyncio.create_task(
            self._audio_sender_loop()
        )

        # Subscribe to audio input source
        if hasattr(self._ledfx, "audio") and self._ledfx.audio is not None:
            self._ledfx.audio.subscribe(self.audio_callback)
            _LOGGER.warning(f"{self.NAME} subscribed to audio input")

        self.diag = self._config.get("diag", False)

        await super().connect()

    async def disconnect(self, msg=None):
        _LOGGER.warning(f"{self.NAME} integration disconnecting")

        # Unsubscribe from audio input source
        if hasattr(self._ledfx, "audio") and self._ledfx.audio is not None:
            self._ledfx.audio.unsubscribe(self.audio_callback)
            _LOGGER.warning(f"{self.NAME} unsubscribed from audio input")

        # Stop audio sender task
        if self._audio_sender_task:
            self._audio_sender_task.cancel()
            try:
                await self._audio_sender_task
            except asyncio.CancelledError:
                pass
            self._audio_sender_task = None

        # Stop worker process
        if self._librosa_client is not None:
            await self._librosa_client.stop()
            self._librosa_client = None

        self._audio_queue = None

        await super().disconnect()

    def on_shutdown(self):
        _LOGGER.warning(f"{self.NAME} integration shutting down")
        self.disconnect()

    async def on_delete(self):
        """
        Called when the integration is being destroyed/deleted.
        Ensures proper cleanup of resources.
        """
        _LOGGER.warning(
            f"{self.NAME} integration being deleted, cleaning up resources"
        )

        # If integration is active, deactivate and disconnect first
        if self._active:
            await self.disconnect()

    async def _audio_sender_loop(self):
        """
        Async task that drains the audio queue and forwards blocks
        to the librosa worker process.
        """
        assert self._audio_queue is not None
        while True:
            try:
                block = await self._audio_queue.get()
            except asyncio.CancelledError:
                break

            client = self._librosa_client
            if client is not None:
                try:
                    await client.send_audio_block(block)
                except Exception as e:
                    _LOGGER.warning("Error sending audio block: %r", e)

            self._audio_queue.task_done()

    async def _on_worker_features(self, msg: dict):
        """
        Async callback for feature updates from the worker.
        For now just logs; later this will update LedFx state / scenes.
        """
        if msg.get("type") == "feature_update":
            _LOGGER.warning("%s worker features: %r", self.NAME, msg)

            # Fire mood change event if mood has changed
            current_mood = msg.get("mood")
            if (
                current_mood is not None
                and current_mood != self._previous_mood
            ):
                self._ledfx.events.fire_event(
                    MoodChangedEvent(current_mood, self._previous_mood)
                )
                self._previous_mood = current_mood

            if self.diag:
                lines = []

                # Numeric / scalar series (time-based plots)
                for key, value in msg.items():
                    if key in ("type", "mood", "section_change"):
                        continue
                    # Teleplot numeric format: name:value
                    lines.append(f"{key}:{value}")

                # Mood as text telemetry
                mood = msg.get("mood")
                if mood is not None:
                    # Text format: name:value|t
                    lines.append(f"mood:{mood}|t")

                # Section change as 0/1 numeric series
                section_change = msg.get("section_change")
                if section_change is not None:
                    lines.append(f"section_change:{int(bool(section_change))}")

                if lines:
                    # Multiple telemetries must be separated by \n, not spaces
                    Teleplot.send("\n".join(lines))

    def audio_callback(self):
        """Process audio data callback from audio input."""
        audio_sample = self._ledfx.audio.audio_sample(raw=True)

        # Enqueue MIC_RATE mono block to send to worker
        if self._audio_queue is not None and self._loop is not None:
            # Ensure we have float32 array
            block = np.asarray(audio_sample, dtype=np.float32)

            try:
                # If audio_callback is on another thread, this is thread-safe
                self._loop.call_soon_threadsafe(
                    self._audio_queue.put_nowait,
                    block,
                )
            except Exception as e:
                _LOGGER.warning(
                    f"{self.NAME} error enqueueing audio block: {e!r}"
                )
