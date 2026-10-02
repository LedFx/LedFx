"""The OpenAPI builder, one rule per test, on a toy router."""

import json
import os
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer

from ledfx.api.v2.core import app as app_module
from ledfx.api.v2.core.app import API_VERSION, OPENAPI_KEY, mount_v2
from ledfx.api.v2.core.binding import BuildError, bind
from ledfx.api.v2.core.openapi import build_openapi
from ledfx.api.v2.core.partial import Partial
from ledfx.api.v2.core.router import Binary, Router
from ledfx.configuration.fields import X_REQUIRED, FromSource
from ledfx.configuration.jsonshape import as_dict
from ledfx.errors import Unavailable
from tests.test_utilities.fake_ledfx import fake_ledfx

REPO = Path(__file__).resolve().parents[2]
ToyId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
PROBLEM = {
    "content": {
        "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
    }
}


class Mode(StrEnum):
    SOLID = "solid"
    FADE = "fade"


class ToyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pixel_count: int = Field(ge=1, le=4096)
    mode: Mode = Mode.SOLID


class ToyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    config: ToyConfig


class Toy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=128)
    name: str = Field(max_length=64)
    config: ToyConfig
    source: Annotated[str, FromSource("virtuals")] = ""
    legacy: int = Field(0, json_schema_extra={X_REQUIRED: True})


class Stamp(BaseModel):
    """Validates an int, serializes a string: two components."""

    model_config = ConfigDict(extra="forbid")
    at_ms: int = Field(ge=0, le=10**12)

    @field_serializer("at_ms")
    def _as_text(self, value: int) -> str:
        return str(value)


router = Router(tag="toys")


@router.get("/toys")
async def list_toys(
    sort: Literal["name", "id"], tag: list[str] | None = None, limit: int = 10
) -> list[Toy]:
    """List toys.

    In manager order, filtered by tag.
    """
    return []


@router.post("/toys", status=201)
async def create_toy(body: ToyCreate) -> Toy:
    """Create a toy."""
    raise NotImplementedError


@router.get("/toys/{toy_id}", errors=[Unavailable])
async def get_toy(toy_id: ToyId) -> Toy:
    raise NotImplementedError


@router.patch("/toys/{toy_id}")
async def update_toy(toy_id: ToyId, body: Partial[ToyCreate]) -> Toy:
    raise NotImplementedError


@router.delete("/toys/{toy_id}", status=204)
async def delete_toy(toy_id: ToyId) -> None:
    return None


@router.get("/toys/{toy_id}/photo", responses={200: Binary("image/png")})
async def get_photo(toy_id: ToyId, request: web.Request) -> web.Response:
    raise NotImplementedError


@router.put("/stamps")
async def put_stamp(body: Stamp) -> Stamp:
    return body


SPEC = build_openapi([bind(spec) for spec in router.routes], version="9.9.9")


def _op(path: str, method: str) -> dict[str, object]:
    return as_dict(as_dict(as_dict(SPEC["paths"]).get("/api/v2" + path)).get(method))


def _schemas(spec: dict[str, object] = SPEC) -> dict[str, object]:
    return as_dict(as_dict(spec["components"]).get("schemas"))


def _json_schema(entry: object) -> object:
    content = as_dict(as_dict(entry).get("content"))
    return as_dict(content.get("application/json")).get("schema")


def test_document_header() -> None:
    assert SPEC["openapi"] == "3.1.0"
    info = as_dict(SPEC["info"])
    assert (info["title"], info["version"]) == ("LedFx API", "9.9.9")
    assert "ignore unknown fields in responses" in str(info["description"])
    assert SPEC["tags"] == [{"name": "toys"}]


def test_operations_are_named_and_described_by_their_handler() -> None:
    assert set(as_dict(SPEC["paths"])) == {
        "/api/v2/toys",
        "/api/v2/toys/{toy_id}",
        "/api/v2/toys/{toy_id}/photo",
        "/api/v2/stamps",
    }
    listing = _op("/toys", "get")
    assert listing["operationId"] == "list_toys"
    assert listing["tags"] == ["toys"]
    assert listing["summary"] == "List toys."
    assert listing["description"] == "In manager order, filtered by tag."
    create = _op("/toys", "post")
    assert create["summary"] == "Create a toy."
    assert "description" not in create
    assert "summary" not in _op("/toys/{toy_id}", "get")


def test_query_parameters() -> None:
    assert _op("/toys", "get")["parameters"] == [
        {
            "name": "sort",
            "in": "query",
            "required": True,
            "schema": {"enum": ["name", "id"], "type": "string"},
        },
        {
            "name": "tag",
            "in": "query",
            "required": False,
            "schema": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "default": None,
            },
            "style": "form",
            "explode": True,
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 10},
        },
    ]


def test_path_parameters_are_required() -> None:
    assert _op("/toys/{toy_id}", "get")["parameters"] == [
        {
            "name": "toy_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "minLength": 1, "maxLength": 128},
        }
    ]


