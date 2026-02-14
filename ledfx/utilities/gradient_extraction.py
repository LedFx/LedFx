"""
Gradient extraction utilities for LedFx.

Extracts LED-optimized color gradients from images (album art, user uploads).
Produces multiple gradient variants optimized for RGB LED hardware (WS2812, HUB75).
"""

import colorsys
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import PIL.Image as Image

_LOGGER = logging.getLogger(__name__)

# LED correction parameters
LED_SAFE_CONFIG = {
    "max_value": 0.85,  # Cap brightness at 85%
    "max_saturation": 0.90,  # Reduce saturation to 90%
    "gamma": 2.2,  # LED-appropriate gamma
    "white_threshold": 0.15,  # Detect near-white (low saturation)
    "white_replacement": "#F5F5F5",  # WhiteSmoke for near-white colors
}

LED_PUNCHY_CONFIG = {
    "max_value": 0.95,  # Higher brightness
    "max_saturation": 1.0,  # Full saturation
    "gamma": 2.2,  # Same gamma
    "white_threshold": 0.15,
    "white_replacement": "#FFFFFF",  # Pure white for punchy variant
}

# Color deduplication parameters
COLOR_DISTANCE_THRESHOLD = 0.20  # HSV distance threshold (0.0-1.0)
DEDUP_MIN_COLORS = 3  # Minimum colors to keep after deduplication
WHITE_REPLACE_MIN_V = (
    0.95  # was effectively 0.85 in the condition; raises the bar a lot
)
# Hue is weighted more heavily as it's most perceptually significant
# Saturation and Value differences are less critical for LED gradients

# === Background cluster detection (minimal additions) =========================
# Treat background as a cluster: dark and/or low-sat dark colors summed together
# above this threshold switch to background-accent pattern
BACKGROUND_CLUSTER_THRESHOLD = 0.50
BG_DARK_V = 0.16  # Value below which colors are considered "dark" enough to be background
BG_LOW_S = (
    0.18  # Saturation below which colors are "background-ish" if also dark
)
BG_LOW_S_V = (
    0.28  # Value below which low-saturation colors are also "background-ish"
)

# === Accent masking (minimal additions) =======================================
# When a background cluster exists, remove “background-ish” pixels before quantize
MASK_DARK_V = (
    0.12  # Value below which colors are considered "dark" enough to be masked
)
MASK_LOW_S = 0.10  # Saturation below which colors are considered "background-ish" if also dark
MASK_LOW_S_V = (
    0.22  # Value below which low-saturation colors are also "background-ish"
)
MIN_MASKED_PIXELS_FRACTION = 0.02  # require at least 2% pixels remain
# === Color similarity distance weights =======================================
# Used for perceptual color similarity calculations in HSV space
# Different weight profiles for gray vs saturated colors

# Gray/low-saturation colors (s < 0.15): Value difference is most important
# because hue is meaningless for grays
GRAY_HUE_WEIGHT = 0.1  # Minimal hue influence for grays
GRAY_SAT_WEIGHT = 0.2  # Some saturation difference matters
GRAY_VAL_WEIGHT = 0.7  # Brightness difference is primary distinguisher

# Saturated colors (s >= 0.15): Hue difference is most important
# for distinguishing distinct colors (red vs blue vs green)
SATURATED_HUE_WEIGHT = 0.65  # Hue is primary distinguisher
SATURATED_SAT_WEIGHT = 0.20  # Saturation difference is secondary
SATURATED_VAL_WEIGHT = 0.15  # Brightness difference is tertiary

# Similarity thresholds for color deduplication
SATURATED_COLOR_THRESHOLD = (
    0.12  # Tighter threshold for distinct saturated colors
)
# COLOR_DISTANCE_THRESHOLD (0.20) defined above is used for grays/near-grays

# === LED correction parameters ==============================================
# Gamma blending: Mix between adjusted color (0.0) and gamma-corrected color (1.0)
# Lower values (0.0-0.10) produce more accurate colors, higher values more vibrant
GAMMA_BLEND = 0.00  # Currently disabled for accuracy; tune 0.0-0.10 if needed

