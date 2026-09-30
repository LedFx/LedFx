"""Binding: each parameter source, the collected 422, and every BuildError."""

from enum import Enum
from typing import Annotated, Literal

import pytest
from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field

from ledfx.api.v2.core.binding import (
    LEDFX_KEY,
    BoundRoute,
    BuildError,
    Depends,
    LedFxDep,
    bind,
    check_unique,
)
from ledfx.api.v2.core.router import Binary, Router
from ledfx.configuration.fields import EnumSource, FromSource, register_enum_source
from tests.api_v2.conftest import ServeRoutes


class Colour(Enum):
    RED = "red"
    BLUE = "blue"


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    count: int = Field(ge=0)


class Ratio(BaseModel):
    x: float


class Cat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["cat"]
    lives: int


class Dog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["dog"]
    good: bool


Pet = Annotated[Cat | Dog, Field(discriminator="kind")]


def _check_colour(value: object) -> object:
    if value == "mauve":
        raise ValueError("not a live colour")
    return value


register_enum_source(
    "v2_test_colours", EnumSource(options=list, validate=_check_colour)
)


class Paint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    colour: Annotated[str, FromSource("v2_test_colours")]


# --- binding rows ------------------------------------------------------------


async def test_path_params_are_lax_and_percent_decoded(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.get("/items/{item_id}/{name}")
    async def get_item(item_id: int, name: str) -> dict[str, object]:
        return {"item_id": item_id, "name": name}

    client = await serve_routes(router)
    response = await client.get("/items/7/dj%20bird")
    assert response.status == 200
    assert await response.json() == {"item_id": 7, "name": "dj bird"}


async def test_query_params_defaults_lists_literals_and_enums(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.get("/search")
    async def search(
        q: str,
        tag: list[str] | None = None,
        limit: Annotated[int, Field(ge=1, le=10)] = 5,
        order: Literal["asc", "desc"] = "asc",
        colour: Colour = Colour.RED,
    ) -> dict[str, object]:
        return {
            "q": q,
            "tag": tag,
            "limit": limit,
            "order": order,
            "colour": colour.value,
        }

    client = await serve_routes(router)
    response = await client.get("/search?q=x&tag=a&tag=b&limit=3&colour=blue")
    assert await response.json() == {
        "q": "x",
        "tag": ["a", "b"],
        "limit": 3,
        "order": "asc",
        "colour": "blue",
    }
    response = await client.get("/search?q=x")
    assert (await response.json())["tag"] is None


async def test_bad_query_values_are_422_with_query_locs(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.get("/search")
    async def search(
        q: str, limit: Annotated[int, Field(ge=1)] = 5, order: Literal["a"] = "a"
    ) -> int:
        return limit

    client = await serve_routes(router)
    response = await client.get("/search?limit=0&order=z")
    assert response.status == 422
    assert response.content_type == "application/problem+json"
    body = await response.json()
    assert sorted(e["loc"] for e in body["errors"]) == [
        ["query", "limit"],
        ["query", "order"],
        ["query", "q"],
    ]


async def test_body_is_strict(serve_routes: ServeRoutes) -> None:
    router = Router(tag="t")

    @router.post("/items", status=201)
    async def create_item(body: Item) -> Item:
        return body

    client = await serve_routes(router)
    response = await client.post("/items", json={"name": "a", "count": 2})
    assert response.status == 201
    assert await response.json() == {"name": "a", "count": 2}
    response = await client.post("/items", json={"name": "a", "count": "2"})
    assert response.status == 422
    assert [e["loc"] for e in (await response.json())["errors"]] == [["body", "count"]]
    response = await client.post("/items", json={"name": "a", "count": 1, "x": 1})
    assert [e["type"] for e in (await response.json())["errors"]] == ["extra_forbidden"]


async def test_discriminated_union_body(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.put("/pet")
    async def put_pet(pet: Pet) -> Cat | Dog:
        return pet

    client = await serve_routes(router)
    response = await client.put("/pet", json={"kind": "dog", "good": True})
    assert await response.json() == {"kind": "dog", "good": True}
    response = await client.put("/pet", json={"kind": "fish"})
    assert response.status == 422
    assert (await response.json())["errors"][0]["type"] == "union_tag_invalid"


async def test_body_validation_uses_the_runtime_context(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.post("/paint")
    async def paint(body: Paint) -> Paint:
        return body

    client = await serve_routes(router)
    assert (await client.post("/paint", json={"colour": "teal"})).status == 200
    response = await client.post("/paint", json={"colour": "mauve"})
    assert response.status == 422
    assert (await response.json())["errors"][0]["loc"] == ["body", "colour"]


async def test_invalid_json_is_400_malformed(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.post("/items")
    async def post_item(body: Item) -> Item:
        return body

    client = await serve_routes(router)
    response = await client.post(
        "/items", data=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert response.status == 400
    assert (await response.json())["type"] == "urn:ledfx:problem:malformed"


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
async def test_non_finite_numbers_in_a_body_are_400_malformed(
    serve_routes: ServeRoutes, constant: bytes
) -> None:
    router = Router(tag="t")

    @router.post("/ratios")
    async def post_ratio(body: Ratio) -> Ratio:
        return body

    client = await serve_routes(router)
    response = await client.post(
        "/ratios",
        data=b'{"x": ' + constant + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status == 400
    assert (await response.json())["type"] == "urn:ledfx:problem:malformed"


async def test_path_query_and_body_errors_come_back_together(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.put("/items/{item_id}")
    async def put_item(item_id: int, body: Item, dry_run: bool = False) -> Item:
        return body

    client = await serve_routes(router)
    response = await client.put(
        "/items/x?dry_run=maybe", json={"name": "a", "count": -1}
    )
    assert response.status == 422
    body = await response.json()
    assert body["type"] == "urn:ledfx:problem:validation"
    assert sorted(e["loc"] for e in body["errors"]) == [
        ["body", "count"],
        ["path", "item_id"],
        ["query", "dry_run"],
    ]


async def test_request_and_dependencies_are_injected(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    def user_agent(request: web.Request) -> str:
        return request.headers.get("User-Agent", "")

    @router.get("/whoami")
    async def whoami(
        request: web.Request,
        ledfx: LedFxDep,
        agent: Annotated[str, Depends(user_agent)],
    ) -> dict[str, object]:
        return {
            "path": request.path,
            "core": ledfx is request.app[LEDFX_KEY],
            "agent": agent,
        }

    client = await serve_routes(router)
    response = await client.get("/whoami", headers={"User-Agent": "probe"})
    assert await response.json() == {"path": "/whoami", "core": True, "agent": "probe"}


async def test_a_non_json_body_on_an_unsafe_method_is_415(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.post("/items")
    async def post_item(body: Item) -> Item:
        return body

    @router.post("/items/refresh", status=204)
    async def refresh() -> None:
        return None

    client = await serve_routes(router)
    response = await client.post(
        "/items", data=b"name=a", headers={"Content-Type": "text/plain"}
    )
    assert response.status == 415
    assert (await response.json())["type"] == "urn:ledfx:problem:unsupported-media-type"
    # A bodiless command POST needs no Content-Type, and gets its 204.
    response = await client.post("/items/refresh")
    assert response.status == 204
    assert await response.read() == b""


# --- BuildError ----------------------------------------------------------------


def _bind_last(router: Router) -> BoundRoute:
    return bind(router.routes[-1])


def test_unbindable_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_x(mapping: dict[str, int]) -> int:
        return 1

    with pytest.raises(BuildError, match="cannot bind 'mapping'"):
        _bind_last(router)


def test_two_bodies() -> None:
    router = Router(tag="t")

    @router.post("/x")
    async def post_x(a: Item, b: Cat) -> int:
        return 1

    with pytest.raises(BuildError, match="two body parameters"):
        _bind_last(router)


def test_missing_return_annotation() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_nothing():  # the missing annotation is the test
        return 1

    with pytest.raises(BuildError, match="no return annotation"):
        _bind_last(router)


def test_missing_parameter_annotation() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_untyped(q) -> int:  # pyrefly: ignore[implicit-any-parameter]
        return 1

    with pytest.raises(BuildError, match="needs a type annotation"):
        _bind_last(router)


def test_placeholder_without_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x/{x_id}")
    async def get_orphan() -> int:
        return 1

    with pytest.raises(BuildError, match="has no parameter"):
        _bind_last(router)


def test_placeholder_with_a_pattern() -> None:
    router = Router(tag="t")

    @router.get(r"/x/{x_id:\d+}")
    async def get_pattern(x_id: int) -> int:
        return x_id

    with pytest.raises(BuildError, match="plain name"):
        _bind_last(router)


def test_none_return_needs_a_bodiless_status() -> None:
    router = Router(tag="t")

    @router.post("/x")
    async def post_none() -> None:
        return None

    with pytest.raises(BuildError, match="status=204"):
        _bind_last(router)


def test_a_return_type_pydantic_cannot_encode() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_raw() -> web.Response:
        return web.Response()

    with pytest.raises(BuildError, match="get_raw"):
        _bind_last(router)


def test_binary_routes_need_no_adapter() -> None:
    router = Router(tag="t")

    @router.get("/x.png", responses={200: Binary("image/png")})
    async def get_png() -> web.Response:
        return web.Response(body=b"", content_type="image/png")

    assert _bind_last(router).return_adapter is None


def test_a_get_or_delete_cannot_take_a_body() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_with_body(body: Item) -> Item:
        return body

    @router.delete("/y")
    async def delete_with_body(body: Item) -> None:
        return None

    for spec in router.routes:
        with pytest.raises(BuildError, match="can't take a body"):
            bind(spec)


def test_a_parameter_named_like_a_pydantic_attribute_is_a_build_error() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_query(model_config: str) -> int:
        return 1

    @router.get("/y/{json}")
    async def get_path(json: str) -> int:
        return 1

    for spec in router.routes:
        with pytest.raises(BuildError, match="clashes with a pydantic"):
            bind(spec)


def test_positional_only_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_pos(q: int, /) -> int:
        return q

    with pytest.raises(BuildError, match="callable by keyword"):
        _bind_last(router)


def test_var_positional_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_args(*args: int) -> int:
        return 1

    with pytest.raises(BuildError, match="callable by keyword"):
        _bind_last(router)


def test_var_keyword_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_kwargs(**kwargs: int) -> int:
        return 1

    with pytest.raises(BuildError, match="callable by keyword"):
        _bind_last(router)


def test_underscore_parameter() -> None:
    router = Router(tag="t")

    @router.get("/x")
    async def get_private(_q: int = 1) -> int:
        return _q

    with pytest.raises(BuildError, match="underscore"):
        _bind_last(router)


def test_204_cannot_return_a_body() -> None:
    router = Router(tag="t")

    @router.post("/x", status=204)
    async def post_body(body: Item) -> Item:
        return body

    with pytest.raises(BuildError, match="cannot carry a body"):
        _bind_last(router)


def test_bound_route_records_its_parts() -> None:
    router = Router(tag="t")

    @router.put("/items/{item_id}")
    async def replace_item(
        item_id: int, body: Item, ledfx: LedFxDep, tag: list[str] | None = None
    ) -> Item:
        return body

    route = _bind_last(router)
    assert route.operation_id == "replace_item"
    assert route.path_params == ("item_id",)
    assert route.query_params == ("tag",)
    assert route.list_params == frozenset({"tag"})
    assert (route.body_param, route.body_type, route.body_is_patch) == (
        "body",
        Item,
        False,
    )
    assert set(route.dep_params) == {"ledfx"}
    assert route.return_type is Item
    assert route.params_model is not None
    assert set(route.params_model.model_fields) == {"item_id", "tag"}


def test_check_unique_rejects_duplicate_method_and_path() -> None:
    router = Router(tag="t")

    @router.get("/items/{item_id}")
    async def get_one(item_id: int) -> int:
        return item_id

    @router.get("/items/{other_id}")
    async def get_two(other_id: int) -> int:
        return other_id

    with pytest.raises(BuildError, match="duplicate route GET /items/"):
        check_unique([bind(spec) for spec in router.routes])


def test_check_unique_rejects_duplicate_operation_ids() -> None:
    first, second = Router(tag="a"), Router(tag="b")

    async def get_same() -> int:
        return 1

    first.get("/a")(get_same)
    second.get("/b")(get_same)
    with pytest.raises(BuildError, match="duplicate operationId 'get_same'"):
        check_unique([bind(first.routes[0]), bind(second.routes[0])])


def test_check_unique_allows_one_path_with_several_methods() -> None:
    router = Router(tag="t")

    @router.get("/items")
    async def list_items() -> int:
        return 1

    @router.post("/items")
    async def add_item(body: Item) -> Item:
        return body

    check_unique([bind(spec) for spec in router.routes])
