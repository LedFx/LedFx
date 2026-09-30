"""The /api/v2 mount: Problems for every error, the origin policy, /system, extensions."""

import logging
import re

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from pydantic import BaseModel, ConfigDict

from ledfx.api.v2.core import app as app_module
from ledfx.api.v2.core.app import BOUND_ROUTES_KEY, V2_PREFIX, mount_v2
from ledfx.api.v2.core.binding import LEDFX_KEY, BuildError
from ledfx.api.v2.core.router import Router
from ledfx.consts import PROJECT_VERSION
from tests.api_v2.conftest import Client
from tests.test_utilities.fake_ledfx import fake_ledfx


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str


toys = Router(tag="toys")


@toys.post("/notes", status=201)
async def create_note(body: Note) -> Note:
    return body


@toys.get("/notes/{note_id}")
async def get_note(note_id: str) -> Note:
    return Note(id=note_id, text="")


@toys.patch("/notes/{note_id}")
async def touch_note(note_id: str) -> Note:
    return Note(id=note_id, text="")


@toys.get("/boom")
async def boom() -> Note:
    raise RuntimeError("secret path /home/someone")


@toys.get("/stored")
async def stored() -> Note:
    return Note.model_validate({"id": 1})  # server-side bad data, not the request


@toys.get("/moved")
async def moved() -> Note:
    raise web.HTTPFound("/api/v2/system")


@pytest.fixture
def v2_routers() -> list[Router]:
    return [toys]


async def test_unknown_v2_paths_are_problem_404s(v2_client: Client) -> None:
    for path in ("/api/v2/nope", "/api/v2"):
        response = await v2_client.get(path)
        assert response.status == 404
        assert response.content_type == "application/problem+json"
        problem = await response.json()
        assert problem["type"] == "urn:ledfx:problem:not-found"
        assert re.fullmatch(r"req-[0-9a-f]{8}", problem["instance"])


async def test_a_wrong_method_is_405_with_allow(v2_client: Client) -> None:
    response = await v2_client.delete("/api/v2/system")
    assert response.status == 405
    assert "GET" in response.headers["Allow"]
    assert (await response.json())["type"] == "urn:ledfx:problem:method-not-allowed"


async def test_a_non_json_body_is_415(v2_client: Client) -> None:
    response = await v2_client.post(
        "/api/v2/notes", data=b"id=a", headers={"Content-Type": "text/plain"}
    )
    assert response.status == 415
    assert (await response.json())["type"] == (
        "urn:ledfx:problem:unsupported-media-type"
    )


async def test_a_body_over_5_mb_is_413(v2_client: Client) -> None:
    body = b'{"id": "a", "text": "' + b"x" * (5 * 1024 * 1024) + b'"}'
    response = await v2_client.post(
        "/api/v2/notes", data=body, headers={"Content-Type": "application/json"}
    )
    assert response.status == 413
    assert (await response.json())["type"] == "urn:ledfx:problem:too-large"


async def test_head_on_a_get_route_answers_like_get_without_a_body(
    v2_client: Client,
) -> None:
    get = await v2_client.get("/api/v2/system")
    head = await v2_client.head("/api/v2/system")
    assert head.status == 200
    assert head.content_type == "application/json"
    assert head.headers["Content-Length"] == get.headers["Content-Length"]
    assert await head.read() == b""
    assert (await v2_client.head("/api/v2/nope")).status == 404


async def test_a_crash_is_a_500_without_the_exception_text(
    v2_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="ledfx.api.v2.core.app"):
        response = await v2_client.get("/api/v2/boom")
    assert response.status == 500
    text = await response.text()
    assert "secret" not in text
    problem = await response.json()
    assert problem["detail"] == "Internal error"
    assert problem["instance"] in caplog.text
    assert "secret path" in caplog.text  # the log keeps the traceback


async def test_a_validation_error_in_a_handler_is_a_logged_500(
    v2_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="ledfx.api.v2.core.app"):
        response = await v2_client.get("/api/v2/stored")
    assert response.status == 500
    problem = await response.json()
    assert "errors" not in problem
    assert "id" not in problem["detail"]
    assert problem["instance"] in caplog.text
    assert "ValidationError" in caplog.text  # the log keeps the traceback


async def test_redirects_pass_through(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/moved", allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"] == "/api/v2/system"


async def test_a_create_links_to_its_item(v2_client: Client) -> None:
    response = await v2_client.post(
        "/api/v2/notes", json={"id": "dj bird", "text": "x"}
    )
    assert response.status == 201
    assert response.headers["Location"] == "/api/v2/notes/dj%20bird"


