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

    NAME = "Random Spotlight"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["flip", "mirror", "gradient_roll"]

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
                description="Spotlight width in pixels (odd numbers only)",
                default=21,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1023)),
            vol.Optional(
                "edge_softness",
                description="How soft the spotlight edge is",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=6.0)),
            vol.Optional(
                "fade_time",
                description="How long a spotlight fades out in seconds",
                default=0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=8.0)),
            vol.Optional(
                "fade_curve",
                description="Shape of the fade curve (higher = faster end fade)",
                default=1.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.3, max=5.0)),
            vol.Optional(
                "min_time_between_spots",
                description="Minimum time between spotlight spawns",
                default=0.02,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "min_active_spots",
                description="Minimum simultaneous spotlights",
                default=3,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=128)),
            vol.Optional(
                "max_active_spots",
                description="Maximum simultaneous fading spotlights",
                default=28,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=128)),
            vol.Optional(
                "base_spawn_rate",
                description="Base spotlight spawns per second",
                default=2.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=30.0)),
            vol.Optional(
                "activity_spawn_rate",
                description="Extra spawns per second based on music activity",
                default=14.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=80.0)),
            vol.Optional(
                "peak_spawn_boost",
                description="Extra spotlight burst on strong transients",
                default=1.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=12.0)),
            vol.Optional(
                "max_spawns_per_update",
                description="Upper limit of spotlights spawned per audio frame",
                default=6,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            vol.Optional(
                "lows_weight",
                description="How much lows influence activity",
                default=0.9,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3.0)),
            vol.Optional(
                "mids_weight",
                description="How much mids influence activity",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3.0)),
            vol.Optional(
                "highs_weight",
                description="How much highs influence activity",
                default=1.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3.0)),
            vol.Optional(
                "transient_sensitivity",
                description="How strongly sudden peaks increase spotlight bursts",
                default=1.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=4.0)),
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
                description="Color at spotlight center",
                default="#FFFFFF",
            ): validate_color,
            vol.Optional(
                "edge_color",
                description="Color at spotlight edge",
                default="#4AA3FF",
            ): validate_color,
        }
    )

    def on_activate(self, pixel_count):
        """Initialize runtime state once the strip pixel count is known."""
        self.active_spots = []
        self.last_spawn_time = 0.0
        self.last_audio_time = time.time()
        self.spawn_accumulator = 0.0
        self.weighted_power = 0.0
        self.dynamic_spot_cap = 1
        self.gradient_phase = 0.0
        self._spot_offsets = np.array([0], dtype=int)
        self._spot_center_mix = np.ones(1, dtype=float)
        self._spot_intensity = np.ones(1, dtype=float)
        self._spot_template = np.zeros((1, 3), dtype=float)
        self._activity_filter = self.create_filter(
            alpha_decay=0.25, alpha_rise=0.6
        )
        self._refresh_spot_template()

    def config_updated(self, config):
        """Cache validated config values and rebuild spot templates when needed."""
        self.beat_trigger = self._config["beat_trigger"]
        self.beat_trigger_func = self.BEAT_TRIGGER_MAPPING[self.beat_trigger]
        self.spot_width = int(self._config["spot_width"])
        if self.spot_width % 2 == 0:
            self.spot_width += 1
        self.edge_softness = self._config["edge_softness"]
        self.fade_time = self._config["fade_time"]
        self.fade_curve = self._config["fade_curve"]
        self.min_time_between_spots = self._config["min_time_between_spots"]
        self.min_active_spots = self._config["min_active_spots"]
        self.max_active_spots = self._config["max_active_spots"]
        if self.min_active_spots > self.max_active_spots:
            self.min_active_spots = self.max_active_spots
        self.base_spawn_rate = self._config["base_spawn_rate"]
        self.activity_spawn_rate = self._config["activity_spawn_rate"]
        self.peak_spawn_boost = self._config["peak_spawn_boost"]
        self.max_spawns_per_update = self._config["max_spawns_per_update"]
        self.lows_weight = self._config["lows_weight"]
        self.mids_weight = self._config["mids_weight"]
        self.highs_weight = self._config["highs_weight"]
        self.transient_sensitivity = self._config["transient_sensitivity"]
        self.use_gradient = self._config["use_gradient"]
        self.gradient_speed = self._config["gradient_speed"]
        self.spot_color_span = self._config["spot_color_span"]
        self.center_color = np.array(
            parse_color(self._config["center_color"]), dtype=float
        )
        self.edge_color = np.array(
            parse_color(self._config["edge_color"]), dtype=float
        )

        if hasattr(self, "pixels") and self.pixels is not None:
            self._refresh_spot_template()

    def _refresh_spot_template(self):
        """Recompute per-spot geometry and color/intensity profiles."""
        max_width = (
            self.pixel_count if self.pixel_count % 2 else self.pixel_count - 1
        )
        max_width = max(max_width, 1)
        effective_width = min(self.spot_width, max_width)

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
            self._spot_template = np.zeros(
                (len(self._spot_offsets), 3), dtype=float
            )
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

    def _ring_distance(self, pixel_a, pixel_b):
        """Return shortest wrapped distance between two pixels on a ring."""
        diff = abs(pixel_a - pixel_b)
        return min(diff, self.pixel_count - diff)

    def _pick_spot_center(self):
        """Pick a random spotlight center, preferring spacing from active spots."""
        if self.pixel_count <= 1:
            return 0

        if not self.active_spots:
            return random.randrange(self.pixel_count)

        min_center_distance = max(1, len(self._spot_offsets) // 2)

        for _ in range(10):
            candidate = random.randrange(self.pixel_count)
            if all(
                self._ring_distance(candidate, center) >= min_center_distance
                for center, _born, _color_anchor in self.active_spots
            ):
                return candidate

        return random.randrange(self.pixel_count)

    def _spawn_spot(self, now):
        """Create a new spotlight and cap list size to max_active_spots."""
        while len(self.active_spots) >= self.max_active_spots:
            self.active_spots.pop(0)

        color_anchor = 0.0
        if self.use_gradient:
            color_anchor = (
                self.gradient_phase + random.random() * self.spot_color_span
            ) % 1.0

        self.active_spots.append((self._pick_spot_center(), now, color_anchor))

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
            0, self.dynamic_spot_cap - len(self.active_spots)
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

    def _render_spot(self, center, color_anchor, fade_amount):
        """Blend a single spotlight contribution into the output pixel buffer."""
        indices = (center + self._spot_offsets) % self.pixel_count

        if self.use_gradient:
            center_color = np.array(
                self.get_gradient_color(color_anchor), dtype=float
            )
            edge_color = np.array(
                self.get_gradient_color(
                    (color_anchor + self.spot_color_span) % 1.0
                ),
                dtype=float,
            )
            color_gradient = (
                edge_color[np.newaxis, :]
                * (1.0 - self._spot_center_mix)[:, np.newaxis]
                + center_color[np.newaxis, :]
                * self._spot_center_mix[:, np.newaxis]
            )
            spot_template = (
                color_gradient * self._spot_intensity[:, np.newaxis]
            )
            np.add.at(self.pixels, indices, spot_template * fade_amount)
            return

        np.add.at(self.pixels, indices, self._spot_template * fade_amount)

    def render(self):
        """Render active spotlights, apply fade-out, and prune expired entries."""
        self.pixels[:] = 0.0
        if not self.active_spots:
            return

        now = time.time()
        remaining_spots = []

        for center, born, color_anchor in self.active_spots:
            age = now - born
            if age >= self.fade_time:
                continue

            life = max(0.0, 1.0 - age / self.fade_time)
            fade_amount = np.power(life, self.fade_curve)
            if fade_amount <= 0.0:
                continue

            self._render_spot(center, color_anchor, fade_amount)
            remaining_spots.append((center, born, color_anchor))

        if len(remaining_spots) > self.dynamic_spot_cap:
            remaining_spots = remaining_spots[-self.dynamic_spot_cap :]

        self.active_spots = remaining_spots
