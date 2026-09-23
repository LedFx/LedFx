"""Snapcast audio source integration for LedFx.

LedFx connects to a snapserver as a regular Snapcast client and uses the
received audio as an audio input.  Each configured server appears in the
audio device list as "SNAPCAST: <server id>".

Supported stream codecs are flac (snapserver's default, requires pyFLAC) and
pcm.  Implemented in pure Python, so it is always available.
"""

from ledfx.snapcast.stream import SnapcastAudioStream  # noqa: F401

__all__ = ["SnapcastAudioStream"]
