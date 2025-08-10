import logging

import numpy as np
import vnoise
import voluptuous as vol
from PIL import Image

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Soap2D(Twod, GradientEffect):
    NAME = "Soap"
    CATEGORY = "Matrix"
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "gradient_roll",
        "test",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "smoothness",
                description="EMA of noise field [0..1]",
                default=0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
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
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # vnoise
        self._vn = None
        # noise state
        self._phase = None              # x,y drift (2D)
        self._noise = None              # (H,W) float32 [0..1]
        # persistent pixels
        self._pixels_prev = None  # (H,W,3) float32 0..255
        # dims
        self._h = 0
        self._w = 0
        # tuning
        self._freq = 3.0
        self._octaves = 1               # faster, close to noise2d.py behavior

        self._need_seed = True
        self.lows_impulse = 0.0

        # cached ramps (per resolution)
        self._x_ramp = None             # (W,) float32 0..W-1
        self._y_ramp = None             # (H,) float32 0..H-1
        # cached indices for smear (per resolution)
        self._j_w  = None               # (1,W) int32
        self._j_h  = None               # (1,H) int32

    def config_updated(self, config):
        super().config_updated(config)
        self.smooth = self._config["smoothness"]
        self.density = self._config["density"]
        self.speed = self._config["speed"]
        self.intensity = self._config["intensity"]


    # ---------- lifecycle ----------

    def audio_data_updated(self, data):
        # simple bass injection
        self.lows_impulse = self.audio.lows_power() * 3.0

    def do_once(self):
        super().do_once()
        self._ensure_buffers(force=True)
        if self._vn is None:
            self._vn = vnoise.Noise()
        if self._phase is None:
            r = np.random.RandomState()
            self._phase = np.array([r.rand()*256, r.rand()*256], dtype=np.float32)

    def _ensure_buffers(self, force: bool = False):
        H, W = int(self.r_height), int(self.r_width)
        if H <= 0 or W <= 0:
            return
        if not force and H == self._h and W == self._w:
            return

        self._h, self._w = H, W
        self._noise = np.zeros((H, W), dtype=np.float32)
        self._pixels_prev = np.zeros((H, W, 3), dtype=np.float32)

        # cache ramps & index bases once per resolution
        self._x_ramp = np.arange(W, dtype=np.float32)
        self._y_ramp = np.arange(H, dtype=np.float32)
        self._j_w    = np.arange(W, dtype=np.int32)[None, :]  # (1,W)
        self._j_h    = np.arange(H, dtype=np.int32)[None, :]  # (1,H)

        self._need_seed = True

    # ---------- noise ----------

    def _gen_noise_field01(self, freq: float, octaves: int) -> np.ndarray:
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

        n2 = self._vn.noise2(y, x, grid_mode=True, octaves=octaves).astype(np.float32)
        return (n2 + 1.0) * 0.5

    # ---------- smear (WLED-style: pixels for in-bounds, palette for OOB) ----------

    def _smear_axis_signed_oob(self,
                               pixels_prev: np.ndarray,
                               palette_rgb: np.ndarray,
                               amount: np.ndarray,
                               axis: int) -> np.ndarray:
        """
        Smear along one axis with signed shifts, vectorized with take_along_axis.
        In-bounds taps come from `pixels_prev`; OOB taps come from `palette_rgb`.
        axis: 1 -> smear across X (rows), 0 -> smear across Y (cols)
        returns new (H,W,3) float32
        """
        H, W, _ = pixels_prev.shape

        if axis == 1:
            N = W
            j = self._j_w                      # (1,W)
            L = H
        else:
            N = H
            j = self._j_h                      # (1,H)
            L = W

        # per-line signed shifts
        sgn  = np.sign(amount).astype(np.int32)[:, None]        # (L,1)
        mag  = np.abs(amount)[:, None]                           # (L,1)
        d_i  = np.floor(mag).astype(np.int32)                    # (L,1)
        frac = (mag - d_i).astype(np.float32)                    # (L,1)
        eased = frac * frac * (3.0 - 2.0 * frac)                 # (L,1) smoothstep
        wB = eased[:, :, None]                                   # (L,N,1) for broadcast in blend

        zD = j + sgn * d_i                                       # (L,N)
        zF = zD + sgn                                            # (L,N)

        inA = (zD >= 0) & (zD < N)
        inB = (zF >= 0) & (zF < N)

        a_idx = np.clip(zD, 0, N - 1).astype(np.int32)          # (L,N)
        b_idx = np.clip(zF, 0, N - 1).astype(np.int32)          # (L,N)

        if axis == 1:
            # Gather along columns (axis=1), shapes -> (H,W,3)
            A_src = np.take_along_axis(pixels_prev, a_idx[:, :, None], axis=1)
            B_src = np.take_along_axis(pixels_prev, b_idx[:, :, None], axis=1)
            A_pal = np.take_along_axis(palette_rgb, a_idx[:, :, None], axis=1)
            B_pal = np.take_along_axis(palette_rgb, b_idx[:, :, None], axis=1)
            inA3, inB3 = inA[:, :, None], inB[:, :, None]
            A = np.where(inA3, A_src, A_pal)
            B = np.where(inB3, B_src, B_pal)
            out = A * (1.0 - wB) + B * wB
        else:
            # Work on transposed views to gather along rows cleanly:
            # (W,H,3) so we can index along axis=1 with (W,H,1) indices
            pixT = pixels_prev.transpose(1, 0, 2)
            palT = palette_rgb.transpose(1, 0, 2)
            A_src = np.take_along_axis(pixT, a_idx[:, :, None], axis=1)
            B_src = np.take_along_axis(pixT, b_idx[:, :, None], axis=1)
            A_pal = np.take_along_axis(palT, a_idx[:, :, None], axis=1)
            B_pal = np.take_along_axis(palT, b_idx[:, :, None], axis=1)
            inA3, inB3 = inA[:, :, None], inB[:, :, None]
            A = np.where(inA3, A_src, A_pal)
            B = np.where(inB3, B_src, B_pal)
            outT = A * (1.0 - wB) + B * wB                      # (W,H,3)
            out = outT.transpose(1, 0, 2)                       # back to (H,W,3)

        return out

    # ---------- render ----------

    def draw(self):
        self._ensure_buffers()
        H, W = self._h, self._w
        if H == 0 or W == 0:
            return

        # audio-modulated speed (free-run if intensity==0)
        audio_speed = self.speed if self.intensity == 0 else (self.speed * self.lows_impulse * self.intensity)

        # time-invariant drift using self.passed; gentle curve at low end
        move = (audio_speed**2) * 0.5 * float(self.passed or 0.0)
        self._phase += move

        # noise + EMA smoothing
        new_field = self._gen_noise_field01(self._freq, self._octaves)
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
