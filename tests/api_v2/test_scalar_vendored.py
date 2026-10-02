"""The vendored Scalar bundle is the pinned release, byte for byte."""

import hashlib
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "ledfx" / "api" / "v2" / "docs"


def test_bundle_matches_its_recorded_sha256() -> None:
    digest, name = (DOCS / "scalar.sha256").read_text(encoding="utf-8").split()
    assert name == "scalar.standalone.js"
    assert hashlib.sha256((DOCS / name).read_bytes()).hexdigest() == digest


def test_pinned_version_and_license() -> None:
    assert (DOCS / "SCALAR_VERSION").read_text(encoding="utf-8").strip() == "1.72.2"
    license_text = (DOCS / "SCALAR_LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License")
