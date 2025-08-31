import logging
import time
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

# ---- Tunables ---------------------------------------------------------------
# Capacity policy for particle storage:
#   - AUTO_GROW=False: fixed-cap per group; extra spawns are dropped (fast, predictable)
#   - AUTO_GROW=True : capacity grows geometrically when needed (no drops)
AUTO_GROW = False
# Initial particle capacity per group (used as hard cap when AUTO_GROW=False)
INIT_CAP = 4096
# Rows to preallocate for HSV->RGB scratch buffer (r_width * this factor)
RGB_SCRATCH_FACTOR = 16
# Resolution-aware spawn scaling. 64x64 is the baseline:
#   DENSITY_EXPONENT = 0.0 -> no scaling (original behavior)
#   DENSITY_EXPONENT = 1.0 -> linear with height (per-pixel-ish density)
DENSITY_EXPONENT = 0.5
# Top-edge randomisation: particles get a personal cutoff up to this fraction of height.
# This breaks the perfectly flat top edge without extra allocations.
TOP_TRIM_FRAC = 0.40
INV_TWOPI = 1.0 / (2.0 * np.pi)

# Particle dynamics / visuals
MIN_VELOCITY_OFFSET = 0.5
MAX_VELOCITY_OFFSET = 1.2
MIN_LIFESPAN = 2.0
MAX_LIFESPAN = 4.0
WOBBLE_RATIO = 0.05
SPAWN_MODIFIER = 4.0

# Structure-of-Arrays for particle groups
ParticleGroup = namedtuple(
    "ParticleGroup",
    ["x", "y", "age", "lifespan", "velocity_y", "size", "wobble_phase"],
)


