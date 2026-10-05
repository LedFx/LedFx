"""GET /api/v2/openapi.json and ``ledfx --dump-openapi``."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from ledfx.api.v2.core.app import OPENAPI_KEY, mount_v2
from ledfx.api.v2.core.binding import LEDFX_KEY
from ledfx.api.v2.core.registry import build_standalone_spec
from ledfx.configuration.jsonshape import as_dict

Client = TestClient[web.Request, web.Application]


async def test_openapi_json_serves_the_built_spec_with_an_etag(
    v2_client: Client,
) -> None:
    response = await v2_client.get("/api/v2/openapi.json")
    assert response.status == 200
    assert response.content_type == "application/json"
    canonical = json.dumps(
        v2_client.app[OPENAPI_KEY].spec, sort_keys=True, separators=(",", ":")
    ).encode()
    assert await response.read() == canonical
    assert response.headers["ETag"] == f'"{hashlib.sha256(canonical).hexdigest()}"'


async def test_openapi_json_answers_304_to_its_own_etag(v2_client: Client) -> None:
    etag = (await v2_client.get("/api/v2/openapi.json")).headers["ETag"]
    cached = await v2_client.get(
        "/api/v2/openapi.json", headers={"If-None-Match": etag}
    )
    assert cached.status == 304
    assert cached.headers["ETag"] == etag
    assert await cached.read() == b""
    stale = await v2_client.get(
        "/api/v2/openapi.json", headers={"If-None-Match": '"not-this-one"'}
    )
    assert stale.status == 200


@pytest.mark.parametrize("header", ["*", "W/{etag}"])
async def test_openapi_json_if_none_match_follows_rfc_9110(
    v2_client: Client, header: str
) -> None:
    etag = (await v2_client.get("/api/v2/openapi.json")).headers["ETag"]
    response = await v2_client.get(
        "/api/v2/openapi.json", headers={"If-None-Match": header.format(etag=etag)}
    )
    assert response.status == 304


def test_mount_without_a_core_builds_the_spec() -> None:
    app = web.Application()
    mount_v2(app, None)
    assert LEDFX_KEY not in app
    assert "/api/v2/openapi.json" in as_dict(app[OPENAPI_KEY].spec["paths"])


@pytest.mark.timeout(120)
def test_dump_openapi_cli_matches_the_in_process_build(tmp_path: Path) -> None:
    out = tmp_path / "ledfx-v2.json"
    subprocess.run(
        [sys.executable, "-m", "ledfx", "--dump-openapi", str(out)],
        check=True,
        timeout=120,
    )
    text = out.read_text(encoding="utf-8")
    assert json.loads(text) == json.loads(json.dumps(build_standalone_spec()))
    # sorted keys, two-space indent, final newline: stable diffs when committed
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_a_failed_dump_leaves_the_target_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ledfx.__main__ import main

    def broken() -> dict[str, object]:
        raise RuntimeError("build failed")

    out = tmp_path / "ledfx-v2.json"
    out.write_text("committed\n", encoding="utf-8")
    monkeypatch.setattr("ledfx.api.v2.core.registry.build_standalone_spec", broken)
    monkeypatch.setattr(sys, "argv", ["ledfx", "--dump-openapi", str(out)])
    with pytest.raises(RuntimeError):
        main()
    assert out.read_text(encoding="utf-8") == "committed\n"
    assert list(tmp_path.iterdir()) == [out]
