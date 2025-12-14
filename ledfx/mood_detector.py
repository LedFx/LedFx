"""
Mood Detection Module for LedFx

This module analyzes audio features to detect the mood/energy of music in real-time,
enabling dynamic effect and color changes based on musical characteristics.
"""

import logging
import threading
import time
from collections import deque
from typing import Any, Optional

import numpy as np
import voluptuous as vol

from ledfx.effects.math import ExpFilter

# Optional librosa integration
# Try relative import first (for files in same package), then absolute
try:
    try:
        from .mood_detector_librosa import (
            classify_music_style,
            classify_sub_genre,
            create_librosa_extractor,
            is_librosa_available,
        )
    except ImportError:
        from ledfx.mood_detector_librosa import (
            classify_music_style,
            classify_sub_genre,
            create_librosa_extractor,
            is_librosa_available,
        )
    LIBROSA_MODULE_AVAILABLE = True
except ImportError:
    LIBROSA_MODULE_AVAILABLE = False

    def is_librosa_available():
        return False

    def create_librosa_extractor(*args, **kwargs):
        return None

    def classify_music_style(*args, **kwargs):
        return {}

    def classify_sub_genre(*args, **kwargs):
        return {}


_LOGGER = logging.getLogger(__name__)


class MoodDetector:
    """
    Analyzes audio features to detect musical mood and energy characteristics.

    Features detected:
    - Energy level (low, medium, high)
    - Valence (sad/dark to happy/bright)
    - Tempo stability
    - Dynamic range (soft vs loud sections)
    - Spectral characteristics (warm vs bright)
    - Beat strength
    """

    CONFIG_SCHEMA = vol.Schema(
        {
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
            vol.Optional(
                "energy_sensitivity",
                description="Sensitivity to energy changes (0-1)",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "mood_smoothing",
                description="Smoothing factor for mood transitions (0-1)",
                default=0.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "use_librosa",
                description="Use librosa for advanced audio analysis",
                default=False,
            ): bool,
            vol.Optional(
                "librosa_buffer_duration",
                description="Audio buffer duration for librosa analysis (seconds)",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=10.0)),
            vol.Optional(
                "librosa_update_interval",
                description="Librosa feature update interval (seconds)",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10.0)),
        }
    )

    def __init__(
        self, audio_source: Any, config: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Initialize the mood detector.

        Args:
            audio_source: AudioAnalysisSource instance to read audio data from
            config: Optional configuration dictionary

        Raises:
            vol.Invalid: If configuration validation fails
            AttributeError: If audio_source lacks required attributes
        """
        if audio_source is None:
            raise ValueError("audio_source cannot be None")

        self.audio = audio_source
        config = config or {}

        try:
            self._config = self.CONFIG_SCHEMA(config)
        except vol.Invalid as e:
            _LOGGER.error(f"Invalid mood detector configuration: {e}")
            raise

        # Calculate history buffer size based on sample rate
        try:
            sample_rate = self.audio._config.get("sample_rate", 60)
            if sample_rate <= 0:
                _LOGGER.warning(
                    f"Invalid sample_rate: {sample_rate}, using default 60"
                )
                sample_rate = 60
        except (AttributeError, KeyError):
            _LOGGER.warning(
                "Could not get sample_rate from audio source, using default 60"
            )
            sample_rate = 60

        history_size = max(
            10, int(self._config["history_length"] * sample_rate)
        )

        # Feature history buffers
        self._energy_history = deque(maxlen=history_size)
        self._spectral_centroid_history = deque(maxlen=history_size)
        self._bass_history = deque(maxlen=history_size)
        self._beat_strength_history = deque(maxlen=history_size)
        self._volume_history = deque(maxlen=history_size)

        # Smoothed mood values
        self._energy_filter = ExpFilter(
            0.5,
            alpha_decay=self._config["mood_smoothing"],
            alpha_rise=self._config["mood_smoothing"],
        )
        self._valence_filter = ExpFilter(
            0.5,
            alpha_decay=self._config["mood_smoothing"],
            alpha_rise=self._config["mood_smoothing"],
        )

        # Current mood state (all values normalized to 0-1 range)
        self._current_mood: dict[str, float] = {
            "energy": 0.5,  # 0-1: calm to energetic
            "valence": 0.5,  # 0-1: sad to happy
            "intensity": 0.5,  # 0-1: soft to intense
            "brightness": 0.5,  # 0-1: dark to bright
            "tempo_bpm": 120.0,  # Beats per minute (not normalized)
            "beat_strength": 0.5,  # 0-1: weak to strong beats
            "spectral_warmth": 0.5,  # 0-1: warm (bass) to cool/bright (treble)
            "rhythm_regularity": 0.5,  # 0-1: irregular to regular rhythm
            "harmonic_ratio": 0.5,  # 0-1: percussive to harmonic
            "complexity": 0.5,  # 0-1: simple to complex
        }

        # Lock for protecting state access (threading.Lock for sync method compatibility)
        self._state_lock = threading.Lock()

        # Cache for expensive calculations
        self._last_feature_extraction = 0.0
        self._feature_extraction_interval = (
            0.1  # Extract features max 10x per second
        )

        # Timing
        self._last_update = time.time()
        self._update_interval = 1.0 / self._config["update_rate"]

        # Librosa integration (optional)
        self._use_librosa = (
            self._config.get("use_librosa", False)
            and LIBROSA_MODULE_AVAILABLE
            and is_librosa_available()
        )
        self._librosa_extractor = None

        if self._use_librosa:
            try:
                sample_rate = self.audio._config.get("sample_rate", 60)
                self._librosa_extractor = create_librosa_extractor(
                    sample_rate=sample_rate,
                    buffer_duration=self._config.get(
                        "librosa_buffer_duration", 3.0
                    ),
                    update_interval=self._config.get(
                        "librosa_update_interval", 2.0
                    ),
                )
                if self._librosa_extractor:
                    _LOGGER.info(
                        "Librosa integration enabled for enhanced mood detection"
                    )
                else:
                    _LOGGER.warning(
                        "Librosa requested but extractor creation failed"
                    )
                    self._use_librosa = False
            except Exception as e:
                _LOGGER.warning(f"Failed to initialize librosa: {e}")
                self._use_librosa = False

    def update(self) -> dict[str, float]:
        """
        Update mood analysis from current audio data.

        This method should be called regularly (at the configured update_rate)
        to keep mood metrics current. Results are throttled to prevent excessive
        computation.

        Returns:
            Dictionary containing current mood metrics (always returns valid dict,
            even if update was skipped due to throttling)
        """
        current_time = time.time()

        # Throttle updates to configured rate (check without lock for performance)
        with self._state_lock:
            if current_time - self._last_update < self._update_interval:
                return self._current_mood.copy()
            self._last_update = current_time

        # Feed audio to librosa buffer if enabled (do this even if we skip feature extraction)
        if self._use_librosa and self._librosa_extractor:
            try:
                audio_sample = self.audio.audio_sample(raw=True)
                if audio_sample is not None and len(audio_sample) > 0:
                    # Validate audio data before processing
                    try:
                        # Ensure it's a numpy array
                        if not isinstance(audio_sample, np.ndarray):
                            audio_sample = np.asarray(audio_sample, dtype=np.float32)
                        
                        # Check for NaN or Inf values
                        if np.any(np.isnan(audio_sample)) or np.any(np.isinf(audio_sample)):
                            _LOGGER.debug("Audio sample contains NaN or Inf values, skipping")
                        else:
                            # Validate data range (clip extreme values)
                            if np.any(np.abs(audio_sample) > 10.0):
                                audio_sample = np.clip(audio_sample, -1.0, 1.0)
                            
                            self._librosa_extractor.audio_buffer.add_sample(
                                audio_sample
                            )
                    except (ValueError, TypeError) as e:
                        _LOGGER.debug(f"Error validating audio sample: {e}")
            except (AttributeError, TypeError) as e:
                _LOGGER.debug(f"Error adding audio to librosa buffer: {e}")
            except Exception as e:
                _LOGGER.warning(
                    f"Unexpected error adding audio to librosa buffer: {e}"
                )

        # Extract features from audio source
        try:
            # Calculate all mood metrics
            energy = self._calculate_energy()
            valence = self._calculate_valence()
            intensity = self._calculate_intensity()
            brightness = self._calculate_brightness()
            beat_strength = self._calculate_beat_strength()
            spectral_warmth = self._calculate_spectral_warmth()

            # Update smoothed values (these filters handle edge cases internally)
            # Note: Filter updates are thread-safe internally, but we protect state access
            self._energy_filter.update(energy)
            self._valence_filter.update(valence)

            # Calculate additional mood metrics from librosa features
            rhythm_regularity = 0.5
            harmonic_ratio = 0.5
            complexity = 0.5

            if self._use_librosa and self._librosa_extractor:
                try:
                    features = self._librosa_extractor.extract_features()
                    if features:
                        # Rhythm regularity
                        if features.get("rhythm_regularity") is not None:
                            rhythm_regularity = float(
                                np.clip(
                                    features["rhythm_regularity"], 0.0, 1.0
                                )
                            )

                        # Harmonic ratio (melodic vs percussive)
                        if features.get("harmonic_ratio") is not None:
                            harmonic_ratio = float(
                                np.clip(features["harmonic_ratio"], 0.0, 1.0)
                            )

                        # Complexity (based on spectral bandwidth and MFCC variance)
                        if features.get("spectral_bandwidth_norm") is not None:
                            bandwidth = float(
                                features["spectral_bandwidth_norm"]
                            )
                            if features.get("mfcc_std") is not None:
                                mfcc_std = (
                                    np.mean(features["mfcc_std"])
                                    if isinstance(
                                        features["mfcc_std"], np.ndarray
                                    )
                                    else 0.0
                                )
                                complexity = float(
                                    np.clip(
                                        (bandwidth * 0.6 + mfcc_std * 0.4),
                                        0.0,
                                        1.0,
                                    )
                                )
                            else:
                                complexity = float(
                                    np.clip(bandwidth, 0.0, 1.0)
                                )
                except (TypeError, AttributeError, ValueError) as e:
                    _LOGGER.debug(
                        f"Error extracting additional mood metrics: {e}"
                    )

            # Update current mood atomically with lock protection
            with self._state_lock:
                self._current_mood.update(
                    {
                        "energy": float(
                            np.clip(self._energy_filter.value, 0.0, 1.0)
                        ),
                        "valence": float(
                            np.clip(self._valence_filter.value, 0.0, 1.0)
                        ),
                        "intensity": float(np.clip(intensity, 0.0, 1.0)),
                        "brightness": float(np.clip(brightness, 0.0, 1.0)),
                        "beat_strength": float(np.clip(beat_strength, 0.0, 1.0)),
                        "spectral_warmth": float(
                            np.clip(spectral_warmth, 0.0, 1.0)
                        ),
                        "rhythm_regularity": float(
                            np.clip(rhythm_regularity, 0.0, 1.0)
                        ),
                        "harmonic_ratio": float(np.clip(harmonic_ratio, 0.0, 1.0)),
                        "complexity": float(np.clip(complexity, 0.0, 1.0)),
                    }
                )
                # Return a copy while holding the lock to ensure consistency
                return self._current_mood.copy()

        except Exception as e:
            _LOGGER.warning(f"Error updating mood: {e}", exc_info=True)
            # Return current mood even if update failed
            with self._state_lock:
                return self._current_mood.copy()

    def _calculate_energy(self) -> float:
        """
        Calculate overall energy level from audio features.

        Enhanced with librosa tempo detection for more accurate energy.

        Energy is based on:
        - Volume level (30% weight)
        - Beat strength (40% weight)
        - Low frequency power (30% weight)
        - Tempo (librosa tempo detection, if available)

        Returns:
            Energy value between 0.0 (calm) and 1.0 (energetic)
        """
        try:
            # Get current volume with error handling
            try:
                volume = float(self.audio.volume(filtered=True))
                volume = np.clip(volume, 0.0, 1.0)
            except (AttributeError, TypeError, ValueError):
                volume = 0.5
                _LOGGER.debug("Could not get volume, using default 0.5")

            self._volume_history.append(volume)

            # Get beat-related energy with safe fallbacks
            try:
                beat_power = float(self.audio.beat_power(filtered=True))
                lows_power = float(self.audio.lows_power(filtered=True))
                beat_power = np.clip(beat_power, 0.0, 1.0)
                lows_power = np.clip(lows_power, 0.0, 1.0)
            except (AttributeError, TypeError):
                beat_power = 0.5
                lows_power = 0.5
                _LOGGER.debug("Could not get melbank features, using defaults")

            # Base energy calculation with weighted combination
            energy_raw = volume * 0.3 + beat_power * 0.4 + lows_power * 0.3

            # Enhance with librosa tempo and onset features (if available and recent)
            if self._use_librosa and self._librosa_extractor:
                try:
                    features = self._librosa_extractor.extract_features()
                    if features:
                        # Use tempo for energy
                        if features.get("tempo") is not None:
                            tempo = float(features["tempo"])
                            # Normalize tempo to 0-1 (assuming 60-180 BPM range)
                            # Tempo outside this range is clipped
                            tempo_norm = np.clip(
                                (tempo - 60.0) / 120.0, 0.0, 1.0
                            )
                            # Higher tempo = higher energy (blend with existing energy)
                            energy_raw = energy_raw * 0.6 + tempo_norm * 0.4

                        # Use onset rate and strength (rhythm intensity)
                        if features.get("onset_rate_norm") is not None:
                            try:
                                onset_rate = float(features["onset_rate_norm"])
                                onset_rate = np.clip(onset_rate, 0.0, 1.0)
                                energy_raw = (
                                    energy_raw * 0.7 + onset_rate * 0.3
                                )
                            except (TypeError, ValueError):
                                pass

                        if features.get("onset_strength_norm") is not None:
                            try:
                                onset_strength = float(
                                    features["onset_strength_norm"]
                                )
                                onset_strength = np.clip(
                                    onset_strength, 0.0, 1.0
                                )
                                energy_raw = (
                                    energy_raw * 0.8 + onset_strength * 0.2
                                )
                            except (TypeError, ValueError):
                                pass
                except (TypeError, ValueError, AttributeError) as e:
                    _LOGGER.debug(
                        f"Error using librosa features for energy: {e}"
                    )

            # Adjust based on sensitivity (sensitivity amplifies the signal)
            sensitivity = float(self._config["energy_sensitivity"])
            # Apply sensitivity: 0.0 = no amplification, 1.0 = double amplification
            energy = np.clip(energy_raw * (1.0 + sensitivity), 0.0, 1.0)

            self._energy_history.append(energy)

            return float(energy)

        except Exception as e:
            _LOGGER.debug(f"Error calculating energy: {e}", exc_info=False)
            return 0.5

    def _calculate_valence(self) -> float:
        """
        Calculate valence (emotional positivity/negativity).

        Enhanced with librosa key detection:
        - Major key → positive valence (happy, bright)
        - Minor key → negative valence (sad, dark)

        Valence is based on:
        - Major vs minor tonality (librosa key detection + spectral balance)
        - Spectral brightness (high frequencies = positive)
        - Chroma features (harmonic brightness)

        Returns:
            Valence value between 0.0 (sad/dark) and 1.0 (happy/bright)
        """
        try:
            # Get spectral power with safe fallbacks
            try:
                mids_power = float(self.audio.mids_power(filtered=True))
                high_power = float(self.audio.high_power(filtered=True))
                bass_power = float(self.audio.bass_power(filtered=True))

                # Clamp to valid range
                mids_power = np.clip(mids_power, 0.0, 1.0)
                high_power = np.clip(high_power, 0.0, 1.0)
                bass_power = np.clip(bass_power, 0.0, 1.0)
            except (AttributeError, TypeError):
                mids_power = high_power = bass_power = 0.5
                _LOGGER.debug("Could not get spectral power, using defaults")

            # Calculate base valence from spectral balance
            # More high/mid content = higher valence (positive)
            # More bass = lower valence (darker)
            valence = (
                mids_power * 0.4 + high_power * 0.4 + (1.0 - bass_power) * 0.2
            )

            # Enhance with librosa key detection (most important for valence)
            if self._use_librosa and self._librosa_extractor:
                try:
                    features = self._librosa_extractor.extract_features()
                    if features and features.get("mode") is not None:
                        mode = str(features["mode"]).lower()
                        if mode == "major":
                            # Major key = more positive (increase valence)
                            valence = min(1.0, valence * 1.15 + 0.1)
                        elif mode == "minor":
                            # Minor key = more negative (decrease valence)
                            valence = max(0.0, valence * 0.85 - 0.1)

                        # Also use chroma features if available
                        if features.get("chroma") is not None:
                            try:
                                chroma = np.asarray(features["chroma"])
                                if len(chroma) >= 12:
                                    # Bright chroma (higher values in upper notes) = positive
                                    bright_chroma = float(
                                        np.mean(chroma[6:])
                                    )  # Upper half
                                    bright_chroma = np.clip(
                                        bright_chroma, 0.0, 1.0
                                    )
                                    valence = (
                                        valence * 0.7 + bright_chroma * 0.3
                                    )
                            except (TypeError, ValueError, IndexError):
                                _LOGGER.debug(
                                    "Error processing chroma features"
                                )
                except (TypeError, AttributeError) as e:
                    _LOGGER.debug(
                        f"Error using librosa features for valence: {e}"
                    )

            return float(np.clip(valence, 0.0, 1.0))

        except Exception as e:
            _LOGGER.debug(f"Error calculating valence: {e}", exc_info=False)
            return 0.5

    def _calculate_intensity(self) -> float:
        """
        Calculate intensity based on dynamic range and volume changes.

        Intensity measures the dramatic variation in the music:
        - High intensity = large volume changes, dramatic dynamics, sudden shifts
        - Low intensity = stable, consistent volume, smooth transitions

        Returns:
            Intensity value between 0.0 (stable) and 1.0 (dramatic)
        """
        try:
            if len(self._volume_history) < 10:
                return 0.5

            # Use recent volume history (last 30 samples for responsiveness)
            # Convert to list only once for efficiency
            recent_volumes = list(self._volume_history)[-30:]

            if len(recent_volumes) < 2:
                return 0.5

            # Calculate variance in recent volume (measures spread)
            variance = float(np.var(recent_volumes))

            # Calculate rate of change (measures how quickly volume changes)
            volumes_array = np.asarray(recent_volumes, dtype=np.float32)
            changes = np.abs(np.diff(volumes_array))
            change_rate = float(np.mean(changes))

            # Combine variance and change rate with weights
            # Variance gets higher weight as it's more indicative of dramatic changes
            intensity = variance * 5.0 + change_rate * 3.0

            return float(np.clip(intensity, 0.0, 1.0))

        except Exception as e:
            _LOGGER.debug(f"Error calculating intensity: {e}", exc_info=False)
            return 0.5

    def _calculate_brightness(self) -> float:
        """
        Calculate spectral brightness (high frequency content).

        Brightness indicates the presence of high-frequency content:
        - High brightness = lots of treble, crisp, sharp sounds
        - Low brightness = more bass/midrange, warmer, darker sounds

        Enhanced with librosa spectral contrast and rolloff for accuracy.

        Returns:
            Brightness value between 0.0 (dark) and 1.0 (bright)
        """
        try:
            # Get spectral power with safe fallbacks
            try:
                high_power = float(self.audio.high_power(filtered=True))
                mids_power = float(self.audio.mids_power(filtered=True))

                high_power = np.clip(high_power, 0.0, 1.0)
                mids_power = np.clip(mids_power, 0.0, 1.0)
            except (AttributeError, TypeError):
                high_power = mids_power = 0.5
                _LOGGER.debug("Could not get spectral power for brightness")

            # Base brightness calculation (weighted towards high frequencies)
            brightness = high_power * 0.7 + mids_power * 0.3

            # Enhance with librosa spectral features (more accurate)
            if self._use_librosa and self._librosa_extractor:
                try:
                    features = self._librosa_extractor.extract_features()
                    if features:
                        # Use spectral centroid (most accurate brightness indicator)
                        if features.get("spectral_centroid_norm") is not None:
                            try:
                                centroid = float(
                                    features["spectral_centroid_norm"]
                                )
                                centroid = np.clip(centroid, 0.0, 1.0)
                                brightness = (
                                    brightness * 0.5 + centroid * 0.5
                                )  # Higher weight for centroid
                            except (TypeError, ValueError):
                                pass

                        # Use spectral contrast for brightness (high-frequency contrast)
                        if features.get("brightness_contrast") is not None:
                            try:
                                contrast = float(
                                    features["brightness_contrast"]
                                )
                                # Normalize contrast to 0-1 range (empirical scaling)
                                contrast_norm = np.clip(
                                    contrast / 10.0, 0.0, 1.0
                                )
                                brightness = (
                                    brightness * 0.7 + contrast_norm * 0.3
                                )
                            except (TypeError, ValueError):
                                pass

                        # Use spectral rolloff as additional indicator
                        if features.get("spectral_rolloff_norm") is not None:
                            try:
                                rolloff = float(
                                    features["spectral_rolloff_norm"]
                                )
                                rolloff = np.clip(rolloff, 0.0, 1.0)
                                brightness = brightness * 0.8 + rolloff * 0.2
                            except (TypeError, ValueError):
                                pass
                except (TypeError, AttributeError) as e:
                    _LOGGER.debug(
                        f"Error using librosa features for brightness: {e}"
                    )

            return float(np.clip(brightness, 0.0, 1.0))

        except Exception as e:
            _LOGGER.debug(f"Error calculating brightness: {e}", exc_info=False)
            return 0.5

    def _calculate_beat_strength(self) -> float:
        """
        Calculate the strength and consistency of beats.

        Beat strength considers both:
        - Average beat power (how strong beats are)
        - Consistency (how regular/steady the beats are)

        Returns:
            Beat strength value between 0.0 (weak/irregular) and 1.0 (strong/consistent)
        """
        try:
            # Get current beat power
            try:
                beat_power = float(self.audio.beat_power(filtered=True))
                beat_power = np.clip(beat_power, 0.0, 1.0)
            except (AttributeError, TypeError):
                beat_power = 0.5
                _LOGGER.debug("Could not get beat_power, using default")

            self._beat_strength_history.append(beat_power)

            # Need enough history to calculate consistency
            if len(self._beat_strength_history) < 10:
                return float(beat_power)

            # Analyze recent beat history for consistency
            recent_beats = list(self._beat_strength_history)[-30:]
            beats_array = np.asarray(recent_beats, dtype=np.float32)

            avg_strength = float(np.mean(beats_array))
            std_strength = float(np.std(beats_array))

            # Consistency: low variance = high consistency
            # Normalize std to 0-1 range (assuming max std ~0.5 for 0-1 range)
            # Add epsilon to prevent division by zero
            consistency = 1.0 - np.clip(std_strength / (0.5 + 1e-10), 0.0, 1.0)

            # Combine average strength (70%) and consistency (30%)
            beat_strength = avg_strength * 0.7 + consistency * 0.3

            return float(np.clip(beat_strength, 0.0, 1.0))

        except Exception as e:
            _LOGGER.debug(
                f"Error calculating beat strength: {e}", exc_info=False
            )
            return 0.5

    def _calculate_spectral_warmth(self) -> float:
        """
        Calculate spectral warmth (bass vs treble).

        0 = warm (bass-heavy)
        1 = cool/bright (treble-heavy)
        """
        try:
            bass_power = float(self.audio.bass_power(filtered=True))
            high_power = float(self.audio.high_power(filtered=True))

            bass_power = np.clip(bass_power, 0.0, 1.0)
            high_power = np.clip(high_power, 0.0, 1.0)

            self._bass_history.append(bass_power)

            # Balance between bass and highs
            # More bass = warmer (lower value)
            # More highs = cooler/brighter (higher value)
            warmth = 1.0 - (bass_power * 0.6 + (1 - high_power) * 0.4)

            return np.clip(warmth, 0.0, 1.0)

        except Exception as e:
            _LOGGER.debug(f"Error calculating spectral warmth: {e}")
            return 0.5

    def get_mood_category(self, include_genre: bool = True) -> str:
        """
        Get a categorical mood description based on current metrics.

        Enhanced categories now include genre information for more accurate classification:
        - Genre: electronic, rock, jazz, classical, hip_hop, acoustic, metal, pop, ambient, blues
        - Energy: calm, moderate, energetic
        - Tone: dark, neutral, bright
        - Intensity: _gentle, (none), _intense

        Returns:
            String describing the mood category (e.g., "electronic_energetic_bright_intense",
            "acoustic_calm_dark_gentle", "rock_moderate_neutral")
        """
        with self._state_lock:
            mood = self._current_mood.copy()

        # Get genre classification if available
        genre_cat = ""
        if include_genre:
            try:
                # Get music style from metrics if available
                music_styles = mood.get("music_styles", {})
                if music_styles and isinstance(music_styles, dict):
                    # Find dominant genre (highest score)
                    dominant_genre = max(
                        music_styles.items(),
                        key=lambda x: (
                            x[1] if isinstance(x[1], (int, float)) else 0
                        ),
                    )
                    if (
                        dominant_genre[1] > 0.15
                    ):  # Minimum confidence threshold
                        genre_cat = f"{dominant_genre[0]}_"
                else:
                    # Fallback: try to get from dominant_style
                    dominant_style = mood.get("dominant_style")
                    if dominant_style and isinstance(dominant_style, str):
                        genre_cat = f"{dominant_style}_"
            except (AttributeError, TypeError, ValueError) as e:
                _LOGGER.debug(f"Error getting genre for category: {e}")

        # Categorize energy (3 levels)
        energy = mood.get("energy", 0.5)
        if energy < 0.3:
            energy_cat = "calm"
        elif energy < 0.7:
            energy_cat = "moderate"
        else:
            energy_cat = "energetic"

        # Categorize tone/brightness (3 levels)
        brightness = mood.get("brightness", 0.5)
        if brightness < 0.3:
            tone_cat = "dark"
        elif brightness < 0.7:
            tone_cat = "neutral"
        else:
            tone_cat = "bright"

        # Categorize intensity (3 levels, optional modifier)
        intensity = mood.get("intensity", 0.5)
        if intensity > 0.7:
            intensity_cat = "_intense"
        elif intensity < 0.3:
            intensity_cat = "_gentle"
        else:
            intensity_cat = ""

        return f"{genre_cat}{energy_cat}_{tone_cat}{intensity_cat}".strip("_")

    def get_mood_metrics(self) -> dict[str, float]:
        """
        Get all current mood metrics, including librosa-enhanced features.

        Returns:
            Dictionary of mood metrics
        """
        with self._state_lock:
            metrics = self._current_mood.copy()

        # Add librosa features if available
        if self._use_librosa and self._librosa_extractor:
            features = self._librosa_extractor.get_cached_features()
            if features:
                if features.get("tempo"):
                    metrics["tempo_bpm_librosa"] = features["tempo"]
                if features.get("mode"):
                    metrics["key_mode"] = features["mode"]
                if features.get("spectral_rolloff_norm"):
                    metrics["spectral_rolloff"] = features[
                        "spectral_rolloff_norm"
                    ]
                if features.get("spectral_centroid_norm"):
                    metrics["spectral_centroid"] = features[
                        "spectral_centroid_norm"
                    ]
                if features.get("onset_rate_norm"):
                    metrics["onset_rate"] = features["onset_rate_norm"]

                # Add music style classification if available
                try:
                    style_scores = classify_music_style(features)
                    if style_scores:
                        metrics["music_styles"] = style_scores
                        # Get dominant style
                        if style_scores:
                            dominant_style = max(
                                style_scores.items(), key=lambda x: x[1]
                            )
                            metrics["dominant_style"] = dominant_style[0]
                            metrics["style_confidence"] = dominant_style[1]

                            # Add sub-genre classification
                            try:
                                sub_genre_scores = classify_sub_genre(
                                    features, dominant_style[0]
                                )
                                if sub_genre_scores:
                                    metrics["sub_genres"] = sub_genre_scores
                                    # Get dominant sub-genre
                                    if sub_genre_scores:
                                        dominant_sub = max(
                                            sub_genre_scores.items(),
                                            key=lambda x: x[1],
                                        )
                                        if (
                                            dominant_sub[1] > 0.2
                                        ):  # Minimum confidence
                                            metrics["dominant_sub_genre"] = (
                                                dominant_sub[0]
                                            )
                                            metrics["sub_genre_confidence"] = (
                                                dominant_sub[1]
                                            )
                            except Exception as e:
                                _LOGGER.debug(
                                    f"Error classifying sub-genre: {e}"
                                )
                except (ImportError, Exception) as e:
                    _LOGGER.debug(f"Error classifying music style: {e}")

        return metrics

    def detect_change(self, threshold: float = 0.2) -> bool:
        """
        Detect if there's been a significant mood change.

        Compares recent energy levels to previous period to detect
        significant shifts in musical mood.

        Args:
            threshold: Minimum change magnitude to trigger (0-1).
                      Default 0.2 means 20% change is considered significant.

        Returns:
            True if significant change detected, False otherwise
        """
        if len(self._energy_history) < 20:
            return False

        try:
            # Get recent and previous energy periods
            energy_list = list(self._energy_history)
            recent_period = energy_list[-10:]
            previous_period = energy_list[-20:-10]

            if len(recent_period) < 10 or len(previous_period) < 10:
                return False

            # Calculate mean energy for each period
            recent_energy = float(np.mean(recent_period))
            previous_energy = float(np.mean(previous_period))

            # Calculate absolute change
            change = abs(recent_energy - previous_energy)

            # Check if change exceeds threshold
            return change > float(threshold)

        except (IndexError, ValueError, TypeError) as e:
            _LOGGER.debug(f"Error detecting mood change: {e}", exc_info=False)
            return False
