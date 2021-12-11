import base64
import io
import json
import os
import sys
import time
import zipfile
from functools import cached_property
from urllib.parse import urlencode

import mido
import mido.frozen as frozen
import rtmidi

# flake8: noqa
# fmt: off

########
# Classes, functions, consts
########

MIDO_MESSAGE_TYPES = list(mido.messages.messages.SPEC_BY_TYPE)

MIDO_MESSAGE_PARAMS = {
    spec["type"]: spec["value_names"] for spec in mido.messages.specs.SPECS
}

byte_range = range(0, 128)
PARAM_RANGES = {
    "data": byte_range,
    "channel": range(0, 16),
    "control": byte_range,
    "frame_type": range(0, 8),
    "frame_value": range(0, 16),
    "note": byte_range,
    "pitch": range(-8192, 8192),
    "pos": range(0, 16384),
    "program": byte_range,
    "song": byte_range,
    "value": byte_range,
    "velocity": byte_range,
}

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

INPUT_RECORDING_TIMEOUT = 3

class Mapping(dict):

    def __repr__(self):
        return "\nMapped Regions:\n"+"\n".join(f"'{region['NAME']}', {region['DIMENSIONALITY']}D region of {INPUT_TYPES[region['INPUT_TYPE']]}" for region in self["regions"])+"\n"

class Region:
    NAME = None
    DIMENSIONALITY = None
    INPUT_TYPE = None
    MIDI_INPUT = {
        "MSG_TYPE" : None, # str
        "MOTION_VALUE": None, # str
        "MOTION_DATA": None, # list, contents depending on input_type
        "POSITION_VALUE": None, # str
        "POSITION_DATA": None, # list, contents depending on dimension
        "CONST_VALUE": None, # optional, str
        "CONST_DATA": None # optional, int
    }
    LED_COLOR_RANGE = None # range(min, max)
    LED_STATE_MAPPINGS = None


    def __init__(self):
                 # name: str,
                 # dimensionality: str,
                 # midi_input: dict,
                 # msg_type: str,
                 # led_config: range):

        # this is some pretty DISGUSTING python but hey
        # at least it's only run once :D
        # i'm a little ashamed to have written this tbh.

        # this is all moved around to allow region to be build dynamically as it is defined

        # what we're doing is making a collection of messages that will be
        # matched against input messages.
        pass

    def as_dict(self):
        return {
            "NAME" : self.NAME,
            "DIMENSIONALITY" : self.DIMENSIONALITY,
            "INPUT_TYPE" : self.INPUT_TYPE,
            "MIDI_INPUT" : self.MIDI_INPUT,
            "LED_COLOR_RANGE" : self.LED_COLOR_RANGE,
            "LED_STATE_MAPPINGS" : self.LED_STATE_MAPPINGS
        }

    def __repr__(self):
        return f"'{self.NAME}', {self.DIMENSIONALITY}D region of {INPUT_TYPES[self.INPUT_TYPE]}"

    @cached_property
    def _input_positions(self):
        if self.DIMENSIONALITY == 2:
            origin, x_steps, y_steps = self.MIDI_INPUT["POSITION_DATA"]
            position_data = []
            for x in x_steps:
                for y in y_steps:
                    position_data.append(origin+x+y)
        else:
            position_data = list(self.MIDI_INPUT["POSITION_DATA"])

        position_data = [(self.MIDI_INPUT["POSITION_VALUE"], i) for i in position_data]
        if self.MIDI_INPUT["CONST_VALUE"]:
            consts = [(self.MIDI_INPUT["CONST_VALUE"], self.MIDI_INPUT["CONST_DATA"])]*len(position_data)
            position_data = list(zip(position_data, consts))
        else:
            position_data = [(i,) for i in position_data]
        # here's our collection of valid messages
        # self._input_positions = tuple(
        #     mido.frozen.FrozenMessage(
        #         self.MIDI_INPUT["MSG_TYPE"],
        #         **{dict(i)})
        #     for i in position_data)
        # oh god it keeps getting worse
        # self._default_motion = {
        #     self.MIDI_INPUT["MOTION_VALUE"]:
        #     getattr(self._input_positions[0], self.MIDI_INPUT["MOTION_VALUE"])
        # }

        return tuple(
            mido.frozen.FrozenMessage(
                self.MIDI_INPUT["MSG_TYPE"],
                **dict(i))
            for i in position_data)

    @cached_property
    def _default_motion(self):
        return {
            self.MIDI_INPUT["MOTION_VALUE"]:
            getattr(self._input_positions[0], self.MIDI_INPUT["MOTION_VALUE"])
        }


    # def __repr__(self):
    #     pass

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
        if msg.type == self.MIDI_INPUT["MSG_TYPE"]:
            if not mido.frozen.is_frozen(msg):
                msg = mido.frozen.freeze_message(msg)
            return msg.copy(**self._default_motion) in self._input_positions


