from enum import Enum

import numpy as np

# -------------------------------------------------------------------------------------
# RGBW Conversion Functions
# -------------------------------------------------------------------------------------


def passthrough(rgb_array: np.ndarray) -> np.ndarray:
    """
    Return the input RGB array unchanged.
    Used for RGB-only devices or reordering-only modes.

    Parameters:
        rgb_array (np.ndarray): An (N, 3) array of RGB values.

    Returns:
        np.ndarray: The same (N, 3) array.
    """
    return rgb_array


def add_white_none(rgb_array: np.ndarray) -> np.ndarray:
    """
    Add a zero white channel to the RGB data.

    Parameters:
        rgb_array (np.ndarray): An (N, 3) array of RGB values.

    Returns:
        np.ndarray: An (N, 4) RGBW array with W = 0.
    """
    n = rgb_array.shape[0]
    w = np.zeros((n, 1), dtype=rgb_array.dtype)
    return np.concatenate([rgb_array, w], axis=1)


def add_white_brighter(rgb_array: np.ndarray) -> np.ndarray:
    """
    Add a white channel using the minimum of R, G, and B.
    Does not subtract white from RGB, resulting in a brighter image.

    Parameters:
        rgb_array (np.ndarray): An (N, 3) RGB array.

    Returns:
        np.ndarray: An (N, 4) RGBW array.
    """
    w = np.min(rgb_array, axis=1, keepdims=True)
    return np.concatenate([rgb_array, w], axis=1)


def add_white_accurate(rgb_array: np.ndarray) -> np.ndarray:
    """
    Add a white channel using the minimum of R, G, and B.
    Subtracts white from RGB to maintain color fidelity.

    Parameters:
        rgb_array (np.ndarray): An (N, 3) RGB array.

    Returns:
        np.ndarray: An (N, 4) RGBW array.
    """
    w = np.min(rgb_array, axis=1, keepdims=True)
    rgb = rgb_array - w
    return np.concatenate([rgb, w], axis=1)


# -------------------------------------------------------------------------------------
# OutputMode Enum
# -------------------------------------------------------------------------------------

# Static channel index mapping
_CHANNEL_MAP = {"R": 0, "G": 1, "B": 2, "W": 3}


class OutputMode(str, Enum):
    """
    Enum representing LED color output modes.

    Each mode defines:
    - A string identifier (used in config)
    - A conversion function to apply to RGB data
    - A channel order string for output formatting
    - A flag indicating if the mode is reordering-only
    """

    RGB = ("RGB", passthrough, "RGB", False, 3)
    RBG = ("RBG", passthrough, "RBG", True, 3)
    GRB = ("GRB", passthrough, "GRB", True, 3)
    GBR = ("GBR", passthrough, "GBR", True, 3)
    BRG = ("BRG", passthrough, "BRG", True, 3)
    BGR = ("BGR", passthrough, "BGR", True, 3)

    RGBW_NONE = ("RGBW No White", add_white_none, "RGBW", False, 4)
    RGBW_BRIGHTER = ("RGBW Brighter", add_white_brighter, "RGBW", False, 4)
    RGBW_ACCURATE = ("RGBW Accurate", add_white_accurate, "RGBW", False, 4)

    def __new__(cls, *args):
        if len(args) == 1:
            desc = args[0]
            return cls._value2member_map_[desc]

        desc, func, order, is_reorder_only, cpp = args
        obj = str.__new__(cls, desc)
        obj._value_ = desc
        obj.converter = func
        obj.order = order
        obj.is_reorder_only = is_reorder_only
        obj.channels_per_pixel = cpp
        return obj

    def apply(self, rgb_array: np.ndarray) -> np.ndarray:
        """
        Convert and reorder the input RGB array using the current mode.

        Parameters:
            rgb_array (np.ndarray): An (N, 3) array of RGB values.

        Returns:
            np.ndarray: An (N, 3 or 4) reordered output array.
        """
        array = self.converter(rgb_array)
        indices = [_CHANNEL_MAP[c] for c in self.order]
        return array[:, indices]

    @classmethod
    def from_value(cls, value: str) -> "OutputMode":
        """
        Get the enum member matching the given string value.

        Parameters:
            value (str): The value to match (e.g., "RGBW Brighter").

        Returns:
            OutputMode: The corresponding enum member.

        Raises:
            ValueError: If no matching member is found.
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid OutputMode value: {value}")

    @classmethod
    def values(cls, reordering_enabled: bool = True) -> list[str]:
        """
        Get a list of available mode values, optionally filtering out reorder-only modes.

        Parameters:
            reordering_enabled (bool): Whether to include reorder-only modes.

        Returns:
            list[str]: A list of mode values (strings).
        """
        return [
            m.value for m in cls if reordering_enabled or not m.is_reorder_only
        ]

    @classmethod
    def valid_modes(
        cls, reordering_enabled: bool = True
    ) -> list["OutputMode"]:
        """
        Get a list of enum members, optionally filtering out reorder-only modes.

        Parameters:
            reordering_enabled (bool): Whether to include reorder-only modes.

        Returns:
            list[OutputMode]: A list of OutputMode members.
        """
        return [m for m in cls if reordering_enabled or not m.is_reorder_only]
