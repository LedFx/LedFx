#!/usr/bin/env python3

from __future__ import annotations

from ledfx.libraries.lifxdev.colors import color
from ledfx.libraries.lifxdev.devices import device
from ledfx.libraries.lifxdev.messages import light_messages, packet

COLOR_T = tuple[float, float, float, int]


class LifxLight(device.LifxDevice):
    """Light control"""

    def __init__(
        self, *args, label: str, max_brightness: float = 1.0, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._label = label
        self.max_brightness = max_brightness

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, _: str):
        raise RuntimeError("Label can only be set on init.")

    @property
    def max_brightness(self) -> float:
        return self._max_brightness

    @max_brightness.setter
    def max_brightness(self, value: float) -> None:
        if value <= 0:
            raise ValueError("Max brightness must be greater than zero.")
        elif value > 1:
            raise ValueError(
                "Max brightness must be less than or equal to one."
            )
        self._max_brightness = float(value)

    def get_color(self) -> color.Hsbk:
        """Get the color of the device

        Returns:
            The human-readable HSBK of the light.
        """
        response = self.send_recv(light_messages.Get(), res_required=True)
        assert response is not None
        return color.Hsbk.from_packet(response.pop().payload["color"])

    def get_power(self) -> bool:
        """Get the power state of the light.

        Returns:
            True if the light is powered on. False if off.
        """
        response = self.send_recv(light_messages.GetPower(), res_required=True)
        assert response is not None
        return response.pop().payload["level"]

    def set_color(
        self,
        hsbk: color.Hsbk | COLOR_T,
        *,
        duration: float = 0.0,
        ack_required: bool = False,
    ) -> packet.LifxResponse | None:
        """Set the color of the light.

        Args:
            hsbk: (color.Hsbk) Human-readable HSBK tuple.
            duration: (float) The time in seconds to make the color transition.
            ack_required: (bool) True gets an acknowledgement from the light.

        Returns:
            If ack_required, get an acknowledgement LIFX response tuple.
        """
        hsbk = color.Hsbk.from_tuple(hsbk).max_brightness(self.max_brightness)
        set_color_msg = light_messages.SetColor(
            color=hsbk.to_packet(),
            duration=int(duration * 1000),
        )
        return self.send_msg(set_color_msg, ack_required=ack_required)

    def set_power(
        self,
        state: bool,
        *,
        duration: float = 0.0,
        ack_required: bool = False,
    ) -> packet.LifxResponse | None:
        """Set power state on the bulb.

        Args:
            state: (bool) True powers on the light. False powers it off.
            duration: (float) The time in seconds to make the color transition.
            ack_required: (bool) True gets an acknowledgement from the light.

        Returns:
            If ack_required, get an acknowledgement LIFX response tuple.
        """
        power = light_messages.SetPower(
            level=state, duration=int(duration * 1000)
        )
        return self.send_msg(power, ack_required=ack_required)


class LifxInfraredLight(LifxLight):
    """Light with IR control"""

    def get_infrared(self) -> float:
        """Get the current infrared level with 1.0 being the maximum."""
        response = self.send_recv(
            light_messages.GetInfrared(), res_required=True
        )
        assert response is not None
        ir_state = response.pop().payload
        return ir_state["brightness"] / ir_state.get_max("brightness")

    def set_infrared(
        self, brightness: float, *, ack_required: bool = False
    ) -> packet.LifxResponse | None:
        """Set the infrared level on the bulb.

        Args:
            brightness: (float) IR brightness level. 1.0 is the maximum.
            ack_required: (bool) True gets an acknowledgement from the light.

        Returns:
            If ack_required, get an acknowledgement LIFX response tuple.
        """
        ir = light_messages.SetInfrared()
        max_brightness = ir.get_max("brightness")
        ir["brightness"] = int(brightness * max_brightness)
        return self.send_msg(ir, ack_required=ack_required)
