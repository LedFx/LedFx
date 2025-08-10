import logging
import numpy as np
import voluptuous as vol
import vnoise
from PIL import Image

from ledfx.effects.twod import Twod
from ledfx.effects.gradient import GradientEffect

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
            vol.Optional("smoothness", description="EMA of noise field [0..1]", default=0.8):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional("density", description="Smear amplitude [0..1]", default=0.5):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional("speed", description="Motion speed (time-invariant) [0..1]", default=0.5):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional("intensity", description="Audio injection to speed [0..2] 0 = free run", default=1.0):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # vnoise
        self._vn = None
        # noise state
        self._phase = None              # x,y,z drift
        self._noise = None              # (H,W) float32 [0..1]
        # persistent pixels
        self._pixels_prev = None        # (H,W,3) float32 0..255
        # dims
        self._h = 0
        self._w = 0
        # tuning
        self._freq = 3.0                # spatial detail
        self._octaves = 2               # mild fractal detail

        self._need_seed = True
        self.lows_impulse = 0.0

    def config_updated(self, config):
        super().config_updated(config)
        self.smooth = self._config["smoothness"]
        self.density = self._config["density"]
        self.speed   = self._config["speed"]
        self.intensity = self._config["intensity"]
    # ---------- lifecycle ----------

    def audio_data_updated(self, data):
        self.lows_impulse = self.audio.lows_power() * 3

    def do_once(self):
        super().do_once()
        self._ensure_buffers(force=True)
        if self._vn is None:
            self._vn = vnoise.Noise()
        if self._phase is None:
            r = np.random.RandomState()
            self._phase = np.array([r.rand()*256, r.rand()*256, r.rand()*256], dtype=np.float32)

    def _ensure_buffers(self, force: bool = False):
        H, W = int(self.r_height), int(self.r_width)
        if H <= 0 or W <= 0:
            return
        if not force and H == self._h and W == self._w:
            return

        self._h, self._w = H, W
        self._noise = np.zeros((H, W), dtype=np.float32)
        self._pixels_prev = np.zeros((H, W, 3), dtype=np.float32)
        self._need_seed = True

    # ---------- noise ----------

    def _gen_noise_field01(self, freq: float, octaves: int) -> np.ndarray:
        """
        Generate (H,W) noise in [0,1] using 1D axes + grid_mode=True (no huge broadcast).
        """
        H, W = self._h, self._w
        span_x = freq * 2.0
        span_y = freq * 2.0

        x0 = self._phase[0] - span_x * 0.5
        y0 = self._phase[1] - span_y * 0.5

        x = np.linspace(x0, x0 + span_x, W, dtype=np.float32)
        y = np.linspace(y0, y0 + span_y, H, dtype=np.float32)
        z = np.array([self._phase[2]], dtype=np.float32)

        # (H, W, 1) in [-1,1]
        n = self._vn.noise3(y, x, z, grid_mode=True, octaves=octaves)
        n2 = n[..., 0].astype(np.float32)
        return (n2 + 1.0) * 0.5

    # ---------- smear (WLED-style: pixels for in-bounds, palette for OOB) ----------

    @staticmethod
    def _smear_axis_signed_oob(pixels_prev: np.ndarray,
                               palette_rgb: np.ndarray,
                               amount: np.ndarray,
                               axis: int) -> np.ndarray:
        """
        Smear along one axis with signed shifts.
        In-bounds taps come from `pixels_prev`; OOB taps come from `palette_rgb`.
        pixels_prev: (H,W,3) float32
        palette_rgb: (H,W,3) float32
        amount: per-line signed shift in pixels; shape (H,) if axis=1 else (W,)
        axis: 1 -> smear across X (rows), 0 -> smear across Y (cols)
        returns new (H,W,3) float32
        """
        H, W, _ = pixels_prev.shape
        if axis == 1:
            L, N = H, W
            j = np.arange(W, dtype=np.int32)[None, :]             # (1,N)
        else:
            L, N = W, H
            j = np.arange(H, dtype=np.int32)[None, :]

        sgn = np.sign(amount).astype(np.int32)[:, None]           # (L,1)
        mag = np.abs(amount)[:, None]                              # (L,1)
        d_i = np.floor(mag).astype(np.int32)                       # (L,1)
        frac = (mag - d_i).astype(np.float32)                      # (L,1)
        eased = frac * frac * (3.0 - 2.0 * frac)                   # smoothstep

        zD = j + sgn * d_i                                         # (L,N)
        zF = zD + sgn                                              # (L,N)

        inA = (zD >= 0) & (zD < N)
        inB = (zF >= 0) & (zF < N)

        a_idx = np.clip(zD, 0, N - 1).astype(np.int32)
        b_idx = np.clip(zF, 0, N - 1).astype(np.int32)

        if axis == 1:
            rows = np.arange(H, dtype=np.int32)[:, None]
            A = palette_rgb[rows, a_idx].copy()
            B = palette_rgb[rows, b_idx].copy()
            A[inA] = pixels_prev[rows, a_idx][inA]
            B[inB] = pixels_prev[rows, b_idx][inB]
            wB = eased[:, :, None]                                 # (H,N,1)
            out = A * (1.0 - wB) + B * wB
        else:
            cols = np.arange(W, dtype=np.int32)[:, None]
            # transpose views for column access
            pixT = pixels_prev.transpose(1, 0, 2)                  # (W,H,3)
            palT = palette_rgb.transpose(1, 0, 2)                  # (W,H,3)
            A = palT[cols, a_idx].copy()
            B = palT[cols, b_idx].copy()
            A[inA] = pixT[cols, a_idx][inA]
            B[inB] = pixT[cols, b_idx][inB]
            wB = eased[:, :, None]                                 # (W,H,1)
            outT = A * (1.0 - wB) + B * wB
            out = outT.transpose(1, 0, 2)                          # back to (H,W,3)

        return out

    # ---------- render ----------

    def draw(self):
        self._ensure_buffers()
        H, W = self._h, self._w
        if H == 0 or W == 0:
            return

        if self.intensity == 0:
            audio_speed = self.speed
        else:
            audio_speed = self.speed * self.lows_impulse * self.intensity

        # time-invariant drift using self.passed; gentle curve at low end
        move = (audio_speed ** 2) * 0.5 * float(self.passed or 0.0)
        self._phase += move

        # noise + EMA smoothing
        new_field = self._gen_noise_field01(self._freq, self._octaves)
        self._noise = self._noise * self.smooth + new_field * (1.0 - self.smooth)

        # palette wrap like WLED (~3x) to use more of the gradient
        pal_idx = np.mod((1.0 - self._noise) * 3.0, 1.0)
        palette_rgb = self.get_gradient_color_vectorized2d(pal_idx).astype(np.float32)

        # seed persistent pixels once from palette so motion has history
        if self._need_seed:
            self._pixels_prev[...] = palette_rgb
            self._need_seed = False

        # smear amplitude: base ~(len-8)/8 scaled by self.density 0..1 -> 1..8×
        amp_factor = 1.0 + 7.0 * self.density
        base_amp_x = max(1.0, (W - 8) / 8.0) * amp_factor
        base_amp_y = max(1.0, (H - 8) / 8.0) * amp_factor

        # per-line signed shifts from first sample of each line (WLED style)
        amt_rows = (self._noise[:, 0] - 0.5) * base_amp_x          # (H,)
        amt_cols = (self._noise[0, :] - 0.5) * base_amp_y          # (W,)

        # smear rows then columns, using previous pixels as in-bounds taps,
        # and current palette as OOB taps (matches WLED soapPixels)
        after_rows = self._smear_axis_signed_oob(self._pixels_prev, palette_rgb, amt_rows, axis=1)
        out_frame  = self._smear_axis_signed_oob(after_rows,       palette_rgb, amt_cols, axis=0)

        # store for next frame (persistence)
        self._pixels_prev[...] = out_frame

        # hand back an image
        self.matrix = Image.fromarray(np.clip(out_frame, 0, 255).astype(np.uint8), "RGB")
