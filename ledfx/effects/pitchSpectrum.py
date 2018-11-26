from ledfx.effects.audio import AudioReactiveEffect, FREQUENCY_RANGES_SIMPLE, MIN_MIDI, MAX_MIDI
from ledfx.effects.gradient import GradientEffect
from ledfx.effects import mix_colors
from ledfx.color import COLORS
from ledfx.events import GraphUpdateEvent
import voluptuous as vol
import numpy as np
import aubio
import math

class PitchSpectrumAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "PitchSpectrum"

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 1.0): vol.Coerce(float),
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
        vol.Optional('fade_rate', description='Rate at which notes fade', default = 0.15):  vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional('responsiveness', description='Responsiveness of the note changes', default = 0.15):  vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
    })

    def config_updated(self, config):
        win_s = 1024
        hop_s = 44100 // 60
        tolerance = 0.8

        # TODO: Move into the base audio effect class
        self.pitch_o = aubio.pitch("schmitt", win_s, hop_s, 41000)
        self.pitch_o.set_unit("midi")
        self.pitch_o.set_tolerance(tolerance)

        self.avg_midi = None


    def audio_data_updated(self, data):
        y = data.interpolated_melbank(self.pixel_count, filtered = False)
        midi_value = self.pitch_o(data.audio_sample())[0]
        note_color = COLORS['black']

        if not self.avg_midi:
            self.avg_midi = midi_value

        # Average out the midi values to be a little more stable
        if midi_value >= MIN_MIDI:
            self.avg_midi = self.avg_midi * (1.0 - self._config['responsiveness']) + midi_value * self._config['responsiveness']

        # Grab the note color based on where it falls in the midi range
        if self.avg_midi >= MIN_MIDI:
            midi_scaled = (self.avg_midi - MIN_MIDI) / (MAX_MIDI - MIN_MIDI)
            note_color = self.get_gradient_color(midi_scaled)

        # Mix in the new color based on the filterbank information and fade out
        # the old colors
        new_pixels = self.pixels
        for index in range(self.pixel_count):
            new_color = mix_colors(self.pixels[index], note_color, y[index])
            new_color = mix_colors(new_color, COLORS['black'], self._config['fade_rate'])
            new_pixels[index] = new_color

        # Set the pixels
        self.pixels = new_pixels
