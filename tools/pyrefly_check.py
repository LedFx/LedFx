"""Run Pyrefly against the interpreter and dependencies selected by uv.

Pyrefly otherwise discovers .venv independently, even when its executable
comes from another environment (for example, UV_PROJECT_ENVIRONMENT).
"""

import subprocess
import sys


def main() -> int:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pyrefly",
            "check",
            "--python-interpreter-path",
            sys.executable,
            *sys.argv[1:],
        ],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
