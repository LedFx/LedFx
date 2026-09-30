"""The response path: status, 204, Binary, encoding, validation, Location."""

import os

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ledfx.api.v2.core.binding import bind, link_locations
from ledfx.api.v2.core.encode import encode, validate_responses_enabled
from ledfx.api.v2.core.router import Binary, Router
from tests.api_v2.conftest import ServeRoutes


class Thing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    size_px: int = Field(ge=0)


class Aliased(BaseModel):
    kind: str = Field(serialization_alias="type")


def test_the_test_session_validates_responses() -> None:
    assert os.environ["LEDFX_API_VALIDATE_RESPONSES"] == "1"
    assert validate_responses_enabled()


def test_validation_is_off_unless_the_variable_is_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDFX_API_VALIDATE_RESPONSES", "0")
    assert not validate_responses_enabled()
    monkeypatch.delenv("LEDFX_API_VALIDATE_RESPONSES")
    assert not validate_responses_enabled()


def test_encode_uses_serialization_aliases() -> None:
    adapter = TypeAdapter[object](Aliased)
    assert encode(adapter, Aliased(kind="x")) == b'{"type":"x"}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_encode_refuses_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        encode(TypeAdapter[object](list[float]), [value])


async def test_declared_status_and_json_body(serve_routes: ServeRoutes) -> None:
    router = Router(tag="t")

    @router.post("/things/rebuild", status=202)
    async def rebuild() -> Thing:
        return Thing(id="a", size_px=1)

    client = await serve_routes(router)
    response = await client.post("/things/rebuild")
    assert response.status == 202
    assert response.content_type == "application/json"
    assert await response.json() == {"id": "a", "size_px": 1}


async def test_none_is_an_empty_204(serve_routes: ServeRoutes) -> None:
    router = Router(tag="t")

    @router.delete("/things/{thing_id}", status=204)
    async def delete_thing(thing_id: str) -> None:
        return None

    client = await serve_routes(router)
    response = await client.delete("/things/a")
    assert response.status == 204
    assert await response.read() == b""


async def test_binary_responses_pass_through(serve_routes: ServeRoutes) -> None:
    router = Router(tag="t")

    @router.get("/thing.png", responses={200: Binary("image/png")})
    async def thing_png() -> web.Response:
        return web.Response(body=b"\x89PNG", content_type="image/png")

    client = await serve_routes(router)
    response = await client.get("/thing.png")
    assert response.status == 200
    assert response.content_type == "image/png"
    assert await response.read() == b"\x89PNG"


def _request_for(router: Router) -> web.Request:
    return make_mocked_request(router.routes[0].method, router.routes[0].path)


async def test_an_undeclared_binary_status_raises() -> None:
    router = Router(tag="t")

    @router.get("/thing.png", responses={200: Binary("image/png")})
    async def teapot_png() -> web.Response:
        return web.Response(status=418)

    with pytest.raises(AssertionError, match="answered 418"):
        await bind(router.routes[0])(_request_for(router))


async def test_a_body_that_is_not_the_declared_type_raises() -> None:
    router = Router(tag="t")

    @router.get("/thing")
    async def wrong_shape() -> Thing:
        return Thing.model_construct(id="a", size_px=-1)  # skipped validation

    with pytest.raises(AssertionError, match="not its declared type"):
        await bind(router.routes[0])(_request_for(router))


async def test_a_none_route_that_returns_something_raises() -> None:
    router = Router(tag="t")

    @router.post("/thing/poke", status=204)
    async def poke() -> None:
        return "surprise"  # pyrefly: ignore[bad-return]

    with pytest.raises(AssertionError, match="returned"):
        await bind(router.routes[0])(_request_for(router))


async def test_a_mismatch_is_a_500_problem_through_the_middleware(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.get("/thing")
    async def wrong_thing() -> Thing:
        return Thing.model_construct(id="a", size_px=-1)

    client = await serve_routes(router)
    response = await client.get("/thing")
    assert response.status == 500
    assert (await response.json())["detail"] == "Internal error"


async def test_without_validation_the_body_is_sent_as_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDFX_API_VALIDATE_RESPONSES", "0")
    router = Router(tag="t")

    @router.get("/thing")
    async def lax_thing() -> Thing:
        return Thing.model_construct(id="a", size_px=-1)

    response = await bind(router.routes[0])(_request_for(router))
    assert isinstance(response, web.Response)
    assert response.body == b'{"id":"a","size_px":-1}'


def _things_router() -> Router:
    router = Router(tag="t")

    @router.post("/things", status=201)
    async def create_thing() -> Thing:
        return Thing(id="dj bird", size_px=1)

    @router.get("/things/{thing_id}")
    async def get_thing(thing_id: str) -> Thing:
        return Thing(id=thing_id, size_px=1)

    @router.post("/widgets", status=201)
    async def create_widget() -> Thing:
        return Thing(id="w", size_px=1)

    return router


def test_link_locations_marks_creates_with_an_item_get() -> None:
    routes = [bind(spec) for spec in _things_router().routes]
    link_locations(routes)
    assert {r.operation_id: r.location for r in routes} == {
        "create_thing": True,
        "get_thing": False,
        "create_widget": False,
    }


async def test_a_201_carries_a_percent_encoded_location() -> None:
    router = _things_router()
    routes = [bind(spec) for spec in router.routes]
    link_locations(routes)
    create_thing, _, create_widget = routes

    response = await create_thing(make_mocked_request("POST", "/api/v2/things"))
    assert response.status == 201
    assert response.headers["Location"] == "/api/v2/things/dj%20bird"

    response = await create_widget(make_mocked_request("POST", "/api/v2/widgets"))
    assert "Location" not in response.headers
