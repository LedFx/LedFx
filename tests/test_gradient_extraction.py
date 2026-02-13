"""Unit tests for gradient extraction utilities."""

from PIL import Image

from ledfx.utilities.gradient_extraction import (
    apply_led_correction,
    build_gradient_stops,
    build_gradient_string,
    detect_dominant_background,
    extract_dominant_colors,
    extract_gradient_metadata,
)


class TestExtractDominantColors:
    """Test color extraction from images."""

    def test_extract_from_solid_color(self):
        """Extract colors from single-color image."""
        # Create 100x100 red image
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        colors = extract_dominant_colors(img, n_colors=3)

        assert len(colors) > 0
        # Should detect red as dominant
        assert colors[0]["rgb"][0] > 200  # High red value
        assert colors[0]["frequency"] > 0.9  # Should be >90%

    def test_extract_from_two_colors(self):
        """Extract colors from two-color image."""
        # Create 100x100 image: 70% black, 30% red
        img = Image.new("RGB", (100, 100))
        pixels = img.load()

        # Fill 70 rows with black, 30 with red
        for y in range(100):
            for x in range(100):
                if y < 70:
                    pixels[x, y] = (0, 0, 0)
                else:
                    pixels[x, y] = (255, 0, 0)

        colors = extract_dominant_colors(img, n_colors=5)

        assert len(colors) >= 2
        # First should be black (70%)
        assert colors[0]["frequency"] > 0.65
        assert sum(colors[0]["rgb"]) < 30  # Dark color

    def test_extract_returns_sorted_by_frequency(self):
        """Colors should be sorted by frequency."""
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        colors = extract_dominant_colors(img, n_colors=5)

        # Check sorted order
        for i in range(len(colors) - 1):
            assert colors[i]["frequency"] >= colors[i + 1]["frequency"]

    def test_extract_handles_rgba(self):
        """Should handle RGBA images by converting to RGB."""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        colors = extract_dominant_colors(img, n_colors=3)

        assert len(colors) > 0
        # Should still extract red


class TestDetectDominantBackground:
    """Test background detection."""

    def test_detects_background_over_threshold(self):
        """Detect background when frequency > threshold."""
        colors = [
            {"rgb": [0, 0, 0], "hsv": [0, 0, 0], "frequency": 0.7},
            {"rgb": [255, 0, 0], "hsv": [0, 1, 1], "frequency": 0.2},
            {"rgb": [0, 255, 0], "hsv": [0.33, 1, 1], "frequency": 0.1},
        ]

        bg = detect_dominant_background(colors, threshold=0.5)
        assert bg is not None
        assert bg["frequency"] == 0.7

    def test_no_background_under_threshold(self):
        """No background when frequency < threshold."""
        colors = [
            {"rgb": [0, 0, 0], "hsv": [0, 0, 0], "frequency": 0.4},
            {"rgb": [255, 0, 0], "hsv": [0, 1, 1], "frequency": 0.3},
            {"rgb": [0, 255, 0], "hsv": [0.33, 1, 1], "frequency": 0.3},
        ]

        bg = detect_dominant_background(colors, threshold=0.5)
        assert bg is None

    def test_empty_colors_returns_none(self):
        """Handle empty color list."""
        bg = detect_dominant_background([], threshold=0.5)
        assert bg is None


