"""
Librosa-based audio feature extraction for enhanced mood detection.

This module provides advanced audio analysis using librosa to improve
mood detection accuracy. It's designed as an optional enhancement that
gracefully falls back to basic features if librosa is unavailable.

Features:
- Key/mode detection (major/minor tonality)
- Chroma features (harmonic content)
- Tempo detection
- Spectral analysis (contrast, rolloff, brightness)
- MFCC (timbre characteristics)
- Zero crossing rate (texture analysis)
"""

import logging
import threading
import time
from collections import deque
from typing import Dict, Optional, Union

import numpy as np

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    librosa = None

_LOGGER = logging.getLogger(__name__)

# Type aliases for better code clarity
FeatureDict = dict[str, Union[float, np.ndarray, str, None]]


class LibrosaAudioBuffer:
    """
    Buffers audio samples for librosa analysis.

    Maintains a sliding window of recent audio data to enable
    librosa's frame-based analysis methods.
    """

    def __init__(self, sample_rate: int = 30000, buffer_duration: float = 3.0):
        """
        Initialize audio buffer.

        Args:
            sample_rate: Audio sample rate in Hz (must be > 0)
            buffer_duration: Duration of audio to buffer in seconds (must be > 0)

        Raises:
            ValueError: If sample_rate or buffer_duration is invalid
        """
        if sample_rate <= 0:
            raise ValueError(
                f"Invalid sample_rate: {sample_rate} (must be > 0)"
            )
        if buffer_duration <= 0:
            raise ValueError(
                f"Invalid buffer_duration: {buffer_duration} (must be > 0)"
            )

        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate * buffer_duration)
        if self.buffer_size <= 0:
            raise ValueError(f"Invalid buffer_size: {self.buffer_size}")

        self.buffer = deque(maxlen=self.buffer_size)
        self.lock = threading.Lock()
        self._total_samples = 0
        self._min_buffer_ratio = 0.3  # Minimum 30% full for analysis

    def add_sample(self, audio_sample: Optional[np.ndarray]) -> None:
        """
        Add new audio sample to buffer.

        Args:
            audio_sample: Numpy array of audio samples (float32 or convertible)

        Note:
            Silently ignores None or empty samples for robustness
        """
        if audio_sample is None:
            return

        try:
            # Ensure we have a numpy array
            if not isinstance(audio_sample, np.ndarray):
                audio_sample = np.asarray(audio_sample, dtype=np.float32)

            if len(audio_sample) == 0:
                return

            # Flatten to 1D and ensure float32
            flattened = audio_sample.flatten().astype(np.float32)

            with self.lock:
                self.buffer.extend(flattened)
                self._total_samples += len(flattened)
        except (ValueError, TypeError) as e:
            _LOGGER.debug(f"Error adding audio sample: {e}")

    def get_buffer(self) -> Optional[np.ndarray]:
        """
        Get current buffer as numpy array.

        Returns:
            Numpy array of buffered audio (float32), or None if insufficient data
        """
        with self.lock:
            min_samples = int(self.buffer_size * self._min_buffer_ratio)
            if len(self.buffer) < min_samples:
                return None

            # Convert to numpy array efficiently
            return np.array(self.buffer, dtype=np.float32)

    def is_ready(self) -> bool:
        """
        Check if buffer has enough data for analysis.

        Returns:
            True if buffer has sufficient data (>= 30% full)
        """
        with self.lock:
            min_samples = int(self.buffer_size * self._min_buffer_ratio)
            return len(self.buffer) >= min_samples

    def get_fill_ratio(self) -> float:
        """
        Get the current buffer fill ratio (0.0 to 1.0).

        Returns:
            Buffer fill ratio as float between 0.0 and 1.0
        """
        with self.lock:
            return (
                min(1.0, len(self.buffer) / self.buffer_size)
                if self.buffer_size > 0
                else 0.0
            )

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()
            self._total_samples = 0


