"""Audio-reactive random spotlight effect for 1D LED strips."""

import random
import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class SpotlightAudioEffect(AudioReactiveEffect, GradientEffect):
    """Spawn fading spotlight segments at random positions based on audio activity."""

    NAME = "Spotlight"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["gradient_roll"]
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + [
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
    INTERNAL_TRANSIENT_SENSITIVITY = 1.2
    INTERNAL_EDGE_SOFTNESS = 1.5
    INTERNAL_FADE_CURVE = 1.4
    INTERNAL_CENTER_COLOR = "#FFFFFF"
    INTERNAL_EDGE_COLOR = "#4AA3FF"
    INTERNAL_LOWS_WEIGHT = 0.5
    INTERNAL_MIDS_WEIGHT = 0.3
    INTERNAL_HIGHS_WEIGHT = 0.2

    CONFIG_SCHEMA = vol.Schema(
        {
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
        self.last_spawn_time = 0.0
        self.last_audio_time = timeit.default_timer()
        self.spawn_accumulator = 0.0
        self.weighted_power = 0.0
        self.dynamic_spot_cap = 1
        self.gradient_phase = 0.0
        self._activity_filter = self.create_filter(
            alpha_decay=0.25, alpha_rise=0.6
        )
        self._refresh_spot_template()
        self._clear_spots()

    def config_updated(self, config):
        """Cache validated config values and rebuild spot templates when needed."""
        old_template_signature = getattr(self, "_template_signature", None)

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
            reallocated = self._ensure_spot_storage(len(self._spot_offsets))

            if (
                not reallocated
                and hasattr(self, "spot_count")
                and self.spot_count > 0
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

        effective_width = round(self.pixel_count * self.spot_width / 100.0)
        effective_width = max(1, min(effective_width, max_width))
        if effective_width % 2 == 0 and effective_width < max_width:
            effective_width += 1
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

    def _get_active_indices(self):
        """Return ring-buffer indices for active spotlight entries."""
        if not hasattr(self, "spot_count") or self.spot_count == 0:
            return np.empty(0, dtype=int)
        return (
            self.spot_head + np.arange(self.spot_count, dtype=int)
        ) % self.spot_capacity

    def _get_active_spot_data(self):
        """Return active spot arrays in chronological order."""
        active_idx = self._get_active_indices()
        if active_idx.size == 0:
            return (
                np.empty(0, dtype=int),
                np.empty(0, dtype=float),
                np.empty(0, dtype=float),
            )
        return (
            self.spot_centers[active_idx].copy(),
            self.spot_born[active_idx].copy(),
            self.spot_anchors[active_idx].copy(),
        )

    def _ensure_spot_storage(self, template_width):
        """Ensure storage matches capacity/template width and report reallocations."""
        capacity = max(1, int(self.max_active_spots))
        storage_valid = (
            hasattr(self, "spot_capacity")
            and self.spot_capacity == capacity
            and hasattr(self, "spot_templates")
            and self.spot_templates.shape[1] == template_width
        )
        if storage_valid:
            return False

        old_centers, old_born, old_anchors = self._get_active_spot_data()
        keep = min(old_centers.size, capacity)

        self.spot_capacity = capacity
        self.spot_centers = np.empty(capacity, dtype=int)
        self.spot_born = np.empty(capacity, dtype=float)
        self.spot_anchors = np.empty(capacity, dtype=float)
        self.spot_templates = np.empty(
            (capacity, template_width, 3), dtype=float
        )
        self.spot_head = 0
        self.spot_count = keep

        if keep == 0:
            return True

        self.spot_centers[:keep] = old_centers[-keep:]
        self.spot_born[:keep] = old_born[-keep:]
        self.spot_anchors[:keep] = old_anchors[-keep:]
        self.spot_templates[:keep] = self._build_templates_from_anchors(
            self.spot_anchors[:keep]
        )
        return True

    def _clear_spots(self):
        """Reset spotlight state arrays while preserving current template width."""
        self._ensure_spot_storage(len(self._spot_offsets))
        self.spot_head = 0
        self.spot_count = 0

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
        active_idx = self._get_active_indices()
        if active_idx.size == 0:
            return
        self.spot_templates[active_idx] = self._build_templates_from_anchors(
            self.spot_anchors[active_idx]
        )

    def _drop_oldest_spots(self, count):
        """Drop the oldest spotlight entries to respect the configured cap."""
        if count <= 0 or self.spot_count == 0:
            return
        count = min(count, self.spot_count)
        self.spot_head = (self.spot_head + count) % self.spot_capacity
        self.spot_count -= count

    def _pick_spot_center(self):
        """Pick a random spotlight center, preferring spacing from active spots."""
        if self.pixel_count <= 1:
            return 0

        if self.spot_count == 0:
            return random.randrange(self.pixel_count)  # noqa: S311

        min_center_distance = max(1, len(self._spot_offsets) // 2)

        active_idx = self._get_active_indices()
        active_centers = self.spot_centers[active_idx]

        for _ in range(2):
            candidates = np.random.randint(0, self.pixel_count, size=64)
            diffs = np.abs(
                candidates[np.newaxis, :] - active_centers[:, np.newaxis]
            )
            ring_diffs = np.minimum(diffs, self.pixel_count - diffs)
            min_distance = np.min(ring_diffs, axis=0)
            valid = np.flatnonzero(min_distance >= min_center_distance)
            if valid.size > 0:
                return int(candidates[valid[0]])

        return random.randrange(self.pixel_count)  # noqa: S311

    def _allocate_spot_entry(self, now, center, color_anchor):
        """Insert spotlight metadata into the ring buffer and return its index."""
        overflow = self.spot_count - self.max_active_spots + 1
        if overflow > 0:
            self._drop_oldest_spots(overflow)

        if self.spot_count < self.spot_capacity:
            insert_idx = (
                self.spot_head + self.spot_count
            ) % self.spot_capacity
            self.spot_count += 1
        else:
            insert_idx = self.spot_head
            self.spot_head = (self.spot_head + 1) % self.spot_capacity

        self.spot_centers[insert_idx] = center
        self.spot_born[insert_idx] = now
        self.spot_anchors[insert_idx] = color_anchor
        return insert_idx

    def _spawn_spot(self, now):
        """Create a single spotlight using shared batch-capable primitives."""
        color_anchor = 0.0
        if self.use_gradient:
            color_anchor = (
                self.gradient_phase
                + random.random() * self.spot_color_span  # noqa: S311
            ) % 1.0

        center = self._pick_spot_center()
        insert_idx = self._allocate_spot_entry(now, center, color_anchor)
        self.spot_templates[insert_idx] = self._build_templates_from_anchors(
            np.array([color_anchor], dtype=float)
        )[0]

    def _spawn_spots(self, now, count):
        """Create multiple spotlights and build their templates in one batch."""
        if count <= 0:
            return

        anchors = np.empty(count, dtype=float)
        insert_indices = np.empty(count, dtype=int)

        for i in range(count):
            color_anchor = 0.0
            if self.use_gradient:
                color_anchor = (
                    self.gradient_phase
                    + random.random() * self.spot_color_span  # noqa: S311
                ) % 1.0

            center = self._pick_spot_center()
            insert_indices[i] = self._allocate_spot_entry(
                now, center, color_anchor
            )
            anchors[i] = color_anchor

        self.spot_templates[insert_indices] = (
            self._build_templates_from_anchors(anchors)
        )

    def _adaptive_boost_detected(self, data):
        """Return whether adaptive burst triggers are currently active."""
        return data.onset() or data.volume_beat_now()

    def audio_data_updated(self, data):
        """Update activity model and schedule new spotlight spawns per audio frame."""
        now = timeit.default_timer()
        dt = max(0.0, min(0.25, now - self.last_audio_time))
        self.last_audio_time = now

        if self.use_gradient and self.gradient_speed > 0:
            self.gradient_phase = (
                self.gradient_phase + dt * self.gradient_speed
            ) % 1.0

        lows = float(data.lows_power())
        mids = float(data.mids_power())
        highs = float(data.high_power())

        if not np.isfinite(lows):
            lows = 0.0
        if not np.isfinite(mids):
            mids = 0.0
        if not np.isfinite(highs):
            highs = 0.0

        weighted_power = float(
            self.INTERNAL_LOWS_WEIGHT * lows
            + self.INTERNAL_MIDS_WEIGHT * mids
            + self.INTERNAL_HIGHS_WEIGHT * highs
        )
        if not np.isfinite(weighted_power):
            weighted_power = 0.0

        previous_weighted_power = self.weighted_power
        if not np.isfinite(previous_weighted_power):
            previous_weighted_power = 0.0

        power_delta = max(0.0, weighted_power - previous_weighted_power)
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

        if self._adaptive_boost_detected(data):
            self.spawn_accumulator += self.peak_spawn_boost * (
                1.0 + power_delta * self.transient_sensitivity
            )

        self.spawn_accumulator = min(self.spawn_accumulator, 64.0)

        if now - self.last_spawn_time < self.min_time_between_spots:
            return

        available_capacity = max(0, self.dynamic_spot_cap - self.spot_count)
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
        self._spawn_spots(now, to_spawn)

        self.spawn_accumulator -= to_spawn
        self.last_spawn_time = now

    def render(self):
        """Render active spotlights in a single batched add pass."""
        self.pixels[:] = 0.0
        if self.spot_count == 0:
            return

        now = timeit.default_timer()
        while self.spot_count > 0:
            oldest_idx = self.spot_head
            if now - self.spot_born[oldest_idx] < self.fade_time:
                break
            self._drop_oldest_spots(1)

        if self.spot_count == 0:
            self._clear_spots()
            return

        active_idx = self._get_active_indices()
        ages = now - self.spot_born[active_idx]
        life = np.clip(1.0 - ages / self.fade_time, 0.0, 1.0)
        fade_amounts = np.power(life, self.fade_curve)

        indices = (
            self.spot_centers[active_idx][:, np.newaxis]
            + self._spot_offsets[np.newaxis, :]
        ) % self.pixel_count
        weighted_templates = (
            self.spot_templates[active_idx]
            * fade_amounts[:, np.newaxis, np.newaxis]
        )

        np.add.at(
            self.pixels,
            indices.reshape(-1),
            weighted_templates.reshape(-1, 3),
        )
