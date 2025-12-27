"""
Shared IPC protocol definitions for librosa engine worker communication.

This module defines the binary protocol used between the main LedFx process
and the analysis worker subprocess.
"""

import struct

# Binary message header format: <msg_type: uint8><payload_len: uint32>
HEADER_STRUCT = struct.Struct("<BI")

# Message type constants
MSG_TYPE_AUDIO = 1  # Audio block (float32 PCM data)
MSG_TYPE_CONFIG = 2  # Configuration (JSON)
MSG_TYPE_SHUTDOWN = 255  # Graceful shutdown

# Default configuration
LEDFX_RATE = 30000  # LedFx audio sample rate
LIBROSA_SAMPLE_RATE = (
    22050  # Standard sample rate for librosa (if resampling needed)
)
LIBROSA_RESAMPLE_RATIO = LIBROSA_SAMPLE_RATE / LEDFX_RATE