def test_json_body_references_its_component() -> None:
    assert _op("/toys", "post")["requestBody"] == {
        "required": True,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/ToyCreate"}}
        },
    }


def test_patch_body_is_the_partial_schema() -> None:
    body = as_dict(_op("/toys/{toy_id}", "patch")["requestBody"])
    assert _json_schema(body) == {"$ref": "#/components/schemas/ToyCreatePartial"}
    partial = as_dict(_schemas()["ToyCreatePartial"])
    assert "required" not in partial
    config = as_dict(as_dict(partial["properties"])["config"])
    assert config == {"$ref": "#/components/schemas/ToyConfigPartial"}
    assert "required" not in as_dict(_schemas()["ToyConfigPartial"])
    # the full models keep theirs
    assert as_dict(_schemas()["ToyConfig-Input"])["required"] == ["pixel_count"]


def test_success_responses() -> None:
    created = as_dict(_op("/toys", "post")["responses"])["201"]
    assert _json_schema(created) == {"$ref": "#/components/schemas/Toy"}
    listed = as_dict(_op("/toys", "get")["responses"])["200"]
    assert _json_schema(listed) == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Toy"},
    }
    deleted = as_dict(_op("/toys/{toy_id}", "delete")["responses"])["204"]
    assert deleted == {"description": "No Content"}
    photo = as_dict(_op("/toys/{toy_id}/photo", "get")["responses"])["200"]
    assert photo == {"description": "OK", "content": {"image/png": {}}}


@pytest.mark.parametrize(
    ("path", "method", "codes"),
    [
        ("/toys", "get", {"200", "403", "422", "500"}),
        ("/toys", "post", {"201", "400", "403", "409", "413", "415", "422", "500"}),
        ("/toys/{toy_id}", "get", {"200", "403", "404", "422", "500", "503"}),
        (
            "/toys/{toy_id}",
            "patch",
            {"200", "400", "403", "404", "409", "413", "415", "422", "500"},
        ),
        ("/toys/{toy_id}", "delete", {"204", "403", "404", "409", "415", "422", "500"}),
        ("/toys/{toy_id}/photo", "get", {"200", "403", "404", "422", "500"}),
        ("/stamps", "put", {"200", "400", "403", "409", "413", "415", "422", "500"}),
    ],
)
def test_error_responses_are_problems(path: str, method: str, codes: set[str]) -> None:
    responses = as_dict(_op(path, method)["responses"])
    assert set(responses) == codes
    for code, response in responses.items():
        if code >= "400":
            assert as_dict(response)["content"] == PROBLEM["content"], code


def test_problem_component_is_always_present() -> None:
    empty = build_openapi([], version="0")
    assert {"Problem", "ProblemDetailError"} <= set(_schemas(empty))
    assert empty["paths"] == {}
    assert empty["tags"] == []


def test_models_that_serialize_differently_get_input_and_output_components() -> None:
    assert {"Stamp-Input", "Stamp-Output"} <= set(_schemas())
    assert "Stamp" not in _schemas()
    stamp = _op("/stamps", "put")
    body = as_dict(stamp["requestBody"])
    assert _json_schema(body) == {"$ref": "#/components/schemas/Stamp-Input"}
    ok = as_dict(stamp["responses"])["200"]
    assert _json_schema(ok) == {"$ref": "#/components/schemas/Stamp-Output"}


def test_backend_keys_are_stripped_and_markers_kept() -> None:
    assert X_REQUIRED not in json.dumps(SPEC)
    source = as_dict(as_dict(as_dict(_schemas()["Toy"])["properties"])["source"])
    assert source["x-ledfx-enum-source"] == "virtuals"


def test_two_models_with_one_component_name_are_refused() -> None:
    class A:
        class Item(BaseModel):
            # Deferred: its adapter holds a mock core schema until built.
            model_config = ConfigDict(defer_build=True)
            x: int

    class B:
        class Item(BaseModel):
            y: int

    clash = Router(tag="clash")

    @clash.post("/clash")
    async def clash_items(body: A.Item) -> B.Item:
        raise NotImplementedError

    with pytest.raises(BuildError, match="'Item'"):
        build_openapi([bind(spec) for spec in clash.routes], version="0")


