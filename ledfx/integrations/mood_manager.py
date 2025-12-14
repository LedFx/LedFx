"""
Mood Manager Integration for LedFx

Automatically adjusts effects and colors based on detected music mood and structure.
"""

import asyncio
import logging
import math
import time
from collections import deque
from typing import Any, Optional

import numpy as np
import voluptuous as vol

from ledfx.config import save_config
from ledfx.events import (
    MoodChangeEvent,
    StructureChangeEvent,
)
from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)

# Try relative imports first, then absolute
try:
    try:
        from .mood_detector import MoodDetector
        from .structure_analyzer import (
            MusicSection,
            MusicStructureAnalyzer,
            StructuralEvent,
        )
    except ImportError:
        from ledfx.mood_detector import MoodDetector
        from ledfx.structure_analyzer import (
            MusicSection,
            MusicStructureAnalyzer,
            StructuralEvent,
        )
except ImportError as e:
    _LOGGER.error(f"Failed to import mood detection modules: {e}")
    raise


class MoodManager(Integration):
    """
    Integration that monitors music mood and structure to automatically
    adjust effects and colors.

    Features:
    - Automatic effect switching based on mood
    - Color palette adjustments based on energy/valence
    - Scene switching for different song sections
    - Response to dramatic moments (drops, builds, etc.)
    """

    NAME = "mood_manager"
    DESCRIPTION = "Automatically adjust effects and colors based on music mood"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "enabled",
                description="Enable automatic mood-based adjustments",
                default=False,
            ): bool,
            vol.Optional(
                "update_interval",
                description="Update interval in seconds",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
            vol.Optional(
                "adjust_colors",
                description="Automatically adjust colors based on mood",
                default=True,
            ): bool,
            vol.Optional(
                "adjust_effects",
                description="Automatically adjust effect parameters based on mood",
                default=True,
            ): bool,
            vol.Optional(
                "switch_scenes",
                description="Switch scenes based on music structure",
                default=False,
            ): bool,
            vol.Optional(
                "react_to_events",
                description="React to dramatic events (drops, builds, etc.)",
                default=True,
            ): bool,
            vol.Optional(
                "intensity",
                description="Overall intensity of mood reactions (0-1)",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "mood_scenes",
                description="Map moods to scene IDs",
                default={},
            ): dict,
            vol.Optional(
                "event_scenes",
                description="Map structural events to scene IDs",
                default={},
            ): dict,
            vol.Optional(
                "target_virtuals",
                description="List of virtual IDs to control (empty = all)",
                default=[],
            ): [str],
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
            vol.Optional(
                "change_threshold",
                description="Minimum mood change threshold to trigger updates (0-1)",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=0.5)),
            vol.Optional(
                "min_change_interval",
                description="Minimum seconds between mood-based changes",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30.0)),
            vol.Optional(
                "enable_force_updates",
                description="Enable periodic force updates (may cause time-based changes)",
                default=False,
            ): bool,
            vol.Optional(
                "force_update_interval",
                description="Force update interval in seconds (only if enabled)",
                default=60.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=300.0)),
            vol.Optional(
                "use_adaptive_threshold",
                description="Adaptively adjust change threshold based on music dynamics",
                default=True,
            ): bool,
            vol.Optional(
                "preserve_scene_settings",
                description="When switching scenes, preserve scene's effect settings instead of applying mood adjustments",
                default=True,
            ): bool,
        }
    )

    def __init__(
        self,
        ledfx: Any,
        config: dict[str, Any],
        active: bool = False,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the Mood Manager.

        Args:
            ledfx: LedFx core instance
            config: Configuration dictionary
            active: Whether integration is initially active
            data: Optional data dictionary
        """
        super().__init__(ledfx, config, active, data or {})

        # Core components
        self._task: Optional[asyncio.Task] = None
        self._mood_detector: Optional[MoodDetector] = None
        self._structure_analyzer: Optional[MusicStructureAnalyzer] = None

        # State tracking
        self._last_mood_category: Optional[str] = None
        self._last_section: Optional[MusicSection] = None
        self._last_mood_metrics: Optional[dict[str, float]] = None
        self._last_update_time: Optional[float] = None
        self._last_change_time: float = 0.0
        self._pool_indices: dict[str, int] = {}
        self._current_scene_id: Optional[str] = None
        self._last_scene_change_time: float = 0.0

        # Configuration - use config values with defaults
        self._change_threshold = float(
            self._config.get("change_threshold", 0.2)
        )
        self._min_change_interval = float(
            self._config.get("min_change_interval", 3.0)
        )
        self._enable_force_updates = bool(
            self._config.get("enable_force_updates", False)
        )
        self._force_update_interval = float(
            self._config.get("force_update_interval", 60.0)
        )
        self._use_adaptive_threshold = bool(
            self._config.get("use_adaptive_threshold", True)
        )

        # Adaptive threshold tracking
        self._recent_changes: deque = deque(
            maxlen=20
        )  # Track recent change magnitudes
        self._adaptive_threshold = self._change_threshold

        # Locks for thread-safe access
        self._config_lock = asyncio.Lock()  # Protect config access
        self._state_lock = asyncio.Lock()  # Protect state variables
        self._scene_lock = asyncio.Lock()  # Protect scene operations

    async def _get_config(self, key: str, default: Any = None) -> Any:
        """
        Thread-safe config getter.

        Args:
            key: Config key to retrieve
            default: Default value if key not found

        Returns:
            Config value or default
        """
        async with self._config_lock:
            return self._config.get(key, default)

    async def _update_config(self, updates: dict[str, Any]) -> None:
        """
        Thread-safe config updater.

        Args:
            updates: Dictionary of config updates to apply
        """
        async with self._config_lock:
            self._config.update(updates)

    async def _get_config_copy(self) -> dict[str, Any]:
        """
        Get a copy of the entire config (thread-safe).

        Returns:
            Copy of config dictionary
        """
        async with self._config_lock:
            return self._config.copy()

    async def connect(self, msg: Optional[str] = None) -> None:
        """
        Establish connection (initialize mood detection).

        Args:
            msg: Optional connection message
        """
        if not hasattr(self._ledfx, "audio") or self._ledfx.audio is None:
            _LOGGER.error(
                "Cannot activate mood manager: audio system not available"
            )
            return

        try:
            # Initialize mood detector with config including librosa settings
            # Use protected config access
            update_interval = float(
                await self._get_config("update_interval", 0.5) or 0.5
            )
            if update_interval <= 0:
                _LOGGER.warning(
                    "Invalid update_interval %.3f; falling back to 0.5s",
                    update_interval,
                )
                update_interval = 0.5

            # Convert seconds interval to detector Hz, clamped to detector bounds (1-30Hz)
            derived_rate = 1.0 / update_interval
            derived_rate = max(1.0, min(30.0, derived_rate))

            mood_detector_config: dict[str, Any] = {
                "update_rate": int(math.ceil(derived_rate)),
            }

            # Pass through librosa config if present
            for key in [
                "use_librosa",
                "librosa_buffer_duration",
                "librosa_update_interval",
            ]:
                value = await self._get_config(key)
                if value is not None:
                    mood_detector_config[key] = value

            # Initialize mood detector
            try:
                self._mood_detector = MoodDetector(
                    self._ledfx.audio, config=mood_detector_config
                )
                _LOGGER.info("Mood detector initialized successfully")
            except Exception as e:
                _LOGGER.error(
                    f"Failed to initialize mood detector: {e}", exc_info=True
                )
                raise

            # Initialize structure analyzer
            try:
                self._structure_analyzer = MusicStructureAnalyzer(
                    self._ledfx.audio, self._mood_detector, config={}
                )
                _LOGGER.info("Structure analyzer initialized successfully")
            except Exception as e:
                _LOGGER.error(
                    f"Failed to initialize structure analyzer: {e}",
                    exc_info=True,
                )
                # Don't fail completely if structure analyzer fails
                self._structure_analyzer = None

            # Start monitoring task if enabled
            if await self._get_config("enabled", False):
                await self.start_monitoring()

            await super().connect("Mood Manager connected")

        except Exception as e:
            _LOGGER.error(
                f"Failed to connect mood manager: {e}", exc_info=True
            )

    async def disconnect(self, msg=None):
        """Disconnect (stop mood detection)."""
        await self.stop_monitoring()
        await super().disconnect("Mood Manager disconnected")

    async def start_monitoring(self):
        """Start the mood monitoring task."""
        if self._task is None:
            self._task = asyncio.create_task(self._monitor_loop())
            _LOGGER.info("Started mood monitoring")

    async def stop_monitoring(self):
        """Stop the mood monitoring task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            _LOGGER.info("Stopped mood monitoring")

    async def _monitor_loop(self) -> None:
        """
        Main monitoring loop.

        Continuously monitors mood and structure, applying changes as needed.
        Handles errors gracefully to prevent loop termination.
        """
        consecutive_errors = 0
        max_consecutive_errors = 10

        try:
            while True:
                try:
                    update_interval = await self._get_config(
                        "update_interval", 0.5
                    )
                    await asyncio.sleep(update_interval)

                    if not await self._get_config("enabled", False):
                        continue

                    await self._update()

                    # Reset error counter on successful update
                    consecutive_errors = 0

                except asyncio.CancelledError:
                    raise  # Re-raise cancellation
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        _LOGGER.error(
                            f"Mood monitoring failed {consecutive_errors} times consecutively. "
                            f"Pausing for 10 seconds before retrying."
                        )
                        await asyncio.sleep(10.0)
                        consecutive_errors = 0
                    else:
                        _LOGGER.warning(
                            f"Error in mood monitoring (attempt {consecutive_errors}/{max_consecutive_errors}): {e}",
                            exc_info=consecutive_errors
                            >= 5,  # Full traceback after 5 errors
                        )

        except asyncio.CancelledError:
            _LOGGER.debug("Mood monitoring loop cancelled")
            raise

    async def _update(self) -> None:
        """
        Update mood analysis and apply changes.

        This method is called periodically by the monitoring loop to:
        1. Update mood and structure analysis
        2. Detect significant changes
        3. Apply mood-based adjustments (colors, effects, scenes)
        """
        if self._mood_detector is None:
            _LOGGER.debug("Mood detector not initialized, skipping update")
            return

        current_time = time.time()

        # Update mood analysis
        try:
            mood_metrics = self._mood_detector.update()
            mood_category = self._mood_detector.get_mood_category()
        except Exception as e:
            _LOGGER.warning(
                f"Error updating mood detector: {e}", exc_info=True
            )
            return

        # Update structure analysis (optional, may be None)
        section: Optional[MusicSection] = None
        event: Optional[StructuralEvent] = None
        if self._structure_analyzer is not None:
            try:
                section, event = self._structure_analyzer.update()
            except Exception as e:
                _LOGGER.debug(
                    f"Error updating structure analyzer: {e}", exc_info=False
                )
                # Continue without structure analysis if it fails

        # Check if we need to force an update (only if enabled)
        force_update = False
        if self._last_update_time is None:
            self._last_update_time = current_time
        elif (
            self._enable_force_updates
            and current_time - self._last_update_time
            > self._force_update_interval
        ):
            force_update = True
            self._last_update_time = current_time
            _LOGGER.debug(
                "Forcing periodic mood update (force updates enabled)"
            )

        # Initialize last metrics on first run and check for changes (protected by state lock)
        async with self._state_lock:
            if self._last_mood_metrics is None:
                self._last_mood_metrics = mood_metrics.copy()

            # Check for significant mood metric changes (even within same category)
            significant_change = False
            change_magnitude = 0.0
            last_mood_metrics_copy = (
                self._last_mood_metrics.copy()
                if self._last_mood_metrics
                else None
            )

        if last_mood_metrics_copy is not None:
            try:
                # Calculate change magnitude for key metrics (using copy from lock)
                energy_change = abs(
                    mood_metrics.get("energy", 0.5)
                    - last_mood_metrics_copy.get("energy", 0.5)
                )
                valence_change = abs(
                    mood_metrics.get("valence", 0.5)
                    - last_mood_metrics_copy.get("valence", 0.5)
                )
                brightness_change = abs(
                    mood_metrics.get("brightness", 0.5)
                    - last_mood_metrics_copy.get("brightness", 0.5)
                )
                intensity_change = abs(
                    mood_metrics.get("intensity", 0.5)
                    - last_mood_metrics_copy.get("intensity", 0.5)
                )

                # Calculate overall change magnitude (weighted combination)
                # Energy and valence are most important for mood changes
                change_magnitude = max(
                    energy_change * 0.4
                    + valence_change * 0.3
                    + brightness_change * 0.2
                    + intensity_change * 0.1,
                    energy_change,
                    valence_change,
                )

                # Update adaptive threshold if enabled (protected by state lock)
                async with self._state_lock:
                    if self._use_adaptive_threshold:
                        self._recent_changes.append(change_magnitude)
                        if len(self._recent_changes) >= 10:
                            # Adjust threshold based on recent change patterns
                            avg_recent_change = float(
                                np.mean(list(self._recent_changes))
                            )
                            # If music is very dynamic, lower threshold slightly; if stable, raise it
                            if avg_recent_change > 0.15:
                                # Music is dynamic, be more sensitive
                                self._adaptive_threshold = max(
                                    0.1, self._change_threshold * 0.9
                                )
                            elif avg_recent_change < 0.08:
                                # Music is stable, require larger changes
                                self._adaptive_threshold = min(
                                    0.3, self._change_threshold * 1.2
                                )
                            else:
                                self._adaptive_threshold = (
                                    self._change_threshold
                                )
                        else:
                            self._adaptive_threshold = self._change_threshold
                    else:
                        self._adaptive_threshold = self._change_threshold

                    # Use adaptive threshold for change detection
                    threshold = self._adaptive_threshold

                # Significant change if change magnitude exceeds threshold
                # Also check individual metrics for more nuanced detection
                if (
                    change_magnitude > threshold
                    or energy_change
                    > threshold
                    * 1.2  # Energy changes are particularly important
                    or valence_change > threshold * 1.2
                ):  # Valence changes indicate mood shifts
                    significant_change = True
                    _LOGGER.debug(
                        f"Significant mood metric change detected (threshold={threshold:.3f}): "
                        f"magnitude={change_magnitude:.3f}, energy={energy_change:.3f}, "
                        f"valence={valence_change:.3f}, brightness={brightness_change:.3f}"
                    )
            except (KeyError, TypeError, ValueError) as e:
                _LOGGER.debug(f"Error calculating mood changes: {e}")
                # Assume no significant change if we can't calculate

        # Check for mood category changes and cooldown (protected by state lock)
        async with self._state_lock:
            category_changed = mood_category != self._last_mood_category
            time_since_last_change = current_time - self._last_change_time
            within_cooldown = (
                time_since_last_change < self._min_change_interval
            )

        # Apply updates if:
        # 1. Category changed (always allow, but still respect cooldown for non-category changes), OR
        # 2. Significant metric change detected AND cooldown period has passed, OR
        # 3. Force update (only if enabled and cooldown passed)
        should_update = (
            category_changed
            or (significant_change and not within_cooldown)
            or (force_update and not within_cooldown)
        )

        if should_update:
            # Update state atomically (protected by state lock)
            async with self._state_lock:
                self._last_change_time = current_time
                if category_changed:
                    self._last_mood_category = mood_category
                # Update last metrics
                self._last_mood_metrics = mood_metrics.copy()

            # Fire event outside lock to avoid blocking
            if category_changed:
                self._ledfx.events.fire_event(
                    MoodChangeEvent(mood_category, mood_metrics)
                )
                _LOGGER.info(f"Mood category changed: {mood_category}")

            # Apply mood-based changes
            # Only adjust colors/effects if there's a real change (not just force update)
            if (
                force_update
                and not category_changed
                and not significant_change
            ):
                # Force update but no real change - skip adjustments to avoid unnecessary changes
                _LOGGER.debug(
                    "Force update triggered but no significant mood change, skipping adjustments"
                )
            else:
                # Real mood change detected - apply adjustments
                # Only adjust if we're not switching scenes (or if preserve_scene_settings is False)
                switch_scenes = await self._get_config("switch_scenes", False)
                will_switch_scene = switch_scenes and category_changed
                preserve_scene = await self._get_config(
                    "preserve_scene_settings", True
                )

                # Skip effect adjustments if we're about to switch scenes and preserve_scene_settings is True
                if not (will_switch_scene and preserve_scene):
                    if await self._get_config("adjust_colors", True):
                        await self._adjust_colors(mood_metrics)

                    if await self._get_config("adjust_effects", True):
                        await self._adjust_effects(mood_metrics)

            # Scene switching only on category changes (not on metric changes alone)
            if (
                await self._get_config("switch_scenes", False)
                and category_changed
            ):
                await self._switch_mood_scene(mood_category)

        # Check for structure changes (only if structure analyzer is available)
        if self._structure_analyzer is not None:
            async with self._state_lock:
                section_changed = section != self._last_section
                if section_changed and section is not None:
                    self._last_section = section

            if section_changed and section is not None:
                _LOGGER.info(f"Section changed: {section.value}")

                # Fire structure change event
                try:
                    self._ledfx.events.fire_event(
                        StructureChangeEvent(section, event)
                    )
                except Exception as e:
                    _LOGGER.debug(f"Error firing structure change event: {e}")

                # React to structural events
                if event is not None and await self._get_config(
                    "react_to_events", True
                ):
                    try:
                        await self._react_to_event(event, mood_metrics)
                    except Exception as e:
                        _LOGGER.warning(
                            f"Error reacting to structural event: {e}",
                            exc_info=True,
                        )

                # Switch scenes based on structure
                if (
                    await self._get_config("switch_scenes", False)
                    and section is not None
                    and section != self._last_section
                ):
                    try:
                        await self._switch_structure_scene(section)
                    except Exception as e:
                        _LOGGER.warning(
                            f"Error switching structure scene: {e}",
                            exc_info=True,
                        )

    async def _adjust_colors(self, mood: dict[str, float]):
        """
        Adjust colors based on mood.

        Maps mood to color gradients:
        - High energy -> warm/bright colors
        - Low energy -> cool/dark colors
        - High valence -> bright colors
        - Low valence -> darker colors
        """
        try:
            # Determine gradient based on mood
            energy = mood["energy"]
            brightness = mood["brightness"]
            warmth = mood["spectral_warmth"]

            # Select appropriate gradient
            if energy > 0.7 and brightness > 0.6:
                # Energetic and bright
                gradient = "Rainbow"
            elif energy > 0.7 and warmth < 0.4:
                # Energetic and warm
                gradient = "Sunset"
            elif energy > 0.7:
                # Just energetic
                gradient = "Plasma"
            elif brightness > 0.7:
                # Bright/cool
                gradient = "Frost"
            elif brightness < 0.3:
                # Dark
                gradient = "Rust"
            elif warmth < 0.4:
                # Warm
                gradient = "Borealis"
            else:
                # Neutral
                gradient = "Viridis"

            # Apply gradient to active effects
            intensity = await self._get_config("intensity", 0.7)
            await self._apply_global_config({"gradient": gradient}, intensity)

        except Exception as e:
            _LOGGER.warning(f"Error adjusting colors: {e}")

    async def _adjust_effects(self, mood: dict[str, float]):
        """
        Adjust effect parameters based on mood.

        Adjusts parameters like:
        - Speed based on energy
        - Blur based on intensity
        - Brightness based on brightness metric
        """
        try:
            config_updates = {}
            intensity = await self._get_config("intensity", 0.7)

            # Map energy to speed (if effect supports it)
            energy = mood["energy"]
            if energy > 0.7:
                config_updates["speed"] = 4.0 * intensity
            elif energy > 0.4:
                config_updates["speed"] = 2.5 * intensity
            else:
                config_updates["speed"] = 1.5 * intensity

            # Map intensity to blur/smoothing
            if mood["intensity"] > 0.6:
                config_updates["blur"] = 0.5 * intensity
            else:
                config_updates["blur"] = 2.0 * intensity

            # Map brightness to brightness parameter
            brightness_value = 0.5 + (mood["brightness"] * 0.5 * intensity)
            config_updates["brightness"] = brightness_value

            # Apply updates
            if config_updates:
                await self._apply_global_config(config_updates, intensity)

        except Exception as e:
            _LOGGER.warning(f"Error adjusting effects: {e}")

    async def _react_to_event(
        self, event: StructuralEvent, mood: dict[str, float]
    ) -> None:
        """
        React to dramatic structural events.

        This method applies immediate visual reactions to structural events like
        beat drops, builds, climaxes, etc. It can either activate a mapped scene
        or apply default effect configurations.

        Args:
            event: The detected structural event (e.g., StructuralEvent.BEAT_DROP)
            mood: Current mood metrics dictionary
        """
        if event is None or event == StructuralEvent.NONE:
            return

        try:
            intensity_val = await self._get_config("intensity", 0.7)
            intensity = float(intensity_val)
            intensity = max(0.0, min(1.0, intensity))  # Clamp to 0-1

            # Prefer scene pools for this event if configured
            event_pools: dict[str, list[str]] = await self._get_config("event_scene_pools", {})  # type: ignore
            scene_id = self._get_next_scene_from_pool(event.value, event_pools)
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
                return
            # Check for single-mapping event scenes as fallback
            event_scenes = await self._get_config("event_scenes", {})
            scene_id = (
                event_scenes.get(event.value)
                if isinstance(event_scenes, dict)
                else None
            )
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
                return

            # Default reactions based on event type
            if event == StructuralEvent.BEAT_DROP:
                # Sudden brightness increase and intense colors
                await self._apply_global_config(
                    {
                        "brightness": 1.0,
                        "gradient": "Plasma",
                        "speed": 5.0 * intensity,
                    },
                    intensity,
                )

            elif event == StructuralEvent.BUILD_START:
                # Increase speed and intensity gradually
                await self._apply_global_config(
                    {
                        "speed": 3.0 * intensity,
                        "gradient": "Sunset",
                    },
                    intensity,
                )

            elif event == StructuralEvent.CLIMAX:
                # Maximum energy
                await self._apply_global_config(
                    {
                        "brightness": 1.0,
                        "speed": 6.0 * intensity,
                        "gradient": "Rainbow",
                    },
                    intensity,
                )

            elif event == StructuralEvent.BREAKDOWN_START:
                # Reduce complexity
                await self._apply_global_config(
                    {
                        "speed": 1.0,
                        "blur": 3.0 * intensity,
                        "brightness": 0.6,
                    },
                    intensity,
                )

            elif event == StructuralEvent.SILENCE:
                # Minimal activity
                await self._apply_global_config(
                    {
                        "speed": 0.5,
                        "brightness": 0.3,
                        "gradient": "Ocean",
                    },
                    intensity,
                )

        except Exception as e:
            _LOGGER.warning(
                f"Error reacting to event {event.value if event else 'unknown'}: {e}",
                exc_info=True,
            )

    async def _switch_mood_scene(self, mood_category: str) -> None:
        """
        Switch to a scene based on mood category.

        Args:
            mood_category: The mood category string (e.g., "energetic_bright_intense")

        Note:
            Only switches if a mapping exists for the mood category and the scene exists.
        """
        if not mood_category:
            _LOGGER.debug("Empty mood category, skipping scene switch")
            return

        try:
            # Rotate through a configured pool for this mood category if available
            pools: dict[str, list[str]] = await self._get_config("mood_scene_pools", {})  # type: ignore
            scene_id = self._get_next_scene_from_pool(mood_category, pools)
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
                return
            # Fall back to a direct mapping if no pool
            mood_scenes = await self._get_config("mood_scenes", {})
            scene_id = (
                mood_scenes.get(mood_category)
                if isinstance(mood_scenes, dict)
                else None
            )
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
        except Exception as e:
            _LOGGER.warning(f"Error switching mood scene: {e}", exc_info=True)

    async def _switch_structure_scene(self, section: MusicSection) -> None:
        """
        Switch to a scene based on music structure.

        Args:
            section: The current music section (e.g., MusicSection.CHORUS)

        Note:
            Only switches if a mapping exists for the structure section and the scene exists.
        """
        if section is None:
            _LOGGER.debug("No section provided, skipping scene switch")
            return

        try:
            structure_key = f"structure_{section.value}"
            # First attempt to rotate through a pool for this structure key
            pools: dict[str, list[str]] = await self._get_config("event_scene_pools", {})  # type: ignore
            scene_id = self._get_next_scene_from_pool(structure_key, pools)
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
                return
            # Fall back to a single mapping
            event_scenes = await self._get_config("event_scenes", {})
            scene_id = (
                event_scenes.get(structure_key)
                if isinstance(event_scenes, dict)
                else None
            )
            if scene_id:
                await self._activate_scene_if_allowed(scene_id)
        except Exception as e:
            _LOGGER.warning(
                f"Error switching structure scene: {e}", exc_info=True
            )

    async def _apply_global_config(
        self, config: dict[str, Any], intensity: float
    ) -> None:
        """
        Apply configuration to effects globally.

        This method safely applies configuration updates to effects on target virtuals,
        filtering out unsupported parameters and handling errors gracefully.

        Args:
            config: Configuration dictionary to apply (e.g., {"speed": 2.0, "brightness": 0.8})
            intensity: Overall intensity modifier (0-1) to scale effect strength

        Note:
            Only applies config keys that are supported by each effect's schema.
            Skips virtuals that don't exist or don't have active effects.
        """
        if not config:
            return

        try:
            # Get target virtuals
            target_virtuals = await self._get_config("target_virtuals", [])
            if not target_virtuals:
                # Apply to all active virtuals
                if not hasattr(self._ledfx, "virtuals"):
                    _LOGGER.debug("No virtuals available")
                    return

                target_virtuals = [
                    virtual.id
                    for virtual in self._ledfx.virtuals.values()
                    if hasattr(virtual, "active_effect")
                    and virtual.active_effect
                ]

            if not target_virtuals:
                _LOGGER.warning(
                    "No target virtuals found for mood config application. "
                    "Make sure you have virtuals with active effects running."
                )
                return

            # Apply to each virtual's active effect
            applied_count = 0
            for virtual_id in target_virtuals:
                try:
                    virtual = self._ledfx.virtuals.get(virtual_id)
                    if not virtual:
                        _LOGGER.debug(f"Virtual '{virtual_id}' not found")
                        continue

                    if (
                        not hasattr(virtual, "active_effect")
                        or not virtual.active_effect
                    ):
                        _LOGGER.debug(
                            f"Virtual '{virtual_id}' has no active effect"
                        )
                        continue

                    # Filter config to only supported keys
                    effect = virtual.active_effect
                    supported_config: dict[str, Any] = {}

                    # Get effect schema to check supported keys
                    effect_schema_keys = set()
                    try:
                        if hasattr(effect, "schema"):
                            schema = type(effect).schema()
                            if hasattr(schema, "schema"):
                                effect_schema_keys = set(schema.schema.keys())
                    except Exception as e:
                        _LOGGER.debug(
                            f"Error getting schema for effect on virtual '{virtual_id}': {e}"
                        )
                        # Fallback: try to get keys from current config if schema fails
                        if hasattr(effect, "_config"):
                            effect_schema_keys = set(effect._config.keys())

                    # Filter config to only keys supported by the effect schema
                    for key, value in config.items():
                        # Check if effect supports this config key in its schema
                        if key in effect_schema_keys:
                            # Apply intensity scaling if value is numeric
                            if (
                                isinstance(value, (int, float))
                                and key != "gradient"
                            ):
                                scaled_value = value * intensity
                                supported_config[key] = scaled_value
                            else:
                                supported_config[key] = value

                    if supported_config:
                        # Update effect config safely
                        try:
                            if hasattr(effect, "update_config"):
                                effect.update_config(supported_config)
                                applied_count += 1
                            else:
                                _LOGGER.debug(
                                    f"Effect on virtual '{virtual_id}' doesn't support update_config"
                                )
                        except Exception as e:
                            _LOGGER.debug(
                                f"Error updating config for virtual '{virtual_id}': {e}"
                            )

                except Exception as e:
                    _LOGGER.debug(
                        f"Error processing virtual '{virtual_id}': {e}"
                    )
                    continue

            if applied_count > 0:
                _LOGGER.info(
                    f"Applied mood config to {applied_count} virtual(s) with keys: {list(config.keys())}"
                )
            else:
                _LOGGER.debug(
                    f"No config applied - {len(target_virtuals)} target virtuals, {len(config)} config keys provided"
                )

        except Exception as e:
            _LOGGER.warning(
                f"Error applying global config: {e}", exc_info=True
            )

    def get_current_mood(self) -> Optional[dict[str, float]]:
        """
        Get current mood metrics.

        Returns:
            Dictionary of current mood metrics, or None if mood detector not initialized.
            Metrics include: energy, valence, intensity, brightness, beat_strength, etc.
        """
        if self._mood_detector is None:
            return None

        try:
            return self._mood_detector.get_mood_metrics()
        except Exception as e:
            _LOGGER.debug(f"Error getting current mood: {e}")
            return None

    async def get_current_structure(self) -> Optional[dict[str, Any]]:
        """
        Get current structure information.

        Returns:
            Dictionary of current structure information, or None if structure analyzer
            not initialized. Includes section, duration, last_event, energy_trend, etc.
        """
        if self._structure_analyzer is None:
            return None

        try:
            current_section = self._structure_analyzer.get_current_section()
            last_event = self._structure_analyzer.get_last_event()

            return {
                "section": (
                    current_section.value if current_section else "unknown"
                ),
                "duration": self._structure_analyzer.get_section_duration(),
                "last_event": last_event.value if last_event else "none",
                "energy_trend": self._structure_analyzer.get_energy_trend(),
                "is_transitional": self._structure_analyzer.is_transitional(),
            }
        except Exception as e:
            _LOGGER.debug(f"Error getting current structure: {e}")
            return None

    async def set_enabled(self, enabled: bool):
        """Enable or disable mood monitoring."""
        await self._update_config({"enabled": enabled})

        if enabled:
            await self.start_monitoring()
        else:
            await self.stop_monitoring()

        # Save config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    def _get_next_scene_from_pool(
        self, key: str, pools: dict[str, list[str]]
    ) -> Optional[str]:
        """
        Retrieve the next scene ID from a configured pool for a given key.
        Scene pools are rotated to provide variety when the same key occurs
        repeatedly. Returns None if no pool exists for the given key.

        Args:
            key: The mood category or event key
            pools: A dictionary mapping keys to lists of scene IDs

        Returns:
            The next scene ID from the pool or None
        """
        pool = pools.get(key)
        if not pool:
            return None
        # Initialize index if not already present
        idx = self._pool_indices.get(key, 0)
        if idx >= len(pool):
            idx = 0
        scene_id = pool[idx]
        # Update index for next rotation
        self._pool_indices[key] = (idx + 1) % len(pool)
        return scene_id

    async def _activate_scene_if_allowed(
        self, scene_id: Optional[str]
    ) -> None:
        """
        Activate the given scene ID if allowed by the hysteresis rules. This
        prevents frequent scene changes and ensures repeated activations of the
        same scene are skipped.

        Args:
            scene_id: The ID of the scene to activate
        """
        if not scene_id:
            return

        # Validate scene exists before attempting activation
        if not hasattr(self._ledfx, "scenes") or self._ledfx.scenes is None:
            _LOGGER.debug("Scenes not available")
            return

        if not self._ledfx.scenes.get(scene_id):
            _LOGGER.debug(
                f"Scene '{scene_id}' does not exist, skipping activation"
            )
            return

        now = time.time()
        min_interval_val = await self._get_config(
            "min_scene_change_interval", 0.0
        )
        min_interval = float(min_interval_val)

        # Atomic check and update with scene lock
        async with self._scene_lock:
            # If the requested scene is already active and hysteresis interval has not passed, skip
            if self._current_scene_id == scene_id:
                if (now - self._last_scene_change_time) < min_interval:
                    _LOGGER.debug(
                        f"Skipping scene '{scene_id}' activation: already active and within hysteresis interval"
                    )
                    return

            # Enforce minimum interval between scene changes (even for different scenes)
            if (now - self._last_scene_change_time) < min_interval:
                _LOGGER.debug(
                    f"Skipping scene change to '{scene_id}' due to hysteresis interval"
                )
                return

            # All checks passed - activate scene atomically
            try:
                self._ledfx.scenes.activate(scene_id)
                self._current_scene_id = scene_id
                self._last_scene_change_time = now
                _LOGGER.info(f"Activated scene '{scene_id}'")
            except Exception as e:
                _LOGGER.warning(f"Failed to activate scene '{scene_id}': {e}")
