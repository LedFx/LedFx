import logging
import time

import numpy as np
import voluptuous as vol

from ledfx.effects.temporal import TemporalEffect
from ledfx.events import Event
from ledfx.utils import resize_pixels

_LOGGER = logging.getLogger(__name__)


class FrontendEffect(TemporalEffect):
    """
    Frontend effect that listens to frontend_visualiser_data events
    """

    NAME = "Frontend"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS = ["background_brightness", "blur", "mirror"]

    CONFIG_SCHEMA = vol.Schema({})

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._event_listener = None

    def on_activate(self, pixel_count):
        """Called when effect is activated - register event listener"""

        # Define the callback for frontend visualiser data events
        def handle_frontend_visualiser_data(event):
            """Callback for frontend_visualiser_data events - does the actual pixel processing"""
            if not hasattr(event, "pixels") or event.pixels is None:
                return

            vis_pixels = event.pixels
            vis_shape = (
                event.shape
                if hasattr(event, "shape")
                else (1, len(vis_pixels))
            )

            try:
                # Calculate our target shape based on virtual configuration
                rows = self._virtual.config.get("rows", 1)
                if rows > 1:
                    # 2D matrix
                    cols = self.pixel_count // rows
                    target_shape = (rows, cols)
                else:
                    # 1D strip
                    target_shape = (1, self.pixel_count)

                incoming_total = (
                    vis_shape[0] * vis_shape[1]
                    if len(vis_shape) >= 2
                    else len(vis_pixels)
                )

                if (
                    vis_shape != target_shape
                    or incoming_total != self.pixel_count
                ):
                    # resize_pixels will handle the [rows, cols, 3] format and return [N, 3]
                    resized_pixels = resize_pixels(
                        vis_pixels, vis_shape, target_shape
                    )
                    with self.lock:
                        self.pixels[:] = resized_pixels
                else:
                    # Shapes match - need to flatten from [rows, cols, 3] to [N, 3]
                    flattened = vis_pixels.reshape(-1, 3)
                    with self.lock:
                        self.pixels[:] = flattened

            except Exception as e:
                _LOGGER.error(
                    f"Error processing visualisation data: {e}", exc_info=True
                )

        # Register the listener with the event system, filtered to only our vis_id
        self._event_listener = self._ledfx.events.add_listener(
            handle_frontend_visualiser_data,
            Event.FRONTEND_VISUALISER_DATA,
            event_filter={"vis_id": "visualiser-capture"},
        )

        _LOGGER.info(
            "Frontend effect activated and listening for visualiser data"
        )

    def deactivate(self):
        """Called when effect is deactivated - clean up event listener"""
        if self._event_listener is not None:
            _LOGGER.info("Frontend effect deactivating, removing listener")
            self._event_listener()  # Call the removal function
            self._event_listener = None

        super().deactivate()

    def config_updated(self, config):
        """Called when configuration is updated"""
        pass

    def effect_loop(self):
        """Main rendering loop - minimal work, pixels updated by event callback"""
        # Pixels are updated directly in the event callback
        # This loop just keeps the effect running
        pass