# === Gradient building parameters ==========================================
# Blend fraction for "island" gradient stops: controls smoothness of color transitions
# Higher values create more blending between color bands, lower values create harder edges
BLEND_FRAC = 0.10  # Typical range: 0.05-0.15


def extract_dominant_colors(
    pil_image: Image.Image, n_colors: int = 9, use_accent_mask: bool = False
) -> list[dict]:
    """
    Extract dominant colors from image using color quantization.

    Args:
        pil_image: PIL Image object
        n_colors: Number of dominant colors to extract (default 9)
        use_accent_mask: If True, attempt to remove background-ish pixels before quantization

    Returns:
        List of color dicts with 'rgb', 'hsv', 'frequency' keys, sorted by frequency
        Example: [
            {'rgb': [255, 0, 0], 'hsv': [0.0, 1.0, 1.0], 'frequency': 0.65},
            {'rgb': [0, 255, 0], 'hsv': [0.33, 1.0, 1.0], 'frequency': 0.25},
            ...
        ]
    """
    try:
        # Convert to RGB if needed (handles RGBA, grayscale, etc.)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        # Optional: build an "accent-only" sample image to prevent background dominance
        src_img = pil_image
        if use_accent_mask:
            masked_img = _build_accent_sample_image(pil_image)
            if masked_img is not None:
                src_img = masked_img

        # Quantize to extract dominant colors
        # Using MEDIANCUT for better color distribution
        quantized = src_img.quantize(
            colors=n_colors, method=Image.Quantize.MEDIANCUT
        )

        # Get palette colors
        palette = quantized.getpalette()[: n_colors * 3]  # RGB triplets
        palette_colors = [
            palette[i : i + 3] for i in range(0, len(palette), 3)
        ]

        # Count pixels per color to get frequency
        pixel_array = np.array(quantized, dtype=np.uint8)
        total_pixels = pixel_array.size
        color_frequencies = []

        # Vectorized counts per palette index
        counts = np.bincount(
            pixel_array.ravel(), minlength=len(palette_colors)
        )
        freqs = (
            counts / float(total_pixels)
            if total_pixels
            else np.zeros_like(counts)
        )

        for idx, rgb in enumerate(palette_colors):
            frequency = float(freqs[idx])
            if frequency <= 0.0:
                continue

            # Convert to HSV
            r, g, b = (c / 255.0 for c in rgb)
            h, s, v = colorsys.rgb_to_hsv(r, g, b)

            color_frequencies.append(
                {
                    "rgb": rgb,
                    "hsv": [h, s, v],
                    "frequency": frequency,
                }
            )

        # Sort by frequency (most dominant first)
        color_frequencies.sort(key=lambda x: x["frequency"], reverse=True)

        # Deduplicate similar colors to prevent gradient dominated by close variants
        deduplicated = _deduplicate_colors(color_frequencies)

        return deduplicated

    except Exception as e:
        _LOGGER.warning("Failed to extract dominant colors", exc_info=True)
        # Return single average color as fallback
        avg_color = pil_image.resize((1, 1)).getpixel((0, 0))
        if isinstance(avg_color, int):  # Grayscale
            avg_color = (avg_color, avg_color, avg_color)
        r, g, b = (c / 255.0 for c in avg_color[:3])
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return [
            {"rgb": list(avg_color[:3]), "hsv": [h, s, v], "frequency": 1.0}
        ]


