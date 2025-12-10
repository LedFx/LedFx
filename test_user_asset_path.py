"""Quick test to verify user asset path resolution in open_gif()"""

import os
import tempfile

from PIL import Image

from ledfx.utils import open_gif


def create_test_gif(path):
    """Create a simple test GIF"""
    img = Image.new("RGB", (10, 10), color="red")
    img.save(path, format="GIF")


def test_user_asset_path():
    """Test that plain paths resolve to config_dir/assets/"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create assets directory
        assets_dir = os.path.join(tmpdir, "assets")
        os.makedirs(assets_dir)

        # Create test GIF in assets directory
        test_gif_path = os.path.join(assets_dir, "test.gif")
        create_test_gif(test_gif_path)

        # Test plain path resolution (should resolve to config_dir/assets/test.gif)
        result = open_gif("test.gif", config_dir=tmpdir)

        assert (
            result is not None
        ), "Plain path 'test.gif' did not resolve to user asset"
        result.close()


def test_builtin_still_works():
    """Test that builtin:// prefix still works"""
    # Test with a known built-in asset
    result = open_gif("builtin://skull.gif")

    assert result is not None, "builtin://skull.gif did not load"
    result.close()


def test_nested_user_asset_path():
    """Test that nested paths work for user assets"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested assets directory
        assets_dir = os.path.join(tmpdir, "assets", "subfolder")
        os.makedirs(assets_dir)

        # Create test GIF in nested directory
        test_gif_path = os.path.join(assets_dir, "nested.gif")
        create_test_gif(test_gif_path)

        # Test nested path resolution
        result = open_gif("subfolder/nested.gif", config_dir=tmpdir)

        assert (
            result is not None
        ), "Nested path 'subfolder/nested.gif' did not resolve"
        result.close()


if __name__ == "__main__":
    print("Testing user asset path resolution...\n")

    print("Test 1: User asset path")
    test_user_asset_path()
    print("✅ PASSED\n")

    print("Test 2: Builtin still works")
    test_builtin_still_works()
    print("✅ PASSED\n")

    print("Test 3: Nested user asset path")
    test_nested_user_asset_path()
    print("✅ PASSED\n")

    print("🎉 All tests passed!")
