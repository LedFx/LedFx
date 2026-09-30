"""Binding: a handler's signature becomes request parsing, once, at app
build. BoundRoute is the aiohttp handler for one route."""

import inspect
import re
import types
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
    NewType,
    Union,
    get_args,
    get_origin,
)
from urllib.parse import quote

from aiohttp import web
from pydantic import (
    BaseModel,
    PydanticUserError,
    TypeAdapter,
    ValidationError,
    create_model,
)

from ledfx.api.v2.core.encode import encode, validate_responses_enabled
from ledfx.api.v2.core.partial import Patch, aliased_field, partial_model
from ledfx.api.v2.core.problem import (
    ProblemDetailError,
    ProblemError,
    json_body,
    validation_errors,
    validation_problem,
)
from ledfx.api.v2.core.router import RouteSpec
from ledfx.configuration.fields import RUNTIME_CONTEXT

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_NO_BODY_METHODS = frozenset({"GET", "HEAD", "DELETE"})
_PLACEHOLDER = re.compile(r"\{([^}]*)\}")
_SCALARS = (str, int, float, bool)


class BuildError(Exception):
    """A route the app refuses to build."""


@dataclass(frozen=True)
class Depends:
    fn: Callable[[web.Request], object]


LEDFX_KEY: web.AppKey["LedFxCore"] = web.AppKey("ledfx")


def get_ledfx(request: web.Request) -> "LedFxCore":
    return request.app[LEDFX_KEY]


LedFxDep = Annotated["LedFxCore", Depends(get_ledfx)]


@dataclass
class BoundRoute:
    spec: RouteSpec
    operation_id: str
    params_model: type[BaseModel] | None
    body_param: str | None
    body_adapter: TypeAdapter[object] | None
    body_is_patch: bool
    dep_params: Mapping[str, Depends]
    request_param: str | None
    return_adapter: TypeAdapter[object] | None
    path_params: tuple[str, ...] = ()
    query_params: tuple[str, ...] = ()
    list_params: frozenset[str] = frozenset()
    body_type: object = None  # the body annotation; M for Partial[M]
    return_type: object = None  # the return annotation
    patch_model: type[BaseModel] | None = None  # M for a Partial[M] body
    location: bool = False  # set by link_locations: 201s answer with Location

    async def __call__(self, request: web.Request) -> web.StreamResponse:
        self._check_media_type(request)
        kwargs: dict[str, object] = {}
        errors = self._bind_params(request, kwargs)
        if self.body_param is not None:
            errors += await self._bind_body(request, self.body_param, kwargs)
        if errors:
            raise validation_problem(errors)
        for name, dep in self.dep_params.items():
            kwargs[name] = dep.fn(request)
        if self.request_param is not None:
            kwargs[self.request_param] = request
        result = await self.spec.handler(**kwargs)
        return self._respond(request, result)

    def _check_media_type(self, request: web.Request) -> None:
        # A body on an unsafe method must be JSON. Bodiless command POSTs pass.
        if request.method not in _UNSAFE_METHODS or not request.body_exists:
            return
        if request.content_type != "application/json":
            raise ProblemError(
                415,
                "unsupported-media-type",
                "Unsupported media type",
                "Send the request body as application/json",
            )

    def _bind_params(
        self, request: web.Request, kwargs: dict[str, object]
    ) -> list[ProblemDetailError]:
        if self.params_model is None:
            return []
        raw: dict[str, object] = {n: request.match_info[n] for n in self.path_params}
        for name in self.query_params:
            if name in self.list_params:
                if name in request.query:
                    raw[name] = request.query.getall(name)
            elif name in request.query:
                raw[name] = request.query[name]
        try:
            params = self.params_model.model_validate(raw)
        except ValidationError as err:
            errors = validation_errors(err)
            for error in errors:
                source = "path" if error.loc[0] in self.path_params else "query"
                error.loc.insert(0, source)
            return errors
        for name in (*self.path_params, *self.query_params):
            kwargs[name] = getattr(params, name)
        return []

    async def _bind_body(
        self, request: web.Request, name: str, kwargs: dict[str, object]
    ) -> list[ProblemDetailError]:
        raw = await request.read()
        if self.patch_model is not None:
            try:
                kwargs[name] = Patch.parse(self.patch_model, raw)
            except ProblemError as err:
                if err.status != 422 or err.errors is None:
                    raise
                return err.errors
            return []
        if self.body_adapter is None:
            raise AssertionError("a body parameter always has an adapter")
        json_body(raw)  # a 400 for invalid JSON, NaN and Infinity
        try:
            kwargs[name] = self.body_adapter.validate_json(
                raw, strict=True, context=RUNTIME_CONTEXT
            )
        except ValidationError as err:
            return validation_errors(err, ("body",))
        return []

    def _respond(self, request: web.Request, result: object) -> web.StreamResponse:
        check = validate_responses_enabled()
        if self.spec.status in self.spec.responses:  # Binary
            if not isinstance(result, web.StreamResponse):
                raise TypeError(f"{self.operation_id} must return a web.StreamResponse")
            declared = result.status == self.spec.status
            if check and not declared and result.status not in self.spec.responses:
                raise AssertionError(
                    f"{self.operation_id} answered {result.status}, "
                    "which its route does not declare"
                )
            return result
        if self.return_adapter is None:  # -> None
            if check and result is not None:
                raise AssertionError(f"{self.operation_id} is -> None but returned")
            return web.Response(status=self.spec.status)
        body = encode(self.return_adapter, result)
        if check:
            # Round-trip what we send: this also catches a model instance that
            # was built without validation.
            try:
                self.return_adapter.validate_json(body, strict=True)
            except ValidationError as err:
                raise AssertionError(
                    f"{self.operation_id} returned a body that is not its "
                    f"declared type: {err}"
                ) from err
        response = web.Response(
            status=self.spec.status, body=body, content_type="application/json"
        )
        item_id = getattr(result, "id", None)
        if self.location and item_id is not None:
            base = request.rel_url.raw_path.rstrip("/")
            response.headers["Location"] = f"{base}/{quote(str(item_id), safe='')}"
        return response


