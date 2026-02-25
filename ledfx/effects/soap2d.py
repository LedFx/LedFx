import logging

import numpy as np
import voluptuous as vol
from PIL import Image
from pyfastnoiselite import pyfastnoiselite as fnl

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Soap2D(Twod, GradientEffect):
    NAME = "Soap"
    CATEGORY = "Matrix"
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "background_brightness",
        "background_mode",
        "gradient_roll",
        "test",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "density", description="Smear amplitude [0..1]", default=0.5
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "speed",
                description="Motion speed (time-invariant) [0..1]",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "intensity",
                description="Audio injection to speed [0..2] 0 = free run",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the audio impulse",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # noise library
        self._fnl = None  # fastnoiselite instance
        # noise state
        self._phase = None  # x,y drift (2D)
        self._noise = None  # (H,W) float32 [0..1]
        # persistent pixels
        self._pixels_prev = None  # (H,W,3) float32 0..255
        # dims
        self._h = 0
        self._w = 0
        # tuning
        self._freq = 3.0

        self._need_seed = True
        self.impulse = 0.0

        # cached ramps (per resolution)
        self._x_ramp = None  # (W,) float32 0..W-1
        self._y_ramp = None  # (H,) float32 0..H-1
        # cached indices for smear (per resolution)
        self._j_w = None  # (1,W) int32
        self._j_h = None  # (1,H) int32

    def config_updated(self, config):
        super().config_updated(config)
        self.smooth = 0.5  # removed slider, not worth it
        self.density = self._config["density"]
        self.speed = self._config["speed"]
        self.intensity = self._config["intensity"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]

    # ---------- lifecycle ----------

    def audio_data_updated(self, data):
        # simple bass injection
        self.impulse = getattr(data, self.power_func)() * 6.0

    def do_once(self):
        super().do_once()
        # Ensure buffers exist / are sized; do not force a reset here
        resized = self._ensure_buffers()

        # Track whether we initialized these now so we only reseed when needed
        noise_was_none = False
        phase_was_none = self._phase is None

        # Initialize the noise library
        if self._fnl is None:
            self._fnl = fnl.FastNoiseLite()
            self._fnl.noise_type = fnl.NoiseType.NoiseType_OpenSimplex2
            # Lower frequency for Soap due to additional freq scaling (self._freq=3.0)
            self._fnl.frequency = 0.3
            noise_was_none = True

        if phase_was_none:
            r = np.random.RandomState()
            self._phase = np.array(
                [r.rand() * 256, r.rand() * 256], dtype=np.float32
            )

        # Only request seeding if buffers were created/resized or we just initialized noise/phase
        if resized or noise_was_none or phase_was_none:
            self._need_seed = True

    def _ensure_buffers(self, force: bool = False) -> bool:
        H, W = int(self.r_height), int(self.r_width)
        if H <= 0 or W <= 0:
            return False
        if not force and H == self._h and W == self._w:
            return False

        resized = (H != self._h) or (W != self._w)
        self._h, self._w = H, W
        self._noise = np.zeros((H, W), dtype=np.float32)
        self._pixels_prev = np.zeros((H, W, 3), dtype=np.float32)

        # cache ramps & index bases once per resolution
        self._x_ramp = np.arange(W, dtype=np.float32)
        self._y_ramp = np.arange(H, dtype=np.float32)
        self._j_w = np.arange(W, dtype=np.int32)[None, :]  # (1,W)
        self._j_h = np.arange(H, dtype=np.int32)[None, :]  # (1,H)

        self._need_seed = True
        return resized

    # ---------- noise ----------

    def _gen_noise_field01(self, freq: float) -> np.ndarray:
        """
        Generate (H,W) noise in [0,1] using cached 1D ramps (no per-frame linspace alloc).
        2D noise; motion from drifting x/y.
        """
        H, W = self._h, self._w
        span_x = freq * 2.0
        span_y = freq * 2.0

        step_x = span_x / max(W - 1, 1)
        step_y = span_y / max(H - 1, 1)

        x0 = self._phase[0] - span_x * 0.5
        y0 = self._phase[1] - span_y * 0.5

        x = x0 + step_x * self._x_ramp
        y = y0 + step_y * self._y_ramp

        # FastNoiseLite uses gen_from_coords for vectorized generation
        # Create meshgrid for 2D coordinates
        x_grid, y_grid = np.meshgrid(x, y, indexing="xy")
        # Flatten coordinates
        x_flat = x_grid.flatten()
        y_flat = y_grid.flatten()
        # Stack as rows: [all_x, all_y] with shape (2, N)
        coords = np.stack([x_flat, y_flat], axis=0).astype(np.float32)

        # Generate noise for all points at once (vectorized)
        noise_flat = self._fnl.gen_from_coords(coords)

        # Reshape back to 2D array (H, W)
        n2 = noise_flat.reshape(H, W).astype(np.float32)

        return (n2 + 1.0) * 0.5

    # ---------- smear (WLED-style: pixels for in-bounds, palette for OOB) ----------

    def _smear_axis_signed_oob(
        self,
        pixels_prev: np.ndarray,
        palette_rgb: np.ndarray,
        amount: np.ndarray,
        axis: int,
    ) -> np.ndarray:
        """
        Optimized smear using direct indexing instead of take_along_axis.
        In-bounds taps come from `pixels_prev`; OOB taps come from `palette_rgb`.
        axis: 1 -> smear across X (rows), 0 -> smear across Y (cols)
        returns new (H,W,3) float32
        """
        H, W, _ = pixels_prev.shape

        # Pre-compute shift parameters
        sgn = np.sign(amount).astype(np.int32)
        mag = np.abs(amount)
        d_i = np.floor(mag).astype(np.int32)
        frac = (mag - d_i).astype(np.float32)
        # Smoothstep easing
        wB = frac * frac * (3.0 - 2.0 * frac)

        if axis == 1:
            # Smear across X (horizontal)
            # Create index arrays: rows stay fixed, columns shift
            row_idx = np.arange(H)[:, None]  # (H, 1)
            col_base = np.arange(W)[None, :]  # (1, W)

            # Calculate shifted indices
            zD = col_base + sgn[:, None] * d_i[:, None]
            zF = zD + sgn[:, None]

            # Clamp indices and check bounds
            a_idx = np.clip(zD, 0, W - 1)
            b_idx = np.clip(zF, 0, W - 1)
            inA = (zD >= 0) & (zD < W)
            inB = (zF >= 0) & (zF < W)

            # Pre-allocate output
            out = np.empty((H, W, 3), dtype=np.float32)

            # Process each color channel
            for c in range(3):
                # Gather pixel values using fancy indexing
                A_pix = pixels_prev[row_idx, a_idx, c]
                B_pix = pixels_prev[row_idx, b_idx, c]
                A_pal = palette_rgb[row_idx, a_idx, c]
                B_pal = palette_rgb[row_idx, b_idx, c]

                # Blend based on bounds (faster to compute per-channel)
                A = np.where(inA, A_pix, A_pal)
                B = np.where(inB, B_pix, B_pal)
                out[:, :, c] = A * (1.0 - wB[:, None]) + B * wB[:, None]
        else:
            # Smear across Y (vertical)
            col_idx = np.arange(W)[None, :]  # (1, W)
            row_base = np.arange(H)[:, None]  # (H, 1)

            # Calculate shifted indices
            zD = row_base + sgn[None, :] * d_i[None, :]
            zF = zD + sgn[None, :]

            # Clamp indices and check bounds
            a_idx = np.clip(zD, 0, H - 1)
            b_idx = np.clip(zF, 0, H - 1)
            inA = (zD >= 0) & (zD < H)
            inB = (zF >= 0) & (zF < H)

            # Pre-allocate output
            out = np.empty((H, W, 3), dtype=np.float32)

            # Process each color channel
            for c in range(3):
                # Gather pixel values using fancy indexing
                A_pix = pixels_prev[a_idx, col_idx, c]
                B_pix = pixels_prev[b_idx, col_idx, c]
                A_pal = palette_rgb[a_idx, col_idx, c]
                B_pal = palette_rgb[b_idx, col_idx, c]

                # Blend based on bounds
                A = np.where(inA, A_pix, A_pal)
                B = np.where(inB, B_pix, B_pal)
                out[:, :, c] = A * (1.0 - wB[None, :]) + B * wB[None, :]

        return out

    # ---------- render ----------

    def draw(self):
        self._ensure_buffers()
        H, W = self._h, self._w
        if H == 0 or W == 0:
            return

        # audio-modulated speed (free-run if intensity==0)
        audio_speed = (
            self.speed
            if self.intensity == 0
            else (self.speed * self.impulse * self.intensity)
        )

        # time-invariant drift using self.passed; gentle curve at low end
        move = (audio_speed**2) * 0.5 * float(self.passed or 0.0)
        self._phase += move

        # noise + EMA smoothing
        new_field = self._gen_noise_field01(self._freq)
        self._noise = self._noise * self.smooth + new_field * (
            1.0 - self.smooth
        )

        # palette wrap like WLED (~3x) to use more of the gradient
        pal_idx = np.mod((1.0 - self._noise) * 3.0, 1.0)
        palette_rgb = self.get_gradient_color_vectorized2d(pal_idx).astype(
            np.float32
        )

        # seed persistent pixels once from palette so motion has history
        if self._need_seed:
            self._pixels_prev[...] = palette_rgb
            self._need_seed = False

        # smear amplitude: base ~(len-8)/8 scaled by self.density 0..1 -> 1..8×
        amp_factor = 1.0 + 7.0 * self.density
        base_amp_x = max(1.0, (W - 8) / 8.0) * amp_factor
        base_amp_y = max(1.0, (H - 8) / 8.0) * amp_factor

        # per-line signed shifts from first sample of each line (WLED style)
        amt_rows = (self._noise[:, 0] - 0.5) * base_amp_x  # (H,)
        amt_cols = (self._noise[0, :] - 0.5) * base_amp_y  # (W,)

        # smear rows then columns, using previous pixels as in-bounds taps,
        # and current palette as OOB taps (matches WLED soapPixels)
        after_rows = self._smear_axis_signed_oob(
            self._pixels_prev, palette_rgb, amt_rows, axis=1
        )
        out_frame = self._smear_axis_signed_oob(
            after_rows, palette_rgb, amt_cols, axis=0
        )

        # store for next frame (persistence)
        self._pixels_prev[...] = out_frame

        # hand back an image
        self.matrix = Image.fromarray(
            np.clip(out_frame, 0, 255).astype(np.uint8), "RGB"
        )
