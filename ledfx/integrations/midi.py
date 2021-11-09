# from ledfx.events import Event
# import importlib
# import pkgutil
import asyncio
import json
import logging
import os
from itertools import zip_longest
from math import log

import mido
import mido.frozen as frozen
import numpy as np
import rtmidi
import voluptuous as vol

from ledfx.config import get_default_config_directory
from ledfx.effects import Effect
from ledfx.events import Event
from ledfx.integrations import Integration
from ledfx.utils import async_fire_and_forget
from ledfx.virtuals import Virtual

# some thoughts

# Virtuals are ordered [0-len(virtuals)] (modifiable order, drag and drop) for automatic consistency across all regions

# A REGION has a DRIVER. A DRIVER controls the action of a region's INPUT.
# A DRIVER has an ENDPOINT - "effect", "virtual_config", "virtual_preset", or "scene". This is the component of LedFx that the driver interacts with

# DRIVERS:

# DIMENSIONALITY 2:
# input type
# 0: [virtuals] set effect preset (configurable list of effect presets eg. select effect -> select preset)
# 1: [effects common] blur, brightness, (bkg_brightness?), gradient, colour
# 1: [effects specific] {TODO} any ranged value, ordered. difficult to show user what each knob does, maybe omit: each knob would control something different for each effect!

# DIMENSIONALITY 1:
# input type
# 0: [scenes] apply scene
# 0: [virtuals] preview_only
# 1: [virtuals] transition time, min/max frequency range, max brightness
# 0: [effects common] flip, mirror
# 1: [effects common] blur, brightness, (bkg_brightness?), gradient, colour
# 2: [effects common] gradient, colour (???)
# 0: [effects specific] {TODO} any bool value, ordered
# 1: [effects specific] {TODO} any ranged value, ordered

# DIMENSIONALITY 0:
# input type
# 0: queue_hold (IMPORTANT! Maybe pre-defined in mapping?)
# 0: [global, virtuals] preview_only (blackout)
# 1: [global, virtuals] transition time, min/max frequency range, max brightness
# 0: [global, effects common] flip, mirror
# 1: [global, effects common] blur, brightness, (bkg_brightness?), gradient, colour
# 2: [global, effects common] gradient, colour (???)

_LOGGER = logging.getLogger(__name__)

MIDO_MESSAGE_TYPES = mido.messages.messages.SPEC_BY_TYPE.keys()

REGION_DIMENSIONS = [
    "A single input (eg. lone button, knob)",
    "A row of inputs (eg. a small collection of buttons, faders)",
    "A matrix of inputs (eg. a grid of buttons, axis corresponding to display and effect respectively)",
]

INPUT_TYPES = [
    "On/Off (button, pressable knob)",
    "Continuous with hard start+stop (fader, slider, knob with limits)",
    "Continuous with no start or end (wheel, knob, continuous rotation)",
]