def print_midi(msg):
    print(f"MIDI: {msg}            ")


def continue_input():
    input("Continue... <Enter> ")


def choose_from(iterable, return_idx=False, msg=None):
    print()
    for i, x in enumerate(iterable):
        print(f"{i}: {x}")
    if msg:
        print(msg)
    idx = int_input(between=range(0, len(iterable)))
    if return_idx:
        return idx
    else:
        return iterable[idx]


def yesno_input(msg=None):
    if msg:
        print(msg)
    while True:
        val = input("(y or n) > ")
        if val not in ["y", "n"]:
            print("Invalid: choose 'y' or 'n'")
            continue
        return val == "y"


def int_input(between=None, msg=None):
    if msg:
        print(msg)
    while True:
        try:
            val = int(input("> "))
        except ValueError:
            print("Invalid: not a number")
            continue
        if between and val not in between:
            print(f"Invalid: not between {between}")
            continue
        return val


def find_changing_value_between_messages(
    msgs, input_change_str="Desired input interaction?"
):
    msg_types = {msg.type for msg in msgs}
    if len(msg_types) != 1:
        msg_type = choose_from(
            list(msg_types),
            msg=f"We detected different MIDI message types. Which one corresponds to the {input_change_str}",
        )
    else:
        msg_type = msg_types.pop()
    values = MIDO_MESSAGE_PARAMS[msg_type]
    msgs_by_value = {}
    for value in values:
        msgs_by_value[value] = {
            getattr(msg, value) for msg in msgs if msg.type == msg_type
        }
    motion_value = max(reversed(msgs_by_value), key=lambda k: len(msgs_by_value[k]))
    return msg_type, motion_value, msgs_by_value[motion_value]


def record_continuous_input(timeout=INPUT_RECORDING_TIMEOUT, prompt=None):
    # clear pending input messages
    for _ in port.iter_pending():
        pass
    print("Recording...")
    port.receive()  # wait for user to start moving the thing
    msgs = set()
    inactivity_timer = 0
    start_time = time.time()
    while inactivity_timer < INPUT_RECORDING_TIMEOUT:
        msg = port.poll()
        if msg:
            print_midi(msg)
            msgs.add(frozen.freeze_message(msg))
            inactivity_timer = 0
            start_time = time.time()
        else:
            inactivity_timer = time.time() - start_time
            print(
                f"{prompt if prompt else ''} [{INPUT_RECORDING_TIMEOUT-inactivity_timer:.1f}s]",
                end="\r",
            )
    print()
    return msgs


