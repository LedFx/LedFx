"""Benchmark-only sACN byte-buffer experiment; never installed by LedFx.

E131Device supplies lists of built-in ints after NumPy integer conversion.
This adapter converts those lists with bytes() (C-level range validation), then
uses a packet setter that can trust an immutable bytes buffer's element range.
It changes only the benchmark sender's output/packet instances, not global
library classes. This is evidence for an upstream API proposal, not a supported
replacement for arbitrary sACN input types or the production transport.
"""

from sacn.messages.data_packet import DataPacket
from sacn.sending.output import Output


class BytesDataPacket(DataPacket):
    @property
    def dmxData(self) -> tuple:
        return self._dmxData

    @dmxData.setter
    def dmxData(self, data):
        if not isinstance(data, bytes):
            # Keep the original semantics for all other callers.
            DataPacket.dmxData.fset(self, data)
            return
        if len(data) > 512:
            raise ValueError("DMX byte buffer exceeds 512 channels")
        self._dmxData = tuple(data) + (0,) * (512 - len(data))
        self.length = 126 + len(self._dmxData)


class BytesOutput(Output):
    @property
    def dmx_data(self) -> tuple:
        return self._packet.dmxData

    @dmx_data.setter
    def dmx_data(self, data):
        # The production E131Device.flush call supplies built-in Python ints.
        # bytes() rejects out-of-range channels instead of silently wrapping.
        self._packet.dmxData = bytes(data)
        self._changed = True


def enable_e131_bytes_prototype(device) -> None:
    """Opt in one benchmark sender; preserve library send/sync/lifecycle code."""
    for universe in range(device.config.universe, device.config.universe_end + 1):
        output = device._sacn[universe]
        output._packet.__class__ = BytesDataPacket
        output.__class__ = BytesOutput
