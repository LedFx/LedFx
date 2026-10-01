import logging
from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)

# copy this file and rename it into the effects folder
# Anywhere you see template1d, replace it with your own class reference / name

# IMPORTANT IMPORTANT IMPORTANT

# no really, this is important


# Remove the @Effect.no_registration line when you use this template
# This is a decorator that prevents the effect from being registered
# If you don't remove it, you will not be able to test your effect!
@Effect.no_registration
class Template1d(AudioReactiveEffect):
    NAME = "template1d"
    # CATEGORY defines where in the UI the effect will be displayed in the effects list
    # "Classic" is a good default to start with, you can have anything here, but don't go
    # creating new categories without a good reason!
    CATEGORY = "Classic"
    # HIDDEN_KEYS are keys that are not shown in the UI, it is a way to hide settings inherited from
    # the parent class, where you don't make use of them. So it does not confuse the user.
    HIDDEN_KEYS: ClassVar[list[str]] = [
        "background_color",
        "background_brightness",
        "blur",
    ]
    # ADVANCED_KEYS are keys that are not shown in the UI, unless Advanced mode is enabled via the switch in the effect edit dialog
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + ["float_range"]

    # various examples are shown below to allow you to add new settings to your effect which will be on top of anything in the base class
    # try not to make it complicated. Hide advanced settings with the ADVANCED_KEYS
    # Try to make any setting and effect behavior independent of FPS or pixel count
    # Measure time passed per frame from the self.now and self.passed vars
    # THOU SHALT use snake case for field names
    class Config(AudioReactiveEffect.Config):
        float_range: CoercedFloat = Field(
            0.1, description="A value picked from a float range", ge=0.01, le=1.0
        )
        color_beat: Color = Field(
            "#FF0000", description="A color picker element to render the beat"
        )
        color_bar: Color = Field(
            "#0000FF", description="A color picker element to render the bar"
        )
        int_value: CoercedInt = Field(
            1, description="A value picked from an int range", ge=0, le=10
        )
        string_value: str = Field(
            "Hey look, I'm a string!", description="A string input box"
        )

    config = TypedConfig(Config)

    # things you want to do on activation, when pixel count is known
    def on_activate(self, pixel_count):
        pass

    # things you want to happen when ever the config is updated
    # the first time through this function pixel_count is not known!
    def config_updated(self, config):
        # it's healthy to get config values out of the dictionary and into variables
        # do any other heavy lifting here that you want done once if the config changes
        self.float_range = self.config.float_range
        self.color_beat = parse_color(self.config.color_beat)
        self.color_bar = parse_color(self.config.color_bar)
        self.int_value = self.config.int_value
        self.string_value = self.config.string_value
        # make sure you initialise anything that might be used in render and otherwise set in audio_data_updated
        self.bar = 0
        self.beat = 0
        # if you are going to log something, use the logger
        _LOGGER.info(
            "This is effect logging spam, but only visible if running in verbose mode due to the info() method\ncolor_beat is %s and the string_value is: %s",
            self.color_beat,
            self.string_value,
        )

    def audio_data_updated(self, data):
        # this function is called every time the audio frame is available
        # there are many ways to interact with the audio data, various filters, beat detection and fft's
        # see other effects for examples
        # try not to do heavy lifting here, get the runtime back to the audio thread that has called this callback
        # beware concurrency, this can be called while your render function is running
        # so don't go changing things your render depends on non atomically
        self.bar = data.bar_oscillator()
        self.beat = data.beat_oscillator()

    def render(self):
        # this is where your magic happens
        # though your magic render into self.pixels which is an np array of length pixels_count
        # if you are doing python loops, try to refactor to vectorised numpy operations, remember chatgpt is your friend
        # the overall performance of ledfx lives and dies by your efforts in here!

        # in this example we are going to do a very simple effect based on the bar oscillator progression

        # clear the pixels to black
        self.pixels = np.zeros(np.shape(self.pixels))

        # scale for number of pixels
        # the /4 is because I only want beat to cover one quarter of the pixels range
        # and for bar, because we know it progresses from 0 to 4
        beat_progress = self.beat * self.pixel_count / 4
        bar_progress = self.bar * self.pixel_count / 4

        self.pixels[: int(bar_progress)] = self.color_bar
        self.pixels[: int(beat_progress)] = self.color_beat
