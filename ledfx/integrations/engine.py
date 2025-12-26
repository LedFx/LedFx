import logging
import time

import voluptuous as vol

from ledfx.integrations import Integration
from ledfx.effects.melbank import MIC_RATE

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    

_LOGGER = logging.getLogger(__name__)

LIBROSA_SAMPLE_RATE = 22050  # Standard sample rate for librosa
LIBROSA_RATIO = LIBROSA_SAMPLE_RATE / MIC_RATE


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
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._data = {}
        
        # Call rate tracking
        self._audio_call_count = 0
        self._last_log_time = time.time()
        
        # Resampler timing tracking
        self._resample_time_sum = 0.0
        self._resample_count = 0

    async def connect(self, msg=None):
        _LOGGER.error(f"{self.NAME} integration connecting")
        if not LIBROSA_AVAILABLE:
            # Protecting here in case a config has been loaded with integration enabled.
            _LOGGER.error(
                f"{self.NAME} integration requires 'librosa' package. Please install it with 'uv sync --group=librosa' to use this integration."
            )
            # TODO: we need a more User facing way to handle failure to enable an extension
            return
        
        # Subscribe to audio input source
        if hasattr(self._ledfx, 'audio') and self._ledfx.audio is not None:
            self._ledfx.audio.subscribe(self.audio_callback)
            _LOGGER.error(f"{self.NAME} subscribed to audio input")
        
        # TODO: launch the librosa process here
        
        await super().connect()

    async def disconnect(self, msg=None):
        _LOGGER.error(f"{self.NAME} integration disconnecting")
        
        # Unsubscribe from audio input source
        if hasattr(self._ledfx, 'audio') and self._ledfx.audio is not None:
            self._ledfx.audio.unsubscribe(self.audio_callback)
            _LOGGER.error(f"{self.NAME} unsubscribed from audio input")
        
        #TODO: shut down the librosa process here

        await super().disconnect()

    def on_shutdown(self):
        _LOGGER.error(f"{self.NAME} integration shutting down")

    def audio_callback(self):
        """Process audio data callback from audio input"""
        audio_sample = self._ledfx.audio.audio_sample(raw=True)
        # audio sample "raw" is already resampled to MIC_RATE and mono        
        librosa_sample = self._ledfx.audio.resampler.process(
                audio_sample,
                LIBROSA_RATIO)

        # diagnostic follows
        self._audio_call_count += 1
        
        current_time = time.time()
        elapsed = current_time - self._last_log_time

        # Log call rate every 1 second
        if elapsed >= 1.0:
            self._last_log_time = current_time
            _LOGGER.error(f"{self.NAME} audio sample length: {len(audio_sample)}")
            _LOGGER.error(f"{self.NAME} sample length: {len(librosa_sample)}")
    
        # TODO: send to librosa process as a binary block over stdio
        
