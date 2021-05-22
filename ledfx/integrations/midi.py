# from ledfx.utils import RegistryLoader, async_fire_and_forget, async_fire_and_return, async_callback
# from ledfx.events import Event
# import importlib
# import pkgutil
import logging

import mido

# import aiohttp
# import asyncio
import voluptuous as vol

from ledfx.integrations import Integration

# import numpy as np


# import time
# import os
# import re

_LOGGER = logging.getLogger(__name__)
MIDO_INPUT_SUFFIX = " 0"
MIDO_OUTPUT_SUFFIX = " 1"

MIDO_MESSAGE_TYPES = mido.messages.messages.SPEC_BY_TYPE.keys()

mido.messages.checks._CHECKS
mido.messages.specs.SPECS

validate_byte = vol.All(int, vol.Range(0, 127))
validators = {
    "type": vol.In(MIDO_MESSAGE_TYPES),
    "data": [validate_byte],
    "channel": vol.All(int, vol.Range(0, 15)),
    "control": validate_byte,
    "frame_type": vol.All(int, vol.Range(0, 7)),
    "frame_value": vol.All(int, vol.Range(0, 15)),
    "note": validate_byte,
    "pitch": vol.All(int, vol.Range(-8192, 8191)),
    "pos": vol.All(int, vol.Range(0, 16383)),
    "program": validate_byte,
    "song": validate_byte,
    "value": validate_byte,
    "velocity": validate_byte,
    "time": vol.Coerce(float),
}


def create_midimsg_schema(msgtype):
    value_names = next(
        spec["value_names"]
        for spec in mido.messages.specs.SPECS
        if spec["type"] == msgtype
    )
    schema = vol.Schema(
        {value_name: validators[value_name] for value_name in value_names}
    )


def list_midi_devices():
    input_devices = mido.get_input_names()
    return input_devices if input_devices else ["No devices..."]


MIDO_INPUT_SUFFIX = " 0"
MIDO_OUTPUT_SUFFIX = " 1"

MIDO_MESSAGE_TYPES = mido.messages.messages.SPEC_BY_TYPE.keys()

mido.messages.checks._CHECKS
mido.messages.specs.SPECS

validate_byte = vol.All(int, vol.Range(0, 127))
validators = {
    "type": vol.In(MIDO_MESSAGE_TYPES),
    "data": [validate_byte],
    "channel": vol.All(int, vol.Range(0, 15)),
    "control": validate_byte,
    "frame_type": vol.All(int, vol.Range(0, 7)),
    "frame_value": vol.All(int, vol.Range(0, 15)),
    "note": validate_byte,
    "pitch": vol.All(int, vol.Range(-8192, 8191)),
    "pos": vol.All(int, vol.Range(0, 16383)),
    "program": validate_byte,
    "song": validate_byte,
    "value": validate_byte,
    "velocity": validate_byte,
    "time": vol.Coerce(float),
}


def create_midimsg_schema(msgtype):
    value_names = next(
        spec["value_names"]
        for spec in mido.messages.specs.SPECS
        if spec["type"] == msgtype
    )
    schema = vol.Schema(
        {value_name: validators[value_name] for value_name in value_names}
    )


def list_midi_devices():
    input_devices = mido.get_input_names()
    return input_devices if input_devices else ["No devices..."]


class MIDI(Integration):
    """MIDI Integration"""

    NAME = "MIDI"
    DESCRIPTION = "Control LedFx with a MIDI device"

    @property
    def CONFIG_SCHEMA(self):
        return vol.Schema(
            {
                vol.Required(
                    "name",
                    description="Name of this integration instance (ie. name of the MIDI device)",
                    default=f"{list_midi_devices()[0].rstrip(MIDO_INPUT_SUFFIX)}",
                ): str,
                vol.Required(
                    "description",
                    description="Description of this integration",
                    default=f"MIDI mappings for {list_midi_devices()[0].rstrip(MIDO_INPUT_SUFFIX)}",
                ): str,
                vol.Required(
                    "port_name",
                    description="MIDI device",
                    default=list_midi_devices()[0],
                ): vol.In(list_midi_devices()),
            }
        )

    MIDI_MESSAGE_SCHEMA = vol.Schema(
        {
            vol.Required(
                "type",
                description="MIDI message type",
                default="note_on",
            ): vol.In(MIDO_MESSAGE_TYPES),
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._data = {}

        self.restore_from_data(data)

    def restore_from_data(self, data):
        """ Might be used in future """
        self._data = data

    def get_triggers(self):
        return self._data

    def add_trigger(self, scene_id, song_id, song_name, song_position):
        """ Add a trigger to saved triggers"""
        trigger_id = f"{song_id}-{str(song_position)}"
        if scene_id not in self._data.keys():
            self._data[scene_id] = {}
        self._data[scene_id][trigger_id] = [song_id, song_name, song_position]

    def delete_trigger(self, trigger_id):
        """ Delete a trigger from saved triggers"""
        for scene_id in self._data.keys():
            if trigger_id in self._data[scene_id].keys():
                del self._data[scene_id][trigger_id]

    def print_message(self, message):
        _LOGGER.info(f"Received: {message}")

    async def connect(self):
        port = self._config["port_name"]

        try:
            self._midi_port = mido.open_input(
                port if port else None, callback=self.print_message
            )
        except OSError:
            _LOGGER.error(
                f"Invalid MIDI device: {port}. Valid devices: {mido.get_input_names()}"
            )
            return
        except SystemError:
            _LOGGER.error(
                f"Failed to open MIDI port on {port}. Are other applications using this device?"
            )
            return
        await super().connect(f"Opened MIDI port on {port}")

    async def disconnect(self):
        self._midi_port.reset()
        self._midi_port.close()
        await super().disconnect(
            f"Closed MIDI port on {self._config['port_name']}"
        )