def get_input_msg_format(input_type: int):
    # clear pending input messages
    for _ in port.iter_pending():
        pass
    if input_type == 0:  # button
        print("Press a SINGLE BUTTON in the region at least 5 times. Just one button!")
        msgs = record_continuous_input(
            prompt="Stop when you've pressed it at least 5 times."
        )
        (
            msg_type,
            motion_value,
            motion_data,
        ) = find_changing_value_between_messages(
            msgs,
            input_change_str="button being PRESSED? (not released) (typically 'note_on')",
        )
        return msg_type, motion_value, motion_data
    elif input_type == 1:  # ranged input (slider etc)
        print(
            "Move the MIDI input back and forth across the full range of motion. Stop when you have hit max/min at least once."
        )
        msgs = record_continuous_input(
            prompt="Stop when you have hit max/min at least once."
        )
        (
            msg_type,
            motion_value,
            motion_data,
        ) = find_changing_value_between_messages(msgs)
        return (
            msg_type,
            motion_value,
            range(min(motion_data), max(motion_data)),
        )
    elif input_type == 2:  # continuously rotating (wheel, knob etc)
        print(
            "Gently turn the MIDI input in each direction, looking for the message value that changes"
        )
        msgs = record_continuous_input(
            prompt="Stop when you have rotated in each direction."
        )
        centre_val = int_input(
            msg="What is the rotation's central value? (typically 64)"
        )
        (
            msg_type,
            motion_value,
            motion_data,
        ) = find_changing_value_between_messages(msgs)
        return msg_type, motion_value, centre_val


def get_first_msg(msg_type: str, num=None):
    # clear pending input messages
    for _ in port.iter_pending():
        pass
    print(
        f"Move/press midi input {f'number {num} ' if type(num) is int else ''}..."
    )
    while True:
        msg = port.receive()
        if msg.type == msg_type:
            break
    return msg


def record_region_1d(length: int, msg_type: str, motion_value: str):
    msgs = []
    for i in range(length):
        while True:
            msg = get_first_msg(msg_type, num=i)
            setattr(msg, motion_value, 0)
            msg = frozen.freeze_message(msg)
            if msg in msgs:
                print(f"You moved input number {msgs.index(msg)}. Try again")
                continue
            msgs.append(msg)
            break
        print("Got it! Release the input.")
        continue_input()
    return msgs


def xy_to_position(x, y, corner_pos, x_steps, y_steps):
    return corner_pos + x_steps[x] + y_steps[y]


