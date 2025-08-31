#!/usr/bin/env python3
"""
LedFx Rust Effects Build Script

This script helps developers build and test Rust effects easily.
"""

import sys
import subprocess
import os
import argparse
from pathlib import Path

def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result

def build_rust_effects(release=False):
    """Build the Rust effects module"""
    rust_dir = Path(__file__).parent / "rust_effects"
    
    if not rust_dir.exists():
        print("Error: rust_effects directory not found!")
        return False
    
    cmd = ["uv", "run", "maturin", "develop"]
    if release:
        cmd.append("--release")
    
    try:
        result = run_command(cmd, cwd=rust_dir)
        print("✅ Rust effects built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build Rust effects: {e}")
        return False

def test_rust_effects():
    """Test the Rust effects module"""
    try:
        result = run_command(["python", "-c", "import ledfx_rust_effects; print('Rust effects import successful!')"])
        print("✅ Rust effects module is working!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to import Rust effects: {e}")
        return False

def clean_build():
    """Clean Rust build artifacts"""
    rust_dir = Path(__file__).parent / "rust_effects"
    target_dir = rust_dir / "target"
    
    if target_dir.exists():
        import shutil
        shutil.rmtree(target_dir)
        print("🧹 Cleaned Rust build artifacts")
    else:
        print("🧹 No build artifacts to clean")

def setup_development():
    """Set up development environment"""
    print("Setting up LedFx Rust effects development environment...")
    
    # Check if uv is available
    try:
        run_command(["uv", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ uv not found. Please install uv first: https://docs.astral.sh/uv/")
        return False
    
    # Check if Rust is available
    try:
        run_command(["rustc", "--version"])
        run_command(["cargo", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Rust not found. Please install Rust: https://rustup.rs/")
        return False
    
    # Install Python dependencies
    try:
        run_command(["uv", "sync", "--dev"])
        print("✅ Python dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies")
        return False
    
    # Build Rust effects
    if not build_rust_effects():
        return False
    
    # Test the build
    if not test_rust_effects():
        return False
    
    print("🎉 Development environment set up successfully!")
    print("\nNext steps:")
    print("1. Run LedFx: uv run python -m ledfx --open-ui")
    print("2. Look for 'The Rusty One' effect in the matrix effects")
    print("3. Edit rust_effects/src/lib.rs to add your own effects")
    print("4. Run this script again to rebuild after changes")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="LedFx Rust Effects Build Script")
    parser.add_argument("--setup", action="store_true", help="Set up development environment")
    parser.add_argument("--build", action="store_true", help="Build Rust effects")
    parser.add_argument("--release", action="store_true", help="Build in release mode (optimized)")
    parser.add_argument("--test", action="store_true", help="Test Rust effects import")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_development()
    elif args.clean:
        clean_build()
    elif args.test:
        test_rust_effects()
    elif args.build or not any(vars(args).values()):
        # Default action is build
        build_rust_effects(release=args.release)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
