"""PATCH bodies: Partial[M] binds a Patch[M], the manager applies it."""

import json
import types
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Generic,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ValidationError

from ledfx.api.v2.core.problem import (
    ProblemDetailError,
    ProblemError,
    json_body,
    validation_errors,
    validation_problem,
)
from ledfx.configuration.fields import RUNTIME_CONTEXT

M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class _PartialOf:
    """Annotated metadata: this parameter is a PATCH body for model."""

    model: type[BaseModel]


class PatchValidationError(ProblemError):
    """Patch.apply failed. A changed field is the client's error (422, errors
    under "body"); an unchanged stored field that no longer validates is a
    409 conflict naming it (stored_field)."""

    def __init__(
        self, errors: list[ProblemDetailError], stored_field: str | None
    ) -> None:
        self.stored_field = stored_field
        if errors:
            super().__init__(
                422,
                "validation",
                "Validation failed",
                f"{len(errors)} invalid value(s)",
                errors,
            )
        else:
            super().__init__(
                409, "conflict", "Conflict", f"Stored field {stored_field!r} is invalid"
            )


class Patch(Generic[M]):
    """A PATCH body: the raw JSON object and the leaf paths it changes."""

    def __init__(
        self,
        model: type[M],
        data: dict[str, object],
        changed: frozenset[tuple[str, ...]],
    ) -> None:
        self.model = model
        self.data = data
        self.changed = changed

    @classmethod
    def parse(cls, model: type[M], raw: bytes) -> "Patch[M]":
        """Parse a body; unknown keys (at any depth) are a 422."""
        data = json_body(raw)
        if not isinstance(data, dict):
            raise validation_problem(
                [
                    ProblemDetailError(
                        loc=["body"], msg="Input should be an object", type="model_type"
                    )
                ]
            )
        errors: list[ProblemDetailError] = []
        changed: set[tuple[str, ...]] = set()
        _walk(model, data, (), errors, changed)
        if errors:
            raise validation_problem(errors)
        return cls(model, data, frozenset(changed))

    def apply(self, current: BaseModel) -> M:
        """current merged with this patch, validated strictly as M. current is
        never modified."""
        base: dict[str, object] = current.model_dump(mode="json")
        # Objects that replace a stored non-object (None) are the client's whole.
        replaced: set[tuple[str, ...]] = set()
        merged = _merge(base, self.data, (), replaced)
        changed = self.changed | replaced
        # FromSource checks only the fields named here, like devices'
        # update_config: every key on a changed path.
        fields = frozenset(key for path in changed for key in path)
        try:
            return self.model.model_validate_json(
                json.dumps(merged),
                strict=True,
                context={**RUNTIME_CONTEXT, "fields": fields},
            )
        except ValidationError as err:
            raise self._error(err, changed) from None

    def _error(
        self, err: ValidationError, changed: frozenset[tuple[str, ...]]
    ) -> PatchValidationError:
        errors: list[ProblemDetailError] = []
        stored_field: str | None = None
        for error in validation_errors(err):
            loc = tuple(error.loc)
            if any(_overlaps(loc, path) for path in changed):
                error.loc.insert(0, "body")
                errors.append(error)
            elif stored_field is None:
                stored_field = ".".join(map(str, loc)) or self.model.__name__
        return PatchValidationError(errors, stored_field)


if TYPE_CHECKING:
    # Type checkers see what the handler receives.
    Partial = Patch
else:

    class Partial:
        """Partial[M] as a handler annotation: the body is a Patch[M]."""

        def __class_getitem__(cls, model: type[BaseModel]) -> object:
            return Annotated[Patch[model], _PartialOf(model)]


def partial_model(annotation: object) -> type[BaseModel] | None:
    """M for a Partial[M] annotation, else None."""
    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, _PartialOf):
                return meta.model
    return None


def partial_schema(model: type[BaseModel]) -> dict[str, object]:
    """M's validation schema with "required" removed from every object,
    $defs included, so any subset of fields is a valid body."""
    return {
        key: _without_required(value)
        for key, value in model.model_json_schema().items()
        if key != "required"
    }


def _without_required(node: object) -> object:
    if isinstance(node, dict):
        # A property may be called "required"; the keyword is always a list.
        return {
            k: _without_required(v)
            for k, v in node.items()
            if not (k == "required" and isinstance(v, list))
        }
    if isinstance(node, list):
        return [_without_required(v) for v in node]
    return node


def aliased_field(model: type[BaseModel]) -> str | None:
    """ "Model.field" for the first field, here or in a nested model, that
    declares an alias, else None. Patch walks and merges by field name, so
    Partial[M] cannot take aliases."""
    seen: set[type[BaseModel]] = set()
    todo = [model]
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        for name, field in current.model_fields.items():
            if field.alias or field.validation_alias or field.serialization_alias:
                return f"{current.__name__}.{name}"
            if (nested := _model_of(field.annotation)) is not None:
                todo.append(nested)
    return None


def _model_of(annotation: object) -> type[BaseModel] | None:
    """The model a field holds (through Annotated and | None), else None."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if get_origin(annotation) in (Union, types.UnionType):
        members = [a for a in get_args(annotation) if a is not type(None)]
        return _model_of(members[0]) if len(members) == 1 else None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _walk(
    model: type[BaseModel],
    data: dict[str, object],
    prefix: tuple[str, ...],
    errors: list[ProblemDetailError],
    changed: set[tuple[str, ...]],
) -> None:
    for key, value in data.items():
        path = (*prefix, key)
        field = model.model_fields.get(key)
        if field is None:
            errors.append(
                ProblemDetailError(
                    loc=["body", *path],
                    msg="Extra inputs are not permitted",
                    type="extra_forbidden",
                )
            )
            continue
        nested = _model_of(field.annotation)
        if nested is not None and isinstance(value, dict):
            _walk(nested, value, path, errors, changed)
        else:
            changed.add(path)


def _merge(
    base: dict[str, object],
    patch: dict[str, object],
    prefix: tuple[str, ...],
    replaced: set[tuple[str, ...]],
) -> dict[str, object]:
    """Objects merge recursively; arrays, scalars and null replace. An object
    landing on a non-object is recorded in replaced."""
    merged = dict(base)
    for key, value in patch.items():
        old = merged.get(key)
        if isinstance(value, dict) and isinstance(old, dict):
            merged[key] = _merge(old, value, (*prefix, key), replaced)
        else:
            if isinstance(value, dict):
                replaced.add((*prefix, key))
            merged[key] = value
    return merged


def _overlaps(loc: tuple[str | int, ...], path: tuple[str, ...]) -> bool:
    """An error at loc concerns path if either is a prefix of the other."""
    n = min(len(loc), len(path))
    return loc[:n] == path[:n]