def add_region():
    print("To begin, give a unique, user friendly name to this region")
    name = input("> ")
    dimension = choose_from(
        REGION_DIMENSIONS,
        return_idx=True,
        msg="What is the DIMENSIONALITY of the input region?",
    )
    input_type = choose_from(
        INPUT_TYPES, return_idx=True, msg="What TYPE of input?"
    )
    msg_type, motion_value, motion_data = get_input_msg_format(input_type)
    if input_type == 0:
        motion_data = [motion_data.pop()]
    elif input_type == 1: # ranged, min/max
        motion_data = [motion_data.start, motion_data.stop]
    elif input_type == 2: # continuous
        motion_data = [motion_data]
    if dimension == 0:
        print(
            "Mapping complete. To confirm, please use the input."
        )
        test_msg = get_first_msg(msg_type)
        # might cause issue if msg only sends one param
        remaining_values = (set(MIDO_MESSAGE_PARAMS[msg_type]) - {motion_value})
        # make some assumptions based on my best guesses
        if "note" in remaining_values:
            position_value = "note"
        elif "control" in remaining_values:
            position_value = "control"
        else:
            position_value = remaining_values.pop()
        position_data = [getattr(test_msg, position_value)]
    elif dimension == 1:
        x = int_input(msg="How MANY inputs in the region?")
        print("We'll now detect each input in the region one by one")
        msgs = record_region_1d(x, msg_type, motion_value)
        _, position_value, _ = find_changing_value_between_messages(
            msgs, input_change_str="input position?"
        )
        position_data = [getattr(msg, position_value) for msg in msgs]
        print(
            "Mapping complete. To confirm, please use an input in the region."
        )
        test_msg = get_first_msg(msg_type)
    elif dimension == 2:
        x = int_input(
            msg="How many COLUMNS (horizontal length) in the 2D region?"
        )
        print("We'll now detect the input at the top of each column.")
        print(
            "Starting from the TOP LEFT, and moving HORIZONTALLY to the RIGHT."
        )
        msgs_x = record_region_1d(x, msg_type, motion_value)
        y = int_input(msg="How many ROWS (vertical length) in the 2D region?")
        print("We'll now detect the input at the left of each row.")
        print("Starting from the TOP LEFT, and moving VERTICALLY DOWN.")
        msgs_y = record_region_1d(y, msg_type, motion_value)
        _, x_position_value, _ = find_changing_value_between_messages(
            msgs_x, input_change_str="button position?"
        )
        _, y_position_value, _ = find_changing_value_between_messages(
            msgs_y, input_change_str="button position?"
        )
        x_positions = [getattr(msg, x_position_value) for msg in msgs_x]
        y_positions = [getattr(msg, y_position_value) for msg in msgs_y]
        assert x_position_value == y_position_value
        position_value = x_position_value
        corner_position = x_positions[0]
        assert corner_position == y_positions[0]
        x_steps = [pos - corner_position for pos in x_positions]
        y_steps = [pos - corner_position for pos in y_positions]
        print(
            "Mapping complete. To confirm, please test the BOTTOM RIGHT CORNER input"
        )
        test_msg = get_first_msg(msg_type)
        assert getattr(test_msg, x_position_value) == xy_to_position(
            x - 1, y - 1, corner_position, x_steps, y_steps
        )
        position_data = (corner_position, x_steps, y_steps)

    # fill in any remaining parameters for consts
    const_value = const_data = None
    remaining_values = set(MIDO_MESSAGE_PARAMS[msg_type]) - {motion_value, position_value}
    if remaining_values:
        const_value = remaining_values.pop()
        const_data = getattr(test_msg, const_value)

    region = Region()
    region.NAME = name
    region.DIMENSIONALITY = dimension
    region.INPUT_TYPE = input_type
    region.MIDI_INPUT = {
        "MSG_TYPE" : msg_type, # str
        "MOTION_VALUE": motion_value, # str
        "MOTION_DATA": motion_data, # list, contents depending on input_type
        "POSITION_VALUE": position_value, # str
        "POSITION_DATA": position_data, # list, contents depending on dimension
        "CONST_VALUE": const_value, # optional, str
        "CONST_DATA": const_data # optional, int
    }
    region.LED_COLOR_RANGE = []
    region.LED_STATE_MAPPINGS = []


    assert test_msg in region # Moment of truth!
    print("Confirmed.")
    print(f"Region Mapping Definition: {region}")
    continue_input()

    if yesno_input("Does this region have LEDs?") and mapping["led_config"]:
        print(
            "Answer the following questions for the LEDs of THIS REGION only"
        )
        continue_input()
        led_on_msg_type = mapping["led_config"]["led_on"]["msg_type"]
        led_on_color_value = mapping["led_config"]["led_on"]["color_value"]
        led_off_msg_type = mapping["led_config"]["led_off"]["msg_type"]
        led_off_color_data = mapping["led_config"]["led_off"]["color_data"]
        led_on_min_val = int_input(
            between=PARAM_RANGES[led_on_color_value],
            msg=f"What is the {led_on_color_value} for this region's first color/state? NOT any number corresponding to LED OFF",
        )
        led_on_max_val = int_input(
            between=PARAM_RANGES[led_on_color_value],
            msg=f"What is the {led_on_color_value} for this region's last color/state? If your buttons are full RGB, this could be as high as 127.",
        )
        led_color_range = range(led_on_min_val, led_on_max_val)
        region.LED_color_RANGE = [led_color_range.start, led_color_range.stop] # range(min, max)
        region.LED_STATE_MAPPINGS = []

        print(
            f"LedFx has {len(INPUT_VISUAL_STATES)} visual states for each input:"
        )
        for i, x in enumerate(INPUT_VISUAL_STATES):
            print(f"{i}. {x}")
        print(f"You will assign an LED color (or off) to each.")
        continue_input()

        led_states = ["LED OFF", *(f"LED ON, color # {v}" for v in range(led_on_min_val, led_on_max_val + 1))]


        for i, x in enumerate(INPUT_VISUAL_STATES):
            while True:
                color = choose_from(
                    led_states,
                    return_idx=True,
                    msg=f"Which color will be used for this input state?\n{i}. {x}",
                )
                print(color)
                for msg in region:
                    channel = msg.channel
                    position = getattr(msg, region.MIDI_INPUT["POSITION_VALUE"])
                    if color == 0:
                        led_msg = mido.Message(led_off_msg_type, channel=channel, note=position, velocity=led_off_color_data)
                    else:
                        led_msg = mido.Message(led_on_msg_type, channel=channel, note=position, velocity=color)
                    port.send(led_msg)
                if yesno_input("Are you happy with this color? To try a different color, choose NO"):
                    break
            region.LED_STATE_MAPPINGS.append(color)
    return region

