import logging
from collections import namedtuple

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.color import (
    hsv_to_rgb_vect,
    parse_color,
    rgb_to_hsv_vect,
    validate_color,
)
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# ---- Tunables ----
AUTO_GROW = False          # False = fixed cap per group (drop overflow); True = auto-grow geometrically
INIT_CAP = 4096            # initial particles capacity per group (only used when AUTO_GROW or as hard cap)
RGB_SCRATCH_FACTOR = 16    # prealloc rgb_scratch rows = r_width * this factor
DENSITY_EXPONENT = 0.5     # 0.0 = no spawn scaling; 1.0 = linear with height (64 is baseline)

MIN_VELOCITY_OFFSET = 0.5
MAX_VELOCITY_OFFSET = 1.2
MIN_LIFESPAN = 2.0
MAX_LIFESPAN = 4.0
WOBBLE_RATIO = 0.05
SPAWN_MODIFIER = 4.0

ParticleGroup = namedtuple(
    "ParticleGroup",
    ["x", "y", "age", "lifespan", "velocity_y", "size", "wobble_phase"],
)


class Flame2d(Twod):
    NAME = "Flame"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test", "background_color"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "spawn_rate", description="Particles spawn rate", default=0.5
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "velocity", description="Trips to top per second", default=0.3
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
            vol.Optional(
                "intensity",
                description="Application of the audio power input",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "blur_amount", description="Blur radius in pixels", default=2
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
            vol.Optional(
                "low_band", description="low band flame", default="#FF0000"
            ): validate_color,
            vol.Optional(
                "mid_band", description="mid band flame", default="#00FF00"
            ): validate_color,
            vol.Optional(
                "high_band", description="high band flame", default="#0000FF"
            ): validate_color,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.particles = None          # dict[str, ParticleGroup] with capacity-backed arrays
        self._counts = {"low": 0, "mid": 0, "high": 0}
        self._caps = {"low": 0, "mid": 0, "high": 0}

        self.audio_pow = np.zeros(3, dtype=np.float32)
        self.spawn_accumulator = np.zeros(3, dtype=np.float32)

        # perf helpers
        self._rng = np.random.default_rng()
        self._rgb_scratch = None
        self._offsets = np.arange(-3, 4, dtype=np.int32)  # [-3..3]
        self._abs_offsets = np.abs(self._offsets)

        # blur scratch
        self._blur_padded = None
        self._blur_cumsum = None

    def config_updated(self, config):
        super().config_updated(config)
        self.spawn_rate = self._config["spawn_rate"]
        self.min_lifespan = MIN_LIFESPAN
        self.max_lifespan = MAX_LIFESPAN
        self.velocity = self._config["velocity"]
        self.blur_amount = self._config["blur_amount"]
        self.low_color = np.array(
            parse_color(self._config["low_band"]), dtype=float
        )
        self.mid_color = np.array(
            parse_color(self._config["mid_band"]), dtype=float
        )
        self.high_color = np.array(
            parse_color(self._config["high_band"]), dtype=float
        )
        self.intensity = self._config["intensity"]

    def _empty_cap(self, n):
        return ParticleGroup(
            x=np.empty(n, np.float32),
            y=np.empty(n, np.float32),
            age=np.empty(n, np.float32),
            lifespan=np.empty(n, np.float32),
            velocity_y=np.empty(n, np.float32),
            size=np.empty(n, np.float32),
            wobble_phase=np.empty(n, np.float32),
        )

    def _ensure_group_caps(self, cap):
        if self.particles is None:
            self.particles = {
                "low": self._empty_cap(cap),
                "mid": self._empty_cap(cap),
                "high": self._empty_cap(cap),
            }
            self._caps = {"low": cap, "mid": cap, "high": cap}
            self._counts = {"low": 0, "mid": 0, "high": 0}

    def _grow_capacity(self, group, need):
        """Grow capacity for a group if AUTO_GROW; returns True if capacity OK."""
        have = self._caps[group]
        want = self._counts[group] + need
        if want <= have:
            return True
        if not AUTO_GROW:
            return False
        new_cap = max(want, int(have * 1.7) + 512)
        old = self.particles[group]
        new = self._empty_cap(new_cap)
        n = self._counts[group]
        for f in ParticleGroup._fields:
            getattr(new, f)[:n] = getattr(old, f)[:n]
        self.particles[group] = new
        self._caps[group] = new_cap
        return True

    def do_once(self):
        super().do_once()

        self.r_pixels = np.zeros((self.r_height, self.r_width, 3), dtype=np.float32)
        self._ensure_group_caps(INIT_CAP)

        self.wobble_amplitude = max(1.0, WOBBLE_RATIO * self.r_width)
        self.color_hsv_values = [
            rgb_to_hsv_vect(self.low_color),
            rgb_to_hsv_vect(self.mid_color),
            rgb_to_hsv_vect(self.high_color),
        ]

        # Preallocate RGB scratch for hsv_to_rgb_vect (fixed cap by preference)
        max_particles_guess = max(1024, self.r_width * RGB_SCRATCH_FACTOR)
        self._rgb_scratch = np.empty((max_particles_guess, 3), dtype=np.float32)

        # Allocate / resize blur scratch (if needed)
        self._ensure_blur_buffers()

    def _ensure_blur_buffers(self):
        """Ensure blur scratch buffers are allocated for current size/blur."""
        if self.blur_amount <= 0:
            return
        r = self.blur_amount
        H, W = self.r_height, self.r_width
        wantH = max(H, H + 2 * r)
        wantW = max(W + 2 * r, W)
        if self._blur_padded is None or self._blur_padded.shape != (wantH, wantW):
            self._blur_padded = np.empty((wantH, wantW), dtype=np.float32)
            self._blur_cumsum = np.empty_like(self._blur_padded)

    def audio_data_updated(self, data):
        self.audio_pow = np.array(
            [
                self.audio.lows_power(),
                self.audio.mids_power(),
                self.audio.high_power(),
            ],
            dtype=np.float32,
        )

    def _compact_alive(self, p: ParticleGroup, n: int, alive: np.ndarray, new_age, new_y):
        """Compact alive particles to front; write updated age/y; return new count."""
        if not np.any(alive):
            return 0
        k = int(alive.sum())
        # stable front-compaction
        for f in ParticleGroup._fields:
            arr = getattr(p, f)
            arr[:k] = arr[:n][alive]
        p.age[:k] = new_age[alive]
        p.y[:k] = new_y[alive]
        return k

    def draw(self):
        self.r_pixels.fill(0)
        delta = self.passed

        # cache
        H = self.r_height
        W = self.r_width
        offsets = self._offsets
        abs_offsets = self._abs_offsets
        cap = self._rgb_scratch.shape[0] if self._rgb_scratch is not None else 1_000_000

        # resolution-aware spawn scaling (64x64 baseline)
        height_scale = (H / 64.0) ** DENSITY_EXPONENT

        for index, (group_name, power, (h_base, s_base, v_base)) in enumerate(
            zip(("low", "mid", "high"), self.audio_pow, self.color_hsv_values)
        ):
            p = self.particles[group_name]
            n = self._counts[group_name]

            # --- update & cull (in-place, compact alive) ---
            if n > 0:
                age = p.age[:n]
                life = p.lifespan[:n]
                vy = p.velocity_y[:n]
                y = p.y[:n]

                new_age = age + delta
                new_y = y - (H / vy) * delta
                alive = (new_age < life) & (new_y >= 0.0)

                n = self._compact_alive(p, n, alive, new_age, new_y)
                self._counts[group_name] = n

            # --- spawn (capacity-backed; drop or grow on overflow) ---
            self.spawn_accumulator[index] += (
                W * self.spawn_rate * delta * SPAWN_MODIFIER * height_scale
            )
            n_spawn = int(self.spawn_accumulator[index])
            self.spawn_accumulator[index] -= n_spawn

            if n_spawn > 0:
                if not self._grow_capacity(group_name, n_spawn):
                    # fixed cap: clip spawns to available space
                    free = max(0, self._caps[group_name] - n)
                    if free == 0:
                        n_spawn = 0
                    else:
                        if n_spawn > free:
                            n_spawn = free
                if n_spawn > 0:
                    s = slice(n, n + n_spawn)
                    p.x[s] = self._rng.integers(0, W, size=n_spawn, dtype=np.int32).astype(np.float32)
                    p.y[s] = H - 1
                    p.age[s] = 0.0
                    p.lifespan[s] = self._rng.uniform(MIN_LIFESPAN, MAX_LIFESPAN, size=n_spawn)
                    p.velocity_y[s] = 1.0 / (self.velocity * self._rng.uniform(MIN_VELOCITY_OFFSET, MAX_VELOCITY_OFFSET, size=n_spawn))
                    p.size[s] = self._rng.integers(1, 4, size=n_spawn).astype(np.float32)
                    p.wobble_phase[s] = self._rng.uniform(0.0, 2*np.pi, size=n_spawn)
                    n += n_spawn
                    self._counts[group_name] = n

            # --- render (chunked to fixed rgb_scratch cap) ---
            if n == 0:
                continue

            scaled_power = (power - 0.3) * self.intensity * 2.0
            wobble = self.wobble_amplitude * (1.0 + scaled_power * 2.0)
            scale = 1.0 + scaled_power

            for start in range(0, n, cap):
                end = min(start + cap, n)
                sl = slice(start, end)

                xs = p.x[sl]
                ys = p.y[sl]
                age = p.age[sl]
                life = p.lifespan[sl]
                size = p.size[sl]
                phase = p.wobble_phase[sl]

                # color over lifetime
                t = age / life
                hues = (h_base * (1.0 - t)) % 1.0
                sats = s_base * (1.0 - 0.5 * t)
                vals = v_base * (1.0 - t * t)

                # HSV -> RGB into preallocated scratch
                rgb = hsv_to_rgb_vect(hues, sats, vals, out=self._rgb_scratch[: end - start])

                # wobble & vertical scaling
                x_disp = xs + wobble * np.sin(t * 10.0 + phase)
                y_scaled = (H - ys) * scale
                y_render = H - y_scaled

                xi = np.round(x_disp).astype(np.int32)
                yi = np.round(y_render).astype(np.int32)

                in_bounds = (
                    (xi >= 0) & (xi < W) &
                    (yi >= 0) & (yi < H)
                )
                if not np.any(in_bounds):
                    continue

                xi = xi[in_bounds]
                yi = yi[in_bounds]
                rgb_in = rgb[in_bounds]
                size_in = size[in_bounds]

                # vectorized scatter across 7 offsets
                dx = xi[:, None] + offsets[None, :]          # (M,7)
                size_ok = (size_in[:, None] >= abs_offsets[None, :])
                valid = (dx >= 0) & (dx < W) & size_ok
                if np.any(valid):
                    dxv = dx[valid]
                    yv = np.repeat(yi, offsets.size)[valid.ravel()]
                    rgbv = np.repeat(rgb_in, offsets.size, axis=0)[valid.ravel()]
                    np.add.at(self.r_pixels, (yv, dxv), rgbv)

        # --- blur (scratch reuse, same math) ---
        if self.blur_amount > 0:
            r = self.blur_amount
            self._ensure_blur_buffers()
            for c in range(3):
                # horizontal
                pad = self._blur_padded[:H, : W + 2 * r]
                pad[:, :r] = self.r_pixels[:, :1, c]
                pad[:, r : r + W] = self.r_pixels[:, :, c]
                pad[:, r + W :] = self.r_pixels[:, -1:, c]

                cs = self._blur_cumsum[:H, : W + 2 * r]
                np.cumsum(pad, axis=1, out=cs)
                self.r_pixels[:, :, c] = (cs[:, 2 * r :] - cs[:, : -2 * r]) / (2 * r)

                # vertical
                pad = self._blur_padded[: H + 2 * r, :W]
                pad[:r, :] = self.r_pixels[:1, :, c]
                pad[r : r + H, :] = self.r_pixels[:, :, c]
                pad[r + H :, :] = self.r_pixels[-1:, :, c]

                cs = self._blur_cumsum[: H + 2 * r, :W]
                np.cumsum(pad, axis=0, out=cs)
                self.r_pixels[:, :, c] = (cs[2 * r :, :] - cs[: -2 * r, :]) / (2 * r)

        # finalize
        clamped = np.clip(self.r_pixels, 0, 255).astype(np.uint8)
        self.matrix = Image.fromarray(clamped, mode="RGB")