def _unwrap(annotation: object) -> object:
    """Strip Annotated and NewType down to the underlying type."""
    while True:
        if get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        elif isinstance(annotation, NewType):
            annotation = annotation.__supertype__
        else:
            return annotation


def _is_union(annotation: object) -> bool:
    return get_origin(annotation) in (Union, types.UnionType)


def _is_scalar(annotation: object) -> bool:
    annotation = _unwrap(annotation)
    if get_origin(annotation) is Literal:
        return True
    if _is_union(annotation):
        return all(a is type(None) or _is_scalar(a) for a in get_args(annotation))
    return isinstance(annotation, type) and (
        issubclass(annotation, Enum) or annotation in _SCALARS
    )


def _list_item(annotation: object) -> object | None:
    """The item type of list[T] (or list[T] | None), else None."""
    annotation = _unwrap(annotation)
    if _is_union(annotation):
        members = [a for a in get_args(annotation) if a is not type(None)]
        if len(members) != 1:
            return None
        annotation = _unwrap(members[0])
    if get_origin(annotation) is list:
        return get_args(annotation)[0]
    return None


def _is_body(annotation: object) -> bool:
    """A model, or a union of models (Annotated, e.g. with a discriminator)."""
    annotation = _unwrap(annotation)
    if _is_union(annotation):
        return all(_is_body(a) for a in get_args(annotation))
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _depends(annotation: object) -> Depends | None:
    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, Depends):
                return meta
    return None


def _check_not_a_model_attribute(where: str, param_name: str) -> None:
    # Path and query parameters become fields of a pydantic model; a name that
    # BaseModel already has (model_config, json, copy...) breaks or shadows it.
    if hasattr(BaseModel, param_name):
        raise BuildError(
            f"{where}: parameter {param_name!r} clashes with a pydantic "
            "BaseModel attribute; rename it"
        )


def _adapter(annotation: object, where: str) -> TypeAdapter[object]:
    try:
        return TypeAdapter(annotation)
    except PydanticUserError as err:
        raise BuildError(f"{where}: {err}") from err


