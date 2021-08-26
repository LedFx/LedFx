# from ledfx.events import Event
# import importlib
# import pkgutil
import asyncio
import json
import logging
import os
from functools import partial
from itertools import zip_longest

import mido
import mido.frozen as frozen
import numpy as np
import rtmidi
import voluptuous as vol

from ledfx.config import get_default_config_directory
from ledfx.integrations import Integration
from ledfx.utils import async_fire_and_forget

# some thoughts

# some desired functionality examples
# - apply one effect to all displays
# - choose from effect presets (tied to displays)
# - choose from scenes (not tied to anything) [1d input type 0]
# - blur all displays on a single slider
# - blackout button

# 2D layouts (choice/choice)
# 1D layouts (choice or options)
# 0D layouts (option)

# choices:
# options:

# EFFECTS
# input type:
# 0: flip, mirror
# 1: blur, brightness, (bkg_brightness?), gradient, colour (lot of variation)
# 2: colour?
# -: SPECIFIC EFFECT PARAMETERS
# -: strobe decay would be example param to adjust

# DISPLAYS
# input type:
# 0: preview_only
# 1: transition_time


# DIMENSIONALITY 1:
# input type
#

# DIMENSIONALITY 0:
# input type
# 0: queue_hold (IMPORTANT!)
# 0: blackout
# 1: global brightness/blur/(any input type 1) (global can be applied to all?)


_LOGGER = logging.getLogger(__name__)

MIDO_MESSAGE_TYPES = mido.messages.messages.SPEC_BY_TYPE.keys()

REGION_DIMENSIONS = [
    "A single input (eg. lone button, knob)",
    "A row of inputs (eg. a small collection of buttons, faders)",
    "A matrix of inputs (eg. a grid of buttons, axis corresponding to display and effect respectively)",
]

INPUT_TYPES = [
    "On/Off (button, pressable knob)",
    "Continous with hard start+stop (fader, slider, knob with limits)",
    "Continous with no start or end (wheel, knob, continuous rotation)",
]

INPUT_VISUAL_STATES = [
    "Unassigned         [input has no function]",
    "Assigned, inactive [input has function, but not doing it]",
    "Assigned, active   [input is doing its function]",
]

validate_byte = vol.All(int, vol.Range(0, 127))
VALIDATORS = {
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
        {value_name: VALIDATORS[value_name] for value_name in value_names}
    )


def create_midimsg_schema(msgtype):
    value_names = next(
        spec["value_names"]
        for spec in mido.messages.specs.SPECS
        if spec["type"] == msgtype
    )
    schema = vol.Schema(
        {value_name: VALIDATORS[value_name] for value_name in value_names}
    )


def list_midi_mappings():
    config_dir = get_default_config_directory()
    return [
        f
        for f in os.listdir(config_dir)
        if os.path.isfile(os.path.join(config_dir, f))
        and f.startswith("LedFxMidiMap")
        and f.endswith(".json")
    ]


def list_midi_devices():
    in_ports = [name.rstrip(" 0123456789") for name in mido.get_input_names()]
    out_ports = [
        name.rstrip(" 0123456789") for name in mido.get_output_names()
    ]

    return list(set(in_ports) & set(out_ports))


