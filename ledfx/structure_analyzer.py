"""
Music Structure Analyzer for LedFx

Detects musical structure elements like verses, choruses, bridges, drops, and builds.
Uses pattern recognition and energy analysis to identify song sections.
"""

import logging
import time
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import voluptuous as vol

from ledfx.effects.math import ExpFilter

_LOGGER = logging.getLogger(__name__)


class MusicSection(Enum):
    """Enumeration of musical section types."""
    UNKNOWN = "unknown"
    INTRO = "intro"
    VERSE = "verse"
    PRE_CHORUS = "pre_chorus"
    CHORUS = "chorus"
    BRIDGE = "bridge"
    BREAKDOWN = "breakdown"
    DROP = "drop"
    BUILD = "build"
    OUTRO = "outro"


class StructuralEvent(Enum):
    """Enumeration of dramatic structural events."""
    NONE = "none"
    BEAT_DROP = "beat_drop"  # Sudden bass drop
    ENERGY_RISE = "energy_rise"  # Gradual energy increase
    ENERGY_FALL = "energy_fall"  # Gradual energy decrease
    BREAKDOWN_START = "breakdown_start"  # Sudden drop in complexity
    BUILD_START = "build_start"  # Start of tension building
    CLIMAX = "climax"  # Peak energy moment
    SILENCE = "silence"  # Near-silence or dramatic pause


