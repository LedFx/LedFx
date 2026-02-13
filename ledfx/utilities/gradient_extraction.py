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


def extract_dominant_colors(
    pil_image: Image.Image, n_colors: int = 9
) -> list[dict]:
    """
    Extract dominant colors from image using color quantization.

    Args:
        pil_image: PIL Image object
        n_colors: Number of dominant colors to extract (default 9)

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

        # Quantize to extract dominant colors
        # Using MEDIANCUT for better color distribution
        quantized = pil_image.quantize(
            colors=n_colors, method=Image.Quantize.MEDIANCUT
        )
        palette_img = quantized.convert("RGB")

        # Get palette colors
        palette = quantized.getpalette()[: n_colors * 3]  # RGB triplets
        palette_colors = [
            palette[i : i + 3] for i in range(0, len(palette), 3)
        ]

        # Count pixels per color to get frequency
        pixel_array = np.array(quantized)
        total_pixels = pixel_array.size
        color_frequencies = []

        for idx, rgb in enumerate(palette_colors):
            # Count pixels matching this palette index
            count = np.sum(pixel_array == idx)
            frequency = count / total_pixels

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

        return color_frequencies

    except Exception as e:
        _LOGGER.error(f"Failed to extract dominant colors: {e}")
        # Return single average color as fallback
        avg_color = pil_image.resize((1, 1)).getpixel((0, 0))
        if isinstance(avg_color, int):  # Grayscale
            avg_color = (avg_color, avg_color, avg_color)
        r, g, b = (c / 255.0 for c in avg_color[:3])
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return [
            {"rgb": list(avg_color[:3]), "hsv": [h, s, v], "frequency": 1.0}
        ]


def detect_dominant_background(
    colors: list[dict], threshold: float = 0.5
) -> Optional[dict]:
    """
    Detect if image has a dominant background color.

    Args:
        colors: List of color dicts from extract_dominant_colors()
        threshold: Frequency threshold for background detection (default 0.5 = 50%)

    Returns:
        Background color dict if detected, None otherwise
    """
    if not colors:
        return None

    # Check if first (most frequent) color exceeds threshold
    if colors[0]["frequency"] >= threshold:
        return colors[0]

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
    if s < config["white_threshold"] and v > 0.85:
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

    # Blend gamma correction (30% gamma, 70% HSV adjustments)
    # This keeps LED-friendly HSV adjustments as primary
    r_final = r_adjusted * 0.7 + r_gamma * 0.3
    g_final = g_adjusted * 0.7 + g_gamma * 0.3
    b_final = b_adjusted * 0.7 + b_gamma * 0.3

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

    If background_color is detected, creates interleaved pattern: bg → c1 → bg → c2 → bg
    Otherwise creates normal weighted gradient.

    Args:
        colors: List of color dicts from extract_dominant_colors()
        background_color: Dominant background color dict if detected
        max_stops: Maximum gradient stops (default 8)

    Returns:
        List of gradient stops with 'color' (hex), 'position' (0.0-1.0), 'type'
        Example: [
            {'color': '#000000', 'position': 0.0, 'type': 'background'},
            {'color': '#FF0000', 'position': 0.14, 'type': 'accent', 'weight': 0.5},
            ...
        ]
    """
    if not colors:
        return []

    stops = []

    if background_color:
        # Interleaved pattern: bg → accent → bg → accent
        # Remove background from accent colors
        accent_colors = [c for c in colors if c != background_color]

        # Limit accent colors based on max_stops
        # With 8 stops: bg, c1, bg, c2, bg, c3, bg, c4 = 8 stops → 4 accents
        # With 7 stops: bg, c1, bg, c2, bg, c3, bg = 7 stops → 3 accents
        max_accents = max_stops // 2
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

        # Calculate positions with even spacing
        num_accents = len(accent_colors)
        total_stops = (
            num_accents * 2 + 1
        )  # bg slots between and around accents

        # Normalize accent frequencies (exclude background)
        total_accent_freq = sum(c["frequency"] for c in accent_colors)
        if total_accent_freq > 0:
            for c in accent_colors:
                c["normalized_weight"] = c["frequency"] / total_accent_freq
        else:
            for c in accent_colors:
                c["normalized_weight"] = 1.0 / len(accent_colors)

        # Build pattern: bg, accent1, bg, accent2, bg, accent3, bg, ...
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
                    "weight": round(accent["normalized_weight"], 3),
                }
            )
            position += step

        # Final background
        stops.append(
            {
                "color": bg_hex,
                "position": 1.0,
                "type": "background",
            }
        )

    else:
        # Normal weighted gradient (no dominant background)
        gradient_colors = colors[:max_stops]

        # Calculate cumulative positions based on frequency
        total_freq = sum(c["frequency"] for c in gradient_colors)
        cumulative = 0.0

        for i, color in enumerate(gradient_colors):
            # Calculate position
            if i == 0:
                position = 0.0
            elif i == len(gradient_colors) - 1:
                position = 1.0
            else:
                # Weighted position
                cumulative += color["frequency"] / total_freq
                position = cumulative

            color_hex = f"#{color['rgb'][0]:02x}{color['rgb'][1]:02x}{color['rgb'][2]:02x}"
            stops.append(
                {
                    "color": color_hex,
                    "position": round(position, 3),
                    "type": "color",
                    "weight": round(color["frequency"], 3),
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
        Example: "linear-gradient(90deg, rgb(0,0,0) 0%, rgb(255,0,0) 14%, ...)"
    """
    if not stops:
        return "linear-gradient(90deg, rgb(0,0,0) 0%, rgb(0,0,0) 100%)"

    # Build color stop strings
    stop_strings = []
    for stop in stops:
        # Convert hex to rgb
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
                     If path is provided, image will be opened and closed automatically.
                     If PIL Image is provided, it will be used directly (useful for tests).

    Returns:
        dict: Complete gradient metadata with all variants
        {
            "raw": {"gradient": "...", "stops": [...], "dominant_colors": [...], ...},
            "led_safe": {...},
            "led_punchy": {...},
            "metadata": {"image_size": [...], "processing_time_ms": ..., ...}
        }
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
            _LOGGER.error(
                f"Failed to open image at {image_source}: {e}", exc_info=True
            )
            return _gradient_fallback_metadata(None, e, start_time)
    elif isinstance(image_source, Image.Image):
        # PIL Image provided - use directly
        return _extract_gradient_metadata_from_image(image_source, start_time)
    else:
        error_msg = f"Invalid image_source type: {type(image_source)}. Expected str (path) or PIL Image."
        _LOGGER.error(error_msg)
        return _gradient_fallback_metadata(
            None, ValueError(error_msg), start_time
        )


def _extract_gradient_metadata_from_image(
    pil_image: Image.Image, start_time: float
) -> dict:
    """
    Internal function to extract gradient metadata from an already-opened PIL Image.

    Args:
        pil_image: PIL Image object
        start_time: Time when extraction started (for performance tracking)

    Returns:
        dict: Complete gradient metadata
    """
    try:
        # Extract dominant colors
        colors = extract_dominant_colors(pil_image, n_colors=9)

        # Detect dominant background
        background = detect_dominant_background(colors, threshold=0.5)

        # Build gradient stops (raw, no correction)
        raw_stops = build_gradient_stops(colors, background, max_stops=8)

        # Build gradient string
        raw_gradient = build_gradient_string(raw_stops)

        # Extract background color as hex
        background_color_hex = None
        background_frequency = None
        if background:
            background_color_hex = f"#{background['rgb'][0]:02x}{background['rgb'][1]:02x}{background['rgb'][2]:02x}"
            background_frequency = round(background["frequency"], 3)

        # Build raw variant
        raw_variant = {
            "gradient": raw_gradient,
            "stops": raw_stops,
            "dominant_colors": colors,
            "background_color": background_color_hex,
            "background_frequency": background_frequency,
        }

        # Build LED-safe variant (apply correction to all colors)
        safe_colors = [
            {
                "rgb": apply_led_correction(c["rgb"], mode="safe"),
                "hsv": c["hsv"],  # Will be recalculated if needed
                "frequency": c["frequency"],
            }
            for c in colors
        ]
        safe_background = None
        if background:
            safe_background = {
                "rgb": apply_led_correction(background["rgb"], mode="safe"),
                "hsv": background["hsv"],
                "frequency": background["frequency"],
            }

        safe_stops = build_gradient_stops(
            safe_colors, safe_background, max_stops=8
        )
        safe_gradient = build_gradient_string(safe_stops)
        safe_bg_hex = None
        if safe_background:
            safe_bg_hex = f"#{safe_background['rgb'][0]:02x}{safe_background['rgb'][1]:02x}{safe_background['rgb'][2]:02x}"

        led_safe_variant = {
            "gradient": safe_gradient,
            "stops": safe_stops,
            "dominant_colors": safe_colors,
            "background_color": safe_bg_hex,
            "background_frequency": background_frequency,
        }

        # Build LED-punchy variant
        punchy_colors = [
            {
                "rgb": apply_led_correction(c["rgb"], mode="punchy"),
                "hsv": c["hsv"],
                "frequency": c["frequency"],
            }
            for c in colors
        ]
        punchy_background = None
        if background:
            punchy_background = {
                "rgb": apply_led_correction(background["rgb"], mode="punchy"),
                "hsv": background["hsv"],
                "frequency": background["frequency"],
            }

        punchy_stops = build_gradient_stops(
            punchy_colors, punchy_background, max_stops=8
        )
        punchy_gradient = build_gradient_string(punchy_stops)
        punchy_bg_hex = None
        if punchy_background:
            punchy_bg_hex = f"#{punchy_background['rgb'][0]:02x}{punchy_background['rgb'][1]:02x}{punchy_background['rgb'][2]:02x}"

        led_punchy_variant = {
            "gradient": punchy_gradient,
            "stops": punchy_stops,
            "dominant_colors": punchy_colors,
            "background_color": punchy_bg_hex,
            "background_frequency": background_frequency,
        }

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Log extraction time for performance monitoring
        _LOGGER.error(
            f"Gradient extraction completed in {processing_time_ms}ms "
            f"(size: {pil_image.size[0]}x{pil_image.size[1]}, "
            f"colors: {len(colors)}, pattern: {'interleaved' if background else 'weighted'})"
        )

        # Determine pattern type
        pattern = "interleaved" if background else "weighted"

        # Build complete metadata
        result = {
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
                "extraction_version": "1.0",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        return result

    except Exception as e:
        _LOGGER.error(
            f"Failed to extract gradient metadata: {e}", exc_info=True
        )
        return _gradient_fallback_metadata(pil_image, e, start_time)


def _gradient_fallback_metadata(pil_image, error, start_time: float) -> dict:
    """
    Generate fallback gradient metadata when extraction fails.

    Args:
        pil_image: PIL Image object (may be None)
        error: Exception that caused the failure
        start_time: Time when extraction started

    Returns:
        dict: Fallback gradient metadata with error information
    """
    processing_time_ms = (
        int((time.time() - start_time) * 1000) if start_time else 0
    )

    return {
        "raw": {
            "gradient": "linear-gradient(90deg, rgb(128,128,128) 0%, rgb(128,128,128) 100%)",
            "stops": [
                {"color": "#808080", "position": 0.0, "type": "color"},
                {"color": "#808080", "position": 1.0, "type": "color"},
            ],
            "dominant_colors": [],
            "background_color": None,
            "background_frequency": None,
        },
        "led_safe": {
            "gradient": "linear-gradient(90deg, rgb(109,109,109) 0%, rgb(109,109,109) 100%)",
            "stops": [
                {"color": "#6D6D6D", "position": 0.0, "type": "color"},
                {"color": "#6D6D6D", "position": 1.0, "type": "color"},
            ],
            "dominant_colors": [],
            "background_color": None,
            "background_frequency": None,
        },
        "led_punchy": {
            "gradient": "linear-gradient(90deg, rgb(128,128,128) 0%, rgb(128,128,128) 100%)",
            "stops": [
                {"color": "#808080", "position": 0.0, "type": "color"},
                {"color": "#808080", "position": 1.0, "type": "color"},
            ],
            "dominant_colors": [],
            "background_color": None,
            "background_frequency": None,
        },
        "metadata": {
            "image_size": list(pil_image.size) if pil_image else [0, 0],
            "processing_time_ms": processing_time_ms,
            "extracted_color_count": 0,
            "has_dominant_background": False,
            "gradient_stop_count": 2,
            "pattern": "fallback",
            "extraction_version": "1.0",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "error": str(error),
        },
    }
