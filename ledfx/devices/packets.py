"""Packet construction for transports owned by LedFx and their SDKs."""

import numpy as np
from ledfx_senders.encoders import encode_adalight, encode_openrgb
from numpy.typing import NDArray


def build_adalight_packet(data: NDArray[np.generic], color_order: str) -> bytes:
    """Adalight RGB frame with protocol-defined inclusive count (N - 1)."""
    return encode_adalight(data, color_order)


def build_openrgb_packet(data: NDArray[np.generic], device_id: int) -> bytes:
    """OpenRGB v3 UPDATELEDS; the existing SDK owns the TCP session."""
    return encode_openrgb(data, device_id)
