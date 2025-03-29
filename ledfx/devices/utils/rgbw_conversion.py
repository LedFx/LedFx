from enum import Enum

import numpy as np


class WhiteChannelComputation(str, Enum):
    """Enum for different white channel computation methods."""

    NONE = "None"  # No white channel, just set to 0
    ACCURATE = "Accurate"  # Color accuracy approach (minimum RGB)
    BRIGHTER = "Brighter"  # Compute white, but don't subtract from RGB


def rgb_to_rgbw(
    rgb_array, white_channel_computation=WhiteChannelComputation.ACCURATE
):
    """
    Convert RGB array to RGBW array using the specified white channel computation method.

    Parameters:
    - rgb_array: NumPy array of shape (n, 3) representing RGB data
    - white_channel_computation: Method to use for computing the white channel

    Returns:
    - rgbw_array: NumPy array of shape (n, 4) representing RGBW data
    """
    # Ensure the input is properly shaped
    assert rgb_array.shape[1] == 3, "Input array must have shape (n, 3)"

    # Number of RGB values
    n = rgb_array.shape[0]

    # Create the white channel based on the selected method
    if white_channel_computation == WhiteChannelComputation.NONE:
        # No white channel, just zeros
        w = np.zeros((n, 1), dtype=rgb_array.dtype)
        rgb_adjusted = rgb_array.copy()

    elif white_channel_computation == WhiteChannelComputation.BRIGHTER:
        # Brighter method: use min value for white, don't subtract from RGB
        w = np.min(rgb_array, axis=1, keepdims=True)
        rgb_adjusted = rgb_array

    elif white_channel_computation == WhiteChannelComputation.ACCURATE:
        # Accurate method: use min value for white, subtract from RGB
        w = np.min(rgb_array, axis=1, keepdims=True)
        rgb_adjusted = rgb_array - w

    else:
        raise ValueError(
            f"Unknown white channel computation method: {white_channel_computation}"
        )

    # Concatenate RGB and W channels
    rgbw_array = np.concatenate((rgb_adjusted, w), axis=1)

    return rgbw_array