async def test_system_reports_the_api_versions(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/system")
    assert response.status == 200
    assert await response.json() == {
        "name": "LedFx Controller",
        "version": PROJECT_VERSION,
        "api_versions": ["v1", "v2"],
    }


ORIGIN = "http://localhost:3000"  # a local origin the policy allows


async def test_preflight_from_allowed_origin_allows_patch(v2_client: Client) -> None:
    response = await v2_client.options(
        "/api/v2/notes/a",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "PATCH"},
    )
    assert response.status == 200
    assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN


async def test_v2_error_from_allowed_origin_carries_cors(v2_client: Client) -> None:
    response = await v2_client.get("/api/v2/nope", headers={"Origin": ORIGIN})
    assert response.status == 404
    assert response.content_type == "application/problem+json"
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN


async def test_origin_refusal_under_v2_is_a_problem(v2_client: Client) -> None:
    refused = [
        await v2_client.get("/api/v2/system", headers={"Host": "evil.example.com"}),
        await v2_client.patch(
            "/api/v2/notes/a", json={}, headers={"Origin": "http://evil.example"}
        ),
    ]
    for response, reason in zip(refused, ("Host not allowed", "Origin not allowed")):
        body = await response.json()
        assert response.status == 403
        assert response.content_type == "application/problem+json"
        assert body["type"] == "urn:ledfx:problem:forbidden"
        assert body["title"] == "Forbidden"
        assert body["status"] == 403
        assert body["detail"].startswith(reason)


async def test_origin_refusal_on_a_v1_path_keeps_its_json(v2_client: Client) -> None:
    response = await v2_client.get("/api/info", headers={"Host": "evil.example.com"})
    assert response.status == 403
    assert response.content_type == "application/json"
    body = await response.json()
    assert body["status"] == "failed"
    assert body["payload"]["reason"].startswith("Host not allowed")


async def test_non_v2_paths_are_untouched() -> None:
    async def v1_info(request: web.Request) -> web.Response:
        raise web.HTTPNotFound(text="v1 says no")

    app = web.Application()
    app.router.add_get("/api/info", v1_info)
    mount_v2(app, fake_ledfx())
    async with Client(TestServer(app)) as client:
        response = await client.get("/api/info")
        assert (response.status, await response.text()) == (404, "v1 says no")
        assert response.content_type == "text/plain"
        for path in ("/api/nope", "/api/v2x"):
            response = await client.get(path)
            assert response.status == 404
            assert response.content_type == "text/plain"


def test_mount_stores_the_core_and_routes() -> None:
    app = web.Application()
    core = fake_ledfx()
    mount_v2(app, core)
    assert app[LEDFX_KEY] is core
    assert "get_system" in {r.operation_id for r in app[BOUND_ROUTES_KEY]}
    paths = {r.canonical for r in app.router.resources()}
    assert V2_PREFIX + "/system" in paths


def _broken_router() -> Router:
    broken = Router(tag="broken")

    @broken.get("/broken/{broken_id}")
    async def get_broken() -> Note:
        return Note(id="", text="")

    return broken


def test_a_broken_extension_is_logged_and_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    builtins, _ = app_module.discover_routers()
    monkeypatch.setattr(
        app_module, "discover_routers", lambda: (builtins, [_broken_router()])
    )
    app = web.Application()
    mount_v2(app, fake_ledfx())
    assert "Skipping v2 extension router 'broken'" in caplog.text
    assert "get_broken" not in {r.operation_id for r in app[BOUND_ROUTES_KEY]}


def test_an_extension_respelling_a_builtin_path_is_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    core, respelt = Router(tag="core"), Router(tag="respelt")

    @core.get("/n/{a}")
    async def get_n(a: str) -> Note:
        return Note(id=a, text="")

    @respelt.patch("/n/{b}")
    async def patch_n(b: str) -> Note:
        return Note(id=b, text="")

    monkeypatch.setattr(app_module, "discover_routers", lambda: ([core], [respelt]))
    app = web.Application()
    mount_v2(app, fake_ledfx())
    assert "Skipping v2 extension router 'respelt'" in caplog.text
    assert "different placeholder names" in caplog.text
    assert {r.operation_id for r in app[BOUND_ROUTES_KEY]} == {"get_n"}


def test_a_broken_builtin_router_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_module, "discover_routers", lambda: ([_broken_router()], [])
    )
    with pytest.raises(BuildError, match="has no parameter"):
        mount_v2(web.Application(), fake_ledfx())