def configure_leds():
    print(
        "Each device generally has its own protocol for controlling the LEDs."
    )
    print(
        f"I'd recommend you search online 'Communications Protocol for {device_name}' to make this process easier."
    )
    print(f"Look for something along the lines of 'Outbound Message: LEDs'")
    continue_input()
    print(
        "To add to this, generally each region has LEDs with different capabilities"
    )
    print(
        "Eg. You might have a pad of full RGB buttons in one region, and another region of buttons that are simple on/off"
    )
    continue_input()
    led_on_msg_type = choose_from(
        MIDO_MESSAGE_TYPES,
        msg="According to your device's documentation, which TYPE of message is used to TURN ON an LED? Typically this is 'note_on'",
    )
    if led_on_msg_type != "note_on":
        print(
            "This program is too dumb to configure LEDs that don't use 'note_on'. Please get in touch with LedFx developers on Discord for help."
        )
        mapping["led_config"] = False
        return False
    led_color_value = "velocity"
    led_on_msg_type = "note_on"
    led_off_msg_type = choose_from(
        MIDO_MESSAGE_TYPES,
        msg="Which TYPE of message is used to TURN OFF an LED? Typically this is either 'note_on' or 'note_off'",
    )
    if led_off_msg_type == "note_on":
        led_off_velocity = int_input(
            between=PARAM_RANGES[led_color_value],
            msg=f"What {led_color_value} would turn off the LED?",
        )
    else:
        led_off_velocity = 0
    mapping["led_config"] = {
        "led_on": {"msg_type": "note_on", "color_value": led_color_value},
        "led_off": {
            "msg_type": led_off_msg_type,
            "color_value": led_color_value,
            "color_data": led_off_velocity
        },
    }
    return True


def save_json():
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(mapping, json_file, ensure_ascii=False, sort_keys=True, indent=4)
        print(f"Your mapping has been saved to {json_path}")