class Flame2d(Twod):
    """
    A 2D flame effect for LED matrices with audio-reactive wobble.

    Performance notes:
    - Capacity-backed particle arrays (SoA) per group (low/mid/high).
    - Chunked HSV->RGB using a preallocated scratch buffer.
    - Vectorized scatter-add across symmetric x-offsets.
    - Separable box blur using reusable scratch buffers.
    - Resolution-aware spawn scaling via DENSITY_EXPONENT.
    - If a group's base color is black (V==0 in HSV), we skip both spawning
      and rendering for that group (fast path). Particles for that group are
      effectively paused in memory for that frame.
    - Top-edge randomisation via TOP_TRIM_FRAC gives each particle a personal
      cutoff height, breaking a uniform top line without extra arrays.

    Visual notes:
    - Hue/value evolve over particle lifetime to create a flame gradient.
    - Audio power modulates horizontal wobble and vertical lift.
    """

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
        """
        Initialize internal state and performance helpers.
        """
        super().__init__(ledfx, config)

        # Particle storage (allocated in do_once)
        self.particles = None  # dict[str, ParticleGroup]
        self._counts = {"low": 0, "mid": 0, "high": 0}
        self._caps = {"low": 0, "mid": 0, "high": 0}

        # Audio powers (low/mid/high)
        self.audio_pow = np.zeros(3, dtype=np.float32)

        # Per-group fractional spawn accumulators
        self.spawn_accumulator = np.zeros(3, dtype=np.float32)

        # Debug tracking for particle counts
        self._debug_last_report = 0.0
        self._debug_report_interval = 1.0  # Report every 1 second

        # Perf helpers
        self._rng = np.random.default_rng()
        self._rgb_scratch = None  # preallocated (N,3) float32 buffer
        self._offsets = np.arange(
            -3, 4, dtype=np.int32
        )  # scatter kernel [-3..3]
        self._abs_offsets = np.abs(self._offsets)

        # Blur scratch buffers (allocated on-demand)
        self._blur_padded = None
        self._blur_cumsum = None

    def config_updated(self, config):
        """
        Pull configurable parameters and parse base band colors.
        """
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

    def _empty_cap(self, n: int) -> ParticleGroup:
        """
        Allocate empty particle arrays with capacity n.
        """
        return ParticleGroup(
            x=np.empty(n, np.float32),
            y=np.empty(n, np.float32),
            age=np.empty(n, np.float32),
            lifespan=np.empty(n, np.float32),
            velocity_y=np.empty(n, np.float32),
            size=np.empty(n, np.float32),
            wobble_phase=np.empty(n, np.float32),
        )

    def _ensure_group_caps(self, cap: int) -> None:
        """
        Ensure particle arrays for each group exist with at least 'cap' capacity.
        """
        if self.particles is None:
            self.particles = {
                "low": self._empty_cap(cap),
                "mid": self._empty_cap(cap),
                "high": self._empty_cap(cap),
            }
            self._caps = {"low": cap, "mid": cap, "high": cap}
            self._counts = {"low": 0, "mid": 0, "high": 0}

    def _grow_capacity(self, group: str, need: int) -> bool:
        """
        Grow capacity for a group if AUTO_GROW is enabled.
        Returns True if capacity is sufficient after the call, else False.
        """
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
        # Copy live front segment
        for f in ParticleGroup._fields:
            getattr(new, f)[:n] = getattr(old, f)[:n]
        self.particles[group] = new
        self._caps[group] = new_cap
        return True

    def do_once(self):
        """
        Allocate buffers that depend on matrix size and seed color conversions.
        """
        super().do_once()

        # Render target (float32 until final clip/cast)
        self.r_pixels = np.zeros(
            (self.r_height, self.r_width, 3), dtype=np.float32
        )

        # Particle capacity
        self._ensure_group_caps(INIT_CAP)

        # Audio wobble amplitude scales with width
        self.wobble_amplitude = max(1.0, WOBBLE_RATIO * self.r_width)

        # Base colors converted to HSV once (float32 0..1)
        self.color_hsv_values = [
            rgb_to_hsv_vect(self.low_color),
            rgb_to_hsv_vect(self.mid_color),
            rgb_to_hsv_vect(self.high_color),
        ]

        # Preallocate HSV->RGB scratch buffer; chunking uses this cap
        max_particles_guess = max(1024, self.r_width * RGB_SCRATCH_FACTOR)
        self._rgb_scratch = np.empty(
            (max_particles_guess, 3), dtype=np.float32
        )

        # Prepare blur scratch if needed
        self._ensure_blur_buffers()

    def _ensure_blur_buffers(self) -> None:
        """
        Ensure blur scratch buffers are allocated (and sized) for current radius and matrix.
        """
        if self.blur_amount <= 0:
            return
        r = self.blur_amount
        H, W = self.r_height, self.r_width
        wantH = max(H, H + 2 * r)
        wantW = max(W + 2 * r, W)
        if self._blur_padded is None or self._blur_padded.shape != (
            wantH,
            wantW,
        ):
            self._blur_padded = np.empty((wantH, wantW), dtype=np.float32)
            self._blur_cumsum = np.empty_like(self._blur_padded)

    def audio_data_updated(self, data):
        """
        Pull latest band powers into a compact float32 vector (low, mid, high).
        """
        self.audio_pow = np.array(
            [
                self.audio.lows_power(),
                self.audio.mids_power(),
                self.audio.high_power(),
            ],
            dtype=np.float32,
        )

    def _compact_alive(
        self,
        p: ParticleGroup,
        n: int,
        alive: np.ndarray,
        new_age: np.ndarray,
        new_y: np.ndarray,
    ) -> int:
        """
        Compact alive particles to the front in-place and write updated age/y.

        Returns
        -------
        int
            New live count after compaction.
        """
        if not np.any(alive):
            return 0
        k = int(alive.sum())
        # Stable compaction of all fields
        for f in ParticleGroup._fields:
            arr = getattr(p, f)
            arr[:k] = arr[:n][alive]
        p.age[:k] = new_age[alive]
        p.y[:k] = new_y[alive]
        return k

    def draw(self):
        """
        Render one frame:
        - Update & cull existing particles.
        - Spawn new particles (capacity-backed).
        - Convert HSV->RGB in chunks and composite with vectorized scatter.
        - Optional separable blur.
        - Skip both spawn and render for any group whose base color is black.
        - Apply per-particle top-edge randomisation for a natural flame top.
        """
        self.r_pixels.fill(0)
        delta = self.passed

        # Cache common locals
        H = self.r_height
        W = self.r_width
        offsets = self._offsets
        abs_offsets = self._abs_offsets
        cap = (
            self._rgb_scratch.shape[0]
            if self._rgb_scratch is not None
            else 1_000_000
        )

        # Resolution-aware spawn scaling (64x64 baseline)
        height_scale = (H / 64.0) ** DENSITY_EXPONENT

        for index, (group_name, power, (h_base, s_base, v_base)) in enumerate(
            zip(("low", "mid", "high"), self.audio_pow, self.color_hsv_values)
        ):
            # Fast path: if base color is black, skip update/spawn/render entirely.
            # NOTE: This will "pause" that group's particles; they will resume
            #       motion/rendering if the color becomes non-black later.
            if v_base == 0.0:
                continue

            p = self.particles[group_name]
            n = self._counts[group_name]

            # --- Update & cull (compact alive to front) -----------------------
            if n > 0:
                age = p.age[:n]
                life = p.lifespan[:n]
                vy = p.velocity_y[:n]
                y = p.y[:n]

                new_age = age + delta
                new_y = y - (H / vy) * delta

                # Per-particle cutoff height derived from wobble_phase:
                # wobble_phase ∈ [0, 2π) -> uniform [0,1) via *INV_TWOPI,
                # scaled by (H * TOP_TRIM_FRAC) -> cutoff in pixels.
                cutoff = p.wobble_phase[:n] * INV_TWOPI * (H * TOP_TRIM_FRAC)

                alive = (new_age < life) & (new_y >= cutoff)

                n = self._compact_alive(p, n, alive, new_age, new_y)
                self._counts[group_name] = n

            # --- Spawn (capacity-backed; drop or grow) ------------------------
            self.spawn_accumulator[index] += (
                W * self.spawn_rate * delta * SPAWN_MODIFIER * height_scale
            )
            n_spawn = int(self.spawn_accumulator[index])
            self.spawn_accumulator[index] -= n_spawn

            if n_spawn > 0:
                if not self._grow_capacity(group_name, n_spawn):
                    # Fixed-cap policy: clip to available space
                    free = max(0, self._caps[group_name] - n)
                    if free == 0:
                        n_spawn = 0
                    elif n_spawn > free:
                        n_spawn = free

                if n_spawn > 0:
                    s = slice(n, n + n_spawn)
                    p.x[s] = self._rng.integers(
                        0, W, size=n_spawn, dtype=np.int32
                    ).astype(np.float32)
                    p.y[s] = H - 1
                    p.age[s] = 0.0
                    p.lifespan[s] = self._rng.uniform(
                        MIN_LIFESPAN, MAX_LIFESPAN, size=n_spawn
                    )
                    p.velocity_y[s] = 1.0 / (
                        self.velocity
                        * self._rng.uniform(
                            MIN_VELOCITY_OFFSET,
                            MAX_VELOCITY_OFFSET,
                            size=n_spawn,
                        )
                    )
                    p.size[s] = self._rng.integers(1, 4, size=n_spawn).astype(
                        np.float32
                    )
                    p.wobble_phase[s] = self._rng.uniform(
                        0.0, 2 * np.pi, size=n_spawn
                    )
                    n += n_spawn
                    self._counts[group_name] = n

            # --- Render (chunked; vectorized scatter) -------------------------
            if n == 0:
                continue

            # Audio-reactive wobble/vertical scale
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

                # Lifetime color ramp (HSV)
                t = age / life
                hues = (h_base * (1.0 - t)) % 1.0
                sats = s_base * (1.0 - 0.5 * t)
                vals = v_base * (1.0 - t * t)

                # HSV -> RGB into preallocated scratch
                rgb = hsv_to_rgb_vect(
                    hues, sats, vals, out=self._rgb_scratch[: end - start]
                )

                # Wobble + vertical lift
                x_disp = xs + wobble * np.sin(t * 10.0 + phase)
                y_scaled = (H - ys) * scale
                y_render = H - y_scaled

                xi = np.round(x_disp).astype(np.int32)
                yi = np.round(y_render).astype(np.int32)

                in_bounds = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
                if not np.any(in_bounds):
                    continue

                xi = xi[in_bounds]
                yi = yi[in_bounds]
                rgb_in = rgb[in_bounds]
                size_in = size[in_bounds]

                # Vectorized scatter across [-3..3] offsets
                dx = xi[:, None] + offsets[None, :]  # (M,7)
                size_ok = size_in[:, None] >= abs_offsets[None, :]
                valid = (dx >= 0) & (dx < W) & size_ok
                if np.any(valid):
                    dxv = dx[valid]
                    yv = np.repeat(yi, offsets.size)[valid.ravel()]
                    rgbv = np.repeat(rgb_in, offsets.size, axis=0)[
                        valid.ravel()
                    ]
                    np.add.at(self.r_pixels, (yv, dxv), rgbv)

        # --- Blur (separable; scratch reuse) ---------------------------------
        if self.blur_amount > 0:
            r = self.blur_amount
            self._ensure_blur_buffers()
            for c in range(3):
                # Horizontal pass
                pad = self._blur_padded[:H, : W + 2 * r]
                pad[:, :r] = self.r_pixels[:, :1, c]
                pad[:, r : r + W] = self.r_pixels[:, :, c]
                pad[:, r + W :] = self.r_pixels[:, -1:, c]

                cs = self._blur_cumsum[:H, : W + 2 * r]
                np.cumsum(pad, axis=1, out=cs)
                self.r_pixels[:, :, c] = (cs[:, 2 * r :] - cs[:, : -2 * r]) / (
                    2 * r
                )

                # Vertical pass
                pad = self._blur_padded[: H + 2 * r, :W]
                pad[:r, :] = self.r_pixels[:1, :, c]
                pad[r : r + H, :] = self.r_pixels[:, :, c]
                pad[r + H :, :] = self.r_pixels[-1:, :, c]

                cs = self._blur_cumsum[: H + 2 * r, :W]
                np.cumsum(pad, axis=0, out=cs)
                self.r_pixels[:, :, c] = (cs[2 * r :, :] - cs[: -2 * r, :]) / (
                    2 * r
                )

        # --- Debug particle count reporting (every 1 second) ----------------
        current_time = time.time()
        if current_time - self._debug_last_report >= self._debug_report_interval:
            total_particles = sum(self._counts.values())
            _LOGGER.debug(
                f"Flame2D particles - Low: {self._counts['low']}, "
                f"Mid: {self._counts['mid']}, High: {self._counts['high']}, "
                f"Total: {total_particles}"
            )
            self._debug_last_report = current_time

        # Finalize (clip to [0,255] and cast to uint8)
        clamped = np.clip(self.r_pixels, 0, 255).astype(np.uint8)
        self.matrix = Image.fromarray(clamped, mode="RGB")
