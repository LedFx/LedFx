"""Old voluptuous vs auto-converted pydantic: same accept/reject, same output.

Rule: 'stricter' (old accepts, new rejects) must be empty except ALLOWED;
'differ' (both accept, outputs differ) must be empty; 'wider' (old rejects, new accepts) is allowed.
Classes with a source-declared Config anywhere in their MRO are covered by
the model-schema snapshot instead (layers 10-12).
"""

import functools
import importlib
import inspect
import logging
import pkgutil
from collections.abc import Iterable, Iterator

import pytest
import voluptuous as vol
from pydantic import ValidationError

from ledfx.configuration.plugin import vol_to_model
from ledfx.utils import BaseRegistry

_LOGGER = logging.getLogger(__name__)
Fixture = dict[str, object]
EXTRAS: Fixture = {"gradient_name": "Rainbow", "zz_unknown": 1}

ALLOWED_STRICTER = {
    # virtual_id_validator was an identity function; non-str ids were never valid.
    ("radial", "source_virtual"),
}
CANDIDATES: list[object] = [
    None,
    True,
    0,
    1,
    -1,
    1.5,
    1.7,
    "1",
    "abc",
    "#ff0000",
    "red",
    10**6,
    -(10**6),
    [],
    {},
]


@functools.cache
def _registry_by_kind() -> dict[str, list[tuple[str, type[BaseRegistry]]]]:
    out: dict[str, list[tuple[str, type[BaseRegistry]]]] = {}
    for kind, package, base_name in (
        ("effects", "ledfx.effects", "Effect"),
        ("devices", "ledfx.devices", "Device"),
        ("integrations", "ledfx.integrations", "Integration"),
    ):
        module = importlib.import_module(package)
        for _, name, _ in pkgutil.iter_modules(module.__path__, package + "."):
            try:
                importlib.import_module(name)
            except ModuleNotFoundError as err:
                # Some modules are platform-specific; say which were skipped.
                _LOGGER.warning("parity: skipped %s (%s)", name, err)
        out[kind] = sorted(getattr(module, base_name).registry().items())
    return out


def _registry_classes() -> list[tuple[str, type[BaseRegistry]]]:
    return [p for plugins in _registry_by_kind().values() for p in plugins]


def test_registry_is_not_silently_shrinking() -> None:
    by_kind = _registry_by_kind()
    assert all(by_kind.values()), {k: len(v) for k, v in by_kind.items()}
    assert len(_registry_classes()) >= 80


def _auto_only(cls: type) -> bool:
    return not any("Config" in c.__dict__ for c in inspect.getmro(cls))


POOL: list[object] = [
    "1.2.3.4",
    "x",
    "#ff0000",
    1,
    5,
    0.5,
    2.5,
    True,
    False,
    [],
    {},
]


def _accepts(validator: object, value: object) -> bool:
    try:
        vol.Schema(validator)(value)
    except (vol.Invalid, ValueError, TypeError):
        return False
    return True


def _parts(validator: object) -> list[object]:
    if isinstance(validator, vol.All):
        return list(validator.validators)
    return [validator]


def _default(key: object) -> object:
    """The key's default value, or vol.UNDEFINED."""
    factory = getattr(key, "default", vol.UNDEFINED)
    return factory() if callable(factory) else factory


def _valid_values(key: object, validator: object) -> list[object]:
    """Values voluptuous accepts for this field: default, In members, Range
    midpoint, then a generic pool. Order is preference order."""
    found: list[object] = []
    if _default(key) is not vol.UNDEFINED:
        found.append(_default(key))
    for part in _parts(validator):
        if isinstance(part, vol.In) and isinstance(part.container, Iterable):
            found += list(part.container)
        if (
            isinstance(part, vol.Range)
            and isinstance(part.min, (int, float))
            and isinstance(part.max, (int, float))
        ):
            mid = (part.min + part.max) / 2
            found += [int(mid), mid]
    found += POOL
    return [v for v in found if _accepts(validator, v)]


def _fixtures(schema: vol.Schema) -> Iterator[Fixture]:
    base: Fixture = {}
    for key, validator in schema.schema.items():
        if isinstance(key, vol.Required) and key.default is vol.UNDEFINED:
            valid = _valid_values(key, validator)
            assert valid, f"no valid filler for required key {key.schema!r}"
            base[key.schema] = valid[0]
    schema(dict(base))  # a bad filler fails loudly
    yield dict(base)
    # Every field valid and non-default at once, then with unknown keys.
    every = dict(base)
    for key, validator in schema.schema.items():
        valid = _valid_values(key, validator)
        default = _default(key)
        others = [v for v in valid if v != default or type(v) is not type(default)]
        if key.schema not in every and (others or valid):
            every[key.schema] = (others or valid)[0]
    yield every
    yield {**every, **EXTRAS}
    yield {**base, **EXTRAS}
    for key, validator in schema.schema.items():
        candidates = list(CANDIDATES)
        for part in _parts(validator):
            if isinstance(part, vol.Range):
                for bound in (part.min, part.max):
                    if isinstance(bound, (int, float)):
                        candidates += [
                            bound,
                            bound - 1,
                            bound + 1,
                            bound + 0.5,
                            str(bound),
                        ]
            if isinstance(part, vol.In) and isinstance(part.container, Iterable):
                candidates += list(part.container)
        for candidate in candidates:
            yield {**base, key.schema: candidate}


def _drop_none(d: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in d.items() if v is not None}


@pytest.mark.parametrize(
    "plugin_type,cls",
    [p for p in _registry_classes() if _auto_only(p[1])],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_auto_model_matches_voluptuous(
    plugin_type: str, cls: type[BaseRegistry]
) -> None:
    schema = cls.schema()
    assert isinstance(schema, vol.Schema)
    model = vol_to_model(plugin_type, schema)
    stricter: list[Fixture] = []
    differ: list[tuple[Fixture, object, object]] = []
    for fixture in _fixtures(schema):
        try:
            old, old_ok = schema(dict(fixture)), True
        except (vol.Invalid, ValueError, TypeError):
            old, old_ok = None, False
        try:
            new, new_ok = model.model_validate(dict(fixture)).as_dict(), True
        except ValidationError:
            new, new_ok = None, False
        if old_ok and not new_ok:
            # Only non-str ids were never valid; a rejected valid str still fails.
            if not any(
                (plugin_type, k) in ALLOWED_STRICTER and not isinstance(v, str)
                for k, v in fixture.items()
            ):
                stricter.append(fixture)
        elif old is not None and new is not None and _drop_none(old) != _drop_none(new):
            differ.append((fixture, old, new))
        if new_ok and EXTRAS.keys() <= fixture.keys():
            # extra="allow": unknown keys are accepted and kept. Where the old
            # schema lacked ALLOW_EXTRA and rejected them, wider is allowed.
            assert new is not None and EXTRAS.items() <= new.items(), new
    assert not stricter, f"new model rejects input voluptuous accepted: {stricter[:3]}"
    assert not differ, f"outputs differ: {differ[:3]}"
