import logging
import voluptuous as vol
import numpy as np
from PIL import Image
from ledfx.effects import Effect
from ledfx.effects.twod import Twod
from ledfx.color import parse_color, validate_color, hsv_to_rgb_vect, rgb_to_hsv_vect
_LOGGER = logging.getLogger(__name__)

MIN_VELOCITY_OFFSET = 0.5
MAX_VELOCITY_OFFSET = 1.2
MIN_LIFESPAN = 2.0
MAX_LIFESPAN = 4.0
WOBBLE_RATIO = 0.05


class Flame2d(Twod):
    NAME = "Flame"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("spawn_rate", description="Particles spawn rate", default=0.5):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),

            vol.Optional("velocity", description="Trips to top per second", default=0.3):
                vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
            
            vol.Optional("intensity", description="Application of the audio power input", default=0.5):
                vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),

            vol.Optional("blur_amount", description="Blur radius in pixels", default=2):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),

            vol.Optional(
                "low_band",
                description="low band flame",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "mid_band",
                description="mid band flame",
                default="#00FF00",
            ): validate_color,
            vol.Optional(
                "high_band",
                description="high band flame",
                default="#0000FF",
            ): validate_color,    
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.particles = None
        self.bar = 0
        self.audio_pow = np.zeros(3, dtype=np.float32)
        self.spawn_accumulator = np.zeros(3, dtype=np.float32)

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

    def do_once(self):
        super().do_once()

        if self.particles is None:
            self.r_pixels = np.zeros((self.r_height, self.r_width, 3), dtype=np.float32)
            self.particles = {}
            for group in ("low", "mid", "high"):
                self.particles[group] = {
                    "x": np.empty(0, dtype=np.float32),
                    "y": np.empty(0, dtype=np.float32),
                    "age": np.empty(0, dtype=np.float32),
                    "lifespan": np.empty(0, dtype=np.float32),
                    "velocity_y": np.empty(0, dtype=np.float32),
                    "size": np.empty(0, dtype=np.int32),
                    "wobble_phase": np.empty(0, dtype=np.float32),
                }
        self.wobble_amplitude = max(1.0, WOBBLE_RATIO * self.r_width)


    def audio_data_updated(self, data):
        self.audio_pow = np.array([
            self.audio.lows_power(),
            self.audio.mids_power(),
            self.audio.high_power()
        ], dtype=np.float32)

    def draw(self):
        self.r_pixels.fill(0)
        delta = self.passed

        for index, (group_name, color, power) in enumerate(zip(
            ("low", "mid", "high"),
            (self.low_color, self.mid_color, self.high_color),
            self.audio_pow
        )):
            p = self.particles[group_name]

            if p["x"].size > 0:
                p["age"] += delta
                p["y"] -= (self.r_height / p["velocity_y"]) * delta
                alive = (p["age"] < p["lifespan"]) & (p["y"] >= 0)
                for key in p:
                    p[key] = p[key][alive]
            
            # magic number 4 is hand tuned from observations
            # this should otherwise be time invariant and deal with different sizes, though not well
            self.spawn_accumulator[index] += self.r_width * self.spawn_rate * delta * 4
            n_spawn = int(self.spawn_accumulator[index])
            self.spawn_accumulator[index] -= n_spawn

            if n_spawn > 0:
                new_particles = {
                    "x": np.random.randint(0, self.r_width, size=n_spawn).astype(np.float32),
                    "y": np.full(n_spawn, self.r_height - 1, dtype=np.float32),
                    "age": np.zeros(n_spawn, dtype=np.float32),
                    "lifespan": np.random.uniform(MIN_LIFESPAN, MAX_LIFESPAN, size=n_spawn).astype(np.float32),
                    "velocity_y": 1.0 / (self.velocity * np.random.uniform(MIN_VELOCITY_OFFSET, MAX_VELOCITY_OFFSET, size=n_spawn)),
                    "size": np.random.randint(1, 4, size=n_spawn),
                    "wobble_phase": np.random.uniform(0, 2 * np.pi, size=n_spawn)
                }
                for key in p:
                    p[key] = np.concatenate([p[key], new_particles[key]])

            if p["x"].size > 0:
                age = p["age"]
                lifespan = p["lifespan"]
                x = p["x"]
                y = p["y"]
                size = p["size"]
                phase = p["wobble_phase"]

                h_base, s_base, v_base = rgb_to_hsv_vect(color)
                t = age / lifespan
                hues = (h_base - h_base * t) % 1.0
                sats = s_base * (1.0 - 0.5 * t)
                vals = v_base * (1.0 - t * t)

                rgb = hsv_to_rgb_vect(hues, sats, vals)

                scaled_power = (power - 0.3) * self.intensity * 2
                # Audio-modulated wobble
                amplified_wobble = self.wobble_amplitude * (1.0 + scaled_power * 2)
    
                x_disp = x + amplified_wobble * np.sin(t * 10 + phase)

                scale = 1.0 + scaled_power

                y_from_bottom = self.r_height - y
                y_scaled = y_from_bottom * scale
                y_render = self.r_height - y_scaled

                xi = np.round(x_disp).astype(int)
                yi = np.round(y_render).astype(int)

                in_bounds = (xi >= 0) & (xi < self.r_width) & (yi >= 0) & (yi < self.r_height)
                xi = xi[in_bounds]
                yi = yi[in_bounds]
                rgb_in = rgb[in_bounds]
                size_in = size[in_bounds]

                for offset in range(-3, 4):
                    mask = size_in >= abs(offset)
                    if np.any(mask):
                        dx = xi[mask] + offset
                        valid = (dx >= 0) & (dx < self.r_width)
                        np.add.at(self.r_pixels, (yi[mask][valid], dx[valid]), rgb_in[mask][valid])

        if self.blur_amount > 0:
            r = self.blur_amount
            for c in range(3):
                padded = np.pad(self.r_pixels[:, :, c], ((0, 0), (r, r)), mode='edge')
                cumsum = np.cumsum(padded, axis=1)
                self.r_pixels[:, :, c] = (cumsum[:, 2*r:] - cumsum[:, :-2*r]) / (2 * r)

                padded = np.pad(self.r_pixels[:, :, c], ((r, r), (0, 0)), mode='edge')
                cumsum = np.cumsum(padded, axis=0)
                self.r_pixels[:, :, c] = (cumsum[2*r:, :] - cumsum[:-2*r, :]) / (2 * r)

        clamped = np.clip(self.r_pixels, 0, 255).astype(np.uint8)
        self.matrix = Image.fromarray(clamped, mode="RGB")
