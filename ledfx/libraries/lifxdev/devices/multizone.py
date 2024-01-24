#!/usr/bin/env python3

from __future__ import annotations

from ledfx.libraries.lifxdev.colors import color
from ledfx.libraries.lifxdev.devices import light
from ledfx.libraries.lifxdev.messages import multizone_messages, packet


class LifxMultiZone(light.LifxLight):
    """MultiZone device (beam, strip) control"""

    def __init__(self, *args, length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._num_zones: int | None = length

    def get_multizone(self) -> list[color.Hsbk]:
        """Get a list the colors on the MultiZone.

        Returns:
            List of human-readable HSBK tuples representing the device.
        """
        response = self.send_recv(
            multizone_messages.GetExtendedColorZones(), res_required=True
        )
        assert response is not None
        payload = response[0].payload
        self._num_zones = payload["count"]
        multizone_colors = payload["colors"][: self._num_zones]
        return [color.Hsbk.from_packet(cc) for cc in multizone_colors]

    def get_num_zones(self) -> int:
        """Get the number of zones that can be controlled"""
        if self._num_zones:
            return self._num_zones
        else:
            return len(self.get_multizone())

    def set_multizone(
        self,
        multizone_colors: list[color.Hsbk],
        *,
        duration: float = 0.0,
        index: int = 0,
        ack_required: bool = False,
    ) -> packet.LifxResponse | None:
        """Set the MultiZone colors.

        Args:
            multizone_colors: (list) A list of human-readable HSBK tuples to set.
            duration: (float) The time in seconds to make the color transition.
            index: (int) MultiZone starting position of the first element of colors.
            ack_required: (bool) True gets an acknowledgement from the device.
        """
        set_colors = multizone_messages.SetExtendedColorZones()
        set_colors["apply"] = multizone_messages.ApplicationRequest.APPLY
        set_colors["duration"] = int(duration * 1000)
        set_colors["index"] = index
        set_colors["colors_count"] = len(multizone_colors)
        for ii, hsbk in enumerate(multizone_colors):
            set_colors.set_value(
                "colors",
                color.Hsbk.from_tuple(hsbk)
                .max_brightness(self.max_brightness)
                .to_packet(),
                index + ii,
            )
        return self.send_msg(set_colors, ack_required=ack_required)
