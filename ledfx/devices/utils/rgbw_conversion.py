import logging
from enum import Enum

import numpy as np

_LOGGER = logging.getLogger(__name__)


_CHANNEL_MAP = {"R": 0, "G": 1, "B": 2, "W": 3}

RGB_MAPPING = {"RGB", "RBG", "GRB", "GBR", "BRG", "BGR"}

WHITE_FUNCS_MAPPING = {
    "None": {"func": "add_white_none", "channels": 3},
    "Zero": {"func": "add_white_zero", "channels": 4},
    "Brighter": {"func": "add_white_brighter", "channels": 4},
    "Accurate": {"func": "add_white_accurate", "channels": 4},
}

# -------------------------------------------------------------------------------------
# Combined Output Mode Class
# -------------------------------------------------------------------------------------


class OutputMode:
    def __init__(self, rgb_order, white_mode):
        self.rgb_order = rgb_order
        self.indices = [_CHANNEL_MAP[c] for c in self.rgb_order]
        self.white_mode = white_mode

        self.channels_per_pixel = WHITE_FUNCS_MAPPING[self.white_mode][
            "channels"
        ]

        self.white_func = getattr(
            self, WHITE_FUNCS_MAPPING[self.white_mode]["func"]
        )

    def apply(self, rgb_array: np.ndarray) -> np.ndarray:
        """Applies white channel addition and channel reordering."""
        reordered = self.rgb_reorder(rgb_array)
        rgbw = self.white_func(reordered)
        return rgbw

    def rgb_reorder(self, rgb: np.ndarray) -> np.ndarray:
        return rgb[:, self.indices]

    # -------------------------------------------------------------------------------------
    # RGBW White Channel Conversion Functions
    # -------------------------------------------------------------------------------------

    def add_white_none(self, rgb: np.ndarray) -> np.ndarray:
        """Returns the RGB data unchanged, no white channel is added."""
        return rgb

    def add_white_zero(self, rgb: np.ndarray) -> np.ndarray:
        w = np.zeros((rgb.shape[0], 1), dtype=rgb.dtype)
        return np.concatenate([rgb, w], axis=1)

    def add_white_brighter(self, rgb: np.ndarray) -> np.ndarray:
        w = np.min(rgb, axis=1, keepdims=True)
        return np.concatenate([rgb, w], axis=1)

    def add_white_accurate(self, rgb: np.ndarray) -> np.ndarray:
        w = np.min(rgb, axis=1, keepdims=True)
        return np.concatenate([rgb - w, w], axis=1)
