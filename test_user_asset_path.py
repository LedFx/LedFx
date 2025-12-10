"""Quick test to verify user asset path resolution in open_gif()"""
import os
import tempfile
from PIL import Image
from ledfx.utils import open_gif

def create_test_gif(path):
    """Create a simple test GIF"""
    img = Image.new('RGB', (10, 10), color='red')
    img.save(path, format='GIF')

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
        
        if result is None:
            print("❌ FAILED: Plain path 'test.gif' did not resolve to user asset")
            return False
        else:
            print("✅ PASSED: Plain path 'test.gif' resolved to user asset")
            print(f"   Config dir: {tmpdir}")
            print(f"   Assets dir: {assets_dir}")
            print(f"   Expected: {test_gif_path}")
            result.close()
            return True

def test_builtin_still_works():
    """Test that builtin:// prefix still works"""
    # Test with a known built-in asset
    result = open_gif("builtin://skull.gif")
    
    if result is None:
        print("❌ FAILED: builtin://skull.gif did not load")
        return False
    else:
        print("✅ PASSED: builtin://skull.gif loaded successfully")
        result.close()
        return True

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
        
        if result is None:
            print("❌ FAILED: Nested path 'subfolder/nested.gif' did not resolve")
            return False
        else:
            print("✅ PASSED: Nested path 'subfolder/nested.gif' resolved to user asset")
            result.close()
            return True

if __name__ == "__main__":
    print("Testing user asset path resolution...\n")
    
    test1 = test_user_asset_path()
    print()
    test2 = test_builtin_still_works()
    print()
    test3 = test_nested_user_asset_path()
    print()
    
    if test1 and test2 and test3:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")
        exit(1)