def bind(spec: RouteSpec) -> BoundRoute:
    """Read the handler's signature once; raise BuildError for any parameter,
    body or return it can't bind."""
    name = spec.handler.__name__
    where = f"{spec.method} {spec.path} ({name})"
    signature = inspect.signature(spec.handler)
    placeholders = _PLACEHOLDER.findall(spec.path)
    for placeholder in placeholders:
        if not placeholder.isidentifier():
            raise BuildError(
                f"{where}: {{{placeholder}}} must be a plain name (one segment)"
            )
        if placeholder not in signature.parameters:
            raise BuildError(f"{where}: {{{placeholder}}} has no parameter")

    fields: dict[str, tuple[object, object]] = {}
    path_params: list[str] = []
    query_params: list[str] = []
    list_params: set[str] = set()
    deps: dict[str, Depends] = {}
    request_param: str | None = None
    body_param: str | None = None
    body_type: object = None
    body_adapter: TypeAdapter[object] | None = None
    patch_model: type[BaseModel] | None = None
    for param_name, param in signature.parameters.items():
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise BuildError(
                f"{where}: parameter {param_name!r} must be callable by keyword "
                "(no positional-only, *args or **kwargs)"
            )
        if param_name.startswith("_"):
            raise BuildError(
                f"{where}: parameter {param_name!r} must not start with an underscore"
            )
        annotation = param.annotation
        if annotation is inspect.Parameter.empty or isinstance(annotation, str):
            raise BuildError(
                f"{where}: parameter {param_name!r} needs a type annotation "
                "(string annotations are not supported)"
            )
        dep = _depends(annotation)
        if annotation is web.Request:
            request_param = param_name
        elif dep is not None:
            deps[param_name] = dep
        elif param_name in placeholders:
            if not _is_scalar(annotation):
                raise BuildError(
                    f"{where}: path parameter {param_name!r} must be a plain type"
                )
            _check_not_a_model_attribute(where, param_name)
            path_params.append(param_name)
            fields[param_name] = (annotation, ...)
        elif partial_model(annotation) is not None or _is_body(annotation):
            if spec.method in _NO_BODY_METHODS:
                raise BuildError(
                    f"{where}: {spec.method} can't take a body ({param_name})"
                )
            if body_param is not None:
                raise BuildError(
                    f"{where}: two body parameters ({body_param}, {param_name})"
                )
            body_param = param_name
            patch_model = partial_model(annotation)
            if patch_model is not None:
                if (aliased := aliased_field(patch_model)) is not None:
                    raise BuildError(
                        f"{where}: Partial[{patch_model.__name__}] can't take "
                        f"aliases ({aliased}); patch by field name"
                    )
                body_type = patch_model
            else:
                body_type = annotation
                body_adapter = _adapter(annotation, where)
        elif _is_scalar(annotation) or _list_item(annotation) is not None:
            item = _list_item(annotation)
            if item is not None:
                if not _is_scalar(item):
                    raise BuildError(
                        f"{where}: query list {param_name!r} must hold a plain type"
                    )
                list_params.add(param_name)
            _check_not_a_model_attribute(where, param_name)
            query_params.append(param_name)
            default = param.default
            fields[param_name] = (
                annotation,
                ... if default is inspect.Parameter.empty else default,
            )
        else:
            raise BuildError(f"{where}: cannot bind {param_name!r}: {annotation!r}")

    returns = signature.return_annotation
    if returns is inspect.Signature.empty or isinstance(returns, str):
        raise BuildError(f"{where}: no return annotation")
    return_adapter: TypeAdapter[object] | None = None
    if spec.status in spec.responses:
        pass  # Binary: the handler returns a web.StreamResponse
    elif returns is None:
        if spec.status not in (202, 204):
            raise BuildError(f"{where}: -> None needs status=204 (or 202)")
    elif spec.status == 204:
        raise BuildError(f"{where}: status=204 cannot carry a body; return None")
    else:
        return_adapter = _adapter(returns, where)

    params_model: type[BaseModel] | None = None
    if fields:
        # pyrefly can't match **fields against create_model's overloads.
        # pyrefly: ignore[no-matching-overload]
        params_model = create_model(f"{name}_params", **fields)
    return BoundRoute(
        spec=spec,
        operation_id=name,
        params_model=params_model,
        body_param=body_param,
        body_adapter=body_adapter,
        body_is_patch=patch_model is not None,
        dep_params=deps,
        request_param=request_param,
        return_adapter=return_adapter,
        path_params=tuple(path_params),
        query_params=tuple(query_params),
        list_params=frozenset(list_params),
        body_type=body_type,
        return_type=returns,
        patch_model=patch_model,
    )


def check_unique(routes: Sequence[BoundRoute]) -> None:
    """No two routes share a method and path shape, or an operationId."""
    by_path: dict[tuple[str, str], str] = {}
    by_operation: dict[str, str] = {}
    for route in routes:
        where = f"{route.spec.method} {route.spec.path}"
        key = (route.spec.method, _PLACEHOLDER.sub("{}", route.spec.path))
        if key in by_path:
            raise BuildError(
                f"duplicate route {where}: {by_path[key]} and {route.operation_id}"
            )
        if route.operation_id in by_operation:
            raise BuildError(
                f"duplicate operationId {route.operation_id!r}: "
                f"{by_operation[route.operation_id]} and {where}"
            )
        by_path[key] = route.operation_id
        by_operation[route.operation_id] = where


def link_locations(routes: Sequence[BoundRoute]) -> None:
    """Mark each 201 route whose created item has a GET route one level down
    (POST /things → GET /things/{thing_id}): its response carries Location."""
    item_gets = {
        _PLACEHOLDER.sub("{}", r.spec.path) for r in routes if r.spec.method == "GET"
    }
    for route in routes:
        shape = _PLACEHOLDER.sub("{}", route.spec.path) + "/{}"
        route.location = route.spec.status == 201 and shape in item_gets
