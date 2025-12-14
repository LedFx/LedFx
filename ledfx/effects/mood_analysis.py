"""
Mood Analysis Effect for LedFx

This effect visualizes real-time mood analysis from audio, displaying
energy, valence, brightness, and other mood metrics as colors and patterns.
"""

import logging
import time

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.mood_detector import MoodDetector

_LOGGER = logging.getLogger(__name__)


class MoodAnalysisEffect(AudioReactiveEffect):
    NAME = "Mood Analysis"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["background_color", "background_brightness"]
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + [
        "mood_smoothing",
        "energy_sensitivity",
        "history_length",
        "update_rate",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "visualization_mode",
                description="How to visualize mood metrics",
                default="energy_valence",
            ): vol.In(
                [
                    "energy_valence",
                    "brightness_warmth",
                    "intensity",
                    "beat_strength",
                    "combined",
                ]
            ),
            vol.Optional(
                "color_energy_low",
                description="Color for low energy",
                default="#000080",
            ): validate_color,
            vol.Optional(
                "color_energy_high",
                description="Color for high energy",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "color_valence_low",
                description="Color for low valence (sad/dark)",
                default="#000000",
            ): validate_color,
            vol.Optional(
                "color_valence_high",
                description="Color for high valence (happy/bright)",
                default="#FFFF00",
            ): validate_color,
            vol.Optional(
                "saturation",
                description="Color saturation multiplier",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(
                "mood_smoothing",
                description="Smoothing factor for mood transitions",
                default=0.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "energy_sensitivity",
                description="Sensitivity to energy changes",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "history_length",
                description="Number of seconds of history to analyze",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=60)),
            vol.Optional(
                "update_rate",
                description="Mood update rate in Hz",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._mood_detector = None
        self._last_mood_update = 0.0
        self._mood_update_interval = 0.1  # Update mood 10 times per second

    def activate(self, channel):
        super().activate(channel)
        # Initialize mood detector now that audio is available
        if hasattr(self, 'audio') and self.audio is not None:
            try:
                mood_config = {
                    "mood_smoothing": self._config["mood_smoothing"],
                    "energy_sensitivity": self._config["energy_sensitivity"],
                    "history_length": self._config["history_length"],
                    "update_rate": self._config["update_rate"],
                }
                self._mood_detector = MoodDetector(self.audio, config=mood_config)
                _LOGGER.info("Mood detector initialized for Mood Analysis effect")
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to initialize mood detector in activate: {e}", exc_info=True
                )
                self._mood_detector = None
        else:
            self._mood_detector = None

    def deactivate(self):
        self._mood_detector = None
        super().deactivate()

    def config_updated(self, config):
        # Parse colors
        self.color_energy_low = np.array(
            parse_color(self._config["color_energy_low"]), dtype=float
        )
        self.color_energy_high = np.array(
            parse_color(self._config["color_energy_high"]), dtype=float
        )
        self.color_valence_low = np.array(
            parse_color(self._config["color_valence_low"]), dtype=float
        )
        self.color_valence_high = np.array(
            parse_color(self._config["color_valence_high"]), dtype=float
        )
        self.saturation = self._config["saturation"]
        self.visualization_mode = self._config["visualization_mode"]

        # Initialize mood detector if audio is available
        # audio is set in activate(), so check if it exists and is not None
        if hasattr(self, 'audio') and self.audio is not None:
            if not self._mood_detector:
                try:
                    mood_config = {
                        "mood_smoothing": self._config["mood_smoothing"],
                        "energy_sensitivity": self._config["energy_sensitivity"],
                        "history_length": self._config["history_length"],
                        "update_rate": self._config["update_rate"],
                    }
                    self._mood_detector = MoodDetector(self.audio, config=mood_config)
                    _LOGGER.info("Mood detector initialized for Mood Analysis effect")
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to initialize mood detector: {e}", exc_info=True
                    )
                    self._mood_detector = None
            else:
                # Reinitialize mood detector if config changed
                try:
                    mood_config = {
                        "mood_smoothing": self._config["mood_smoothing"],
                        "energy_sensitivity": self._config["energy_sensitivity"],
                        "history_length": self._config["history_length"],
                        "update_rate": self._config["update_rate"],
                    }
                    self._mood_detector = MoodDetector(self.audio, config=mood_config)
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to reinitialize mood detector: {e}", exc_info=True
                    )

    def audio_data_updated(self, data):
        # Initialize mood detector on first audio data if not already done
        if hasattr(self, 'audio') and self.audio is not None and not self._mood_detector:
            try:
                mood_config = {
                    "mood_smoothing": self._config["mood_smoothing"],
                    "energy_sensitivity": self._config["energy_sensitivity"],
                    "history_length": self._config["history_length"],
                    "update_rate": self._config["update_rate"],
                }
                self._mood_detector = MoodDetector(self.audio, config=mood_config)
            except Exception as e:
                _LOGGER.debug(f"Could not initialize mood detector yet: {e}")

    def render(self):
        if self._mood_detector is None:
            # No mood data yet, show black
            self.pixels = np.zeros(np.shape(self.pixels))
            return

        # Update mood metrics (throttled)
        current_time = time.time()
        if current_time - self._last_mood_update >= self._mood_update_interval:
            try:
                mood_metrics = self._mood_detector.update()
                self._last_mood_update = current_time
            except Exception as e:
                _LOGGER.debug(f"Error updating mood: {e}")
                mood_metrics = self._mood_detector.get_mood_metrics()

        else:
            # Use cached metrics
            mood_metrics = self._mood_detector.get_mood_metrics()

        # Extract mood values
        energy = mood_metrics.get("energy", 0.5)
        valence = mood_metrics.get("valence", 0.5)
        brightness = mood_metrics.get("brightness", 0.5)
        intensity = mood_metrics.get("intensity", 0.5)
        beat_strength = mood_metrics.get("beat_strength", 0.5)
        spectral_warmth = mood_metrics.get("spectral_warmth", 0.5)

        # Visualize based on selected mode
        if self.visualization_mode == "energy_valence":
            # Map energy to position, valence to color
            energy_pos = int(energy * self.pixel_count)
            # Interpolate between valence colors
            color = (
                self.color_valence_low * (1.0 - valence)
                + self.color_valence_high * valence
            )
            # Apply energy-based brightness
            color = color * (0.3 + 0.7 * energy)
            self.pixels = np.zeros(np.shape(self.pixels))
            self.pixels[:energy_pos] = color

        elif self.visualization_mode == "brightness_warmth":
            # Map brightness to position, warmth to color temperature
            brightness_pos = int(brightness * self.pixel_count)
            # Warm colors (red/orange) for low warmth, cool colors (blue/cyan) for high warmth
            warm_color = np.array([1.0, 0.3, 0.0])  # Orange
            cool_color = np.array([0.0, 0.5, 1.0])  # Cyan
            color = warm_color * (1.0 - spectral_warmth) + cool_color * spectral_warmth
            color = color * (0.4 + 0.6 * brightness)
            self.pixels = np.zeros(np.shape(self.pixels))
            self.pixels[:brightness_pos] = color

        elif self.visualization_mode == "intensity":
            # Intensity as a pulsing effect
            intensity_scale = 0.5 + 0.5 * intensity
            # Use energy and valence to determine base color
            base_color = (
                self.color_valence_low * (1.0 - valence)
                + self.color_valence_high * valence
            )
            color = base_color * intensity_scale * (0.5 + 0.5 * energy)
            self.pixels = np.tile(color, (self.pixel_count, 1))

        elif self.visualization_mode == "beat_strength":
            # Beat strength as segments
            beat_segments = int(beat_strength * 8) + 1  # 1-8 segments
            segment_size = self.pixel_count // beat_segments
            # Alternate colors based on energy
            color1 = (
                self.color_energy_low * (1.0 - energy)
                + self.color_energy_high * energy
            )
            color2 = color1 * 0.3  # Dimmer alternate
            self.pixels = np.zeros(np.shape(self.pixels))
            for i in range(beat_segments):
                start = i * segment_size
                end = min((i + 1) * segment_size, self.pixel_count)
                if i % 2 == 0:
                    self.pixels[start:end] = color1
                else:
                    self.pixels[start:end] = color2

        else:  # combined
            # Combine multiple metrics in a gradient
            # Left side: energy-based color
            energy_color = (
                self.color_energy_low * (1.0 - energy)
                + self.color_energy_high * energy
            )
            # Right side: valence-based color
            valence_color = (
                self.color_valence_low * (1.0 - valence)
                + self.color_valence_high * valence
            )
            # Create gradient from energy to valence
            positions = np.linspace(0, 1, self.pixel_count)
            for i, pos in enumerate(positions):
                self.pixels[i] = energy_color * (1.0 - pos) + valence_color * pos
            # Apply brightness and intensity modulation
            brightness_mod = 0.5 + 0.5 * brightness
            intensity_mod = 0.7 + 0.3 * intensity
            self.pixels = self.pixels * brightness_mod * intensity_mod

        # Apply saturation
        if self.saturation != 1.0:
            # Convert to HSV, adjust saturation, convert back
            # Simplified: reduce color intensity for desaturation
            gray = np.mean(self.pixels, axis=1, keepdims=True)
            self.pixels = gray + (self.pixels - gray) * self.saturation

        # Ensure values are in valid range
        self.pixels = np.clip(self.pixels, 0.0, 1.0)