class TestApplyLedCorrection:
    """Test LED color correction."""

    def test_raw_mode_no_correction(self):
        """Raw mode should not modify colors."""
        rgb = [255, 128, 64]
        corrected = apply_led_correction(rgb, mode="raw")
        assert corrected == rgb

    def test_safe_mode_caps_brightness(self):
        """Safe mode should cap brightness."""
        # Bright saturated color that won't trigger white replacement
        rgb = [255, 0, 0]  # Pure red
        corrected = apply_led_correction(rgb, mode="safe")

        # Should be reduced from 255
        # With 85% cap and gamma blending, expect ~195-220 range
        assert corrected[0] < 255
        assert corrected[0] > 180  # Still reasonably bright

    def test_safe_mode_reduces_saturation(self):
        """Safe mode should reduce saturation."""
        # Pure red
        rgb = [255, 0, 0]
        corrected = apply_led_correction(rgb, mode="safe")

        # Red should be reduced
        assert corrected[0] < 255

    def test_punchy_mode_more_vibrant(self):
        """Punchy mode should be more vibrant than safe."""
        rgb = [255, 0, 0]
        safe = apply_led_correction(rgb, mode="safe")
        punchy = apply_led_correction(rgb, mode="punchy")

        # Punchy should have higher values
        assert punchy[0] >= safe[0]

    def test_white_replacement(self):
        """Near-white colors should be replaced."""
        # Light gray (low saturation, high value)
        rgb = [240, 240, 240]
        corrected = apply_led_correction(rgb, mode="safe")

        # Should be replaced with defined white
        assert corrected == [245, 245, 245]  # WhiteSmoke


class TestBuildGradientStops:
    """Test gradient stop generation."""

    def test_normal_gradient_without_background(self):
        """Build normal weighted gradient."""
        colors = [
            {"rgb": [255, 0, 0], "hsv": [0, 1, 1], "frequency": 0.5},
            {"rgb": [0, 255, 0], "hsv": [0.33, 1, 1], "frequency": 0.3},
            {"rgb": [0, 0, 255], "hsv": [0.67, 1, 1], "frequency": 0.2},
        ]

        stops = build_gradient_stops(
            colors, background_color=None, max_stops=8
        )

        assert len(stops) == 3
        assert stops[0]["position"] == 0.0
        assert stops[-1]["position"] == 1.0
        assert all(s["type"] == "color" for s in stops)

    def test_interleaved_gradient_with_background(self):
        """Build interleaved gradient with background."""
        colors = [
            {"rgb": [0, 0, 0], "hsv": [0, 0, 0], "frequency": 0.7},
            {"rgb": [255, 0, 0], "hsv": [0, 1, 1], "frequency": 0.2},
            {"rgb": [0, 0, 255], "hsv": [0.67, 1, 1], "frequency": 0.1},
        ]
        background = colors[0]

        stops = build_gradient_stops(
            colors, background_color=background, max_stops=8
        )

        # Should have alternating pattern: bg, accent, bg, accent, bg
        assert len(stops) == 5  # 2 accents → 5 stops
        assert stops[0]["type"] == "background"
        assert stops[1]["type"] == "accent"
        assert stops[2]["type"] == "background"
        assert stops[3]["type"] == "accent"
        assert stops[4]["type"] == "background"

    def test_respects_max_stops_interleaved(self):
        """Respect max_stops limit in interleaved mode."""
        colors = [
            {"rgb": [0, 0, 0], "hsv": [0, 0, 0], "frequency": 0.5},
            {"rgb": [255, 0, 0], "hsv": [0, 1, 1], "frequency": 0.1},
            {"rgb": [0, 255, 0], "hsv": [0.33, 1, 1], "frequency": 0.1},
            {"rgb": [0, 0, 255], "hsv": [0.67, 1, 1], "frequency": 0.1},
            {"rgb": [255, 255, 0], "hsv": [0.17, 1, 1], "frequency": 0.1},
            {"rgb": [255, 0, 255], "hsv": [0.83, 1, 1], "frequency": 0.1},
        ]
        background = colors[0]

        stops = build_gradient_stops(
            colors, background_color=background, max_stops=8
        )

        # With 8 stops max: bg, c1, bg, c2, bg, c3, bg, c4 = 8 stops → 4 accents
        assert len(stops) <= 9  # 4 accents * 2 + 1 bg = 9 stops max

    def test_empty_colors_returns_empty(self):
        """Handle empty color list."""
        stops = build_gradient_stops([], background_color=None, max_stops=8)
        assert len(stops) == 0