def _build_accent_sample_image(
    pil_image: Image.Image,
) -> Optional[Image.Image]:
    """
    Build a 1xN RGB image containing only “accent-like” pixels, excluding
    background-ish pixels (very dark, or low-sat dark).

    Returns None if masking removes too many pixels.
    """
    try:
        arr = np.asarray(pil_image, dtype=np.uint8)
        if arr.ndim != 3 or arr.shape[2] != 3:
            return None

        rgbf = arr.astype(np.float32) / 255.0
        r = rgbf[..., 0]
        g = rgbf[..., 1]
        b = rgbf[..., 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        v = maxc
        delt = maxc - minc
        s = np.where(maxc > 1e-6, delt / (maxc + 1e-6), 0.0)

        # Background-ish pixels to exclude
        bg = (v < MASK_DARK_V) | ((s < MASK_LOW_S) & (v < MASK_LOW_S_V))
        keep = ~bg

        kept = arr[keep]
        total = int(arr.shape[0] * arr.shape[1])
        if total <= 0:
            return None

        if (
            kept.size == 0
            or (kept.shape[0] / float(total)) < MIN_MASKED_PIXELS_FRACTION
        ):
            return None

        sample = kept.reshape((1, kept.shape[0], 3))
        return Image.fromarray(sample, mode="RGB")
    except Exception:
        return None


def _deduplicate_colors(colors: list[dict]) -> list[dict]:
    """
    Merge similar colors to prevent gradients dominated by close color variants.

    Uses weighted HSV distance to determine similarity. If normal merging reduces
    the palette below DEDUP_MIN_COLORS, performs greedy farthest-point sampling
    to recover a minimum palette size from the most distinct colors.

    Args:
        colors: List of color dicts with 'rgb', 'hsv', 'frequency' keys,
                sorted by frequency (most dominant first)

    Returns:
        Deduplicated list of color dicts, sorted by frequency
    """
    if len(colors) <= 1:
        return colors

    # 1) Normal merge pass
    merged: list[dict] = []
    for color in colors:
        merged_into = None
        for existing in merged:
            if _colors_similar(color["hsv"], existing["hsv"]):
                merged_into = existing
                break

        if merged_into is not None:
            merged_into["frequency"] += color["frequency"]
        else:
            merged.append(color.copy())

    merged.sort(key=lambda x: x["frequency"], reverse=True)

    # 2) Floor recovery: if we collapsed too far, pick distinct colors
    if len(merged) >= DEDUP_MIN_COLORS or len(colors) <= DEDUP_MIN_COLORS:
        return merged

    # Build a "most distinct" selection from the original (pre-merge) list.
    # Always keep the most frequent first, then greedily add colors that are farthest
    # (by the same weighted HSV distance idea) from what we've already picked.
    picked: list[dict] = [colors[0].copy()]

    def _weighted_hsv_distance(hsv1, hsv2) -> float:
        h1, s1, v1 = hsv1
        h2, s2, v2 = hsv2

        hue_diff = abs(h1 - h2)
        if hue_diff > 0.5:
            hue_diff = 1.0 - hue_diff

        sat_diff = abs(s1 - s2)
        val_diff = abs(v1 - v2)

        avg_s = (s1 + s2) / 2.0
        if avg_s < 0.15:
            hue_w, sat_w, val_w = (
                GRAY_HUE_WEIGHT,
                GRAY_SAT_WEIGHT,
                GRAY_VAL_WEIGHT,
            )
        else:
            hue_w, sat_w, val_w = (
                SATURATED_HUE_WEIGHT,
                SATURATED_SAT_WEIGHT,
                SATURATED_VAL_WEIGHT,
            )

        return hue_w * hue_diff + sat_w * sat_diff + val_w * val_diff

    # Greedy farthest-point sampling
    while len(picked) < DEDUP_MIN_COLORS and len(picked) < len(colors):
        best = None
        best_score = -1.0

        for cand in colors:
            # skip if already picked (by exact rgb match)
            if any(cand["rgb"] == p["rgb"] for p in picked):
                continue

            # distance to the closest picked color
            d_min = min(
                _weighted_hsv_distance(cand["hsv"], p["hsv"]) for p in picked
            )

            # Prefer higher frequency as a tiebreaker
            score = d_min + 0.05 * float(cand["frequency"])

            if score > best_score:
                best_score = score
                best = cand

        if best is None:
            break

        picked.append(best.copy())

    # Recompute frequencies normalized across picked (so downstream weighting behaves)
    total = sum(float(c["frequency"]) for c in picked) or 1.0
    for c in picked:
        c["frequency"] = float(c["frequency"]) / total

    picked.sort(key=lambda x: x["frequency"], reverse=True)
    return picked


def _colors_similar(hsv1: list[float], hsv2: list[float]) -> bool:
    """
    Check if two colors are perceptually similar using weighted HSV distance.

    Args:
        hsv1: First color [h, s, v] where h,s,v are in [0.0, 1.0]
        hsv2: Second color [h, s, v]

    Returns:
        True if colors are within similarity threshold
    """
    h1, s1, v1 = hsv1
    h2, s2, v2 = hsv2

    # Hue distance (circular, 0-1 wraps around)
    # Hue difference can be at most 0.5 (opposite sides of color wheel)
    hue_diff = abs(h1 - h2)
    if hue_diff > 0.5:
        hue_diff = 1.0 - hue_diff

    # Saturation and Value are linear [0, 1]
    sat_diff = abs(s1 - s2)
    val_diff = abs(v1 - v2)

    # Weighted distance: Hue is most important for distinctness
    # For very low saturation (grays), rely more on Value difference
    avg_saturation = (s1 + s2) / 2

    if avg_saturation < 0.15:
        # Low saturation (grays/near-grays): Use Value primarily
        hue_weight = GRAY_HUE_WEIGHT
        sat_weight = GRAY_SAT_WEIGHT
        val_weight = GRAY_VAL_WEIGHT
    else:
        # Saturated colors: Hue is most important
        hue_weight = SATURATED_HUE_WEIGHT
        sat_weight = SATURATED_SAT_WEIGHT
        val_weight = SATURATED_VAL_WEIGHT

    weighted_distance = (
        hue_weight * hue_diff + sat_weight * sat_diff + val_weight * val_diff
    )

    # Tighten threshold for saturated colors so distinct hues (e.g. red vs yellow)
    # don't get merged. Keep the looser threshold for grays/near-grays.
    if avg_saturation >= 0.25:
        threshold = SATURATED_COLOR_THRESHOLD
    else:
        threshold = COLOR_DISTANCE_THRESHOLD

    return weighted_distance < threshold


def detect_dominant_background(
    colors: list[dict], threshold: float = 0.5
) -> Optional[dict]:
    """
    Detect if image has a dominant background color cluster.

    Treats "background" as a CLUSTER of background-like colors (dark and/or low-sat dark)
    rather than a single color. Sums frequencies of all background-ish colors and returns
    the most frequent one if the cluster sum exceeds the threshold. If cluster is dominant,
    returns a representative background color dict: the most frequent background-like color,
    but with frequency set to the cluster sum.

    Args:
        colors: List of color dicts with 'rgb', 'hsv', 'frequency' keys
        threshold: Minimum frequency for background cluster detection (default 0.5)

    Returns:
        Background color dict with cluster frequency, or None if no dominant background
    """
    if not colors:
        return None

    bg_candidates = [
        c
        for c in colors
        if (c["hsv"][2] < BG_DARK_V)
        or ((c["hsv"][1] < BG_LOW_S) and (c["hsv"][2] < BG_LOW_S_V))
    ]
    if not bg_candidates:
        return None

    bg_freq = sum(float(c["frequency"]) for c in bg_candidates)
    if bg_freq >= threshold:
        bg_candidates.sort(key=lambda x: x["frequency"], reverse=True)
        bg = bg_candidates[0].copy()
        bg["frequency"] = bg_freq  # cluster frequency
        return bg

    return None


def apply_led_correction(rgb: list[int], mode: str = "safe") -> list[int]:
    """
    Apply LED-specific color correction to RGB values.

    Args:
        rgb: RGB color as [R, G, B] where values are 0-255
        mode: "safe" for conservative correction, "punchy" for vibrant, "raw" for none

    Returns:
        Corrected RGB color as [R, G, B]
    """
    if mode == "raw":
        return rgb

    config = LED_SAFE_CONFIG if mode == "safe" else LED_PUNCHY_CONFIG

    # Convert to HSV for easier manipulation
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Detect and replace near-white colors FIRST
    if s < config["white_threshold"] and v > WHITE_REPLACE_MIN_V:
        # Replace with defined white
        white_hex = config["white_replacement"]
        white_rgb = tuple(int(white_hex[i : i + 2], 16) for i in (1, 3, 5))
        return list(white_rgb)

    # Apply brightness cap
    v = min(v, config["max_value"])

    # Apply saturation cap
    s = min(s, config["max_saturation"])

    # Convert back to RGB with adjustments
    r_adjusted, g_adjusted, b_adjusted = colorsys.hsv_to_rgb(h, s, v)

    # Apply gamma correction
    gamma = config["gamma"]
    r_gamma = pow(r_adjusted, 1.0 / gamma)
    g_gamma = pow(g_adjusted, 1.0 / gamma)
    b_gamma = pow(b_adjusted, 1.0 / gamma)

    # Blend between adjusted color and gamma-corrected color
    r_final = r_adjusted * (1.0 - GAMMA_BLEND) + r_gamma * GAMMA_BLEND
    g_final = g_adjusted * (1.0 - GAMMA_BLEND) + g_gamma * GAMMA_BLEND
    b_final = b_adjusted * (1.0 - GAMMA_BLEND) + b_gamma * GAMMA_BLEND

    # Clamp to valid range and convert to 0-255
    rgb_corrected = [
        int(max(0, min(255, c * 255))) for c in [r_final, g_final, b_final]
    ]

    return rgb_corrected


def build_gradient_stops(
    colors: list[dict],
    background_color: Optional[dict] = None,
    max_stops: int = 8,
) -> list[dict]:
    """
    Build gradient stops from extracted colors.

    Creates two types of gradients:
    - Interleaved: If background detected, alternates bg → accent → bg for emphasis
    - Island: Creates weighted color bands with soft blending at boundaries

    Args:
        colors: List of color dicts with 'rgb', 'hsv', 'frequency' keys
        background_color: Optional background color dict for interleaved pattern
        max_stops: Maximum number of gradient stops to generate

    Returns:
        List of gradient stop dicts with 'color' (hex), 'position' (0-1),
        'type' ('color'/'accent'/'background'), and 'weight' (frequency)
    """
    if not colors:
        return []

    stops = []

    if background_color:
        # Interleaved pattern: bg → accent → bg → accent
        # Remove background-like colors from accent colors.
        # Do NOT rely on dict equality (background is a cluster representative).
        accent_colors = [
            c
            for c in colors
            if not (
                (c["hsv"][2] < BG_DARK_V)
                or ((c["hsv"][1] < BG_LOW_S) and (c["hsv"][2] < BG_LOW_S_V))
            )
        ]

        # In interleaved mode, max_stops should represent accent capacity (not total stops),
        # because background consumes half the slots otherwise.
        max_accents = max_stops
        accent_colors = accent_colors[:max_accents]

        if not accent_colors:
            # Edge case: only background color, create simple gradient
            bg_hex = f"#{background_color['rgb'][0]:02x}{background_color['rgb'][1]:02x}{background_color['rgb'][2]:02x}"
            return [
                {"color": bg_hex, "position": 0.0, "type": "background"},
                {"color": bg_hex, "position": 1.0, "type": "background"},
            ]

        # Build interleaved stops
        bg_hex = f"#{background_color['rgb'][0]:02x}{background_color['rgb'][1]:02x}{background_color['rgb'][2]:02x}"

        # Normalize accent frequencies (exclude background)
        total_accent_freq = sum(c["frequency"] for c in accent_colors)
        if total_accent_freq > 0:
            accent_weights = [
                c["frequency"] / total_accent_freq for c in accent_colors
            ]
        else:
            accent_weights = [1.0 / len(accent_colors)] * len(accent_colors)

        # Build pattern: bg, accent1, bg, accent2, bg, ...
        num_accents = len(accent_colors)
        total_stops = num_accents * 2 + 1
        position = 0.0
        step = 1.0 / (total_stops - 1) if total_stops > 1 else 1.0

        for i, accent in enumerate(accent_colors):
            # Background before accent
            stops.append(
                {
                    "color": bg_hex,
                    "position": round(position, 3),
                    "type": "background",
                }
            )
            position += step

            # Accent color
            accent_hex = f"#{accent['rgb'][0]:02x}{accent['rgb'][1]:02x}{accent['rgb'][2]:02x}"
            stops.append(
                {
                    "color": accent_hex,
                    "position": round(position, 3),
                    "type": "accent",
                    "weight": round(accent_weights[i], 3),
                }
            )
            position += step

        # Final background
        stops.append({"color": bg_hex, "position": 1.0, "type": "background"})

    else:
        # Normal weighted gradient (no dominant background)
        gradient_colors = colors[:max_stops]

        if not gradient_colors:
            return []

        # Single-color edge case: emit a valid 2-stop gradient
        if len(gradient_colors) == 1:
            c = gradient_colors[0]
            c_hex = f"#{c['rgb'][0]:02x}{c['rgb'][1]:02x}{c['rgb'][2]:02x}"
            stops.append(
                {
                    "color": c_hex,
                    "position": 0.0,
                    "type": "color",
                    "weight": round(c["frequency"], 3),
                }
            )
            stops.append(
                {
                    "color": c_hex,
                    "position": 1.0,
                    "type": "color",
                    "weight": round(c["frequency"], 3),
                }
            )
            return stops

        # Normalize weights to band widths over [0,1]
        total_freq = sum(float(c["frequency"]) for c in gradient_colors) or 1.0
        widths = [float(c["frequency"]) / total_freq for c in gradient_colors]

        # Helper: BLEND_FRAC is "fraction of current band width"
        def _blend_for_boundary(
            w_i: float, w_next: float, blend_frac: float
        ) -> float:
            b = blend_frac * w_i
            # safety cap so blend can't consume either band
            return min(b, 0.45 * min(w_i, w_next))

        # Build cumulative band boundaries
        starts = [0.0]
        for w in widths[:-1]:
            starts.append(starts[-1] + w)
        ends = [s + w for s, w in zip(starts, widths)]
        ends[-1] = 1.0  # force exact end

        # Emit "islands" with soft boundaries:
        # For each boundary at ends[i], keep color_i flat until (end-b),
        # then allow interpolation across (end-b .. end+b) by switching to next at (end+b).

        # First stop at 0
        c0 = gradient_colors[0]
        c0_hex = f"#{c0['rgb'][0]:02x}{c0['rgb'][1]:02x}{c0['rgb'][2]:02x}"
        stops.append(
            {
                "color": c0_hex,
                "position": 0.0,
                "type": "color",
                "weight": round(c0["frequency"], 3),
            }
        )

        last_pos = 0.0

        for i in range(len(gradient_colors) - 1):
            c_i = gradient_colors[i]
            c_n = gradient_colors[i + 1]

            c_i_hex = (
                f"#{c_i['rgb'][0]:02x}{c_i['rgb'][1]:02x}{c_i['rgb'][2]:02x}"
            )
            c_n_hex = (
                f"#{c_n['rgb'][0]:02x}{c_n['rgb'][1]:02x}{c_n['rgb'][2]:02x}"
            )

            start_i = starts[i]
            end_i = ends[i]
            start_n = starts[i + 1]

            w_i = widths[i]
            w_n = widths[i + 1]

            b = _blend_for_boundary(w_i, w_n, BLEND_FRAC)

            left_flat_end = end_i - b
            right_flat_start = end_i + b

            # Clamp into legal ranges to avoid overlaps / inversions
            left_flat_end = max(left_flat_end, start_i)
            right_flat_start = min(right_flat_start, ends[i + 1])

            if right_flat_start < left_flat_end:
                mid = 0.5 * (end_i + start_n)
                left_flat_end = mid
                right_flat_start = mid

            # Enforce monotonic positions (rounding can otherwise regress)
            left_flat_end = max(left_flat_end, last_pos)
            last_pos = left_flat_end

            stops.append(
                {
                    "color": c_i_hex,
                    "position": round(left_flat_end, 3),
                    "type": "color",
                    "weight": round(c_i["frequency"], 3),
                }
            )

            right_flat_start = max(right_flat_start, last_pos)
            last_pos = right_flat_start

            stops.append(
                {
                    "color": c_n_hex,
                    "position": round(right_flat_start, 3),
                    "type": "color",
                    "weight": round(c_n["frequency"], 3),
                }
            )

        # Final stop at 1.0 to close
        c_last = gradient_colors[-1]
        c_last_hex = f"#{c_last['rgb'][0]:02x}{c_last['rgb'][1]:02x}{c_last['rgb'][2]:02x}"
        stops.append(
            {
                "color": c_last_hex,
                "position": 1.0,
                "type": "color",
                "weight": round(c_last["frequency"], 3),
            }
        )

    return stops


def build_gradient_string(stops: list[dict]) -> str:
    """
    Build LedFx gradient string from stops.

    Args:
        stops: List of gradient stops from build_gradient_stops()

    Returns:
        LedFx gradient string
    """
    if not stops:
        return "linear-gradient(90deg, rgb(0,0,0) 0%, rgb(0,0,0) 100%)"

    stop_strings = []
    for stop in stops:
        hex_color = stop["color"]
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
        position_pct = int(stop["position"] * 100)
        stop_strings.append(f"rgb({rgb[0]},{rgb[1]},{rgb[2]}) {position_pct}%")

    gradient_str = f"linear-gradient(90deg, {', '.join(stop_strings)})"
    return gradient_str


def extract_gradient_metadata(image_source) -> dict:
    """
    Extract all gradient variants and metadata from an image.

    This is the main entry point for gradient extraction. Returns a complete
    metadata dict suitable for storage in ImageCache or asset metadata.

    Args:
        image_source: Either a file path (str) or PIL Image object.

    Returns:
        dict: Complete gradient metadata with all variants
    """
    start_time = time.time()

    # Handle both path and PIL Image inputs
    if isinstance(image_source, str):
        # Path provided - open and manage the image
        try:
            with Image.open(image_source) as pil_image:
                return _extract_gradient_metadata_from_image(
                    pil_image, start_time
                )
        except Exception as e:
            _LOGGER.warning("Failed to open image", exc_info=True)
            return _gradient_fallback_metadata(None, e, start_time)
    elif isinstance(image_source, Image.Image):
        # PIL Image provided - use directly
        return _extract_gradient_metadata_from_image(image_source, start_time)
    else:
        error_msg = f"Invalid image_source type: {type(image_source)}. Expected str (path) or PIL Image."
        _LOGGER.warning(error_msg)
        return _gradient_fallback_metadata(
            None, ValueError(error_msg), start_time
        )


def _extract_gradient_metadata_from_image(
    pil_image: Image.Image, start_time: float
) -> dict:
    """
    Internal function to extract gradient metadata from an already-opened PIL Image.

    Performs two-pass extraction:
    1. Full-image palette (12 colors) for robust background cluster detection
    2. Accent-masked palette (9 colors) to emphasize foreground colors

    Falls back to full-image accents if masking over-filters.

    Args:
        pil_image: Already-opened PIL Image object
        start_time: Start time for performance tracking

    Returns:
        Complete gradient metadata dict with all variants and metadata
    """
    try:
        # First pass: full-image palette for robust background-cluster detection
        full_colors = extract_dominant_colors(
            pil_image, n_colors=12, use_accent_mask=False
        )

        # Detect dominant background *cluster*
        background = detect_dominant_background(
            full_colors, threshold=BACKGROUND_CLUSTER_THRESHOLD
        )

        # Second pass: extract accents with masking iff background cluster exists
        colors = extract_dominant_colors(
            pil_image, n_colors=9, use_accent_mask=(background is not None)
        )

        # Fail-open: if accent masking collapses the palette, reuse the full-image palette.
        # This prevents losing small but important low-saturation warm tones (e.g., yellows).
        if background is not None and len(colors) < 5:
            _LOGGER.debug(
                "Accent pass produced too few colors (%d). Falling back to full-image accents (background removed).",
                len(colors),
            )
            colors = [c for c in full_colors if c["rgb"] != background["rgb"]]

        # Build gradient stops (raw, no correction)
        raw_stops = build_gradient_stops(colors, background, max_stops=8)
        raw_gradient = build_gradient_string(raw_stops)

        # Always extract the most frequent color as background_color (bin-based)
        most_frequent = (
            full_colors[0] if full_colors else (colors[0] if colors else None)
        )
        background_color_hex = (
            f"#{most_frequent['rgb'][0]:02x}{most_frequent['rgb'][1]:02x}{most_frequent['rgb'][2]:02x}"
            if most_frequent
            else None
        )
        background_frequency = (
            round(most_frequent["frequency"], 3) if most_frequent else None
        )

        raw_variant = {"gradient": raw_gradient}

        # LED-safe variant
        safe_colors = []
        for c in colors:
            corrected_rgb = apply_led_correction(c["rgb"], mode="safe")
            r, g, b = (val / 255.0 for val in corrected_rgb)
            corrected_hsv = list(colorsys.rgb_to_hsv(r, g, b))
            safe_colors.append(
                {
                    "rgb": corrected_rgb,
                    "hsv": corrected_hsv,
                    "frequency": c["frequency"],
                }
            )
        safe_background = None
        if background:
            corrected_rgb = apply_led_correction(
                background["rgb"], mode="safe"
            )
            r, g, b = (val / 255.0 for val in corrected_rgb)
            corrected_hsv = list(colorsys.rgb_to_hsv(r, g, b))
            safe_background = {
                "rgb": corrected_rgb,
                "hsv": corrected_hsv,
                "frequency": background["frequency"],
            }

        safe_stops = build_gradient_stops(
            safe_colors, safe_background, max_stops=8
        )
        safe_gradient = build_gradient_string(safe_stops)
        led_safe_variant = {"gradient": safe_gradient}

        # LED-punchy variant
        punchy_colors = []
        for c in colors:
            corrected_rgb = apply_led_correction(c["rgb"], mode="punchy")
            r, g, b = (val / 255.0 for val in corrected_rgb)
            corrected_hsv = list(colorsys.rgb_to_hsv(r, g, b))
            punchy_colors.append(
                {
                    "rgb": corrected_rgb,
                    "hsv": corrected_hsv,
                    "frequency": c["frequency"],
                }
            )
        punchy_background = None
        if background:
            corrected_rgb = apply_led_correction(
                background["rgb"], mode="punchy"
            )
            r, g, b = (val / 255.0 for val in corrected_rgb)
            corrected_hsv = list(colorsys.rgb_to_hsv(r, g, b))
            punchy_background = {
                "rgb": corrected_rgb,
                "hsv": corrected_hsv,
                "frequency": background["frequency"],
            }

        punchy_stops = build_gradient_stops(
            punchy_colors, punchy_background, max_stops=8
        )
        punchy_gradient = build_gradient_string(punchy_stops)
        led_punchy_variant = {"gradient": punchy_gradient}

        processing_time_ms = int((time.time() - start_time) * 1000)

        _LOGGER.debug(
            f"Gradient extraction completed in {processing_time_ms}ms "
            f"(size: {pil_image.size[0]}x{pil_image.size[1]}, "
            f"colors: {len(colors)}, pattern: {'interleaved' if background else 'weighted'})"
        )

        pattern = "interleaved" if background else "weighted"

        return {
            "raw": raw_variant,
            "led_safe": led_safe_variant,
            "led_punchy": led_punchy_variant,
            "metadata": {
                "image_size": list(pil_image.size),
                "processing_time_ms": processing_time_ms,
                "extracted_color_count": len(colors),
                "has_dominant_background": background is not None,
                "gradient_stop_count": len(raw_stops),
                "pattern": pattern,
                "background_color": background_color_hex,
                "background_frequency": background_frequency,
                "extraction_version": "1.1",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    except Exception as e:
        _LOGGER.warning("Failed to extract gradient metadata", exc_info=True)
        return _gradient_fallback_metadata(pil_image, e, start_time)


def _gradient_fallback_metadata(pil_image, error, start_time: float) -> dict:
    """
    Generate fallback gradient metadata when extraction fails.

    Args:
        pil_image: PIL Image object (may be None)
        error: Exception that caused the failure (logged but not exposed)
        start_time: Time when extraction started

    Returns:
        dict: Fallback gradient metadata with neutral gray gradient
    """
    processing_time_ms = (
        int((time.time() - start_time) * 1000) if start_time else 0
    )

    return {
        "raw": {
            "gradient": "linear-gradient(90deg, rgb(128,128,128) 0%, rgb(128,128,128) 100%)",
        },
        "led_safe": {
            "gradient": "linear-gradient(90deg, rgb(109,109,109) 0%, rgb(109,109,109) 100%)",
        },
        "led_punchy": {
            "gradient": "linear-gradient(90deg, rgb(128,128,128) 0%, rgb(128,128,128) 100%)",
        },
        "metadata": {
            "image_size": list(pil_image.size) if pil_image else [0, 0],
            "processing_time_ms": processing_time_ms,
            "extracted_color_count": 0,
            "has_dominant_background": False,
            "gradient_stop_count": 2,
            "pattern": "fallback",
            "background_color": None,
            "background_frequency": None,
            "extraction_version": "1.1",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        },
    }