class LibrosaFeatureExtractor:
    """
    Extracts advanced audio features using librosa.

    This class runs analysis in a way that minimizes performance impact
    by caching results and updating features at configurable intervals.
    """

    def __init__(
        self,
        audio_buffer: LibrosaAudioBuffer,
        sample_rate: int = 30000,
        update_interval: float = 2.0,
    ):
        """
        Initialize feature extractor.

        Args:
            audio_buffer: LibrosaAudioBuffer instance
            sample_rate: Original audio sample rate
            update_interval: Minimum seconds between feature updates
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa is not available")

        self.audio_buffer = audio_buffer
        self.original_sample_rate = sample_rate
        self.target_sample_rate = 22050  # Librosa's preferred rate
        self.update_interval = update_interval

        self._features_cache: dict = {}
        self._last_update = 0.0
        self._lock = threading.Lock()

    def extract_features(self) -> Optional[FeatureDict]:
        """
        Extract all librosa features from buffered audio.

        This method performs expensive audio analysis operations, so results
        are cached and only updated at the configured interval.

        Returns:
            Dictionary of extracted features, or None if not ready or error occurs.
            Features include: key, mode, chroma, tempo, spectral_contrast, etc.
        """
        if not self.audio_buffer.is_ready():
            return None

        current_time = time.time()

        # Check if we need to update (throttle expensive operations)
        with self._lock:
            time_since_update = current_time - self._last_update
            if time_since_update < self.update_interval:
                # Return cached features if available
                return (
                    self._features_cache.copy()
                    if self._features_cache
                    else None
                )

        # Get audio buffer
        audio_data = self.audio_buffer.get_buffer()
        if audio_data is None or len(audio_data) == 0:
            return None

        try:
            # Resample to librosa's preferred rate
            # Use 'kaiser_best' for highest quality, but can be slow
            # Consider 'kaiser_fast' for better performance if needed
            audio_resampled = librosa.resample(
                audio_data,
                orig_sr=self.original_sample_rate,
                target_sr=self.target_sample_rate,
                res_type="kaiser_best",
            )

            # Validate resampled audio
            if len(audio_resampled) == 0:
                _LOGGER.warning("Resampled audio is empty")
                return None

            features = {}

            # 1. Key Detection (Major/Minor) - Most important for valence
            # This is computationally expensive, so we catch all exceptions
            try:
                # Extract harmonic component first for better key detection
                y_harmonic = librosa.effects.harmonic(audio_resampled)
                key, mode = librosa.harmonic.key(
                    y=y_harmonic, sr=self.target_sample_rate
                )
                features["key"] = str(key) if key is not None else None
                features["mode"] = (
                    str(mode) if mode is not None else None
                )  # 'major' or 'minor'
                features["mode_numeric"] = (
                    1.0
                    if mode == "major"
                    else (0.0 if mode == "minor" else 0.5)
                )
            except Exception as e:
                _LOGGER.debug(f"Error detecting key: {e}", exc_info=False)
                features["key"] = None
                features["mode"] = None
                features["mode_numeric"] = 0.5

            # 2. Chroma Features (Harmonic content)
            try:
                chroma = librosa.feature.chroma_stft(
                    y=audio_resampled, sr=self.target_sample_rate, n_chroma=12
                )
                features["chroma"] = np.mean(
                    chroma, axis=1
                )  # Average across time
                features["chroma_std"] = np.std(chroma, axis=1)  # Variability
            except Exception as e:
                _LOGGER.debug(f"Error extracting chroma: {e}")
                features["chroma"] = None
                features["chroma_std"] = None

            # 3. Tempo Detection
            try:
                tempo, beats = librosa.beat.beat_track(
                    y=audio_resampled, sr=self.target_sample_rate, units="time"
                )
                features["tempo"] = float(tempo)
                features["beat_times"] = beats
            except Exception as e:
                _LOGGER.debug(f"Error detecting tempo: {e}")
                features["tempo"] = None
                features["beat_times"] = None

            # 4. Spectral Contrast (Brightness indicator)
            try:
                spectral_contrast = librosa.feature.spectral_contrast(
                    y=audio_resampled, sr=self.target_sample_rate
                )
                features["spectral_contrast"] = np.mean(
                    spectral_contrast, axis=1
                )
                # High-frequency contrast indicates brightness
                features["brightness_contrast"] = np.mean(
                    spectral_contrast[-3:]
                )
            except Exception as e:
                _LOGGER.debug(f"Error extracting spectral contrast: {e}")
                features["spectral_contrast"] = None
                features["brightness_contrast"] = None

            # 5. Spectral Rolloff (Frequency distribution)
            try:
                rolloff = librosa.feature.spectral_rolloff(
                    y=audio_resampled, sr=self.target_sample_rate
                )
                features["spectral_rolloff"] = float(np.mean(rolloff))
                # Normalize to 0-1 range (assuming max rolloff ~ sr/2)
                features["spectral_rolloff_norm"] = np.clip(
                    features["spectral_rolloff"]
                    / (self.target_sample_rate / 2),
                    0.0,
                    1.0,
                )
            except Exception as e:
                _LOGGER.debug(f"Error extracting spectral rolloff: {e}")
                features["spectral_rolloff"] = None
                features["spectral_rolloff_norm"] = None

            # 6. Zero Crossing Rate (Timbre/texture)
            try:
                zcr = librosa.feature.zero_crossing_rate(audio_resampled)
                features["zero_crossing_rate"] = float(np.mean(zcr))
            except Exception as e:
                _LOGGER.debug(f"Error extracting zero crossing rate: {e}")
                features["zero_crossing_rate"] = None

            # 7. MFCC (Timbre characteristics) - Full set for genre-like classification
            try:
                mfcc = librosa.feature.mfcc(
                    y=audio_resampled, sr=self.target_sample_rate, n_mfcc=13
                )
                # Store mean and std for each coefficient (important for genre classification)
                features["mfcc"] = np.mean(mfcc, axis=1)  # All 13 coefficients
                features["mfcc_std"] = np.std(mfcc, axis=1)  # Variability
                # First coefficient is energy-related, others capture timbre
                features["mfcc_energy"] = float(np.mean(mfcc[0]))
                features["mfcc_timbre"] = np.mean(
                    mfcc[1:6], axis=1
                )  # Timbre coefficients
            except Exception as e:
                _LOGGER.debug(f"Error extracting MFCC: {e}")
                features["mfcc"] = None
                features["mfcc_std"] = None
                features["mfcc_energy"] = None
                features["mfcc_timbre"] = None

            # 8. Spectral Centroid (Brightness indicator, similar to genre classification)
            try:
                spectral_centroid = librosa.feature.spectral_centroid(
                    y=audio_resampled, sr=self.target_sample_rate
                )
                features["spectral_centroid"] = float(
                    np.mean(spectral_centroid)
                )
                # Normalize to 0-1 (typical range 0-5000 Hz, normalize to sr/2)
                features["spectral_centroid_norm"] = np.clip(
                    features["spectral_centroid"]
                    / (self.target_sample_rate / 2),
                    0.0,
                    1.0,
                )
                features["spectral_centroid_std"] = float(
                    np.std(spectral_centroid)
                )
            except Exception as e:
                _LOGGER.debug(f"Error extracting spectral centroid: {e}")
                features["spectral_centroid"] = None
                features["spectral_centroid_norm"] = None
                features["spectral_centroid_std"] = None

            # 9. Spectral Bandwidth (Frequency spread)
            try:
                spectral_bandwidth = librosa.feature.spectral_bandwidth(
                    y=audio_resampled, sr=self.target_sample_rate
                )
                features["spectral_bandwidth"] = float(
                    np.mean(spectral_bandwidth)
                )
                features["spectral_bandwidth_norm"] = np.clip(
                    features["spectral_bandwidth"]
                    / (self.target_sample_rate / 2),
                    0.0,
                    1.0,
                )
            except Exception as e:
                _LOGGER.debug(f"Error extracting spectral bandwidth: {e}")
                features["spectral_bandwidth"] = None
                features["spectral_bandwidth_norm"] = None

            # 10. Onset Detection (Rhythm and beat strength)
            try:
                onset_frames = librosa.onset.onset_detect(
                    y=audio_resampled, sr=self.target_sample_rate, units="time"
                )
                # Calculate onset rate (onsets per second)
                if len(onset_frames) > 0:
                    duration = len(audio_resampled) / self.target_sample_rate
                    features["onset_rate"] = (
                        len(onset_frames) / duration if duration > 0 else 0.0
                    )
                    # Normalize to 0-1 (assuming max ~10 onsets/sec)
                    features["onset_rate_norm"] = np.clip(
                        features["onset_rate"] / 10.0, 0.0, 1.0
                    )
                    # Calculate onset strength
                    onset_strength = librosa.onset.onset_strength(
                        y=audio_resampled, sr=self.target_sample_rate
                    )
                    features["onset_strength"] = float(np.mean(onset_strength))
                    features["onset_strength_norm"] = np.clip(
                        features["onset_strength"], 0.0, 1.0
                    )
                else:
                    features["onset_rate"] = 0.0
                    features["onset_rate_norm"] = 0.0
                    features["onset_strength"] = 0.0
                    features["onset_strength_norm"] = 0.0
            except Exception as e:
                _LOGGER.debug(f"Error detecting onsets: {e}")
                features["onset_rate"] = None
                features["onset_rate_norm"] = None
                features["onset_strength"] = None
                features["onset_strength_norm"] = None

            # 11. Tonnetz (Harmonic network features - useful for genre classification)
            try:
                tonnetz = librosa.feature.tonnetz(
                    y=librosa.effects.harmonic(audio_resampled),
                    sr=self.target_sample_rate,
                )
                features["tonnetz"] = np.mean(
                    tonnetz, axis=1
                )  # 6-dimensional feature
                features["tonnetz_stability"] = float(
                    1.0 - np.std(tonnetz)
                )  # Higher = more stable harmony
            except Exception as e:
                _LOGGER.debug(f"Error extracting tonnetz: {e}")
                features["tonnetz"] = None
                features["tonnetz_stability"] = None

            # 12. Polyphonic Features (Complexity indicator)
            try:
                # Harmonic/percussive separation
                y_harmonic, y_percussive = librosa.effects.hpss(
                    audio_resampled
                )
                # Ratio of harmonic to total energy
                harmonic_energy = float(np.sum(y_harmonic**2))
                total_energy = float(np.sum(audio_resampled**2))
                features["harmonic_ratio"] = (
                    harmonic_energy / total_energy if total_energy > 0 else 0.5
                )
                features["percussive_ratio"] = 1.0 - features["harmonic_ratio"]
                # Higher harmonic ratio = more melodic, lower = more percussive/rhythmic
            except Exception as e:
                _LOGGER.debug(f"Error extracting polyphonic features: {e}")
                features["harmonic_ratio"] = None
                features["percussive_ratio"] = None

            # 13. Rhythm Features (Tempo stability and regularity)
            try:
                if (
                    features.get("tempo") is not None
                    and features.get("beat_times") is not None
                ):
                    beat_times = features["beat_times"]
                    if len(beat_times) > 1:
                        # Calculate inter-beat intervals
                        intervals = np.diff(beat_times)
                        # Regularity: lower std = more regular rhythm
                        features["rhythm_regularity"] = float(
                            1.0
                            - np.clip(
                                np.std(intervals) / np.mean(intervals),
                                0.0,
                                1.0,
                            )
                        )
                        # Tempo stability
                        expected_interval = (
                            60.0 / features["tempo"]
                            if features["tempo"] > 0
                            else 0.5
                        )
                        tempo_stability = 1.0 - np.clip(
                            np.abs(np.mean(intervals) - expected_interval)
                            / expected_interval,
                            0.0,
                            1.0,
                        )
                        features["tempo_stability"] = float(tempo_stability)
                    else:
                        features["rhythm_regularity"] = 0.5
                        features["tempo_stability"] = 0.5
                else:
                    features["rhythm_regularity"] = None
                    features["tempo_stability"] = None
            except Exception as e:
                _LOGGER.debug(f"Error calculating rhythm features: {e}")
                features["rhythm_regularity"] = None
                features["tempo_stability"] = None

            # Update cache atomically
            with self._lock:
                self._features_cache = features.copy()  # Store a copy
                self._last_update = current_time

            return features

        except Exception as e:
            _LOGGER.warning(
                f"Error in librosa feature extraction: {e}", exc_info=True
            )
            # Return cached features if available, even if extraction failed
            with self._lock:
                if self._features_cache:
                    return self._features_cache.copy()
            return None

    def get_cached_features(self) -> Optional[FeatureDict]:
        """
        Get cached features without re-extraction.

        Returns:
            Copy of cached features dictionary, or None if no cache exists
        """
        with self._lock:
            return (
                self._features_cache.copy() if self._features_cache else None
            )

    def clear_cache(self) -> None:
        """Clear the feature cache, forcing next extraction to recompute."""
        with self._lock:
            self._features_cache = {}
            self._last_update = 0.0

    def get_cache_age(self) -> float:
        """
        Get the age of the cached features in seconds.

        Returns:
            Seconds since last feature update, or float('inf') if no cache
        """
        with self._lock:
            if self._last_update == 0.0:
                return float("inf")
            return time.time() - self._last_update


def is_librosa_available() -> bool:
    """Check if librosa is available."""
    return LIBROSA_AVAILABLE


def classify_music_style(features: FeatureDict) -> dict[str, float]:
    """
    Classify music style/genre-like characteristics from audio features.

    Enhanced rule-based classifier with more accurate genre detection.
    Uses comprehensive feature analysis inspired by music information retrieval research.

    Returns a dictionary with style probabilities/characteristics:
    - electronic: Electronic/dance/EDM music (high tempo, percussive, regular)
    - rock: Rock/pop rock (moderate-high tempo, balanced spectral, strong beats)
    - jazz: Jazz/fusion (high harmonic, variable rhythm, complex harmony)
    - classical: Classical/orchestral (high harmonic, lower tempo, smooth)
    - hip_hop: Hip-hop/rap/trap (high percussive, moderate tempo, strong beats)
    - acoustic: Acoustic/folk/country (high harmonic, warm spectral, moderate tempo)
    - metal: Metal/hard rock (high energy, high spectral centroid, fast tempo)
    - pop: Pop music (moderate tempo, balanced features, catchy)
    - ambient: Ambient/electronic ambient (low tempo, high harmonic, smooth)
    - blues: Blues (moderate tempo, moderate harmonic, expressive)

    Args:
        features: Dictionary of extracted audio features

    Returns:
        Dictionary mapping style names to confidence scores (0-1)
    """
    if not features:
        return {}

    style_scores = {
        "electronic": 0.0,
        "rock": 0.0,
        "jazz": 0.0,
        "classical": 0.0,
        "hip_hop": 0.0,
        "acoustic": 0.0,
        "metal": 0.0,
        "pop": 0.0,
        "ambient": 0.0,
        "blues": 0.0,
    }

    try:
        # Get key features with safe defaults
        tempo = (
            float(features.get("tempo", 120.0))
            if features.get("tempo") is not None
            else 120.0
        )
        spectral_centroid = (
            float(features.get("spectral_centroid_norm", 0.5))
            if features.get("spectral_centroid_norm") is not None
            else 0.5
        )
        zero_crossing = (
            float(features.get("zero_crossing_rate", 0.05))
            if features.get("zero_crossing_rate") is not None
            else 0.05
        )
        harmonic_ratio = (
            float(features.get("harmonic_ratio", 0.5))
            if features.get("harmonic_ratio") is not None
            else 0.5
        )
        percussive_ratio = (
            float(features.get("percussive_ratio", 0.5))
            if features.get("percussive_ratio") is not None
            else 0.5
        )
        onset_rate = (
            float(features.get("onset_rate_norm", 0.5))
            if features.get("onset_rate_norm") is not None
            else 0.5
        )
        rhythm_regularity = (
            float(features.get("rhythm_regularity", 0.5))
            if features.get("rhythm_regularity") is not None
            else 0.5
        )
        spectral_bandwidth = (
            float(features.get("spectral_bandwidth_norm", 0.5))
            if features.get("spectral_bandwidth_norm") is not None
            else 0.5
        )
        tempo_stability = (
            float(features.get("tempo_stability", 0.5))
            if features.get("tempo_stability") is not None
            else 0.5
        )

        # Get MFCC features for timbre analysis
        mfcc_energy = (
            float(features.get("mfcc_energy", 0.0))
            if features.get("mfcc_energy") is not None
            else 0.0
        )
        mfcc_timbre = features.get("mfcc_timbre")
        if mfcc_timbre is not None and isinstance(mfcc_timbre, np.ndarray):
            mfcc_timbre_mean = float(np.mean(mfcc_timbre))
        else:
            mfcc_timbre_mean = 0.0

        # Get mode (major/minor) for emotional context
        mode = features.get("mode", "").lower() if features.get("mode") else ""
        mode_numeric = (
            1.0 if mode == "major" else (0.0 if mode == "minor" else 0.5)
        )

        # 1. ELECTRONIC/DANCE/EDM
        # Characteristics: High tempo (120-180 BPM), high percussive ratio, very regular rhythm,
        #                  high onset rate, moderate-high spectral centroid
        if (
            tempo >= 120
            and percussive_ratio > 0.35
            and rhythm_regularity > 0.55
        ):
            tempo_score = min(1.0, (tempo - 100) / 80)  # 100-180 BPM range
            electronic_score = (
                tempo_score * 0.25
                + percussive_ratio * 0.25
                + rhythm_regularity * 0.20
                + onset_rate * 0.15
                + (spectral_centroid * 0.8 + 0.2)
                * 0.15  # Prefer moderate-high brightness
            )
            style_scores["electronic"] = min(1.0, electronic_score)

        # 2. ROCK
        # Characteristics: Moderate-high tempo (100-160 BPM), balanced spectral content,
        #                  moderate harmonic ratio, strong beats, moderate regularity
        if 95 < tempo < 165:
            tempo_match = 1.0 - abs(tempo - 130) / 35  # Peak around 130 BPM
            rock_score = (
                max(0.0, tempo_match) * 0.30
                + (1.0 - abs(spectral_centroid - 0.5) / 0.5)
                * 0.25  # Balanced brightness
                + harmonic_ratio * 0.20
                + rhythm_regularity * 0.15
                + (1.0 - abs(percussive_ratio - 0.5) / 0.5)
                * 0.10  # Balanced percussive/harmonic
            )
            style_scores["rock"] = min(1.0, rock_score)

        # 3. METAL/HARD ROCK
        # Characteristics: Fast tempo (140-200 BPM), high spectral centroid (bright/harsh),
        #                  high percussive ratio, high energy, irregular rhythm sometimes
        if tempo >= 140 and spectral_centroid > 0.55:
            metal_score = (
                min(1.0, (tempo - 120) / 80) * 0.30
                + spectral_centroid * 0.30
                + percussive_ratio * 0.20
                + onset_rate * 0.20
            )
            style_scores["metal"] = min(1.0, metal_score)

        # 4. JAZZ
        # Characteristics: Variable tempo, high harmonic ratio, lower rhythm regularity,
        #                  moderate spectral centroid, complex harmony
        if harmonic_ratio > 0.55:
            jazz_score = (
                harmonic_ratio * 0.35
                + (1.0 - rhythm_regularity * 0.8)
                * 0.25  # Less regular = more jazz-like
                + (1.0 - abs(spectral_centroid - 0.45) / 0.45) * 0.20
                + (1.0 - abs(tempo - 120) / 60) * 0.20  # Wide tempo range
            )
            style_scores["jazz"] = min(1.0, jazz_score)

        # 5. CLASSICAL
        # Characteristics: Lower tempo (< 120 BPM), very high harmonic ratio,
        #                  low zero crossing rate (smooth), low percussive ratio
        if harmonic_ratio > 0.65 and tempo < 125 and zero_crossing < 0.12:
            classical_score = (
                harmonic_ratio * 0.35
                + (1.0 - tempo / 125) * 0.25
                + (1.0 - zero_crossing * 8) * 0.25
                + (1.0 - percussive_ratio) * 0.15
            )
            style_scores["classical"] = min(1.0, classical_score)

        # 6. HIP-HOP/RAP/TRAP
        # Characteristics: Moderate tempo (70-110 BPM), very high percussive ratio,
        #                  high onset rate, strong beats, regular rhythm
        if 70 < tempo < 115 and percussive_ratio > 0.45:
            hiphop_score = (
                percussive_ratio * 0.35
                + (1.0 - abs(tempo - 90) / 25) * 0.25  # Peak around 90 BPM
                + onset_rate * 0.20
                + rhythm_regularity * 0.20
            )
            style_scores["hip_hop"] = min(1.0, hiphop_score)

        # 7. ACOUSTIC/FOLK/COUNTRY
        # Characteristics: High harmonic ratio, lower spectral centroid (warm),
        #                  moderate tempo, moderate regularity
        if harmonic_ratio > 0.55 and spectral_centroid < 0.55:
            acoustic_score = (
                harmonic_ratio * 0.40
                + (1.0 - spectral_centroid) * 0.30  # Warmer = better
                + (1.0 - abs(tempo - 100) / 60) * 0.30  # Wide tempo range
            )
            style_scores["acoustic"] = min(1.0, acoustic_score)

        # 8. POP
        # Characteristics: Moderate tempo (100-140 BPM), balanced features,
        #                  moderate-high harmonic ratio, catchy/regular rhythm
        if 95 < tempo < 145:
            pop_score = (
                (1.0 - abs(tempo - 120) / 25) * 0.30  # Peak around 120 BPM
                + (1.0 - abs(harmonic_ratio - 0.6) / 0.6)
                * 0.25  # Balanced harmonic
                + rhythm_regularity * 0.25
                + (1.0 - abs(spectral_centroid - 0.5) / 0.5)
                * 0.20  # Balanced brightness
            )
            style_scores["pop"] = min(1.0, pop_score)

        # 9. AMBIENT
        # Characteristics: Very low tempo (< 90 BPM), very high harmonic ratio,
        #                  low percussive ratio, low onset rate, smooth
        if tempo < 95 and harmonic_ratio > 0.7 and percussive_ratio < 0.3:
            ambient_score = (
                (1.0 - tempo / 95) * 0.30
                + harmonic_ratio * 0.30
                + (1.0 - percussive_ratio) * 0.20
                + (1.0 - onset_rate) * 0.20
            )
            style_scores["ambient"] = min(1.0, ambient_score)

        # 10. BLUES
        # Characteristics: Moderate tempo (80-120 BPM), moderate harmonic ratio,
        #                  expressive (moderate regularity), moderate spectral centroid
        if 75 < tempo < 125:
            blues_score = (
                (1.0 - abs(tempo - 100) / 25) * 0.30
                + (1.0 - abs(harmonic_ratio - 0.55) / 0.55) * 0.25
                + (1.0 - abs(spectral_centroid - 0.45) / 0.45) * 0.25
                + (1.0 - abs(rhythm_regularity - 0.5) / 0.5)
                * 0.20  # Moderate regularity
            )
            style_scores["blues"] = min(1.0, blues_score)

        # Apply mode-based adjustments (major = more pop/electronic, minor = more rock/metal)
        if mode == "major":
            style_scores["pop"] *= 1.15
            style_scores["electronic"] *= 1.10
            style_scores["acoustic"] *= 1.10
        elif mode == "minor":
            style_scores["rock"] *= 1.15
            style_scores["metal"] *= 1.15
            style_scores["blues"] *= 1.10

        # Normalize scores to create probability distribution
        total = sum(style_scores.values())
        if total > 0:
            for key in style_scores:
                style_scores[key] = min(1.0, style_scores[key] / total)
        else:
            # If no genre detected, assign equal small probabilities
            for key in style_scores:
                style_scores[key] = 0.1

    except Exception as e:
        _LOGGER.debug(f"Error in style classification: {e}")

    return style_scores


def classify_sub_genre(
    features: FeatureDict, dominant_genre: str
) -> dict[str, float]:
    """
    Classify sub-genre characteristics within a dominant genre.

    Provides more granular classification for better mood detection accuracy.

    Args:
        features: Dictionary of extracted audio features
        dominant_genre: The dominant genre from classify_music_style()

    Returns:
        Dictionary mapping sub-genre names to confidence scores (0-1)
    """
    if not features or not dominant_genre:
        return {}

    sub_genre_scores = {}

    try:
        tempo = (
            float(features.get("tempo", 120.0))
            if features.get("tempo") is not None
            else 120.0
        )
        spectral_centroid = (
            float(features.get("spectral_centroid_norm", 0.5))
            if features.get("spectral_centroid_norm") is not None
            else 0.5
        )
        harmonic_ratio = (
            float(features.get("harmonic_ratio", 0.5))
            if features.get("harmonic_ratio") is not None
            else 0.5
        )
        percussive_ratio = (
            float(features.get("percussive_ratio", 0.5))
            if features.get("percussive_ratio") is not None
            else 0.5
        )
        rhythm_regularity = (
            float(features.get("rhythm_regularity", 0.5))
            if features.get("rhythm_regularity") is not None
            else 0.5
        )
        onset_rate = (
            float(features.get("onset_rate_norm", 0.5))
            if features.get("onset_rate_norm") is not None
            else 0.5
        )

        dominant_genre_lower = dominant_genre.lower()

        # Electronic sub-genres
        if dominant_genre_lower == "electronic":
            sub_genre_scores = {
                "house": 0.0,
                "techno": 0.0,
                "trance": 0.0,
                "dubstep": 0.0,
                "drum_and_bass": 0.0,
                "ambient_electronic": 0.0,
            }

            # House: Moderate tempo (120-130), high percussive, regular
            if 115 < tempo < 135:
                sub_genre_scores["house"] = (
                    (1.0 - abs(tempo - 125) / 10) * 0.4
                    + percussive_ratio * 0.3
                    + rhythm_regularity * 0.3
                )

            # Techno: Higher tempo (130-140), very percussive, very regular
            if 125 < tempo < 145:
                sub_genre_scores["techno"] = (
                    (1.0 - abs(tempo - 135) / 10) * 0.4
                    + percussive_ratio * 0.4
                    + rhythm_regularity * 0.2
                )

            # Trance: High tempo (130-150), high harmonic ratio, regular
            if 125 < tempo < 155:
                sub_genre_scores["trance"] = (
                    (1.0 - abs(tempo - 140) / 15) * 0.35
                    + harmonic_ratio * 0.35
                    + rhythm_regularity * 0.3
                )

            # Dubstep: Lower tempo (70-75 BPM, but often doubled), high spectral centroid
            if (65 < tempo < 80) or (130 < tempo < 150):
                if spectral_centroid > 0.6:
                    sub_genre_scores["dubstep"] = (
                        spectral_centroid * 0.4
                        + percussive_ratio * 0.3
                        + onset_rate * 0.3
                    )

            # Drum & Bass: Very high tempo (160-180), very percussive
            if tempo >= 155:
                sub_genre_scores["drum_and_bass"] = (
                    min(1.0, (tempo - 150) / 30) * 0.5
                    + percussive_ratio * 0.3
                    + rhythm_regularity * 0.2
                )

            # Ambient Electronic: Low tempo, high harmonic, low percussive
            if tempo < 100 and harmonic_ratio > 0.6:
                sub_genre_scores["ambient_electronic"] = (
                    (1.0 - tempo / 100) * 0.4
                    + harmonic_ratio * 0.4
                    + (1.0 - percussive_ratio) * 0.2
                )

        # Rock sub-genres
        elif dominant_genre_lower == "rock":
            sub_genre_scores = {
                "classic_rock": 0.0,
                "alternative_rock": 0.0,
                "punk": 0.0,
                "indie_rock": 0.0,
            }

            # Classic Rock: Moderate tempo, balanced features
            if 100 < tempo < 140:
                sub_genre_scores["classic_rock"] = (
                    (1.0 - abs(tempo - 120) / 20) * 0.4
                    + (1.0 - abs(harmonic_ratio - 0.6) / 0.6) * 0.3
                    + rhythm_regularity * 0.3
                )

            # Alternative Rock: Slightly faster, more varied
            if 110 < tempo < 150:
                sub_genre_scores["alternative_rock"] = (
                    (1.0 - abs(tempo - 130) / 20) * 0.35
                    + (1.0 - abs(spectral_centroid - 0.55) / 0.55) * 0.35
                    + (1.0 - rhythm_regularity * 0.9)
                    * 0.3  # Slightly less regular
                )

            # Punk: Fast tempo, high energy, high percussive
            if tempo >= 140:
                sub_genre_scores["punk"] = (
                    min(1.0, (tempo - 130) / 50) * 0.4
                    + percussive_ratio * 0.35
                    + onset_rate * 0.25
                )

            # Indie Rock: Moderate tempo, higher harmonic, less regular
            if 100 < tempo < 130:
                sub_genre_scores["indie_rock"] = (
                    (1.0 - abs(tempo - 115) / 15) * 0.35
                    + harmonic_ratio * 0.35
                    + (1.0 - rhythm_regularity * 0.85) * 0.3
                )

        # Hip-hop sub-genres
        elif dominant_genre_lower == "hip_hop":
            sub_genre_scores = {
                "old_school": 0.0,
                "trap": 0.0,
                "rap": 0.0,
            }

            # Old School: Lower tempo, more balanced
            if 75 < tempo < 95:
                sub_genre_scores["old_school"] = (
                    1.0 - abs(tempo - 85) / 10
                ) * 0.5 + (1.0 - abs(harmonic_ratio - 0.5) / 0.5) * 0.5

            # Trap: Higher tempo (often 140-160 doubled), very percussive, high spectral
            if (65 < tempo < 80) or (130 < tempo < 160):
                if percussive_ratio > 0.6 and spectral_centroid > 0.55:
                    sub_genre_scores["trap"] = (
                        percussive_ratio * 0.4
                        + spectral_centroid * 0.35
                        + onset_rate * 0.25
                    )

            # Rap: Moderate tempo, high percussive
            if 80 < tempo < 100:
                sub_genre_scores["rap"] = (
                    (1.0 - abs(tempo - 90) / 10) * 0.4
                    + percussive_ratio * 0.4
                    + rhythm_regularity * 0.2
                )

        # Normalize sub-genre scores
        total = sum(sub_genre_scores.values())
        if total > 0:
            for key in sub_genre_scores:
                sub_genre_scores[key] = min(1.0, sub_genre_scores[key] / total)
        else:
            # If no sub-genre detected, return empty
            sub_genre_scores = {}

    except Exception as e:
        _LOGGER.debug(f"Error in sub-genre classification: {e}")

    return sub_genre_scores


def create_librosa_extractor(
    sample_rate: int = 30000,
    buffer_duration: float = 3.0,
    update_interval: float = 2.0,
) -> Optional[LibrosaFeatureExtractor]:
    """
    Factory function to create a librosa feature extractor.

    Args:
        sample_rate: Audio sample rate in Hz (must be > 0)
        buffer_duration: Buffer duration in seconds (must be > 0)
        update_interval: Feature update interval in seconds (must be > 0)

    Returns:
        LibrosaFeatureExtractor instance, or None if librosa unavailable or creation fails

    Raises:
        ValueError: If any parameter is invalid
    """
    if not LIBROSA_AVAILABLE:
        _LOGGER.debug("Librosa not available, cannot create extractor")
        return None

    # Validate parameters
    if sample_rate <= 0:
        raise ValueError(f"Invalid sample_rate: {sample_rate} (must be > 0)")
    if buffer_duration <= 0:
        raise ValueError(
            f"Invalid buffer_duration: {buffer_duration} (must be > 0)"
        )
    if update_interval <= 0:
        raise ValueError(
            f"Invalid update_interval: {update_interval} (must be > 0)"
        )

    try:
        buffer = LibrosaAudioBuffer(sample_rate, buffer_duration)
        extractor = LibrosaFeatureExtractor(
            buffer, sample_rate, update_interval
        )
        _LOGGER.debug(
            f"Created librosa extractor: sample_rate={sample_rate}, "
            f"buffer_duration={buffer_duration}s, update_interval={update_interval}s"
        )
        return extractor
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        _LOGGER.warning(
            f"Failed to create librosa extractor: {e}", exc_info=True
        )
        return None
