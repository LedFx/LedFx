"""Packet construction for transports owned by LedFx and their SDKs."""

from ledfx_senders import Frame
from ledfx_senders.encoders import encode_adalight, encode_openrgb


def build_adalight_packet(data: Frame, color_order: str) -> bytes:
    """Adalight RGB frame with protocol-defined inclusive count (N - 1)."""
    return encode_adalight(data, color_order)


def build_openrgb_packet(data: Frame, device_id: int) -> bytes:
    """OpenRGB v3 UPDATELEDS; the existing SDK owns the TCP session."""
    return encode_openrgb(data, device_id)
