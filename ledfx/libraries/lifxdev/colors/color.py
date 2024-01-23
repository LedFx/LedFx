#!/usr/bin/env python3

from __future__ import annotations

import dataclasses

from ledfx.libraries.lifxdev.messages import packet

KELVIN = 5500


@dataclasses.dataclass
class Hsbk:
    """Human-readable HSBK tuple"""

    hue: float
    saturation: float
    brightness: float
    kelvin: int

    @classmethod
    def from_packet(cls, hsbk: packet.Hsbk) -> Hsbk:
        """Create a HSBK tuple from a message packet"""
        max_hue = hsbk.get_max("hue") + 1
        max_saturation = hsbk.get_max("saturation")
        max_brightness = hsbk.get_max("brightness")

        hue = 360 * hsbk["hue"] / max_hue
        saturation = hsbk["saturation"] / max_saturation
        brightness = hsbk["brightness"] / max_brightness
        kelvin = hsbk["kelvin"]

        return cls(
            hue=hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=kelvin,
        )

    @classmethod
    def from_tuple(cls, hsbk: tuple | Hsbk) -> Hsbk:
        """Create a HSBK tuple from a normal tuple. Assume input is human-readable"""
        if isinstance(hsbk, Hsbk):
            return hsbk
        hue, saturation, brightness, kelvin = hsbk
        return cls(
            hue=hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=kelvin,
        )

    def max_brightness(self, brightness: float) -> Hsbk:
        """Force the brightness to be at most a specific value"""
        if self.brightness > brightness:
            return dataclasses.replace(self, brightness=brightness)
        return self

    def to_packet(self) -> packet.Hsbk:
        """Create a message packet from an HSBK tuple"""
        hsbk = packet.Hsbk()
        max_hue = hsbk.get_max("hue") + 1
        max_saturation = hsbk.get_max("saturation")
        max_brightness = hsbk.get_max("brightness")

        hsbk["hue"] = int(self.hue * max_hue / 360) % max_hue
        hsbk["saturation"] = min(
            int(self.saturation * max_saturation), max_saturation
        )
        hsbk["brightness"] = min(
            int(self.brightness * max_brightness), max_brightness
        )
        hsbk["kelvin"] = int(self.kelvin)
        return hsbk
