"""
Playwright E2E Test Setup and Runner Script

This script helps set up and run Playwright E2E tests for LedFx.
"""

import argparse
import os
import subprocess
import sys


def run_command(cmd, description, check=True):
    """Run a shell command and handle errors."""
    print(f"\n{'=' * 60}")
    print(f"{description}")
    print(f"{'=' * 60}")
    print(f"Running: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"\n❌ Error: Command not found: {cmd[0]}")
        print("Make sure all dependencies are installed.")
        return False


def setup_playwright():
    """Install Playwright and its browsers."""
    print("\n🎭 Setting up Playwright for E2E testing...\n")
    
    # Install Python dependencies
    if not run_command(
        ["uv", "sync", "--group", "dev"],
        "Installing Python dependencies with dev group"
    ):
        return False
    
    # Install Playwright browsers
    if not run_command(
        ["uv", "run", "playwright", "install", "chromium"],
        "Installing Playwright Chromium browser"
    ):
        return False
    
    print("\n✅ Playwright setup complete!")
    return True


def run_tests(args):
    """Run E2E tests with specified options."""
    print("\n🧪 Running Playwright E2E tests...\n")
    
    # Build pytest command
    cmd = ["uv", "run", "pytest", "tests/e2e", "-m", "e2e"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add specific test file or test
    if args.test:
        cmd.append(args.test)
    
    # Environment variables
    env = os.environ.copy()
    
    if args.headed:
        env["HEADLESS"] = "false"
    
    if args.slow_mo:
        env["SLOW_MO"] = str(args.slow_mo)
    
    if args.video:
        env["VIDEO"] = "true"
    
    if args.debug:
        env["PWDEBUG"] = "1"
    
    # Run tests
    print(f"Environment: HEADLESS={env.get('HEADLESS', 'true')}, "
          f"SLOW_MO={env.get('SLOW_MO', '0')}, "
          f"VIDEO={env.get('VIDEO', 'false')}")
    
    result = subprocess.run(cmd, env=env)
    return result.returncode == 0


def show_trace(trace_file):
    """Open Playwright trace viewer."""
    print(f"\n🔍 Opening trace viewer for: {trace_file}\n")
    
    run_command(
        ["uv", "run", "playwright", "show-trace", trace_file],
        "Opening Playwright trace viewer",
        check=False
    )


def list_artifacts():
    """List available test artifacts."""
    print("\n📁 Test Artifacts:\n")
    
    artifacts = {
        "Screenshots": "tests/e2e/screenshots",
        "Videos": "tests/e2e/videos",
        "Traces": "tests/e2e/traces",
    }
    
    for name, path in artifacts.items():
        if os.path.exists(path):
            files = os.listdir(path)
            if files:
                print(f"\n{name} ({path}):")
                for f in files:
                    print(f"  - {f}")
            else:
                print(f"\n{name} ({path}): Empty")
        else:
            print(f"\n{name} ({path}): Not found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LedFx Playwright E2E Test Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup Playwright
  python run_e2e_tests.py --setup
  
  # Run all E2E tests
  python run_e2e_tests.py
  
  # Run with visible browser
  python run_e2e_tests.py --headed
  
  # Run specific test
  python run_e2e_tests.py --test tests/e2e/test_homepage.py
  
  # Run in debug mode
  python run_e2e_tests.py --debug
  
  # View trace from failed test
  python run_e2e_tests.py --trace tests/e2e/traces/test_name.zip
  
  # List test artifacts
  python run_e2e_tests.py --list-artifacts
        """
    )
    
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Install Playwright and browsers"
    )
    
    parser.add_argument(
        "--test",
        help="Specific test file or test to run"
    )
    
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run tests with visible browser"
    )
    
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=0,
        help="Slow down test execution by N milliseconds"
    )
    
    parser.add_argument(
        "--video",
        action="store_true",
        help="Record video of test execution"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode with Playwright Inspector"
    )
    
    parser.add_argument(
        "--trace",
        help="Open trace file in Playwright trace viewer"
    )
    
    parser.add_argument(
        "--list-artifacts",
        action="store_true",
        help="List available test artifacts (screenshots, videos, traces)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose test output"
    )
    
    args = parser.parse_args()
    
    # Handle different commands
    if args.setup:
        success = setup_playwright()
        sys.exit(0 if success else 1)
    
    elif args.trace:
        show_trace(args.trace)
        sys.exit(0)
    
    elif args.list_artifacts:
        list_artifacts()
        sys.exit(0)
    
    else:
        # Run tests
        success = run_tests(args)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