class MIDI(Integration):
    """MIDI Integration"""

    NAME = "MIDI"
    DESCRIPTION = "Control LedFx with a MIDI device"

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        """dynamic config schema"""
        midi_devices = list_midi_devices()
        midi_mappings = list_midi_mappings()
        try:
            midi_devices = list_midi_devices()
            midi_mappings = list_midi_mappings()
        except rtmidi._rtmidi.SystemError as e:
            _LOGGER.error(f"Unable to enumerate midi devices: {e}")
            return vol.Schema({})

        if not midi_devices:
            # raise Exception("No MIDI devices are connected.")
            return vol.Schema({}, extra=vol.ALLOW_EXTRA)
        if not midi_mappings:
            # raise Exception("No MIDI mappings in config.")
            return vol.Schema({}, extra=vol.ALLOW_EXTRA)
        try:
            midi_mapping_guess = next(
                i
                for i, x in enumerate(midi_mappings)
                if x.lstrip("LedFxMidiMap ").rstrip(".json").lower()
                in midi_devices[0]
            )
        except StopIteration:
            midi_mapping_guess = midi_mappings[0]

        return vol.Schema(
            {
                vol.Required(
                    "name",
                    description="Name of this integration instance (ie. name of the MIDI device)",
                    default=f"{midi_devices[0]}",
                ): str,
                vol.Required(
                    "description",
                    description="Description of this integration",
                    default=f"MIDI mappings for {midi_devices[0]}",
                ): str,
                vol.Required(
                    "midi_device",
                    description="MIDI device",
                    default=midi_devices[0],
                ): vol.In(midi_devices),
                vol.Required(
                    "midi_mapping",
                    description="MIDI Mapping File",
                    default=midi_mapping_guess,
                ): vol.In(midi_mappings),
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

    # This schema is not complete, just checks the basics are there.
    MAPPING_SCHEMA = vol.Schema(
        {
            vol.Required(
                "led_config",
                description="The general outbound LED protocol for the MIDI device",
            ): dict,
            vol.Required(
                "regions",
                description="The defined input regions (grid of buttons, row of faders, etc)",
            ): [dict],
            vol.Required(
                "image",
                description="A base64 encoded image showing the defined regions on the MIDI device",
            ): str,
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._port = None
        self._config = self.CONFIG_SCHEMA.fget()(config)
        self.restore_from_data(data)

        mapping_dict = self.load_mapping()
        if not mapping_dict:
            return
            # do something when mapping doesn't work

        self.mapping = Mapping(mapping_dict)
        self.message_queue = set()
        self.led_queue = set()
        self.hold_queue_flag = False
        self.disconnected_task = None

    def restore_from_data(self, data):
        """Might be used in future"""
        self._data = data

    def load_mapping(self):
        """
        Load an LedFx MIDI mapping
        """
        mapping_path = os.path.join(
            get_default_config_directory(), self._config["midi_mapping"]
        )

        if not os.path.exists(mapping_path):
            _LOGGER.error(
                f"MIDI mapping file {self._config['midi_mapping']} does not exist in config directory"
            )
            return

        try:
            with open(mapping_path, encoding="utf-8") as file:
                mapping_json = json.load(file)
                validated_mapping = self.MAPPING_SCHEMA(mapping_json)
                _LOGGER.info(f"Loaded MIDI mapping file: {mapping_path}")
                return validated_mapping
        except KeyError:
            _LOGGER.error(
                f"Mapping file {self._config['midi_mapping']} is incomplete."
            )
        except json.JSONDecodeError:
            _LOGGER.error(
                f"Mapping file {self._config['midi_mapping']} is not json readable."
            )
        except OSError as e:
            _LOGGER.error(f"Error loading {self._config['midi_mapping']}. {e}")

    def get_triggers(self):
        return self._data

    def add_trigger(self, scene_id, song_id, song_name, song_position):
        """Add a trigger to saved triggers"""
        trigger_id = f"{song_id}-{str(song_position)}"
        if scene_id not in self._data.keys():
            self._data[scene_id] = {}
        self._data[scene_id][trigger_id] = [song_id, song_name, song_position]

    def delete_trigger(self, trigger_id):
        """Delete a trigger from saved triggers"""
        for scene_id in self._data.keys():
            if trigger_id in self._data[scene_id].keys():
                del self._data[scene_id][trigger_id]

    def set_led(self, region, index, state):
        msg = region.set_led(state, index)
        self.send_msg(msg)

    def handle_message(self, message):
        message = frozen.freeze_message(message)
        try:
            region = next(
                region for region in self.mapping.regions if message in region
            )
            _LOGGER.info(f"Received input to region: {region}: {message}")
        except StopIteration:
            _LOGGER.info(f"Received input to unmapped region: {message}")
            return

        # special case, handle holding the queue
        # if region.function == "queue hold": or whatever, future me will figure that one out
        # DONT FORGET ME!
        if message == mido.Message(
            "note_on", channel=0, note=98, velocity=127
        ):
            self.hold_queue_flag = not self.hold_queue_flag
            print(f"QUEUE {'PAUSED' if self.hold_queue_flag else 'UNPAUSED'}")
            if not self.hold_queue_flag:
                self.process_message_queue()
            return

        if region.input_type == 0:
            # if button press not in queue, add it
            # else if button press in queue, remove it (ie cancel the action if queue is held)
            try:
                self.message_queue.remove(message)
            except KeyError:
                self.message_queue.add(message)
        elif region.input_type == 1:
            # if message with same type, position, const in queue, remove it
            # before adding the new one.
            # this ensures that if the queue is held, then a slider moved, when
            # the queue is released only the most recent slider value is processed
            pos = region.midi_input["POSITION_VALUE"]
            const = region.midi_input["CONST_VALUE"]
            for q_message in self.message_queue:
                if (
                    q_message.type == message.type
                    and getattr(q_message, pos) == getattr(message, pos)
                    and getattr(q_message, const) == getattr(message, const)
                ):
                    # removing item while iterating? 'ware the moon...
                    self.message_queue.remove(q_message)
                    break
            self.message_queue.add(message)
        elif region.input_type == 2:
            # who knows what this even means
            # wheels are pretty undefined rn
            self.message_queue.add(message)

        input_position = region.where(message)
        if region.has_leds:
            self.set_led(region, input_position, 2)
            if not self.hold_queue_flag:
                self._ledfx.loop.call_later(
                    0.3, partial(self.set_led, region, input_position, 0)
                )

        self.process_message_queue()

    def send_msg(self, msg):
        try:
            self._port.send(msg)
        except rtmidi._rtmidi.SystemError:
            _LOGGER.warning(
                f"Unable to send message to {self._config['midi_device']}"
            )

    def process_message_queue(self):
        """
        this is the big cheese function, all the action.
        handles stuff. what stuff? to be continued...
        """
        if not self.hold_queue_flag:
            for _ in range(len(self.message_queue)):
                message = self.message_queue.pop()
                print(f"handling message: {message}")

    async def poll_midi_closed(self):
        """
        Occasionally checks if the midi device is still there
        """
        midi_device = self._config["midi_device"]

        while True:
            if not next(
                (
                    port
                    for port in mido.get_input_names()
                    if midi_device in port
                ),
                None,
            ):
                await super().disconnect(
                    f"{self._config['midi_device']} disconnected"
                )
                break
            else:
                await asyncio.sleep(1)

    async def connect(self):
        midi_device = self._config["midi_device"]

        _LOGGER.info(f"Waiting for {midi_device} connection...")
        while True:
            if next(
                (
                    port
                    for port in mido.get_input_names()
                    if midi_device in port
                ),
                None,
            ):
                break
            else:
                await asyncio.sleep(1)

        in_port = next(
            (port for port in mido.get_input_names() if midi_device in port),
            None,
        )
        out_port = next(
            (port for port in mido.get_output_names() if midi_device in port),
            None,
        )

        if not all((in_port, out_port)):
            _LOGGER.error(
                f"Failed to open a two way port on {midi_device}. Does this midi device support two way communication?"
            )
            return

        try:
            self._port = mido.ports.IOPort(
                mido.open_input(in_port, callback=self.handle_message),
                mido.open_output(out_port),
            )
        except rtmidi._rtmidi.SystemError:
            _LOGGER.error(
                f"Failed to open MIDI port on {midi_device}.\nAre other applications using this device?\nClose them and try again."
            )
            return
        except OSError:
            _LOGGER.error(
                f"Invalid MIDI device: {midi_device}. Valid devices: {list_midi_devices()}"
            )
            return
        self.disconnected_task = self._ledfx.loop.create_task(
            self.poll_midi_closed()
        )
        async_fire_and_forget(self.connect_animation(), self._ledfx.loop)
        await super().connect(f"Opened MIDI port on {midi_device}")

    async def connect_animation(self):
        animation_regions = tuple(
            region
            for region in self.mapping.regions
            if region.dimensionality > 0 and region.has_leds
        )

        def iter_triangle(region):
            # creates a nice triangle animation on a 2d region
            x = -np.arange(region.width)
            a = np.array([x - i for i in range(region.height)]).flatten()
            for i in range(region.width + region.height - 1):
                yield np.where(a == 0)[0]
                a += 1

        # muahahaha somebody stop me
        led_groups = tuple(
            zip_longest(
                *map(
                    lambda r: (
                        range(len(r))
                        if r.dimensionality == 1
                        else iter_triangle(r)
                    ),
                    animation_regions,
                )
            )
        )

        for state in (1, 2, 3, 0):
            for led_group in led_groups:
                for reg_idx, led_idx in enumerate(led_group):
                    if isinstance(led_idx, int):
                        self.set_led(
                            animation_regions[reg_idx], led_idx, state
                        )
                    elif isinstance(led_idx, np.ndarray):
                        for led in led_idx:
                            self.set_led(
                                animation_regions[reg_idx], led, state
                            )
                await asyncio.sleep(0.04)
            await asyncio.sleep(0.4)

    async def disconnect(self):
        if self._port is not None:
            try:
                self._port.reset()
            except rtmidi._rtmidi.SystemError:
                pass
            self._port.close()
        await super().disconnect(
            f"Closed MIDI port on {self._config['midi_device']}"
        )


class Mapping:
    def __init__(self, mapping: dict):
        self.image = mapping["image"]
        self.led_config = mapping["led_config"]
        self.regions = tuple(
            Region(
                self,
                region["NAME"],
                region["DIMENSIONALITY"],
                region["INPUT_TYPE"],
                region["MIDI_INPUT"],
                region["LED_COLOUR_RANGE"],
                region["LED_STATE_MAPPINGS"],
            )
            for region in mapping["regions"]
        )


class Region:
    # name = None
    # dimensionality = None
    # input_type = None
    # midi_input = {
    #     "MSG_TYPE" : None, # str
    #     "MOTION_VALUE": None, # str
    #     "MOTION_DATA": None, # list, contents depending on input_type
    #     "POSITION_VALUE": None, # str
    #     "POSITION_DATA": None, # list, contents depending on dimension
    #     "CONST_VALUE": None, # optional, str
    #     "CONST_DATA": None # optional, int
    # }
    # led_colour_range = None # range(min, max)
    # led_state_mappings = None

    def __init__(
        self,
        mapping,
        name: str,
        dimensionality: int,
        input_type: int,
        midi_input: dict,
        led_colour_range: list,
        led_state_mappings: list,
    ):
        self.mapping = mapping
        self.name = name
        self.dimensionality = dimensionality
        self.input_type = input_type
        self.midi_input = midi_input
        self.led_colour_range = led_colour_range
        self.led_state_mappings = led_state_mappings

        # what we're doing is making a collection of messages that will be
        # matched against input messages.
        if self.dimensionality == 2:
            origin, x_steps, y_steps = self.midi_input["POSITION_DATA"]
            POSITION_DATA = []
            self.width = len(x_steps)
            self.height = len(y_steps)
            for x in x_steps:
                for y in y_steps:
                    POSITION_DATA.append(origin + x + y)
        else:
            POSITION_DATA = list(self.midi_input["POSITION_DATA"])

        POSITION_DATA = [
            (self.midi_input["POSITION_VALUE"], i) for i in POSITION_DATA
        ]
        if self.midi_input["CONST_VALUE"]:
            consts = [
                (self.midi_input["CONST_VALUE"], self.midi_input["CONST_DATA"])
            ] * len(POSITION_DATA)
            POSITION_DATA = list(zip(POSITION_DATA, consts))
        else:
            POSITION_DATA = [(i,) for i in POSITION_DATA]

        # here's our collection of valid messages
        self._input_positions = tuple(
            frozen.FrozenMessage(self.midi_input["MSG_TYPE"], **dict(i))
            for i in POSITION_DATA
        )

        # here's a valid default motion value
        self._default_motion = {
            self.midi_input["MOTION_VALUE"]: getattr(
                self._input_positions[0], self.midi_input["MOTION_VALUE"]
            )
        }

    @property
    def has_leds(self):
        return bool(self.led_state_mappings)

    def set_led(
        self,
        state: int,  # colour state, defined in mapping [0 off, 1,2 for each state]
        index: int,  # index of led
    ):
        """
        returns a message that when sent will set the led to the appropriate colour
        """
        if not self.has_leds:
            _LOGGER.warning(
                f"Cannot set LED colour on MIDI region '{self.name}'"
            )
            return
        msg = self._input_positions[index]
        if state == 0:
            msg_type = self.mapping.led_config["led_off"]["msg_type"]
            msg_colour = self.mapping.led_config["led_off"]["colour_data"]
        else:
            msg_type = self.mapping.led_config["led_on"]["msg_type"]
            msg_colour = self.led_state_mappings[state]
        return mido.Message(
            msg_type, channel=msg.channel, note=msg.note, velocity=msg_colour
        )

    def where(self, msg):
        """
        Find the index of an input to the region
        """
        return next(
            x
            for x, i in enumerate(self._input_positions)
            if msg.copy(**self._default_motion) == i
        )

    def __repr__(self):
        return f"'{self.name}'"

    def __len__(self):
        return len(self._input_positions)

    def __iter__(self) -> mido.Message:
        """
        Iterate through the region, returning messages
        corresponding to the position of each input.
        Motion value will not be set, and should
        be set as needed by the calling function.
        """
        return iter(self._input_positions)

    def __contains__(self, msg: mido.Message):
        """
        Check if a message falls within this region's
        scope
        """
        if msg.type != self.midi_input["MSG_TYPE"]:
            return False

        return msg.copy(**self._default_motion) in self._input_positions