class MusicStructureAnalyzer:
    """
    Analyzes music structure to detect verses, choruses, bridges, and dramatic moments.
    
    Detection methods:
    - Pattern repetition (chorus detection)
    - Energy level changes (verse vs chorus)
    - Spectral complexity (breakdown vs drop)
    - Transition detection (builds, drops, rises, falls)
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "analysis_window",
                description="Window size for structure analysis (seconds)",
                default=8,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=30)),
            vol.Optional(
                "pattern_memory",
                description="How many patterns to remember for comparison",
                default=4,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=10)),
            vol.Optional(
                "transition_sensitivity",
                description="Sensitivity to transitions (0-1)",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "event_cooldown",
                description="Minimum seconds between event triggers",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10.0)),
        }
    )

    def __init__(self, audio_source, mood_detector, config: Optional[dict] = None):
        """
        Initialize the structure analyzer.
        
        Args:
            audio_source: AudioAnalysisSource instance
            mood_detector: MoodDetector instance
            config: Configuration dictionary
        """
        self.audio = audio_source
        self.mood = mood_detector
        config = config or {}
        self._config = self.CONFIG_SCHEMA(config)
        
        # Calculate buffer sizes
        sample_rate = self.audio._config.get("sample_rate", 60)
        window_size = int(self._config["analysis_window"] * sample_rate)
        
        # Feature buffers for pattern detection
        self._energy_buffer = deque(maxlen=window_size)
        self._spectral_buffer = deque(maxlen=window_size)
        self._beat_buffer = deque(maxlen=window_size)
        
        # Pattern memory for repetition detection
        self._pattern_memory = deque(maxlen=self._config["pattern_memory"])
        
        # Current state
        self._current_section = MusicSection.UNKNOWN
        self._section_start_time = time.time()
        self._last_event = StructuralEvent.NONE
        self._last_event_time = 0.0
        
        # Energy tracking for transitions
        self._energy_baseline = 0.5
        self._energy_trend = 0.0  # Positive = rising, negative = falling
        self._peak_energy = 0.0
        
        # Event detection state
        self._in_build = False
        self._in_drop = False
        self._build_start_time = 0.0
        self._build_start_energy = 0.5
        
    def update(self) -> Tuple[MusicSection, Optional[StructuralEvent]]:
        """
        Update structure analysis from current audio and mood data.
        
        Returns:
            Tuple of (current_section, detected_event)
            detected_event is None if no new event
        """
        current_time = time.time()
        
        try:
            # Get current mood metrics
            mood = self.mood.get_mood_metrics()
            
            # Update buffers
            self._energy_buffer.append(mood["energy"])
            self._spectral_buffer.append(mood["brightness"])
            self._beat_buffer.append(mood["beat_strength"])
            
            # Update energy baseline (slow-moving average)
            if len(self._energy_buffer) > 10:
                self._energy_baseline = np.mean(list(self._energy_buffer))
            
            # Calculate energy trend
            self._update_energy_trend()
            
            # Detect structural events
            event = self._detect_event(mood, current_time)
            
            # Update section classification
            self._update_section(mood, event)
            
            return self._current_section, event
            
        except Exception as e:
            _LOGGER.warning(f"Error in structure analysis: {e}")
            return self._current_section, None
    
    def _update_energy_trend(self):
        """Calculate the current energy trend (rising or falling)."""
        if len(self._energy_buffer) < 20:
            self._energy_trend = 0.0
            return
        
        try:
            # Compare recent vs previous energy
            recent = np.mean(list(self._energy_buffer)[-10:])
            previous = np.mean(list(self._energy_buffer)[-20:-10])
            
            # Normalize trend to -1 to 1
            self._energy_trend = np.clip((recent - previous) * 5.0, -1.0, 1.0)
            
        except Exception as e:
            _LOGGER.debug(f"Error updating energy trend: {e}")
            self._energy_trend = 0.0
    
    def _detect_event(self, mood: Dict[str, float], current_time: float) -> Optional[StructuralEvent]:
        """
        Detect dramatic structural events with genre-aware thresholds.
        
        Enhanced detection that adapts thresholds based on detected genre for
        more accurate event recognition across different music styles.
        
        Args:
            mood: Current mood metrics (may include genre information)
            current_time: Current timestamp
            
        Returns:
            StructuralEvent if detected, None otherwise
        """
        # Check cooldown
        time_since_last = current_time - self._last_event_time
        if time_since_last < self._config["event_cooldown"]:
            return None
        
        sensitivity = self._config["transition_sensitivity"]
        energy = mood["energy"]
        intensity = mood["intensity"]
        beat_strength = mood.get("beat_strength", 0.5)
        
        # Get genre information for adaptive thresholds
        dominant_genre = mood.get("dominant_style", "").lower() if mood.get("dominant_style") else ""
        genre_confidence = float(mood.get("style_confidence", 0.0)) if mood.get("style_confidence") else 0.0
        
        # Genre-specific threshold adjustments
        # Electronic/EDM: More sensitive to drops, builds, and energy changes
        # Rock/Metal: More sensitive to intensity changes and climaxes
        # Jazz/Classical: More sensitive to harmonic changes and subtle transitions
        # Hip-hop: More sensitive to beat drops and percussive events
        # Ambient: More sensitive to subtle energy changes
        
        drop_threshold = 0.3  # Base threshold for beat drops
        build_threshold = 0.3  # Base threshold for builds
        energy_change_threshold = 0.2  # Base threshold for energy rises/falls
        breakdown_threshold = 0.25  # Base threshold for breakdowns
        
        if genre_confidence > 0.2:  # Only adjust if we have reasonable genre confidence
            if dominant_genre in ['electronic', 'metal']:
                # Electronic and metal: More dramatic events, lower thresholds
                drop_threshold *= 0.85
                build_threshold *= 0.85
                energy_change_threshold *= 0.9
            elif dominant_genre in ['jazz', 'classical', 'ambient']:
                # Jazz, classical, ambient: More subtle events, higher thresholds
                drop_threshold *= 1.2
                build_threshold *= 1.15
                energy_change_threshold *= 1.1
                breakdown_threshold *= 0.9  # More sensitive to breakdowns
            elif dominant_genre in ['hip_hop']:
                # Hip-hop: Very sensitive to beat drops, less sensitive to builds
                drop_threshold *= 0.75
                build_threshold *= 1.2
            elif dominant_genre in ['rock', 'pop']:
                # Rock and pop: Balanced, slightly more sensitive
                drop_threshold *= 0.95
                build_threshold *= 0.95
        
        # Track peak energy for climax detection
        if energy > self._peak_energy:
            self._peak_energy = energy
        else:
            # Decay peak slowly
            self._peak_energy *= 0.995
        
        event = None
        
        # Detect silence/breakdown (genre-agnostic)
        if energy < 0.15 and beat_strength < 0.2:
            if self._last_event != StructuralEvent.SILENCE:
                event = StructuralEvent.SILENCE
                
        # Detect beat drop (sudden bass increase with energy spike)
        # Enhanced detection with genre-aware thresholds
        elif len(self._energy_buffer) >= 5:
            recent_energy = list(self._energy_buffer)[-5:]
            energy_spike = recent_energy[-1] - np.mean(recent_energy[:-1])
            
            # Use genre-adaptive threshold
            adjusted_drop_threshold = drop_threshold * (1.0 + sensitivity)
            
            # Additional checks for more accurate drop detection
            # For electronic/hip-hop: require stronger beat
            # For other genres: be more lenient
            beat_requirement = 0.6
            if dominant_genre in ['electronic', 'hip_hop']:
                beat_requirement = 0.65
            elif dominant_genre in ['jazz', 'classical', 'ambient']:
                beat_requirement = 0.5
            
            if energy_spike > adjusted_drop_threshold and beat_strength > beat_requirement:
                # Additional validation: check for sudden bass increase
                if len(self._beat_buffer) >= 3:
                    recent_beats = list(self._beat_buffer)[-3:]
                    beat_spike = recent_beats[-1] - np.mean(recent_beats[:-1])
                    if beat_spike > 0.15:  # Significant beat strength increase
                        event = StructuralEvent.BEAT_DROP
                        self._in_drop = True
                else:
                    event = StructuralEvent.BEAT_DROP
                    self._in_drop = True
                
        # Detect build start (sustained energy increase)
        # Enhanced with genre-aware thresholds and better validation
        elif self._energy_trend > (build_threshold * (1.0 + sensitivity)) and not self._in_build:
            # Genre-specific intensity requirements
            intensity_requirement = 0.5
            if dominant_genre in ['electronic', 'metal', 'rock']:
                intensity_requirement = 0.4  # More lenient for high-energy genres
            elif dominant_genre in ['jazz', 'classical', 'ambient']:
                intensity_requirement = 0.6  # Require more intensity for subtle genres
            
            if intensity > intensity_requirement:
                # Validate it's a sustained trend, not just a spike
                if len(self._energy_buffer) >= 10:
                    recent_trend = list(self._energy_buffer)[-10:]
                    trend_consistency = 1.0 - np.std(recent_trend) / (np.mean(recent_trend) + 0.01)
                    if trend_consistency > 0.7:  # Consistent upward trend
                        event = StructuralEvent.BUILD_START
                        self._in_build = True
                        self._build_start_time = current_time
                        self._build_start_energy = energy
                else:
                    event = StructuralEvent.BUILD_START
                    self._in_build = True
                    self._build_start_time = current_time
                    self._build_start_energy = energy
                
        # Detect climax (peak after build)
        # Enhanced with genre-aware timing
        elif self._in_build:
            time_building = current_time - self._build_start_time
            energy_gain = energy - self._build_start_energy
            
            # Genre-specific build duration requirements
            min_build_time = 4.0
            min_energy_gain = 0.3
            if dominant_genre in ['electronic', 'metal']:
                min_build_time = 3.5  # Faster builds in electronic/metal
                min_energy_gain = 0.25
            elif dominant_genre in ['jazz', 'classical']:
                min_build_time = 5.0  # Longer builds in jazz/classical
                min_energy_gain = 0.35
            
            # Climax if we've been building and reach peak
            if time_building > min_build_time and energy_gain > min_energy_gain:
                # Plateau indicates peak (energy trend near zero)
                if abs(self._energy_trend) < 0.15:
                    event = StructuralEvent.CLIMAX
                    self._in_build = False
                # Or if energy starts dropping after peak
                elif self._energy_trend < -0.1 and energy > self._peak_energy * 0.95:
                    event = StructuralEvent.CLIMAX
                    self._in_build = False
                    
        # Detect sustained energy rise (genre-aware)
        elif self._energy_trend > (energy_change_threshold * (1.0 + sensitivity)):
            if self._last_event != StructuralEvent.ENERGY_RISE:
                # Longer cooldown for subtle genres
                cooldown_multiplier = 2.0
                if dominant_genre in ['jazz', 'classical', 'ambient']:
                    cooldown_multiplier = 2.5
                if time_since_last > self._config["event_cooldown"] * cooldown_multiplier:
                    event = StructuralEvent.ENERGY_RISE
                    
        # Detect sustained energy fall (genre-aware)
        elif self._energy_trend < (-energy_change_threshold * (1.0 + sensitivity)):
            if self._last_event != StructuralEvent.ENERGY_FALL:
                # Longer cooldown for subtle genres
                cooldown_multiplier = 2.0
                if dominant_genre in ['jazz', 'classical', 'ambient']:
                    cooldown_multiplier = 2.5
                if time_since_last > self._config["event_cooldown"] * cooldown_multiplier:
                    event = StructuralEvent.ENERGY_FALL
                    self._in_build = False  # Cancel any build
                    
        # Detect breakdown (sudden complexity reduction)
        # Enhanced with genre-aware thresholds
        elif len(self._spectral_buffer) >= 10:
            recent_spectral = list(self._spectral_buffer)[-10:]
            spectral_drop = np.mean(recent_spectral[:5]) - np.mean(recent_spectral[5:])
            
            # Genre-specific breakdown detection
            adjusted_breakdown_threshold = breakdown_threshold * (1.0 + sensitivity)
            energy_requirement = 0.6
            
            if dominant_genre in ['electronic', 'metal']:
                # Electronic/metal: More sensitive to breakdowns
                adjusted_breakdown_threshold *= 0.9
                energy_requirement = 0.65
            elif dominant_genre in ['jazz', 'classical']:
                # Jazz/classical: Less sensitive (more gradual changes)
                adjusted_breakdown_threshold *= 1.1
                energy_requirement = 0.55
            
            if spectral_drop > adjusted_breakdown_threshold and energy < energy_requirement:
                if self._last_event != StructuralEvent.BREAKDOWN_START:
                    event = StructuralEvent.BREAKDOWN_START
        
        # Update state if event detected
        if event is not None:
            self._last_event = event
            self._last_event_time = current_time
            genre_info = f" (genre: {dominant_genre})" if dominant_genre else ""
            _LOGGER.info(f"Detected structural event: {event.value}{genre_info}")
            
        return event
    
    def _update_section(self, mood: Dict[str, float], event: Optional[StructuralEvent]):
        """
        Update the current section classification.
        
        Args:
            mood: Current mood metrics
            event: Recently detected event (if any)
        """
        current_time = time.time()
        time_in_section = current_time - self._section_start_time
        
        energy = mood["energy"]
        intensity = mood["intensity"]
        beat_strength = mood["beat_strength"]
        
        # Use events to help classify sections
        if event == StructuralEvent.BEAT_DROP:
            self._change_section(MusicSection.DROP)
            
        elif event == StructuralEvent.BUILD_START:
            self._change_section(MusicSection.BUILD)
            
        elif event == StructuralEvent.BREAKDOWN_START:
            self._change_section(MusicSection.BREAKDOWN)
            
        elif event == StructuralEvent.SILENCE:
            # Could be intro or outro
            if time_in_section < 15:
                self._change_section(MusicSection.INTRO)
            else:
                self._change_section(MusicSection.OUTRO)
                
        # Classify based on energy and intensity
        elif time_in_section > 8:  # Give sections at least 8 seconds
            
            # Chorus: high energy, strong beats
            if energy > 0.6 and beat_strength > 0.6:
                if self._current_section != MusicSection.CHORUS:
                    self._change_section(MusicSection.CHORUS)
                    
            # Verse: moderate energy, structured
            elif 0.3 < energy < 0.6 and beat_strength > 0.4:
                if self._current_section not in [MusicSection.VERSE, MusicSection.PRE_CHORUS]:
                    self._change_section(MusicSection.VERSE)
                    
            # Bridge: varies, often different from verse/chorus
            elif intensity > 0.6 and energy > 0.5:
                if self._current_section in [MusicSection.VERSE, MusicSection.CHORUS]:
                    # Only switch to bridge from verse/chorus
                    self._change_section(MusicSection.BRIDGE)
    
    def _change_section(self, new_section: MusicSection):
        """
        Change to a new section.
        
        Args:
            new_section: The new section to switch to
        """
        if new_section != self._current_section:
            _LOGGER.info(f"Section changed: {self._current_section.value} -> {new_section.value}")
            self._current_section = new_section
            self._section_start_time = time.time()
    
    def get_current_section(self) -> MusicSection:
        """Get the current section."""
        return self._current_section
    
    def get_section_duration(self) -> float:
        """Get how long we've been in the current section (seconds)."""
        return time.time() - self._section_start_time
    
    def get_last_event(self) -> StructuralEvent:
        """Get the most recent structural event."""
        return self._last_event
    
    def get_energy_trend(self) -> float:
        """
        Get the current energy trend.
        
        Returns:
            -1 to 1: negative = falling, positive = rising
        """
        return self._energy_trend
    
    def is_transitional(self) -> bool:
        """
        Check if we're currently in a transitional state (build, drop, etc).
        
        Returns:
            True if in a transitional section
        """
        return self._current_section in [
            MusicSection.BUILD,
            MusicSection.DROP,
            MusicSection.BREAKDOWN,
            MusicSection.PRE_CHORUS,
        ]







