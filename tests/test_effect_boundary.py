"""Effect-ownership ratchet (sibling of test_config_boundary): only the
Virtuals manager starts, stops or stores a virtual's effect, activates a
virtual or changes its config.

An AST walk over ledfx/** counts, per file:
- effects-create: ``<x>.effects.create(...)`` builds an effect nobody owns, and
  leaks it when the virtual refuses it;
- effect-call: ``.set_effect(``, ``.clear_effect(`` or ``.update_effect_config(``
  on anything but the manager (a receiver whose last name is ``virtuals``:
  ``virtuals.set_effect(...)``, ``self._ledfx.virtuals.clear_effect(...)``).
  Called on a Virtual they skip the safe-mode check, the typed errors, the
  history and the save;
- virtual-call: ``.activate(``, ``.deactivate(``, ``.update_config(``,
  ``.replace_config(``, ``.update_segments(``, ``.activate_segments(`` or
  ``.deactivate_segments(`` on a Virtual. Devices, integrations and effects have
  methods of the same names, so a receiver counts only when its last name
  contains "virtual" (``virtual``, ``blocking_virtual``, ``self._virtual``) or
  it is the result of a manager lookup (``virtuals.get(...)``,
  ``virtuals.get_or_raise(...)``). The rules below use the same receiver rule;
- active-write: ``<x>.active = ...`` for any receiver but ``self``. A write to
  another object's ``active`` is never the right way to change a virtual, so
  the rule does not depend on what the receiver is called; a non-virtual
  (an integration) is pinned in the allowlist;
- entry-write: a store (``del`` and augmented stores too) or a mutating call
  (``MUTATORS`` of test_config_boundary) through a virtual's ``.entry``:
  ``virtual.entry.effect = ...``, ``virtual.entry.effects.pop(...)``, or the
  same through a name bound in the same function by ``x = virtual.entry``
  (the alias walk of test_config_boundary). The manager saves what it stores;
  a write behind it is lost, or saved half done;
- private-write: ``<virtual>._name = ...`` (a private store of a Virtual, such
  as ``_segments``, ``_active_effect`` or ``_config``) for a virtual receiver;
- effect-config: ``.update_config(`` on a receiver whose last name is
  ``active_effect``: it changes the running effect with no history and no save;
- virtual-rows: ``<virtual>.rows = ...``: the setter rewrites the virtual's
  config and its entry.

Known limits (not detected): a Virtual under a name without "virtual"
(``v.deactivate()``) for the rules that use the receiver rule, ``getattr``/
``setattr``, an alias of a bound method (``f = virtual.set_effect``), and an
entry alias across functions, bound by ``:=``, ``with`` or an annotated or
tuple assignment, or by a ``for`` over a call or a literal
(``for e in virtual.entry.effects.values()``; a ``for`` over the chain itself
is followed). The effect-call rule needs no name: anything not called on
``virtuals`` counts.

The only owner is ledfx/virtuals.py (the manager and Virtual itself). Device
lifecycle code (ledfx/devices/*) is not an owner.

tests/effect_boundary_allowlist.txt holds today's counts as ``path:rule:count``.
It may only shrink, and never names a file under ledfx/api/v2/. What it holds:
- ledfx/devices/__init__.py: a removed device deactivates and clears the effect
  of a virtual that lost its segments, and a device change reactivates or
  deactivates the virtuals it feeds and sets their segments (``entry.segments``,
  ``_segments``, ``update_segments``, ``activate_segments``). That runs in safe
  mode and is runtime-only device lifecycle; they leave when device lifecycle
  goes through the manager.
- ledfx/devices/lifx.py, ledfx/devices/twinkly_squares.py: a matrix device sets
  its virtual's ``rows``; they leave when device code changes rows through
  ``Virtuals.set_config``.
- ledfx/api/integrations.py: ``integration.active`` is an integration's flag,
  not a virtual's.
After removing a violation, regenerate it:
    uv run python -m tests.test_effect_boundary > tests/effect_boundary_allowlist.txt
"""

import ast
import functools
from collections import Counter
from pathlib import Path

import pytest

from tests.test_config_boundary import (
    MUTATORS,
    ROOT,
    SRC_DIR,
    V2_PREFIX,
    _aliases,
    _write_targets,
    load_allowlist,
)

ALLOWLIST = Path(__file__).with_name("effect_boundary_allowlist.txt")
OWNERS = {"ledfx/virtuals.py": "the manager and Virtual"}
EFFECT_CALLS = frozenset({"set_effect", "clear_effect", "update_effect_config"})
VIRTUAL_CALLS = frozenset(
    {
        "activate",
        "deactivate",
        "update_config",
        "replace_config",
        "update_segments",
        "activate_segments",
        "deactivate_segments",
    }
)