def save_zip():
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except OSError:
            print(f"Could not remove {zip_path}")
            return
    uri_safe_midi_name = urlencode(f"{device_name} MIDI Map")
    with zipfile.ZipFile(json_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(zip_path)
        print(f"Your mapping has also been saved as a zip file to {zip_path}")
        print(f"You can upload this via GitHub to share with the community - https://github.com/LedFx/LedFx/issues/new?assignees=&labels=&template=midi_upload.md&title={uri_safe_midi_name}")


########
# Device selection and port
########

print(
    """
   __          ______
  / /  ___ ___/ / __/_ __
 / /__/ -_) _  / _/ \\ \\ /
/____/\\__/\\_,_/_/  /_\\_\\
   __  __________  ____
  /  |/  /  _/ _ \\/  _/
 / /|_/ // // // // /
/_/__/_/___/____/___/
  /  |/  /__ ____  ___  ___ ____
 / /|_/ / _ `/ _ \\/ _ \\/ -_) __/
/_/  /_/\\_,_/ .__/ .__/\\__/_/
           /_/  /_/
"""
)

in_ports = [name.rstrip(" 0123456789") for name in mido.get_input_names()]
out_ports = [name.rstrip(" 0123456789") for name in mido.get_output_names()]
io_ports = list(set(in_ports) & set(out_ports))

device_name = choose_from(io_ports, msg="Select your midi device by number")

in_port = next(
    (port for port in mido.get_input_names() if device_name in port), None
)
out_port = next(
    (port for port in mido.get_output_names() if device_name in port), None
)
assert in_port, out_port

try:
    port = mido.ports.IOPort(
        mido.open_input(in_port), mido.open_output(out_port)
    )
except rtmidi._rtmidi.SystemError:
    print(
        f"Failed to open MIDI port on {device_name}.\nAre other applications using this device?\nClose them and try again."
    )
    sys.exit(0)

########
# Make json to store mapping
########

mapping = Mapping()
json_name = f"LedFxMidiMap {device_name}.json"
zip_name = f"{json_name}.zip"
zip_path = os.path.join(os.path.expanduser("~"), zip_name)
json_path = os.path.join(os.path.expanduser("~"), json_name)

# load existing mapping if it's there
if os.path.exists(json_path):
    with open(json_path, encoding="utf-8") as json_file:
        try:
            mapping.update(json.load(json_file))
        except io.UnsupportedOperation as e:
            print(f"Error loading mapping: {e}")
        except json.decoder.JSONDecodeError:
            pass
        finally:
            if mapping:
                print(f"Loaded mapping from {json_path}")

print("How it works:")
print(
    "You will define REGIONS of your midi device, eg. A ROW of SLIDERS, a MATRIX of BUTTONS (note - regions must have homogenous input types)"
)
print(
    "You will also define an LED PROTOCOL for each region (so LedFx can turn your device lights on and off)"
)
print(
    "Finally, you will create an image of the midi device, showing the regions you created."
)
continue_input()

if "led_config" not in mapping.keys():
    configure_leds()
    save_json()

if "regions" not in mapping.keys():
    mapping["regions"] = []
else:
    print(mapping)

print("Are you ready to begin?")
continue_input()
while True:
    if not yesno_input(msg="Do you want to add a region?"):
        break
    region = add_region()
    print(region)
    mapping["regions"].append(region.as_dict())
    save_json()
    save_zip()
    print(mapping)

if "image" not in mapping.keys():
    print()
    print(f"Finally, you should add an image to this mapping, so that others can easily understand all the defined regions.")
    print(f"1 - Download a clear, top-down image of your device online")
    print(f"2 - Draw over it, highlighting the regions and their names")
    print(f"3 - Feel free to add suggested uses for each region")
    print(f"4 - Save the image as a JPG, making sure it is no larger than 1MB")
    print(f"When you've finished, come back here and we'll add the image to the mapping")
    continue_input()
    while True:
        print("Drag and drop the image file to this console. If that doesn't work, type the path to the image manually.")
        image_path = input(" > ").rstrip()
        if os.path.getsize(image_path) > 1e6:
            print(f"Your image is too big: {size/1e6:.2f} MB")
            print(f"Please increase compression or scale it down. JPG is recommended.")
            continue
        try:
            with open(image_path, "rb") as img_file:
                image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                break
        except Exception as e:
            print("Something went wrong:")
            print(repr(e))
    mapping["image"] = image_b64
    print("Done, thank you!")
    continue_input()
    save_json()
    save_zip()

print()
print(f"You can add more regions by running this script again.")
print(f"Feel free to amend the mapping json if you made a mistake - nobody's perfect! :P")

# fmt: on
