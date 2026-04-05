import logging
import time

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)


class FrontendEffect(Twod):
    """
    Frontend effect that receives pixel data from the frontend visualiser
    and displays it on the LED matrix using the Twod pipeline for
    rotation and flip support.
    """

    NAME = "Frontend"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "background_brightness",
        "test",
        "background_mode",
    ]

    CONFIG_SCHEMA = vol.Schema({})

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._event_listener = None
        self._cached_client_id = None
        self._rejected_client_ids = set()
        self._last_client_frame_time = None
        self._client_timeout = (
            3.0  # seconds before cached client is considered gone
        )
        self._incoming_pixels = None  # latest raw numpy array from frontend

    def _handle_visualiser_data(self, event):
        """Process incoming frontend visualiser data events."""
        if not hasattr(event, "pixels") or event.pixels is None:
            return

        # Handle client ID caching to prevent multiple frontends from interfering.
        # If no data has been received from the cached client within the timeout,
        # treat it as gone and accept the new client (handles page refresh).
        if hasattr(event, "client_id") and event.client_id:
            current_time = time.time()
            cached_client_timed_out = (
                self._cached_client_id is not None
                and self._cached_client_id != event.client_id
                and self._last_client_frame_time is not None
                and (current_time - self._last_client_frame_time)
                > self._client_timeout
            )

            if self._cached_client_id is None or cached_client_timed_out:
                if cached_client_timed_out:
                    _LOGGER.info(
                        "Frontend effect: cached client %s timed out, switching to client %s",
                        self._cached_client_id,
                        event.client_id,
                    )
                else:
                    _LOGGER.info(
                        "Frontend effect: cached client ID %s",
                        event.client_id,
                    )
                self._cached_client_id = event.client_id
                self._rejected_client_ids.clear()
            elif self._cached_client_id != event.client_id:
                if event.client_id not in self._rejected_client_ids:
                    self._rejected_client_ids.add(event.client_id)
                    _LOGGER.warning(
                        "Frontend effect: ignoring updates from client %s, already bound to client %s",
                        event.client_id,
                        self._cached_client_id,
                    )
                return

            self._last_client_frame_time = current_time

        # Store latest pixels for draw() to consume on the next render tick
        self._incoming_pixels = event.pixels

    def on_activate(self, pixel_count):
        """Called when effect is activated - register event listener"""
        self._event_listener = self._ledfx.events.add_listener(
            self._handle_visualiser_data,
            Event.FRONTEND_VISUALISER_DATA,
        )

        _LOGGER.info(
            "Frontend effect activated and listening for visualiser data"
        )

    def draw(self):
        """Called by Twod.render() — paste the latest frontend pixels into self.matrix."""
        if self._incoming_pixels is None:
            return

        src = Image.fromarray(self._incoming_pixels.astype(np.uint8))
        if src.size != (self.r_width, self.r_height):
            src = src.resize((self.r_width, self.r_height), Image.BILINEAR)
        self.matrix.paste(src)

    def deactivate(self):
        """Called when effect is deactivated - clean up event listener"""
        if self._event_listener is not None:
            _LOGGER.info("Frontend effect deactivating, removing listener")
            self._event_listener()
            self._event_listener = None

        self._cached_client_id = None
        self._rejected_client_ids.clear()
        self._last_client_frame_time = None
        self._incoming_pixels = None

        super().deactivate()

    def config_updated(self, config):
        super().config_updated(config)
