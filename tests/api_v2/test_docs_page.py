"""The offline API reference at /api/v2/docs."""

import hashlib
import json
import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from ledfx.api.v2.routes import meta
from ledfx.api.v2.routes.meta import CSP, DOCS_DIR

Client = TestClient[web.Request, web.Application]
REPO = Path(__file__).resolve().parents[2]
VERSION = (DOCS_DIR / "SCALAR_VERSION").read_text(encoding="utf-8").strip()


async def test_docs_page_has_the_csp_and_mounts_scalar(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/docs")
    assert response.status == 200
    assert response.content_type == "text/html"
    assert response.headers["Content-Security-Policy"] == CSP
    for directive in (
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ):
        assert directive in CSP
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    html = await response.text()
    assert '<div id="api-reference"' in html
    assert f'<script src="./docs/scalar.standalone.js?v={VERSION}"></script>' in html
    match = re.search(r"data-configuration='([^']*)'", html)
    assert match is not None
    assert json.loads(match[1]) == {
        "url": "./openapi.json",
        "withDefaultFonts": False,
        "hideClientButton": True,
        "hideTestRequestButton": True,
        "telemetry": False,
        "showDeveloperTools": "never",
        "agent": {"disabled": True},
        "mcp": {"disabled": True},
    }


async def test_the_page_urls_resolve_to_v2_routes(v2_client: Client) -> None:
    """Relative to /api/v2/docs, ./x means /api/v2/x: both must be served."""
    page = "http://ledfx.local/api/v2/docs"
    for relative in (f"./docs/scalar.standalone.js?v={VERSION}", "./openapi.json"):
        path = urljoin(page, relative).removeprefix("http://ledfx.local")
        assert (await v2_client.get(path)).status == 200, path


async def test_docs_script_is_cached_as_immutable(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/docs/scalar.standalone.js")
    assert response.status == 200
    assert response.content_type == "text/javascript"
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    digest = (DOCS_DIR / "scalar.sha256").read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(await response.read()).hexdigest() == digest


def test_the_page_markup_names_no_outside_host() -> None:
    html = (DOCS_DIR / "docs.html").read_text(encoding="utf-8")
    code = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    assert "http://" not in code
    assert "https://" not in code
    # the CSP blocks inline scripts, so every script must be a src= file
    assert all("src=" in tag for tag in re.findall(r"<script\b[^>]*>", code))


def test_sphinx_stages_the_reference_with_the_committed_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))  # conf.py prepends to it
    copy = runpy.run_path(str(REPO / "docs" / "conf.py"))["_copy_api_v2"]
    assert callable(copy)
    app = SimpleNamespace(outdir=str(tmp_path), builder=SimpleNamespace(format="html"))
    copy(app, None)
    out = tmp_path / "_static" / "api-v2"
    assert (out / "index.html").read_bytes() == (DOCS_DIR / "docs.html").read_bytes()
    assert (out / "docs" / "scalar.standalone.js").is_file()
    committed = REPO / "openapi" / "ledfx-v2.json"
    assert (out / "openapi.json").read_bytes() == committed.read_bytes()


@pytest.mark.parametrize("path", ["/api/v2/docs", "/api/v2/docs/scalar.standalone.js"])
async def test_a_missing_bundle_is_a_problem_not_an_empty_404(
    v2_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: str
) -> None:
    monkeypatch.setattr(meta, "DOCS_DIR", tmp_path)
    response = await v2_client.get(path)
    assert response.status == 500
    assert response.content_type == "application/problem+json"
    assert "not installed" in (await response.json())["detail"]


async def test_a_trailing_slash_redirects_to_the_page(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/docs/", allow_redirects=False)
    assert response.status == 308
    assert response.headers["Location"] == "/api/v2/docs"


async def test_the_docs_routes_are_served_but_not_in_the_contract(
    v2_client: Client,
) -> None:
    paths = (await (await v2_client.get("/api/v2/openapi.json")).json())["paths"]
    assert [p for p in paths if "docs" in p] == []
    committed = json.loads((REPO / "openapi" / "ledfx-v2.json").read_text("utf-8"))
    assert [p for p in committed["paths"] if "docs" in p] == []
    assert (await v2_client.get("/api/v2/docs")).status == 200
