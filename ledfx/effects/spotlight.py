"""Audio-reactive random spotlight effect for 1D LED strips."""

import random
import time

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class RandomSpotlightAudioEffect(AudioReactiveEffect, GradientEffect):
    """Spawn fading spotlight segments at random positions based on audio activity."""

    NAME = "Spotlight"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["gradient_roll"]
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + [
        "beat_trigger",
        "max_active_spots",
        "use_gradient",
        "gradient_speed",
        "spot_color_span",
        "center_color",
        "edge_color",
    ]

    INTERNAL_MIN_TIME_BETWEEN_SPOTS = 0.02
    INTERNAL_MIN_ACTIVE_SPOTS = 3
    INTERNAL_MAX_ACTIVE_SPOTS = 28
    INTERNAL_BASE_SPAWN_RATE = 2.5
    INTERNAL_ACTIVITY_SPAWN_RATE = 14.0
    INTERNAL_PEAK_SPAWN_BOOST = 1.8
    INTERNAL_MAX_SPAWNS_PER_UPDATE = 6
    INTERNAL_LOWS_WEIGHT = 0.9
    INTERNAL_MIDS_WEIGHT = 1.0
    INTERNAL_HIGHS_WEIGHT = 1.3
    INTERNAL_TRANSIENT_SENSITIVITY = 1.2
    INTERNAL_EDGE_SOFTNESS = 1.5
    INTERNAL_FADE_CURVE = 1.4
    INTERNAL_CENTER_COLOR = "#FFFFFF"
    INTERNAL_EDGE_COLOR = "#4AA3FF"

    BEAT_TRIGGER_MAPPING = {
        "Adaptive (recommended)": None,
        "Volume Beat": "volume_beat_now",
        "Onset": "onset",
        "BPM Beat": "bpm_beat_now",
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "beat_trigger",
                description="Source used to add extra spotlight bursts",
                default="Adaptive (recommended)",
            ): vol.In(list(BEAT_TRIGGER_MAPPING.keys())),
            vol.Optional(
                "spot_width",
                description="Spotlight width relative to strip length (%)",
                default=8.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=100.0)),
            vol.Optional(
                "fade_time",
                description="How long a spotlight fades out in seconds",
                default=0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=8.0)),
            vol.Optional(
                "max_active_spots",
                description="Maximum simultaneous fading spotlights",
                default=INTERNAL_MAX_ACTIVE_SPOTS,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=128)),
            vol.Optional(
                "use_gradient",
                description="Use LedFx gradient instead of fixed spotlight colors",
                default=True,
            ): bool,
            vol.Optional(
                "gradient_speed",
                description="How fast the gradient color advances (cycles per second)",
                default=0.12,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3.0)),
            vol.Optional(
                "spot_color_span",
                description="Color spread from center to edge when using gradient",
                default=0.08,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "center_color",
                description="Color at spotlight center when gradient is disabled",
                default=INTERNAL_CENTER_COLOR,
            ): validate_color,
            vol.Optional(
                "edge_color",
                description="Color at spotlight edge when gradient is disabled",
                default=INTERNAL_EDGE_COLOR,
            ): validate_color,
        }
    )

    def on_activate(self, pixel_count):
        """Initialize runtime state once the strip pixel count is known."""
        self.spot_centers = np.empty(0, dtype=int)
        self.spot_born = np.empty(0, dtype=float)
        self.spot_anchors = np.empty(0, dtype=float)
        self.spot_templates = np.empty((0, 1, 3), dtype=float)
        self.last_spawn_time = 0.0
        self.last_audio_time = time.time()
        self.spawn_accumulator = 0.0
        self.weighted_power = 0.0
        self.dynamic_spot_cap = 1
        self.gradient_phase = 0.0
        self._activity_filter = self.create_filter(
            alpha_decay=0.25, alpha_rise=0.6
        )
        self._refresh_spot_template()
        self._template_signature = self._get_template_signature()
        self._clear_spots()

    def config_updated(self, config):
        """Cache validated config values and rebuild spot templates when needed."""
        old_template_signature = getattr(self, "_template_signature", None)

        self.beat_trigger = self._config["beat_trigger"]
        self.beat_trigger_func = self.BEAT_TRIGGER_MAPPING[self.beat_trigger]
        self.spot_width = self._config["spot_width"]
        self.edge_softness = self.INTERNAL_EDGE_SOFTNESS
        self.fade_time = self._config["fade_time"]
        self.fade_curve = self.INTERNAL_FADE_CURVE
        self.min_time_between_spots = self.INTERNAL_MIN_TIME_BETWEEN_SPOTS
        self.min_active_spots = self.INTERNAL_MIN_ACTIVE_SPOTS
        self.max_active_spots = self._config["max_active_spots"]
        if self.min_active_spots > self.max_active_spots:
            self.min_active_spots = self.max_active_spots
        self.base_spawn_rate = self.INTERNAL_BASE_SPAWN_RATE
        self.activity_spawn_rate = self.INTERNAL_ACTIVITY_SPAWN_RATE
        self.peak_spawn_boost = self.INTERNAL_PEAK_SPAWN_BOOST
        self.max_spawns_per_update = self.INTERNAL_MAX_SPAWNS_PER_UPDATE
        self.lows_weight = self.INTERNAL_LOWS_WEIGHT
        self.mids_weight = self.INTERNAL_MIDS_WEIGHT
        self.highs_weight = self.INTERNAL_HIGHS_WEIGHT
        self.transient_sensitivity = self.INTERNAL_TRANSIENT_SENSITIVITY
        self.use_gradient = self._config["use_gradient"]
        self.gradient_speed = self._config["gradient_speed"]
        self.spot_color_span = self._config["spot_color_span"]
        self.center_color = np.array(
            parse_color(self._config["center_color"]), dtype=float
        )
        self.edge_color = np.array(
            parse_color(self._config["edge_color"]), dtype=float
        )

        self._template_signature = self._get_template_signature()

        if hasattr(self, "pixels") and self.pixels is not None:
            self._refresh_spot_template()

            if (
                hasattr(self, "spot_centers")
                and self.spot_centers.size > 0
                and old_template_signature != self._template_signature
            ):
                self._rebuild_active_spot_templates()

    def _get_template_signature(self):
        """Return a compact signature of parameters that affect spot templates."""
        return (
            self.use_gradient,
            self.spot_color_span,
            self.edge_softness,
            self.spot_width,
            self._config.get("gradient"),
            tuple(self.center_color.tolist()),
            tuple(self.edge_color.tolist()),
        )

    def _refresh_spot_template(self):
        """Recompute per-spot geometry and color/intensity profiles."""
        max_width = (
            self.pixel_count if self.pixel_count % 2 else self.pixel_count - 1
        )
        max_width = max(max_width, 1)

        effective_width = int(
            round(self.pixel_count * self.spot_width / 100.0)
        )
        effective_width = max(1, min(effective_width, max_width))
        if effective_width % 2 == 0:
            if effective_width < max_width:
                effective_width += 1
            else:
                effective_width -= 1
        effective_width = max(1, effective_width)

        half_width = effective_width // 2
        self._spot_offsets = np.arange(-half_width, half_width + 1, dtype=int)

        if half_width == 0:
            distance = np.zeros(1, dtype=float)
        else:
            distance = np.abs(self._spot_offsets) / float(half_width)

        self._spot_center_mix = 1.0 - distance
        self._spot_intensity = np.power(
            self._spot_center_mix, self.edge_softness
        )

        if self.use_gradient:
            self._spot_template = None
            return

        color_gradient = (
            self.edge_color[np.newaxis, :]
            * (1.0 - self._spot_center_mix)[:, np.newaxis]
            + self.center_color[np.newaxis, :]
            * self._spot_center_mix[:, np.newaxis]
        )
        self._spot_template = (
            color_gradient * self._spot_intensity[:, np.newaxis]
        )

    def _clear_spots(self):
        """Reset spotlight state arrays while preserving current template width."""
        width = len(self._spot_offsets)
        self.spot_centers = np.empty(0, dtype=int)
        self.spot_born = np.empty(0, dtype=float)
        self.spot_anchors = np.empty(0, dtype=float)
        self.spot_templates = np.empty((0, width, 3), dtype=float)

    def _build_templates_from_anchors(self, anchors):
        """Build one template per anchor using vectorized gradient sampling."""
        count = anchors.size
        width = len(self._spot_offsets)
        if count == 0:
            return np.empty((0, width, 3), dtype=float)

        if not self.use_gradient:
            return np.repeat(
                self._spot_template[np.newaxis, :, :], count, axis=0
            )

        edge_anchors = np.mod(anchors + self.spot_color_span, 1.0)
        center_colors = self.get_gradient_color_vectorized1d(anchors)
        edge_colors = self.get_gradient_color_vectorized1d(edge_anchors)

        center_mix = self._spot_center_mix[np.newaxis, :, np.newaxis]
        intensity = self._spot_intensity[np.newaxis, :, np.newaxis]

        color_gradient = (
            edge_colors[:, np.newaxis, :] * (1.0 - center_mix)
            + center_colors[:, np.newaxis, :] * center_mix
        )
        return color_gradient * intensity

    def _rebuild_active_spot_templates(self):
        """Rebuild cached templates for active spotlights after template changes."""
        self.spot_templates = self._build_templates_from_anchors(
            self.spot_anchors
        )

    def _drop_oldest_spots(self, count):
        """Drop the oldest spotlight entries to respect the configured cap."""
        if count <= 0:
            return
        self.spot_centers = self.spot_centers[count:]
        self.spot_born = self.spot_born[count:]
        self.spot_anchors = self.spot_anchors[count:]
        self.spot_templates = self.spot_templates[count:]

    def _ring_distance(self, pixel_a, pixel_b):
        """Return shortest wrapped distance between two pixels on a ring."""
        diff = abs(pixel_a - pixel_b)
        return min(diff, self.pixel_count - diff)

    def _pick_spot_center(self):
        """Pick a random spotlight center, preferring spacing from active spots."""
        if self.pixel_count <= 1:
            return 0

        if self.spot_centers.size == 0:
            return random.randrange(self.pixel_count)

        min_center_distance = max(1, len(self._spot_offsets) // 2)

        for _ in range(10):
            candidate = random.randrange(self.pixel_count)
            if all(
                self._ring_distance(candidate, center) >= min_center_distance
                for center in self.spot_centers
            ):
                return candidate

        return random.randrange(self.pixel_count)

    def _spawn_spot(self, now):
        """Create a new spotlight and cap list size to max_active_spots."""
        overflow = self.spot_centers.size - self.max_active_spots + 1
        if overflow > 0:
            self._drop_oldest_spots(overflow)

        color_anchor = 0.0
        if self.use_gradient:
            color_anchor = (
                self.gradient_phase + random.random() * self.spot_color_span
            ) % 1.0

        center = self._pick_spot_center()
        new_anchor = np.array([color_anchor], dtype=float)
        new_template = self._build_templates_from_anchors(new_anchor)

        self.spot_centers = np.append(self.spot_centers, center)
        self.spot_born = np.append(self.spot_born, now)
        self.spot_anchors = np.append(self.spot_anchors, color_anchor)
        self.spot_templates = np.concatenate(
            (self.spot_templates, new_template), axis=0
        )

    def _adaptive_boost_detected(self, data):
        """Return whether adaptive burst triggers are currently active."""
        return data.onset() or data.volume_beat_now()

    def _specific_boost_detected(self, data):
        """Return whether the selected explicit beat trigger fired."""
        return bool(getattr(data, self.beat_trigger_func)())

    def _current_boost_detected(self, data):
        """Dispatch burst detection for adaptive or explicit trigger mode."""
        if self.beat_trigger_func is None:
            return self._adaptive_boost_detected(data)
        return self._specific_boost_detected(data)

    def audio_data_updated(self, data):
        """Update activity model and schedule new spotlight spawns per audio frame."""
        now = time.time()
        dt = max(0.0, min(0.25, now - self.last_audio_time))
        self.last_audio_time = now

        if self.use_gradient and self.gradient_speed > 0:
            self.gradient_phase = (
                self.gradient_phase + dt * self.gradient_speed
            ) % 1.0

        lows = float(data.lows_power())
        mids = float(data.mids_power())
        highs = float(data.high_power())
        weight_sum = max(
            0.001,
            self.lows_weight + self.mids_weight + self.highs_weight,
        )

        weighted_power = (
            lows * self.lows_weight
            + mids * self.mids_weight
            + highs * self.highs_weight
        ) / weight_sum

        power_delta = max(0.0, weighted_power - self.weighted_power)
        self.weighted_power = weighted_power

        activity_input = np.clip(
            weighted_power + power_delta * self.transient_sensitivity,
            0.0,
            2.0,
        )
        activity_level = np.clip(
            self._activity_filter.update(activity_input), 0, 1
        )

        dynamic_span = self.max_active_spots - self.min_active_spots
        self.dynamic_spot_cap = self.min_active_spots + int(
            dynamic_span * activity_level
        )

        spawn_rate = (
            self.base_spawn_rate + self.activity_spawn_rate * activity_level
        )
        self.spawn_accumulator += spawn_rate * dt

        if self._current_boost_detected(data):
            self.spawn_accumulator += self.peak_spawn_boost * (
                1.0 + power_delta * self.transient_sensitivity
            )

        self.spawn_accumulator = min(self.spawn_accumulator, 64.0)

        if now - self.last_spawn_time < self.min_time_between_spots:
            return

        available_capacity = max(
            0, self.dynamic_spot_cap - self.spot_centers.size
        )
        if available_capacity <= 0:
            return

        spawn_budget = int(self.spawn_accumulator)
        if spawn_budget <= 0:
            return

        to_spawn = min(
            spawn_budget,
            available_capacity,
            self.max_spawns_per_update,
        )
        for _ in range(to_spawn):
            self._spawn_spot(now)

        self.spawn_accumulator -= to_spawn
        self.last_spawn_time = now

    def render(self):
        """Render active spotlights in a single batched add pass."""
        self.pixels[:] = 0.0
        if self.spot_centers.size == 0:
            return

        now = time.time()
        ages = now - self.spot_born
        alive_idx = np.flatnonzero(ages < self.fade_time)
        if alive_idx.size == 0:
            self._clear_spots()
            return

        if alive_idx.size > self.dynamic_spot_cap:
            alive_idx = alive_idx[-self.dynamic_spot_cap :]

        self.spot_centers = self.spot_centers[alive_idx]
        self.spot_born = self.spot_born[alive_idx]
        self.spot_anchors = self.spot_anchors[alive_idx]
        self.spot_templates = self.spot_templates[alive_idx]

        ages = now - self.spot_born
        life = np.clip(1.0 - ages / self.fade_time, 0.0, 1.0)
        fade_amounts = np.power(life, self.fade_curve)

        positive_idx = np.flatnonzero(fade_amounts > 0.0)
        if positive_idx.size == 0:
            self._clear_spots()
            return

        self.spot_centers = self.spot_centers[positive_idx]
        self.spot_born = self.spot_born[positive_idx]
        self.spot_anchors = self.spot_anchors[positive_idx]
        self.spot_templates = self.spot_templates[positive_idx]
        fade_amounts = fade_amounts[positive_idx]

        indices = (
            self.spot_centers[:, np.newaxis]
            + self._spot_offsets[np.newaxis, :]
        ) % self.pixel_count
        weighted_templates = (
            self.spot_templates * fade_amounts[:, np.newaxis, np.newaxis]
        )

        np.add.at(
            self.pixels,
            indices.reshape(-1),
            weighted_templates.reshape(-1, 3),
        )
