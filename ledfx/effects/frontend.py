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
        self._cached_client_id = None
        self._rejected_client_ids = set()
        self._frame_count = 0
        self._fps_last_time = None
        self._fps_report_interval = 5.0  # Report FPS every 5 seconds

    def on_activate(self, pixel_count):
        """Called when effect is activated - register event listener"""

        # Define the callback for frontend visualiser data events
        def handle_frontend_visualiser_data(event):
            """Callback for frontend_visualiser_data events - does the actual pixel processing"""
            if not hasattr(event, "pixels") or event.pixels is None:
                return

            # Handle client ID caching to prevent multiple frontends from interfering
            if hasattr(event, "client_id") and event.client_id:
                if self._cached_client_id is None:
                    # Cache the first client ID we receive
                    self._cached_client_id = event.client_id
                    _LOGGER.info(
                        f"Frontend effect: cached client ID {event.client_id}"
                    )
                elif self._cached_client_id != event.client_id:
                    # Ignore updates from other client IDs, warn only once per client
                    if event.client_id not in self._rejected_client_ids:
                        self._rejected_client_ids.add(event.client_id)
                        _LOGGER.warning(
                            f"Frontend effect: ignoring updates from client {event.client_id}, "
                            f"already bound to client {self._cached_client_id}"
                        )
                    return

            # FPS tracking
            current_time = time.time()
            if self._fps_last_time is None:
                self._fps_last_time = current_time
                self._frame_count = 0

            self._frame_count += 1
            elapsed = current_time - self._fps_last_time

            if elapsed >= self._fps_report_interval:
                fps = self._frame_count / elapsed
                _LOGGER.info(
                    f"Frontend effect: receiving {fps:.1f} FPS from client {self._cached_client_id}"
                )
                self._frame_count = 0
                self._fps_last_time = current_time

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
                    processed_pixels = resized_pixels
                else:
                    # Shapes match - need to flatten from [rows, cols, 3] to [N, 3]
                    flattened = vis_pixels.reshape(-1, 3)
                    processed_pixels = flattened

                # Apply rotation if this is a 2D matrix (rows > 1)
                if rows > 1:
                    rotation = self._virtual.config.get("rotate", 0)
                    if rotation != 0:
                        # Reshape back to 2D matrix for rotation
                        matrix_pixels = processed_pixels.reshape(
                            target_shape[0], target_shape[1], 3
                        )
                        # Apply rotation: rot90 rotates counter-clockwise, k=rotation gives us 0°, 90°, 180°, 270°
                        rotated = np.rot90(matrix_pixels, k=rotation)
                        # Flatten back to [N, 3]
                        processed_pixels = rotated.reshape(-1, 3)

                with self.lock:
                    self.pixels[:] = processed_pixels

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

        # Reset cached client ID and rejected list for next session
        self._cached_client_id = None
        self._rejected_client_ids.clear()
        self._frame_count = 0
        self._fps_last_time = None

        super().deactivate()

    def config_updated(self, config):
        """Called when configuration is updated"""
        pass

    def effect_loop(self):
        """Main rendering loop - minimal work, pixels updated by event callback"""
        # Pixels are updated directly in the event callback
        # This loop just keeps the effect running
        pass
