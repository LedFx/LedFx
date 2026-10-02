"""Vendor the Scalar API reference bundle that /api/v2/docs serves offline.

Usage:
    uv run python tools/update_scalar.py <version>   e.g. 1.72.2
    uv run python tools/update_scalar.py --sync

The bundle comes from the npm registry tarball and is verified against its
dist.integrity (sha512); a mismatch refuses. Each bump adds about 1.25 MB of
compressed history (the bundle is 4.4 MB), so bump deliberately.

Writes ledfx/api/v2/docs/scalar.standalone.js, scalar.sha256 (checked by
tests/api_v2/test_scalar_vendored.py), SCALAR_VERSION and SCALAR_LICENSE, and
points the ?v= cache-buster on the script tag in docs.html at the version.

--sync takes the target from SCALAR_VERSION and rebuilds only if docs.html's
?v= differs. Renovate bumps SCALAR_VERSION; the scalar-vendored prek hook runs
--sync in the autofix workflow, which commits the rebuilt bundle to the PR.
In step, --sync exits 0 without touching the network.
"""

import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "ledfx" / "api" / "v2" / "docs"
# The registry's metadata carries dist.tarball and dist.integrity (sha512 of
# the tarball), so the bundle is verified against npm, not trusted from a CDN.
REGISTRY = "https://registry.npmjs.org/@scalar/api-reference/{version}"
MEMBER = "package/dist/browser/standalone.js"
# The npm package ships no LICENSE file and the scalar repo has no per-package
# release tags, so the text comes from the repo; the verified tarball's own
# package.json must declare MIT.
LICENSE = "https://raw.githubusercontent.com/scalar/scalar/main/LICENSE"
MANIFEST = "package/package.json"
MAX_BYTES = 20 * 1024 * 1024


def fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"could not fetch {url}: {exc}") from exc
    if len(data) > MAX_BYTES:
        raise SystemExit(f"{url} is larger than {MAX_BYTES} bytes; refusing")
    return data


def fetch_bundle(version: str) -> bytes:
    """standalone.js from the registry tarball, after checking dist.integrity."""
    url = REGISTRY.format(version=version)
    try:
        dist = json.loads(fetch(url))["dist"]
        tarball, integrity = dist["tarball"], dist["integrity"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"{url}: no dist.tarball and dist.integrity") from exc
    data = fetch(tarball)
    algorithm, _, expected = integrity.partition("-")
    if algorithm != "sha512":
        raise SystemExit(f"{url}: integrity {integrity!r} is not sha512")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode()
    if actual != expected:
        raise SystemExit(
            f"{tarball}: sha512 does not match the registry; not vendoring"
        )
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = archive.extractfile(MEMBER)
            if member is None:
                raise KeyError(MEMBER)
            bundle = member.read(MAX_BYTES + 1)
            manifest = archive.extractfile(MANIFEST)
            if manifest is None:
                raise KeyError(MANIFEST)
            declared = json.loads(manifest.read(MAX_BYTES)).get("license")
    except (tarfile.TarError, KeyError, ValueError) as exc:
        raise SystemExit(f"{tarball}: no {MEMBER} or {MANIFEST}: {exc}") from exc
    if declared != "MIT":
        raise SystemExit(f"{tarball}: package.json declares {declared!r}, not MIT")
    if len(bundle) > MAX_BYTES:
        raise SystemExit(f"{MEMBER} is larger than {MAX_BYTES} bytes; refusing")
    return bundle


SCRIPT_TAG = r"(scalar\.standalone\.js\?v=)\d+\.\d+\.\d+"


def main(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"not a version: {version!r}")
    # Fetch everything before writing anything, so a bad fetch leaves the tree intact.
    bundle = fetch_bundle(version)
    license_text = fetch(LICENSE)
    if not license_text.startswith(b"MIT License"):
        raise SystemExit(
            "licence text does not start with 'MIT License'; not vendoring"
        )
    html = (DOCS / "docs.html").read_text(encoding="utf-8")
    html, count = re.subn(SCRIPT_TAG, rf"\g<1>{version}", html)
    if count != 1:
        raise SystemExit(
            f"docs.html: expected one scalar script tag with ?v=, found {count}"
        )
    digest = hashlib.sha256(bundle).hexdigest()
    (DOCS / "scalar.standalone.js").write_bytes(bundle)
    (DOCS / "scalar.sha256").write_text(
        f"{digest}  scalar.standalone.js\n", encoding="utf-8", newline="\n"
    )
    (DOCS / "SCALAR_VERSION").write_text(f"{version}\n", encoding="utf-8", newline="\n")
    (DOCS / "SCALAR_LICENSE").write_bytes(license_text)
    (DOCS / "docs.html").write_text(html, encoding="utf-8", newline="\n")
    print(f"Scalar {version}: {len(bundle)} bytes, sha256 {digest}")


def sync() -> None:
    target = (DOCS / "SCALAR_VERSION").read_text(encoding="utf-8").strip()
    match = re.search(SCRIPT_TAG, (DOCS / "docs.html").read_text(encoding="utf-8"))
    built = match.group(0).rsplit("=", 1)[1] if match else None
    if built == target:
        return
    print(f"Scalar bundle is {built}, SCALAR_VERSION wants {target}: rebuilding")
    main(target)


if __name__ == "__main__":
    if sys.argv[1:] == ["--sync"]:
        sync()
    elif len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        main(sys.argv[1])
    else:
        raise SystemExit(__doc__)