def _tail(node: ast.expr) -> str | None:
    """The last name of ``a.b.c`` (``c``) or ``c``; None for a call or subscript."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_virtual(node: ast.expr) -> bool:
    """A name containing "virtual" (not the manager), or ``virtuals.get(...)``."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _tail(node.func.value) == "virtuals"
    tail = (_tail(node) or "").lower()
    return "virtual" in tail and tail != "virtuals"


def _through_entry(node: ast.expr, aliases: frozenset[str] = frozenset()) -> bool:
    """Is node a virtual's ``.entry``, an alias of it, or a chain below either?"""
    while True:
        if isinstance(node, ast.Attribute):
            if node.attr == "entry" and _is_virtual(node.value):
                return True
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            return isinstance(node, ast.Name) and node.id in aliases


def _entry_writes(tree: ast.AST) -> int:
    """Number of distinct stores and mutating calls through a virtual's entry."""
    writes: set[int] = set()

    def collect(scope: ast.AST, aliases: frozenset[str]) -> None:
        for node in ast.walk(scope):
            for target in _write_targets(node):
                if not isinstance(target, ast.Name) and _through_entry(target, aliases):
                    writes.add(id(target))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in MUTATORS
                and _through_entry(node.func.value, aliases)
            ):
                writes.add(id(node))

    collect(tree, frozenset())
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            aliases := _aliases(fn, _through_entry)
        ):
            collect(fn, aliases)
    return len(writes)


def violations(source: str) -> Counter[str]:
    """Rule name -> number of violations in source."""
    found = Counter[str]()
    tree = ast.parse(source)
    if entry_writes := _entry_writes(tree):
        found["entry-write"] = entry_writes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = _tail(node.func.value)
            if node.func.attr == "create" and receiver == "effects":
                found["effects-create"] += 1
            elif node.func.attr in EFFECT_CALLS and receiver != "virtuals":
                found["effect-call"] += 1
            elif node.func.attr in VIRTUAL_CALLS and _is_virtual(node.func.value):
                found["virtual-call"] += 1
            elif node.func.attr == "update_config" and receiver == "active_effect":
                found["effect-config"] += 1
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            if node.attr == "active" and not (
                isinstance(node.value, ast.Name) and node.value.id == "self"
            ):
                found["active-write"] += 1
            elif node.attr == "rows" and _is_virtual(node.value):
                found["virtual-rows"] += 1
            elif (
                node.attr.startswith("_")
                and not node.attr.startswith("__")
                and _is_virtual(node.value)
            ):
                found["private-write"] += 1
    return found


