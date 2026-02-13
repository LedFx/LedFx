"""Integration tests for gradient extraction in ImageCache and assets."""

import os
import tempfile

import pytest
from PIL import Image

from ledfx.assets import list_assets, save_asset
from ledfx.libraries.cache import ImageCache


class TestImageCacheGradientIntegration:
    """Test gradient extraction in ImageCache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary directory for cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create ImageCache instance."""
        return ImageCache(temp_cache_dir, max_size_mb=10, max_items=10)

    def test_cache_put_extracts_gradients(self, cache):
        """Cache entry should include gradient metadata."""
        # Create test image data
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        # Cache the image
        url = "https://example.com/test.png"
        cache.put(
            url=url,
            data=image_data,
            content_type="image/png",
            etag=None,
            last_modified=None,
        )

        # Retrieve cached path
        cache_path = cache.get(url)
        assert cache_path is not None

        # Get cache entry metadata directly
        cache_key = cache._generate_cache_key(url, None)
        entry = cache.metadata["cache_entries"][cache_key]

        # Verify gradients are in entry
        assert "gradients" in entry
        assert entry["gradients"] is not None

        # Verify gradient structure
        gradients = entry["gradients"]
        assert "raw" in gradients
        assert "led_safe" in gradients
        assert "led_punchy" in gradients
        assert "metadata" in gradients

        # Verify raw variant structure
        raw = gradients["raw"]
        assert "gradient" in raw
        assert "stops" in raw
        assert "dominant_colors" in raw
        assert raw["gradient"].startswith("linear-gradient")

    def test_cache_put_handles_gradient_extraction_failure(self, cache):
        """Cache should continue even if gradient extraction fails."""
        # Create tiny 1x1 image that might stress extraction
        img = Image.new("RGB", (1, 1), color=(0, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        url = "https://example.com/tiny.png"
        cache.put(
            url=url,
            data=image_data,
            content_type="image/png",
            etag=None,
            last_modified=None,
        )

        # Image should still be cached
        cache_path = cache.get(url)
        assert cache_path is not None

        # Get cache entry metadata
        cache_key = cache._generate_cache_key(url, None)
        entry = cache.metadata["cache_entries"][cache_key]

        # Gradient might be None or present
        assert "gradients" in entry

    def test_cache_includes_all_gradient_variants(self, cache):
        """All three gradient variants should be present."""
        # Create colorful test image
        img = Image.new("RGB", (100, 100))
        pixels = img.load()
        for y in range(100):
            for x in range(100):
                if x < 33:
                    pixels[x, y] = (255, 0, 0)
                elif x < 66:
                    pixels[x, y] = (0, 255, 0)
                else:
                    pixels[x, y] = (0, 0, 255)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        url = "https://example.com/colors.png"
        cache.put(
            url=url,
            data=image_data,
            content_type="image/png",
            etag=None,
            last_modified=None,
        )

        cache_path = cache.get(url)
        assert cache_path is not None

        # Get cache entry metadata
        cache_key = cache._generate_cache_key(url, None)
        entry = cache.metadata["cache_entries"][cache_key]

        gradients = entry["gradients"]
        assert gradients is not None

        # Check all variants exist
        assert "raw" in gradients
        assert "led_safe" in gradients
        assert "led_punchy" in gradients

        # Verify each has required fields
        for variant_name in ["raw", "led_safe", "led_punchy"]:
            variant = gradients[variant_name]
            assert "gradient" in variant
            assert "stops" in variant
            assert len(variant["stops"]) > 0


class TestAssetGradientIntegration:
    """Test gradient extraction in asset storage."""

    @pytest.fixture
    def temp_assets_dir(self):
        """Create temporary directory for assets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_list_assets_includes_gradients(self, temp_assets_dir):
        """Asset listing should include gradient metadata."""
        # Create test image
        img = Image.new("RGB", (100, 100), color=(0, 128, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        # Save as asset
        success, abs_path, error = save_asset(
            config_dir=temp_assets_dir,
            relative_path="test.png",
            data=image_data,
            allow_overwrite=True,
        )

        assert success is True
        assert error is None

        # List assets
        assets = list_assets(temp_assets_dir)

        assert len(assets) == 1
        asset = assets[0]

        # Verify gradients are included
        assert "gradients" in asset
        assert asset["gradients"] is not None

        # Verify gradient structure
        gradients = asset["gradients"]
        assert "raw" in gradients
        assert "led_safe" in gradients
        assert "led_punchy" in gradients

    def test_list_assets_handles_gradient_extraction_failure(
        self, temp_assets_dir
    ):
        """Asset listing should continue even if gradient extraction fails."""
        # Create minimal image
        img = Image.new("RGB", (2, 2), color=(255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        save_asset(
            config_dir=temp_assets_dir,
            relative_path="small.png",
            data=image_data,
            allow_overwrite=True,
        )

        # Should still list the asset
        assets = list_assets(temp_assets_dir)
        assert len(assets) == 1

        # Gradient might be None or present
        assert "gradients" in assets[0]

    def test_asset_gradients_detect_background(self, temp_assets_dir):
        """Assets with dominant backgrounds should have interleaved gradients."""
        # Create image with 80% black background, 20% red
        img = Image.new("RGB", (100, 100))
        pixels = img.load()
        for y in range(100):
            for x in range(100):
                if y < 80:
                    pixels[x, y] = (0, 0, 0)
                else:
                    pixels[x, y] = (255, 0, 0)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_data = img_bytes.getvalue()

        save_asset(
            config_dir=temp_assets_dir,
            relative_path="bg_dominant.png",
            data=image_data,
            allow_overwrite=True,
        )

        assets = list_assets(temp_assets_dir)
        assert len(assets) == 1

        gradients = assets[0]["gradients"]
        assert gradients is not None

        # Should detect dominant background
        metadata = gradients["metadata"]
        assert metadata["has_dominant_background"] is True
        assert metadata["pattern"] == "interleaved"

        # Background color should be set
        assert gradients["raw"]["background_color"] is not None

    def test_multiple_assets_all_have_gradients(self, temp_assets_dir):
        """All assets in directory should have gradient metadata."""
        # Create multiple test images
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

        for i, color in enumerate(colors):
            img = Image.new("RGB", (50, 50), color=color)
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            image_data = img_bytes.getvalue()

            save_asset(
                config_dir=temp_assets_dir,
                relative_path=f"color_{i}.png",
                data=image_data,
                allow_overwrite=True,
            )

        # List all assets
        assets = list_assets(temp_assets_dir)
        assert len(assets) == 3

        # All should have gradients
        for asset in assets:
            assert "gradients" in asset
            assert asset["gradients"] is not None
            assert "raw" in asset["gradients"]
            assert "led_safe" in asset["gradients"]
            assert "led_punchy" in asset["gradients"]


# Import io for BytesIO
import io
