#!/usr/bin/env python3
"""
LedFx Rust Effects Build Script

This script helps developers build and test Rust effects easily.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # Replace invalid characters instead of failing
            check=check,
        )
        if result.stdout:
            # Handle encoding issues on Windows CI
            try:
                print(result.stdout)
            except UnicodeEncodeError:
                print(
                    result.stdout.encode("ascii", errors="replace").decode(
                        "ascii"
                    )
                )
        if result.stderr:
            try:
                print(result.stderr, file=sys.stderr)
            except UnicodeEncodeError:
                print(
                    result.stderr.encode("ascii", errors="replace").decode(
                        "ascii"
                    ),
                    file=sys.stderr,
                )
        return result
    except UnicodeDecodeError:
        # Fallback to bytes mode if UTF-8 fails
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, check=check)
        if result.stdout:
            print(result.stdout.decode("utf-8", errors="replace"))
        if result.stderr:
            print(
                result.stderr.decode("utf-8", errors="replace"),
                file=sys.stderr,
            )
        return result


def build_rust(release=False):
    """Build the Rust effects module"""
    rust_dir = Path(__file__).parent  # We're already in rust directory
    cargo_toml = rust_dir.joinpath("Cargo.toml")

    if not cargo_toml.exists():
        print(
            "Error: Cargo.toml not found! Make sure you're in the rust directory."
        )
        return False

    cmd = [
        "uv",
        "run",
        "maturin",
        "develop",
        "--manifest-path",
        cargo_toml,
    ]
    if release:
        cmd.append("--release")

    try:
        run_command(cmd, cwd=rust_dir)
        print("[SUCCESS] Rust effects built successfully!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to build Rust effects: {e}")
        return False


def test_rust():
    """Test the Rust effects module"""
    # Run from project root to find ledfx module
    project_root = Path(__file__).parents[2]
    try:
        run_command(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from ledfx.rust import RUST_AVAILABLE; import sys; sys.exit(0 if RUST_AVAILABLE else 1)",
            ],
            cwd=project_root,
        )
        print("[SUCCESS] Rust effects module is working!")
        return True
    except subprocess.CalledProcessError:
        print("[ERROR] Rust effects are not available - module failed to load")
        return False
    except FileNotFoundError as e:
        print(f"[ERROR] Failed to run test command: {e}")
        return False


def clean_build():
    """Clean Rust build artifacts"""
    rust_dir = Path(__file__).parent  # We're already in rust directory
    target_dir = rust_dir.joinpath("target")

    if target_dir.exists():
        import shutil

        shutil.rmtree(target_dir)
        print("[CLEAN] Cleaned Rust build artifacts")
    else:
        print("[CLEAN] No build artifacts to clean")


def setup_development():
    """Set up development environment"""
    print("Setting up LedFx Rust effects development environment...")

    # Check if uv is available
    try:
        run_command(["uv", "self", "version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "[ERROR] uv not found. Please install uv first: https://docs.astral.sh/uv/"
        )
        return False

    # Check if Rust is available
    try:
        run_command(["rustc", "--version"])
        run_command(["cargo", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "[ERROR] Rust not found. Please use the 'Build Rust' VS Code task which will automatically install Rust, or install manually: https://rustup.rs/"
        )
        return False

    # Install Python dependencies (at repo root)
    try:
        rust_dir = Path(__file__).parent
        repo_root = rust_dir.parents[1].resolve()
        run_command(["uv", "sync", "--dev"], cwd=repo_root)
        print("[SUCCESS] Python dependencies installed")
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install Python dependencies")
        return False

    # Build Rust effects
    if not build_rust():
        return False

    # Test the build
    if not test_rust():
        return False

    print("[SUCCESS] Development environment set up successfully!")
    print("\nNext steps:")
    print("1. Run LedFx: uv run python -m ledfx --open-ui")
    print("2. Look for the new Rust-backed effects in the Matrix effects")
    print(f"3. Edit {Path('ledfx').joinpath('rust', 'src', 'lib.rs')} to add your own effects")
    print("4. Run this script again to rebuild after changes")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="LedFx Rust Effects Build Script"
    )
    parser.add_argument(
        "--setup", action="store_true", help="Set up development environment"
    )
    parser.add_argument(
        "--build", action="store_true", help="Build Rust effects"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Build in release mode (optimized)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Test Rust effects import"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean build artifacts"
    )

    args = parser.parse_args()

    ok = True
    if args.setup:
        ok = setup_development()
    elif args.clean:
        clean_build()
        ok = True  # Clean operation always succeeds
    elif args.test:
        ok = test_rust()
    elif args.build or args.release or not any(vars(args).values()):
        # Default action is build, also treat --release as a build trigger
        ok = build_rust(release=args.release)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
