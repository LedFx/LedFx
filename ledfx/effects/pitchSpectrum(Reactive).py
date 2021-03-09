import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects import mix_colors
from ledfx.effects.audio import MAX_MIDI, MIN_MIDI, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class PitchSpectrumAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "PitchSpectrum"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=True,
            ): bool,
            vol.Optional(
                "fade_rate",
                description="Rate at which notes fade",
                default=0.15,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "responsiveness",
                description="Responsiveness to note changes",
                default=0.15,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        }
    )

    def config_updated(self, config):
        self.avg_midi = None

    def audio_data_updated(self, data):
        y = data.interpolated_melbank(self.pixel_count, filtered=False)
        midi_value = data.midi_value()
        if midi_value is None:
            midi_value = 0
        note_color = COLORS["black"]
        if not self.avg_midi:
            self.avg_midi = midi_value

        # Average out the midi values to be a little more stable
        if midi_value >= MIN_MIDI:
            self.avg_midi = (
                self.avg_midi * (1.0 - self._config["responsiveness"])
                + midi_value * self._config["responsiveness"]
            )

        # Grab the note color based on where it falls in the midi range
        if self.avg_midi >= MIN_MIDI:
            midi_scaled = (self.avg_midi - MIN_MIDI) / (MAX_MIDI - MIN_MIDI)

            note_color = self.get_gradient_color(midi_scaled)

        # Mix in the new color based on the filterbank information and fade out
        # the old colors
        new_pixels = self.pixels
        for index in range(self.pixel_count):
            new_color = mix_colors(self.pixels[index], note_color, y[index])
            new_color = mix_colors(
                new_color, COLORS["black"], self._config["fade_rate"]
            )
            new_pixels[index] = new_color

        # Set the pixels
        self.pixels = new_pixels