INPUT_VISUAL_STATES = [
    "Unassigned           [input has no function (cannot be pressed)]",
    "Assigned, inactive   [input has function, but not doing it (button can be pressed)]",
    "Assigned, activating [input has function, and is going to do it (button press in queue)]",
    "Assigned, active     [input is doing its function (button has been pressed)]",
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


class VisualStates:
    UNASSIGNED = 0
    INACTIVE = 1
    ACTIVATING = 2
    ACTIVE = 3


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
    # This doesn't respect the -c parameter and I don't know how to fix it.
    try:
        config_dir = get_default_config_directory()
    except OSError as error:
        _LOGGER.warning("Error attempting to list MIDI Mappings: {error}")
        return None
    # This is a hacky way of bypassing the -c parameter and just returning none
    if not os.path.exists(config_dir):
        _LOGGER.warning(
            "Currently using -c and MIDI isn't supported. We're working on it!"
        )
        return None
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
        # dynamic config schema
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

        # TODO: This should be configurable by user by API
        # this is just an example to show functionality.
        _virtual_ids = ["outer", "inner", "all"]
        self.virtual_targets = tuple(
            self._ledfx.virtuals.get(i) for i in _virtual_ids
        )

        # This efficiently describes the attributes of different
        # endpoints so they can be generated as needed.

        # "input_options":  the things that this endpoint can act on for a given midi input type
        #        - 0: boolean values, single button press
        #        - 1: ranged values, sliders/faders/knobs
        #        - 2: lists, "choose from" type things. Stepped fully rotating knobs, jogwheels

        # "apply":          a simple function that will apply an option to the endpoint
        #   args - "option": the option to modify (from input_options)
        #        - "input_position": the endpoint will choose a target based on the input's position
        #        - "value": the value to set

        # "target":         the endpoint's target, some part of ledfx
        #   args - "input_position": if applicable, to choose a target based on the input position

        # "target_count":   the number of possible targets this endpoint has
        #
        self.endpoint_factory = {
            "effect": {
                "input_options": {
                    0: ("flip", "mirror"),
                    1: ("blur", "brightness", "background_brightness"),
                    2: ("background_color"),
                },
                "apply": lambda self, option, target, value: (
                    target.update_config(
                        {option: not target._config.get(option)}
                    )
                    if self.input_type == 0
                    else target.update_config({option: value})
                ),
                "schema": Effect.schema().schema,
                "refresh_event_listener": Event.EFFECT_SET,
                "target": lambda self, input_position: self.virtual_targets[
                    input_position
                ].active_effect,
                "target_count": lambda self: len(self.virtual_targets),
            },
            "virtual_config": {
                "input_options": {
                    0: ("preview_only"),
                    1: (
                        "max_brightness",
                        "transition_time",
                        "frequency_min",
                        "frequency_max",
                    ),
                    2: ("mapping", "transition_mode"),
                },
                "apply": lambda self, option, target, value: (
                    target.update_config(
                        {option: not target._config.get(option)}
                    )
                    if self.input_type == 0
                    else target.update_config({option: value})
                ),
                "schema": Virtual.schema().schema,
                "refresh_event_listener": Event.VIRTUAL_CONFIG_UPDATE,
                "target": lambda self, input_position: self.virtual_targets[
                    input_position
                ],
                "target_count": lambda self: len(self.virtual_targets),
            },
            "virtual_preset": {
                "input_options": {
                    0: ("preset",),
                },
                "apply": lambda self, option, target, value: (
                    target.set_preset(value)
                ),
                "refresh_event_listener": Event.PRESET_ACTIVATED,
                "target": lambda self, input_position: self.virtual_targets[
                    input_position
                ],
                "target_count": lambda self: len(self.virtual_targets),
            },
            "scene": {
                "input_options": {0: ("scene",)},
                "apply": lambda self, option, target, value: (
                    target.activate(value)
                ),
                "refresh_event_listener": Event.SCENE_ACTIVATED,
                "target": lambda self, _: self._ledfx.scenes,
                "target_count": lambda self: 1,
            },
        }

        for region in self.mapping.regions:
            if region.name == "Button Matrix":
                self.create_driver(region, "virtual_preset")
                options = (
                    ("preset", "user_presets", "energy", "gentle"),
                    ("preset", "user_presets", "energy", "intense"),
                    ("preset", "user_presets", "scroll", "gentle"),
                    ("preset", "user_presets", "scroll", "intense"),
                    ("preset", "user_presets", "strobe", "default"),
                    ("preset", "user_presets", "strobe", "intense"),
                    ("preset", "user_presets", "real_strobe", "gentle"),
                    ("preset", "ledfx_presets", "pitchSpectrum", "reset"),
                )
                region.driver.set_options(options)
            elif region.name == "Faders":
                self.create_driver(region, "virtual_config")
                options = (("frequency_max",),) * 8
                region.driver.set_options(options)
            elif region.name == "Solo Fader":
                self.create_driver(region, "virtual_config")
                options = (("max_brightness",),)
                region.driver.set_options(options)
            elif region.name == "Button Row":
                self.create_driver(region, "effect")
                options = (("mirror",),) * 8
                region.driver.set_options(options)
            elif region.name == "Button Column":
                self.create_driver(region, "scene")
                options = (
                    ("scene", "test"),
                    ("scene", "test3"),
                    (None,),
                    (None,),
                    (None,),
                    (None,),
                    (None,),
                    (None,),
                )
                region.driver.set_options(options)

    def restore_from_data(self, data):
        """Might be used in future"""
        self._data = data

    def load_mapping(self):
        """
        Load an LedFx MIDI mapping
        """
        mapping_path = os.path.join(
            self._ledfx.config_dir, self._config["midi_mapping"]
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

    def set_led(self, region, index, state):
        msg = region.set_led(state, index)
        self.send_msg(msg)

    def handle_message(self, message):
        message = frozen.freeze_message(message)
        try:
            region = next(
                region for region in self.mapping.regions if message in region
            )
            _LOGGER.debug(f"Received input to region: {region}: {message}")
        except StopIteration:
            _LOGGER.debug(f"Received input to unmapped region: {message}")
            return

        input_position = region.where(message)

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
                if region.has_leds:
                    self.set_led(region, input_position, VisualStates.INACTIVE)
            except KeyError:
                self.message_queue.add(message)
                if region.has_leds:
                    self.set_led(
                        region, input_position, VisualStates.ACTIVATING
                    )
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
                region = next(
                    region
                    for region in self.mapping.regions
                    if message in region
                )
                region.driver.handle_message(message)

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

    def create_driver(self, region, endpoint_type):
        """
        Creates a driver for a region.
        This connects the regions inputs to a ledfx "endpoint" (some module of ledfx)
        """
        input_type = region.input_type
        dimensionality = region.dimensionality

        assert endpoint_type in self.endpoint_factory
        endpoint_config = self.endpoint_factory.get(endpoint_type)
        assert input_type in endpoint_config.get("input_options")

        # dynamically build an endpoint class for this driver
        # using the endpoint factory
        endpoint_class = type(
            f"{endpoint_type.title()}_Endpoint",
            (object,),
            {
                "_ledfx": self._ledfx,
                "endpoint_type": endpoint_type,
                "input_type": input_type,
                "options": endpoint_config.get("input_options").get(
                    input_type
                ),
                "virtual_targets": self.virtual_targets,
                "apply": endpoint_config.get("apply"),
                "target": endpoint_config.get("target"),
                "target_count": endpoint_config.get("target_count"),
                "schema": endpoint_config.get("schema", None),
            },
        )

        region.driver = type(
            f"D{dimensionality}I{input_type}_{endpoint_type.title()}Driver",
            (Driver,),
            {
                "region": region,
                "endpoint": endpoint_class(),
                "options": (),
                "virtual_targets": self.virtual_targets,
            },
        )()


class Driver:
    def set_options(self, options):
        """
        options is a tuple of tuples, each containing an option key and any associated settings
        input_type 0 generic  : just the option key
                                eg. ("flip",)
        input_type 0 "preset" : option key and preset info
                                eg. ("preset", "ledfx", "energy", "fast_rgb")
        input type 0 "scene"  : option key and scene id
                                eg. ("scene", "my_cool_scene")
        input type 1 generic  : option key and a lambda to scale midi input to endpoint range
                                eg. ("blur", <lambda>)
        input type 2 generic  : option key and available choices
                                eg. ("bg_colour", "red", "green", "purple", ... )


        """
        if not options:
            self.options = ()
            return

        assert all(
            option[0] is None or option[0] in self.endpoint.options
            for option in options
        )

        if self.region.dimensionality == 0:
            assert len(options) == 1
        elif self.region.dimensionality == 1:
            assert len(options) == len(self.region)
        elif self.region.dimensionality == 2:
            assert len(options) == self.region.height

        def range_scaler(a, b, c, d):
            # scales x between range(a,b) to range (c,d)
            return lambda x: ((x - a) / (b - a)) * (d - c) + c

        logit = lambda x: 3700.0 * log(1 + x / 200.0, 13)  # noqa: E731
        hzit = lambda x: 200.0 * 13 ** (x / 3700.0) - 200.0  # noqa: E731

        def frequency_range_scaler(a, b, c, d):
            # scales frequency x between range(a,b) to range (c,d)
            # using a logarithmic conversion for "linear" feel
            c = logit(c)
            d = logit(d)
            return lambda x: hzit(((x - a) / (b - a)) * (d - c) + c)

        if self.region.input_type == 0:
            for option in options:
                key, *settings = option
                if key == "preset":
                    assert len(settings) == 3
                    assert all(
                        isinstance(setting, str) for setting in settings
                    )
                    self.options += ((key, *settings),)
                elif key == "scene":
                    assert len(settings) == 1
                    assert isinstance(settings[0], str)
                    self.options += ((key, settings[0]),)
                else:
                    self.options += ((key,),)

        elif self.region.input_type == 1:
            for option in options:
                key, *settings = option
                validators = self.endpoint.schema.get(key).validators
                range_val = next(
                    val for val in validators if isinstance(val, vol.Range)
                )
                scaler_func = (
                    frequency_range_scaler
                    if "frequency" in key
                    else range_scaler
                )
                self.options += (
                    (
                        key,
                        scaler_func(
                            *self.region.midi_input["MOTION_DATA"],
                            range_val.min,
                            range_val.max,
                        ),
                    ),
                )

        elif self.region.input_type == 2:
            for option in options:
                key, *settings = option
                validator = self.endpoint.schema.get(key)
                self.options += ((key, *validator.container),)

    def midi_to_endpoint_value(self, midi_value, input_position):
        """
        Uses self.options to convert the motion value of a midi input
        to the corresponding value expected by the endpoint
        """
        assert input_position in range(len(self.options))

        if self.region.input_type == 0:
            return self.options[input_position][1:]
        elif self.region.input_type == 1:
            return self.options[input_position][1](midi_value)
        elif self.region.input_type == 2:
            return None
            # TODO
            # - get current index in list from active effect
            # - change by delta
            # - return the item of the new index
            delta = midi_value - self.region.midi_input["MOTION_DATA"][0]

    def handle_message(self, msg):
        if not self.options:
            return

        if self.region.dimensionality == 0:
            input_position = options_position = 0
        elif self.region.dimensionality == 1:
            input_position = options_position = self.region.where(msg)
        elif self.region.dimensionality == 2:
            input_position, options_position = self.region.where_2d(msg)

        option = self.options[options_position][0]

        if option is None:
            return

        value = self.midi_to_endpoint_value(
            getattr(msg, self.region.midi_input["MOTION_VALUE"]),
            options_position,
        )

        # if 0d, apply the option to all targets
        # otherwise, apply to specific target
        if self.region.dimensionality == 0:
            for i in range(self.endpoint.target_count()):
                target = self.endpoint.target(i)
                self.endpoint.apply(option, target, value)
        else:
            self.endpoint.apply(
                option, self.endpoint.target(input_position), value
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
        """
        Handles a region; a defined set of midi messages of homogenous input type.
        eg. check if a message falls in this region, set leds for the region.
        """
        self.mapping = mapping
        self.name = name
        self.dimensionality = dimensionality
        self.input_type = input_type
        self.midi_input = midi_input
        self.led_colour_range = led_colour_range
        self.led_state_mappings = led_state_mappings
        self.has_leds = bool(self.led_state_mappings)

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

        if self.has_leds:
            self.led_states = list(
                0 for _ in range(len(self._input_positions))
            )

    def set_led(
        self,
        state: int,  # colour state, defined in mapping [0 off, 1,2,3 for each state]
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

        if self.has_leds:
            self.led_states[index] = state

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

    def where_2d(self, msg):
        if self.dimensionality != 2:
            _LOGGER.error(f"where_2d called on a {self.dimensionality} region")
        return divmod(self.where(msg), self.height)

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