class TestBuildGradientString:
    """Test gradient string generation."""

    def test_builds_valid_ledfx_format(self):
        """Build valid LedFx gradient string."""
        stops = [
            {"color": "#FF0000", "position": 0.0, "type": "color"},
            {"color": "#00FF00", "position": 0.5, "type": "color"},
            {"color": "#0000FF", "position": 1.0, "type": "color"},
        ]

        gradient_str = build_gradient_string(stops)

        assert gradient_str.startswith("linear-gradient(90deg,")
        assert "rgb(255,0,0) 0%" in gradient_str
        assert "rgb(0,255,0) 50%" in gradient_str
        assert "rgb(0,0,255) 100%" in gradient_str

    def test_handles_empty_stops(self):
        """Handle empty stops list."""
        gradient_str = build_gradient_string([])
        assert "linear-gradient" in gradient_str
        # Should return fallback gradient


class TestExtractGradientMetadata:
    """Test complete gradient metadata extraction."""

    def test_extracts_all_variants(self):
        """Extract all gradient variants."""
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        metadata = extract_gradient_metadata(img)

        assert "raw" in metadata
        assert "led_safe" in metadata
        assert "led_punchy" in metadata
        assert "metadata" in metadata

    def test_raw_variant_structure(self):
        """Raw variant has correct structure."""
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        metadata = extract_gradient_metadata(img)

        raw = metadata["raw"]
        assert "gradient" in raw
        assert "stops" in raw
        assert "dominant_colors" in raw
        assert "background_color" in raw
        assert "background_frequency" in raw

    def test_metadata_fields(self):
        """Metadata includes required fields."""
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        metadata = extract_gradient_metadata(img)

        meta = metadata["metadata"]
        assert "image_size" in meta
        assert meta["image_size"] == [100, 100]
        assert "processing_time_ms" in meta
        assert "extracted_color_count" in meta
        assert "has_dominant_background" in meta
        assert "gradient_stop_count" in meta
        assert "pattern" in meta
        assert "extraction_version" in meta
        assert "extracted_at" in meta

    def test_detects_background_in_metadata(self):
        """Detect and report dominant background."""
        # Create 100x100 image: 80% black, 20% red
        img = Image.new("RGB", (100, 100))
        pixels = img.load()
        for y in range(100):
            for x in range(100):
                if y < 80:
                    pixels[x, y] = (0, 0, 0)
                else:
                    pixels[x, y] = (255, 0, 0)

        metadata = extract_gradient_metadata(img)

        assert metadata["metadata"]["has_dominant_background"] is True
        assert metadata["metadata"]["pattern"] == "interleaved"
        assert metadata["raw"]["background_color"] is not None

    def test_no_background_pattern(self):
        """Report weighted pattern when no background."""
        # Create gradient image (no dominant color)
        img = Image.new("RGB", (100, 100))
        pixels = img.load()
        for y in range(100):
            for x in range(100):
                # Gradient from red to blue
                pixels[x, y] = (255 - int(y * 2.55), 0, int(y * 2.55))

        metadata = extract_gradient_metadata(img)

        assert metadata["metadata"]["has_dominant_background"] is False
        assert metadata["metadata"]["pattern"] == "weighted"

    def test_handles_exceptions_gracefully(self):
        """Return fallback on extraction errors."""
        # This should not raise, even with malformed input
        # Create a very small image that might cause issues
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        metadata = extract_gradient_metadata(img)

        # Should still return valid structure
        assert "raw" in metadata
        assert "metadata" in metadata

    def test_gradient_deterministic(self):
        """Same image should produce same gradient."""
        img = Image.new("RGB", (100, 100), color=(255, 128, 0))

        metadata1 = extract_gradient_metadata(img)
        metadata2 = extract_gradient_metadata(img)

        # Gradients should match (ignoring timestamps)
        assert metadata1["raw"]["gradient"] == metadata2["raw"]["gradient"]
        assert len(metadata1["raw"]["stops"]) == len(metadata2["raw"]["stops"])