def test_an_extension_whose_component_clashes_is_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A clashing extension router is logged and skipped."""

    class SystemInfo(BaseModel):  # the name of the built-in GET /system model
        model_config = ConfigDict(extra="forbid")
        other: int

    clash = Router(tag="clash")

    @clash.get("/clash")
    async def get_clash() -> SystemInfo:
        raise NotImplementedError

    builtins, _ = app_module.discover_routers()
    monkeypatch.setattr(app_module, "discover_routers", lambda: (builtins, [clash]))
    app = web.Application()
    mount_v2(app, fake_ledfx())
    assert "Skipping v2 extension router 'clash'" in caplog.text
    assert "/api/v2/clash" not in as_dict(app[OPENAPI_KEY].spec["paths"])
    assert "/api/v2/system" in as_dict(app[OPENAPI_KEY].spec["paths"])


def test_an_extension_taking_a_builtin_response_model_as_a_body_is_mounted(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The built-ins answer with SystemInfo (an open response schema); an
    extension taking it as a request body gets a closed one. A combined build
    names them apart, so this is no clash and the extension is mounted."""
    from ledfx.api.v2.models.system import SystemInfo

    echo = Router(tag="echo")

    @echo.post("/echo", status=204)
    async def post_echo(body: SystemInfo) -> None:
        raise NotImplementedError

    builtins, _ = app_module.discover_routers()
    monkeypatch.setattr(app_module, "discover_routers", lambda: (builtins, [echo]))
    app = web.Application()
    mount_v2(app, fake_ledfx())
    assert "Skipping v2 extension router" not in caplog.text
    assert "/api/v2/echo" in as_dict(app[OPENAPI_KEY].spec["paths"])


SNIPPETS = {
    "toy": "from tests.api_v2.test_openapi import SPEC as spec",
    "standalone": (
        "from ledfx.api.v2.core.registry import build_standalone_spec\n"
        "spec = build_standalone_spec()"
    ),
}


@pytest.mark.timeout(120)
@pytest.mark.parametrize("snippet", list(SNIPPETS.values()), ids=list(SNIPPETS))
def test_spec_is_stable_across_hash_seeds(snippet: str) -> None:
    code = f"import json, sys\n{snippet}\nsys.stdout.write(json.dumps(spec, sort_keys=True))"
    outputs = [
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        ).stdout
        for seed in ("0", "1")
    ]
    assert outputs[0]
    assert outputs[0] == outputs[1]


async def test_mount_stores_the_spec(
    v2_client: TestClient[web.Request, web.Application],
) -> None:
    spec = v2_client.app[OPENAPI_KEY].spec
    assert "/api/v2/system" in as_dict(spec["paths"])
    assert as_dict(spec["info"])["version"] == API_VERSION


def test_response_schemas_are_open_and_request_schemas_closed() -> None:
    schemas = _schemas()
    assert "additionalProperties" not in as_dict(schemas["Toy"])
    assert "additionalProperties" not in as_dict(schemas["Problem"])
    assert as_dict(schemas["ToyCreate"])["additionalProperties"] is False
    assert as_dict(schemas["ToyCreatePartial"])["additionalProperties"] is False


def test_a_partial_reuses_defs_it_leaves_unchanged() -> None:
    assert "Mode" in _schemas()
    assert "ModePartial" not in _schemas()
    config = as_dict(_schemas()["ToyConfigPartial"])
    mode = as_dict(as_dict(config["properties"])["mode"])
    assert '#/components/schemas/Mode"' in json.dumps(mode)


def _spec_for(router: Router) -> dict[str, object]:
    return build_openapi([bind(spec) for spec in router.routes], version="0")


def test_two_models_with_one_name_in_a_patch_body_are_refused() -> None:
    class A:
        class Item(BaseModel):
            x: int = 0

    class B:
        class Item(BaseModel):
            y: int = 0

    class Holder(BaseModel):
        a: A.Item = A.Item()
        b: B.Item = B.Item()

    clash = Router(tag="clash")

    @clash.patch("/h/{h_id}", status=204)
    async def patch_h(h_id: str, body: Partial[Holder]) -> None:
        return None

    with pytest.raises(BuildError, match="'Item'"):
        _spec_for(clash)


def test_a_recursive_model_under_partial_builds() -> None:
    class Node(BaseModel):
        name: str = ""
        children: list["Node"] = []

    rec = Router(tag="rec")

    @rec.patch("/nodes/{node_id}")
    async def patch_node(node_id: str, body: Partial[Node]) -> Node:
        raise NotImplementedError

    spec = _spec_for(rec)
    schema = as_dict(_schemas(spec)["NodePartial"])
    assert "required" not in schema
    assert "#/components/schemas/NodePartial" in json.dumps(schema)


def test_a_clash_between_builtins_is_not_blamed_on_extensions(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class A:
        class Item(BaseModel):
            x: int

    class B:
        class Item(BaseModel):
            y: int

    one, two, ext = Router(tag="one"), Router(tag="two"), Router(tag="ext")

    @one.get("/one")
    async def get_one() -> A.Item:
        raise NotImplementedError

    @two.get("/two")
    async def get_two() -> B.Item:
        raise NotImplementedError

    @ext.get("/ext")
    async def get_ext() -> int:
        return 1

    monkeypatch.setattr(app_module, "discover_routers", lambda: ([one, two], [ext]))
    with pytest.raises(BuildError, match="'Item'"):
        mount_v2(web.Application(), fake_ledfx())
    assert "Skipping" not in caplog.text
