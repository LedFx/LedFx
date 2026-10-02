"""The vendored Scalar bundle is the pinned release, byte for byte."""

import base64
import hashlib
import importlib
import io
import json
import re
import shutil
import tarfile
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

import pytest

DOCS = Path(__file__).resolve().parents[2] / "ledfx" / "api" / "v2" / "docs"


def test_bundle_matches_its_recorded_sha256() -> None:
    digest, name = (DOCS / "scalar.sha256").read_text(encoding="utf-8").split()
    assert name == "scalar.standalone.js"
    assert hashlib.sha256((DOCS / name).read_bytes()).hexdigest() == digest


def test_pinned_version_and_license() -> None:
    version = (DOCS / "SCALAR_VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    license_text = (DOCS / "SCALAR_LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License")


FILES = (
    "scalar.standalone.js",
    "scalar.sha256",
    "SCALAR_VERSION",
    "SCALAR_LICENSE",
    "docs.html",
)


def tarball(bundle: bytes, license: str = "MIT") -> bytes:
    """A registry-shaped package tarball: standalone.js and a package.json."""
    out = io.BytesIO()
    manifest = json.dumps({"license": license}).encode()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        for name, data in (
            ("package/dist/browser/standalone.js", bundle),
            ("package/package.json", manifest),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


def integrity(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


class Tool(NamedTuple):
    module: ModuleType
    docs: Path
    calls: list[str]


@pytest.fixture
def tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Tool:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "tools"))
    module = importlib.import_module("update_scalar")
    for name in FILES:
        shutil.copy(DOCS / name, tmp_path / name)
    monkeypatch.setattr(module, "DOCS", tmp_path)
    calls: list[str] = []

    packed = tarball(b"fake bundle")

    def fake_fetch(url: str) -> bytes:
        calls.append(url)
        if url == "https://registry.example/pkg.tgz":
            return packed
        if url.startswith("https://registry.npmjs.org/"):
            dist = {"tarball": "https://registry.example/pkg.tgz"}
            dist["integrity"] = integrity(packed)
            return json.dumps({"dist": dist}).encode()
        return b"MIT License\n..."

    monkeypatch.setattr(module, "fetch", fake_fetch)
    return Tool(module, tmp_path, calls)


def snapshot(directory: Path) -> dict[str, bytes]:
    return {name: (directory / name).read_bytes() for name in FILES}


def test_sync_in_step_is_an_offline_noop(tool: Tool) -> None:
    before = snapshot(tool.docs)
    tool.module.sync()
    assert tool.calls == []
    assert snapshot(tool.docs) == before


def test_sync_rebuilds_when_the_target_moves(tool: Tool) -> None:
    (tool.docs / "SCALAR_VERSION").write_text("9.9.9\n", encoding="utf-8")
    tool.module.sync()
    assert len(tool.calls) == 3
    assert "api-reference/9.9.9" in tool.calls[0]
    assert tool.calls[2].endswith("/main/LICENSE")
    assert (tool.docs / "scalar.standalone.js").read_bytes() == b"fake bundle"
    digest, name = (tool.docs / "scalar.sha256").read_text(encoding="utf-8").split()
    assert name == "scalar.standalone.js"
    assert digest == hashlib.sha256(b"fake bundle").hexdigest()
    assert (tool.docs / "SCALAR_LICENSE").read_bytes() == b"MIT License\n..."
    assert (tool.docs / "SCALAR_VERSION").read_text(encoding="utf-8") == "9.9.9\n"
    assert 'scalar.standalone.js?v=9.9.9"' in (tool.docs / "docs.html").read_text(
        encoding="utf-8"
    )


def test_non_mit_license_writes_nothing(
    tool: Tool, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tool.module.fetch

    def gpl(url: str) -> bytes:
        return b"GPL" if "LICENSE" in url else fake(url)

    monkeypatch.setattr(tool.module, "fetch", gpl)
    before = snapshot(tool.docs)
    with pytest.raises(SystemExit):
        tool.module.main("9.9.9")
    assert snapshot(tool.docs) == before


def test_a_package_not_declared_mit_writes_nothing(
    tool: Tool, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tool.module.fetch
    packed = tarball(b"fake bundle", license="GPL-3.0")

    def gpl_package(url: str) -> bytes:
        if url == "https://registry.example/pkg.tgz":
            return packed
        if url.startswith("https://registry.npmjs.org/"):
            dist = {"tarball": "https://registry.example/pkg.tgz"}
            dist["integrity"] = integrity(packed)
            return json.dumps({"dist": dist}).encode()
        return fake(url)

    monkeypatch.setattr(tool.module, "fetch", gpl_package)
    before = snapshot(tool.docs)
    with pytest.raises(SystemExit, match="not MIT"):
        tool.module.main("9.9.9")
    assert snapshot(tool.docs) == before


def test_integrity_mismatch_writes_nothing(
    tool: Tool, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tool.module.fetch

    def tampered(url: str) -> bytes:
        data = fake(url)
        return tarball(b"evil bundle") if url.endswith(".tgz") else data

    monkeypatch.setattr(tool.module, "fetch", tampered)
    before = snapshot(tool.docs)
    with pytest.raises(SystemExit, match="sha512 does not match"):
        tool.module.main("9.9.9")
    assert snapshot(tool.docs) == before


def test_network_errors_are_one_line(
    tool: Tool, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.reload(tool.module)  # the fixture faked fetch

    def refuse(url: str, timeout: int) -> None:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(module.urllib.request, "urlopen", refuse)
    with pytest.raises(SystemExit, match="could not fetch https://x: .*no route"):
        module.fetch("https://x")
