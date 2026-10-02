"""Vendor the Scalar API reference bundle that /api/v2/docs serves offline.

Usage: uv run python tools/update_scalar.py <version>    e.g. 1.72.2

Writes ledfx/api/v2/docs/scalar.standalone.js, scalar.sha256 (checked by
tests/api_v2/test_scalar_vendored.py), SCALAR_VERSION and SCALAR_LICENSE.
Then bump the ?v= query on the script tag in docs.html to the new version.
"""

import hashlib
import re
import sys
import urllib.request
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "ledfx" / "api" / "v2" / "docs"
BUNDLE = "https://cdn.jsdelivr.net/npm/@scalar/api-reference@{version}/dist/browser/standalone.js"
# The npm package ships no LICENSE file; this is the MIT text its package.json declares.
LICENSE = "https://raw.githubusercontent.com/scalar/scalar/main/LICENSE"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"not a version: {version!r}")
    bundle = fetch(BUNDLE.format(version=version))
    digest = hashlib.sha256(bundle).hexdigest()
    (DOCS / "scalar.standalone.js").write_bytes(bundle)
    (DOCS / "scalar.sha256").write_text(
        f"{digest}  scalar.standalone.js\n", encoding="utf-8", newline="\n"
    )
    (DOCS / "SCALAR_VERSION").write_text(f"{version}\n", encoding="utf-8", newline="\n")
    (DOCS / "SCALAR_LICENSE").write_bytes(fetch(LICENSE))
    print(f"Scalar {version}: {len(bundle)} bytes, sha256 {digest}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