@functools.cache  # the tree does not change during a run
def scan() -> dict[str, int]:
    """``path:rule`` -> count for every violation under ledfx/."""
    out: dict[str, int] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in OWNERS:
            continue
        for rule, count in sorted(violations(path.read_text("utf-8")).items()):
            out[f"{rel}:{rule}"] = count
    return out


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # each banned form
        (
            "e = self._ledfx.effects.create(ledfx=l, type=t, config=c)",
            {"effects-create": 1},
        ),
        ("effects.create(type=t)", {"effects-create": 1}),
        ("virtual.set_effect(effect)", {"effect-call": 1}),
        ("self._virtual.set_effect(effect, fallback=1)", {"effect-call": 1}),
        ("virtual.clear_effect()", {"effect-call": 1}),
        ("virtual.update_effect_config(effect)", {"effect-call": 1}),
        ("self._ledfx.virtuals.get(i).set_effect(effect)", {"effect-call": 1}),
        ("virtual.active = True", {"active-write": 1}),
        ("self._virtual.active = not x", {"active-write": 1}),
        ("a, virtual.active = 1, 2", {"active-write": 1}),
        ("virtual.active += 1", {"active-write": 1}),
        # the manager's forms do not count
        ("self._ledfx.virtuals.set_effect(vid, t, c)", {}),
        ("virtuals.clear_effect(vid)", {}),
        ("self._ledfx.virtuals.update_effect_config(e)", {}),
        ("self.virtuals.set_effect(vid, t, c)", {}),
        # not effects, not virtuals, reads
        ("effects.get_class(t)", {}),
        ("self._ledfx.effects.types()", {}),
        ("self.active = active", {}),
        ("x = virtual.active", {}),
        # virtual-call: a Virtual's lifecycle and config
        ("virtual.activate()", {"virtual-call": 1}),
        ("blocking_virtual.deactivate()", {"virtual-call": 1}),
        ("virtual.update_config({'rows': 2})", {"virtual-call": 1}),
        ("self._virtual.replace_config(c)", {"virtual-call": 1}),
        ("self._ledfx.virtuals.get(i).deactivate()", {"virtual-call": 1}),
        ("virtuals.get_or_raise(i).update_config(c)", {"virtual-call": 1}),
        # ... but not other objects with the same method names, or the manager
        ("device.activate()\nsuper().deactivate()\nself.update_config(c)", {}),
        ("integration.update_config(c)\neffect.update_config(c)", {}),
        ("self._ledfx.devices.get(i).activate()", {}),
        ("self._ledfx.scenes.activate(i)", {}),
        ("self._ledfx.virtuals.set_config(i, c)", {}),
        # active-write: any receiver but self
        ("_integration.active = not active", {"active-write": 1}),
        ("v.active = True", {"active-write": 1}),
        ("self._ledfx.thing.active = 1", {"active-write": 1}),
        ("devices.create(a)", {}),
        # virtual-call: the segment methods
        ("virtual.update_segments(s)", {"virtual-call": 1}),
        ("self._virtual.activate_segments(s)", {"virtual-call": 1}),
        ("virtuals.get(i).deactivate_segments()", {"virtual-call": 1}),
        ("device.update_segments(s)\nself.deactivate_segments()", {}),
        # entry-write: a store or mutating call through a virtual's entry
        ("virtual.entry.effect = e", {"entry-write": 1}),
        ("virtual.entry.active = True", {"active-write": 1, "entry-write": 1}),
        ("virtual.entry.effects['a'] = e", {"entry-write": 1}),
        ("virtual.entry.effects.pop('a')", {"entry-write": 1}),
        ("virtual.entry.segments += [s]", {"entry-write": 1}),
        ("del virtuals.get(i).entry.effects['a']", {"entry-write": 1}),
        ("virtual.entry = e", {"entry-write": 1}),
        ("def f():\n entry = virtual.entry\n entry.effect = e", {"entry-write": 1}),
        (
            "def f():\n e = self._virtual.entry\n x = e.effects\n x.clear()",
            {"entry-write": 1},
        ),
        # ... but not reads, a copy, another object's entry, or a rebound alias
        ("x = virtual.entry.effect\nvirtual.entry.model_copy()", {}),
        ("device.entry.x = 1\nself.entry.x = 1\nentry.x = 1", {}),
        ("def f():\n entry = virtual.entry\n x = entry.effect", {}),
        ("def f():\n entry = other.entry\n entry.x = 1", {}),
        ("def f():\n entry = virtual.entry\ndef g():\n entry.x = 1", {}),
        # private-write: a virtual's private state, from outside
        ("virtual._segments = s", {"private-write": 1}),
        ("self._virtual._active_effect = None", {"private-write": 1}),
        ("virtual._config = c", {"private-write": 1}),
        ("virtual._paused += 1", {"private-write": 1}),
        ("self._config = c\nself._virtual = v", {}),
        ("device._config = c\nself.game._stack = None", {}),
        ("Source._stream = s\nx = virtual._segments", {}),
        ("virtual.__class__ = C", {}),
        # effect-config: the running effect's config changed behind the manager
        ("virtual.active_effect.update_config(c)", {"effect-config": 1}),
        (
            "self._ledfx.virtuals.get(i).active_effect.update_config(c)",
            {"effect-config": 1},
        ),
        ("effect.update_config(c)\nself.update_config(c)", {}),
        ("virtual.active_effect.config.speed", {}),
        # virtual-rows: the setter rewrites the config and the entry
        ("virtual.rows = 3", {"virtual-rows": 1}),
        ("self._virtual.rows += 1", {"virtual-rows": 1}),
        ("self.rows = 3\nself.rows = virtual.config.rows", {}),
        ("x = virtual.rows\nmatrix.rows = 2", {}),
    ],
)
def test_rules(source: str, expected: dict[str, int]) -> None:
    assert dict(violations(source)) == expected


def test_owners_exist() -> None:
    assert [o for o in OWNERS if not (ROOT / o).exists()] == []


def test_no_new_violations() -> None:
    allowed = load_allowlist(ALLOWLIST)
    new = {k: n for k, n in scan().items() if n > allowed.get(k, 0)}
    assert new == {}, (
        "An effect was started, stopped or stored, or a virtual activated, "
        "outside the Virtuals manager; call the manager instead"
    )


def test_allowlist_is_not_stale() -> None:
    current = scan()
    stale = {
        k: n for k, n in load_allowlist(ALLOWLIST).items() if current.get(k, 0) < n
    }
    assert stale == {}, (
        "Violations were removed: shrink the allowlist with "
        "`uv run python -m tests.test_effect_boundary > tests/effect_boundary_allowlist.txt`"
    )


def test_v2_is_never_allowlisted() -> None:
    assert [k for k in load_allowlist(ALLOWLIST) if k.startswith(V2_PREFIX)] == []


if __name__ == "__main__":
    for key, count in scan().items():
        print(f"{key}:{count}")
