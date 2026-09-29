"""Validate a config tree, quarantining the smallest invalid piece at a time."""

import copy
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)
Quarantine = Callable[[str, object, list[str]], None]
Loc = tuple[int | str, ...]
_MISSING = object()
MAX_REPAIRS = 1000
# The failing value should have been a model/dict: its list holds entries.
_ENTRY_ERRORS = frozenset({"missing", "model_type", "dict_type"})


def _get(container: object, key: int | str) -> object:
    if (
        isinstance(container, list)
        and isinstance(key, int)
        and 0 <= key < len(container)
    ):
        return container[key]
    if isinstance(container, dict) and key in container:
        return container[key]
    return _MISSING


def _pop_at(data: object, loc: Loc, entry: bool) -> tuple[Loc, object]:
    """Pop the deepest existing container item on loc; return (path, value).

    A list item is popped on its own only when it is an entry (entry: the error
    says the item should be a model or dict), so the other entries survive. Any
    other list item resets the whole enclosing field to its default instead:
    popping it would shift the list (a melbank frequency list would lose a band).
    """
    node = data
    trail: list[tuple[object, int | str]] = []
    for key in loc:
        child = _get(node, key)
        if child is _MISSING:
            break
        trail.append((node, key))
        node = child
    if not entry:
        while len(trail) > 1 and isinstance(trail[-1][0], list):
            trail.pop()
    if not trail:
        return (), _MISSING
    container, key = trail[-1]
    path = tuple(k for _, k in trail)
    if isinstance(container, list) and isinstance(key, int):
        return path, container.pop(key)
    if isinstance(container, dict):
        return path, container.pop(key)
    return (), _MISSING


def _restore(value: object, rel: Loc, item: object) -> None:
    """Undo an earlier _pop_at inside value (rel is relative to value)."""
    node = value
    for key in rel[:-1]:
        node = _get(node, key)
    last = rel[-1]
    if isinstance(node, list) and isinstance(last, int):
        node.insert(last, item)
    elif isinstance(node, dict):
        node[last] = item


def lenient_validate(
    model: type[M], data: dict[str, object], path: str, quarantine: Quarantine
) -> M | None:
    """Validate data. For each error, remove the offending value (the field then
    falls back to its default) and quarantine it; a missing required field
    escalates to its parent. Returns None when the whole object is unusable.

    Records are written once validation settles, and a later removal that contains
    an earlier one replaces it, so each bad value is quarantined exactly once.
    """
    work = copy.deepcopy(data)
    prefix: list[str] = path.split(".") if path else []
    records: list[tuple[Loc, object, list[str]]] = []
    for _ in range(MAX_REPAIRS):
        try:
            result = model.model_validate(work)
        except ValidationError as err:
            first = err.errors(include_url=False)[0]
            loc: Loc = tuple(first["loc"])
            if first["type"] == "missing":
                loc = loc[:-1]
            removed_at, value = _pop_at(work, loc, first["type"] in _ENTRY_ERRORS)
            if value is _MISSING:
                quarantine(
                    path, data, [e["msg"] for e in err.errors(include_url=False)]
                )
                return None
            # Strictly inside: an equal path is a different item shifted into place.
            inside = [
                r
                for r in records
                if len(r[0]) > len(removed_at) and r[0][: len(removed_at)] == removed_at
            ]
            for sub_at, sub_value, _ in reversed(inside):
                # Quarantine the escalated value whole, as it was on disk.
                _restore(value, sub_at[len(removed_at) :], sub_value)
            records = [r for r in records if r not in inside]
            records.append(
                (
                    removed_at,
                    value,
                    [f"{'.'.join(map(str, first['loc']))}: {first['msg']}"],
                )
            )
            continue
        for removed_at, value, errors in records:
            quarantine(".".join(str(k) for k in [*prefix, *removed_at]), value, errors)
        return result
    quarantine(path, data, ["too many invalid values"])
    return None
