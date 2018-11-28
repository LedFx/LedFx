from ledfx.effects.audio import AudioReactiveEffect, FREQUENCY_RANGES_SIMPLE
from ledfx.effects.gradient import GradientEffect
from ledfx.events import GraphUpdateEvent
import voluptuous as vol
import numpy as np
import aubio
import math

class NoteAudioEffect(AudioReactiveEffect):

    NAME = "NoteTest"

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 3.0): vol.Coerce(float),
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
        vol.Optional('speed', description='Speed of the effect', default = 4):  vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional('decay', description='Decay rate of the scroll', default = 0.95):  vol.All(vol.Coerce(float), vol.Range(min=0.2, max=1.0)),
    })

    A4 = 440
    C0 = A4*np.power(2, -4.75)
    NOTES_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    NOTES_COLORS = [
        (255, 0, 0), # red
        (255, 0, 0), # red
        (255, 255, 0), # yellow
        (255, 255, 0), # yellow
        (0xC3, 0xF2, 0xFF), # light cyan
        (0x7F, 0x8B, 0xFD), # light blue
        (0x7F, 0x8B, 0xFD), # light blue
        (0xF3, 0x79, 0x00), # orange
        (0xF3, 0x79, 0x00), # orange 
        (0x33, 0xCC, 0x33), # green
        (0x33, 0xCC, 0x33), # green
        (0x8E, 0xC9, 0xFF)  # light blue
    ]

    def config_updated(self, config):

        win_s = 1024
        hop_s = 44100 // 60

        tolerance = 0.8
        self.pitch_o = aubio.pitch("default", win_s, hop_s, 41000)
        self.pitch_o.set_unit("Hz")
        self.pitch_o.set_tolerance(tolerance)

        self.output = None
        self.avg_pitch = None

    def get_note_index(self, freq):
        div = freq/self.C0
        if div == 0:
            return 0
        h = round(12 * math.log(div, 2))
        octave = h // 12
        n = h % 12
        return int(n)

    def mix_colors(self, color_1, color_2, ratio):
        return (color_1[0] * (1-ratio) + color_2[0] * ratio,
                color_1[1] * (1-ratio) + color_2[1] * ratio,
                color_1[2] * (1-ratio) + color_2[2] * ratio)

    def audio_data_updated(self, data):

        new_energies = data.melbank()
        pitch_val = self.pitch_o(data.audio_sample().astype(np.float32))[0]
        if not self.avg_pitch:
            self.avg_pitch = pitch_val

        if pitch_val < 9500:
            ratio = 0.85
            self.avg_pitch = self.avg_pitch * ratio + pitch_val * (1-ratio)

        note_index = self.get_note_index(self.avg_pitch)

        param_max_level = 1.0 # maximum energy 
        param_highlight_power = 1 # filter only high energy beats.
        param_energy_multiply = 0.29 # multiply energy values by.
        param_mix_power = 1 # for color mixing
        param_fade = 0.10 # 5% black every tick.

        new_energies = new_energies - min(new_energies)

        new_energies_processed = new_energies
        new_pixels = self.pixels
        for index in range(self.pixel_count):
            energy_index = int(index/(self.pixel_count / 24))
            energy_ratio = index % 1

            if energy_ratio == 0:
                energy = new_energies[energy_index]
            else: 
                energy = new_energies[energy_index] * (1-energy_ratio) + new_energies[energy_index+1] * (energy_ratio)
            energy = round(energy, 6)
            energy = pow(energy, param_highlight_power)
            energy = energy*param_energy_multiply
            #energy = pow(energy, param_mix_power)
            #print("pow2", energy)
            if energy > param_max_level:
                energy = param_max_level
            elif energy < 0.0:
                energy = 0
            new_energies_processed[energy_index] = energy
            
            cur_color = self.pixels[index]
            color_mix = self.mix_colors(cur_color, self.NOTES_COLORS[note_index], energy)
            black_mix = self.mix_colors(color_mix, (0, 0, 0), param_fade)
            new_pixels[index] = black_mix

        self._ledfx.events.fire_event(GraphUpdateEvent(
            'noteEnergy', new_energies_processed, np.array(data.melbank_frequencies)))

        # Set the pixels
        self.pixels = new_pixels
