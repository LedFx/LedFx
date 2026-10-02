"""Config-ownership ratchet: only the config owners manage config.

An AST walk over ledfx/** counts, per file:
- config-store: any ``.config_store`` attribute;
- config-write: an assignment, augmented assignment or ``del`` whose target is
  reached through the core's ``.config`` (``self._ledfx.config.x = 1``,
  ``ledfx.config.x[k] = 1``), or a mutating call on such a chain
  (``self._ledfx.config.virtuals.append(...)``);
and, under ledfx/api/** only:
- core-config: ``.config`` read off the core (``self._ledfx``, ``self.ledfx``,
  ``ledfx`` or ``_ledfx``);
- private: a ``_private`` (not dunder) attribute of the core or of anything
  reached from it by attributes (``self._ledfx.virtuals._paused``).

Aliases count: a name bound in a function by ``x = <core.config chain>`` or
``for x in <core.config chain>`` is the config, so writes and mutator calls
rooted at it are config-write. Known limits (not detected): ``setattr(...)``,
passing the config to a helper that writes it, a mutator after a call
(``core.config.items().x``), aliases across functions, via ``self.x`` or at
module level, and aliases bound by an annotated assignment, ``:=``, ``with ...
as`` or a tuple right-hand side. Alias tracking ignores order, so a name
rebound to something else before a write still counts (none in the tree).

OWNERS lists the modules allowed config-store and config-write: the config
package, the core's wiring, and the managers that own a persisted section.
Adding an owner is a reviewed change. Reads of config outside ledfx/api stay
allowed.

tests/config_boundary_allowlist.txt holds today's counts as ``path:rule:count``.
It may only shrink, and never names a file under ledfx/api/v2/. What it holds:
- ledfx/api/*: v1 handlers that still read or manage config themselves. They
  shrink as each v2 family moves that logic into its manager.
- ledfx/devices/twinkly_squares.py, ledfx/integrations/mqtt_hass.py: plugins
  that save, or write the audio section, directly. Follow-ups.
- Pinned non-owners, kept off OWNERS so any new write fails: ledfx/utils.py
  (the user collections and BaseRegistry._set_config_values save through the
  store), ledfx/nowplaying/service.py (its own now_playing section, in
  _persist_config), ledfx/errors.py (ensure_writable reads read_only).
After moving logic into a manager, regenerate it:
    uv run python -m tests.test_config_boundary > tests/config_boundary_allowlist.txt
"""

import ast
import functools
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "ledfx"
API_PREFIX = "ledfx/api/"
ALLOWLIST = Path(__file__).with_name("config_boundary_allowlist.txt")
PYREFLY_BASELINE = ROOT / "pyrefly_errors.json"
V2_PREFIX = "ledfx/api/v2/"
CORE_NAMES = frozenset({"ledfx", "_ledfx", "core", "_core"})
MUTATORS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "pop",
        "remove",
        "clear",
        "update",
        "setdefault",
        "__setitem__",
        "__delitem__",
        "sort",
        "popitem",
        "add",
        "discard",
        "reverse",
    }
)

# module (or "dir/" prefix) -> the config it owns. Only these may touch the
# config store or write through ``core.config``. Modules that merely touch the
# store (utils.py, errors.py, nowplaying/service.py) are NOT owners: their counts
# are pinned in the allowlist, so any added write fails.
OWNERS = {
    "ledfx/configuration/": "the config package: store, models, migration",
    "ledfx/core.py": "wires the store and flushes it on shutdown",
    "ledfx/virtuals.py": "virtuals section and per-virtual effect presets",
    "ledfx/devices/__init__.py": "devices section (and the virtuals of a device)",
    "ledfx/scenes.py": "scenes section",
    "ledfx/playlists.py": "playlists section",
    "ledfx/integrations/__init__.py": "integrations section",
    "ledfx/effects/audio.py": "audio section (AudioInputSource persists its own)",
    "ledfx/effects/melbank.py": "melbanks and melbank_collection sections",
}


def _getattr_const(node: ast.AST) -> tuple[ast.expr, str] | None:
    """``getattr(obj, "name"...)`` -> (obj, name)."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        return node.args[0], node.args[1].value
    return None


def _is_core(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in CORE_NAMES
    if (got := _getattr_const(node)) is not None:  # getattr(self, "_ledfx", None)
        return got[1] in CORE_NAMES and isinstance(got[0], ast.Name)
    return (
        isinstance(node, ast.Attribute)
        and node.attr in CORE_NAMES
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _reached_from_core(node: ast.expr) -> bool:
    while isinstance(node, ast.Attribute):
        if _is_core(node):
            return True
        node = node.value
    return _is_core(node)


def _owner(rel: str) -> bool:
    return any(rel == o or (o.endswith("/") and rel.startswith(o)) for o in OWNERS)


def _through_core_config(node: ast.expr, aliases: frozenset[str] = frozenset()) -> bool:
    """Is node ``core.config``, an alias of it, or a chain below either?"""
    while True:
        if isinstance(node, ast.Attribute):
            if node.attr == "config" and _is_core(node.value):
                return True
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        elif (got := _getattr_const(node)) is not None:
            return got[1] == "config" and _is_core(got[0])
        else:
            return isinstance(node, ast.Name) and node.id in aliases


def _rooted_at(node: ast.expr, aliases: frozenset[str]) -> bool:
    """A write target below ``core.config`` or below an alias (not the bare alias)."""
    return not isinstance(node, ast.Name) and _through_core_config(node, aliases)


def _flatten(target: ast.expr) -> list[ast.expr]:
    """Unpack ``a, (b, *c) = ...`` into its leaf targets."""
    if isinstance(target, (ast.Tuple, ast.List)):
        return [leaf for elt in target.elts for leaf in _flatten(elt)]
    if isinstance(target, ast.Starred):
        return _flatten(target.value)
    return [target]


def _write_targets(node: ast.AST) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        targets = [node.target]
    elif isinstance(node, ast.Delete):
        targets = node.targets
    else:
        return []
    return [leaf for t in targets for leaf in _flatten(t)]


def _aliases(scope: ast.AST) -> frozenset[str]:
    """Names bound to the core's config (or below it) inside scope."""
    found: set[str] = set()
    while True:
        before = len(found)
        names = frozenset(found)
        for n in ast.walk(scope):
            if isinstance(n, ast.Assign) and _through_core_config(n.value, names):
                found.update(t.id for t in n.targets if isinstance(t, ast.Name))
            elif (
                isinstance(n, (ast.For, ast.comprehension))
                and isinstance(n.target, ast.Name)
                and _through_core_config(n.iter, names)
            ):
                found.add(n.target.id)
        if len(found) == before:
            return frozenset(found)


def _config_writes(tree: ast.AST) -> int:
    """Number of distinct writes through the core's config or an alias of it."""
    writes: set[int] = set()

    def collect(scope: ast.AST, aliases: frozenset[str]) -> None:
        for node in ast.walk(scope):
            for target in _write_targets(node):
                if _rooted_at(target, aliases):
                    writes.add(id(target))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in MUTATORS
                and _through_core_config(node.func.value, aliases)
            ):
                writes.add(id(node))

    collect(tree, frozenset())
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            aliases := _aliases(fn)
        ):
            collect(fn, aliases)
    return len(writes)


def violations(source: str, *, api: bool = True, owner: bool = False) -> Counter[str]:
    """Rule name -> number of violations in source.

    api: also apply the ledfx/api-only rules; owner: skip the owner-only ones.
    """
    found = Counter[str]()
    tree = ast.parse(source)
    if not owner:
        found["config-write"] = _config_writes(tree)
    for node in ast.walk(tree):
        got = _getattr_const(node)
        if got is not None and got[1] == "config_store" and not owner:
            found["config-store"] += 1
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr == "config_store":
            if not owner:
                found["config-store"] += 1
        elif not api:
            continue
        elif node.attr == "config" and _is_core(node.value):
            found["core-config"] += 1
        elif (
            node.attr.startswith("_")
            and not node.attr.startswith("__")
            and _reached_from_core(node.value)
        ):
            found["private"] += 1
    return +found  # unary plus drops the zero counts


@functools.cache  # the tree does not change during a run
def scan() -> dict[str, int]:
    """``path:rule`` -> count for every violation under ledfx/."""
    out: dict[str, int] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        found = violations(
            path.read_text("utf-8"), api=rel.startswith(API_PREFIX), owner=_owner(rel)
        )
        for rule, count in sorted(found.items()):
            out[f"{rel}:{rule}"] = count
    return out


def load_allowlist() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in ALLOWLIST.read_text("utf-8").splitlines():
        if line.strip():
            key, count = line.rsplit(":", 1)
            out[key] = int(count)
    return out


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("self._ledfx.config_store.request_save()", {"config-store": 1}),
        ("store = ledfx.config_store", {"config-store": 1}),
        ("x = self._ledfx.config['port']", {"core-config": 1}),
        ("x = self.ledfx.config.port", {"core-config": 1}),
        ("x = ledfx.config.virtuals", {"core-config": 1}),
        ("x = _ledfx.config", {"core-config": 1}),
        ("x = self._ledfx.virtuals._paused", {"private": 1}),
        ("self._ledfx._load_sendspin_servers()", {"private": 1}),
        ("x = ledfx.devices.get(i)._config", {}),  # a call breaks the chain
        ("x = virtual.config", {}),
        ("x = self._ledfx.virtuals.config", {}),
        ("x = self._ledfx.__class__", {}),
        ("x = self._ledfx.virtuals.get(i)", {}),
        ("x = request.app.config", {}),
        # config-write: every assignment form through the core's config
        ("self._ledfx.config.port = 1", {"config-write": 1, "core-config": 1}),
        ("ledfx.config.virtuals[k] = v", {"config-write": 1, "core-config": 1}),
        ("self._ledfx.config.n += 1", {"config-write": 1, "core-config": 1}),
        ("del ledfx.config.scenes[k]", {"config-write": 1, "core-config": 1}),
        ("del self._ledfx.config.scenes", {"config-write": 1, "core-config": 1}),
        ("a, ledfx.config.x = 1, 2", {"config-write": 1, "core-config": 1}),
        ("self._ledfx.config.x: int = 1", {"config-write": 1, "core-config": 1}),
        # config-write: mutating calls on a chain below the core's config
        *[
            (
                f"self._ledfx.config.virtuals.{m}(1)",
                {"config-write": 1, "core-config": 1},
            )
            for m in sorted(MUTATORS)
        ],
        (
            "ledfx.config.user_presets['a'].update(b)",
            {"config-write": 1, "core-config": 1},
        ),
        # aliases: assignment, for, alias of alias, mutator, del, subscript
        (
            "def f():\n cfg = ledfx.config\n cfg.audio = 1",
            {"config-write": 1, "core-config": 1},
        ),
        (
            "def f():\n for v in ledfx.config.virtuals:\n  v.x = 1",
            {"config-write": 1, "core-config": 1},
        ),
        (
            "def f():\n a = ledfx.config.scenes\n a.pop(k)",
            {"config-write": 1, "core-config": 1},
        ),
        (
            "def f():\n a = ledfx.config\n b = a.scenes\n del b[k]",
            {"config-write": 1, "core-config": 1},
        ),
        (
            "def f():\n c = self._ledfx.config\n c.x[1] += 1",
            {"config-write": 1, "core-config": 1},
        ),
        # a nested function is not counted twice
        (
            "def f():\n c = ledfx.config\n def g():\n  c.x = 1",
            {"config-write": 1, "core-config": 1},
        ),
        # an alias only read, rebound, or in another function
        ("def f():\n c = ledfx.config\n x = c.port\n c = {}", {"core-config": 1}),
        ("def f():\n c = ledfx.config\ndef g():\n c.x = 1", {"core-config": 1}),
        # getattr spellings of the core, config and store
        ('getattr(ledfx, "config").x = 1', {"config-write": 1}),
        ('getattr(self, "_ledfx").config.x = 1', {"config-write": 1, "core-config": 1}),
        (
            's = getattr(getattr(self, "_ledfx", None), "config_store", None)',
            {"config-store": 1},
        ),
        ('getattr(effect, "config").x = 1', {}),
        # core / _core are core names; more mutators; recursive unpacking
        ("self._core.config.x = 1", {"config-write": 1, "core-config": 1}),
        ("core.config.s.add(1)", {"config-write": 1, "core-config": 1}),
        *[
            (f"ledfx.config.l.{m}()", {"config-write": 1, "core-config": 1})
            for m in ("sort", "popitem", "add", "discard", "reverse")
        ],
        ("a, (b, *ledfx.config.x) = 1", {"config-write": 1, "core-config": 1}),
        ("[a, [ledfx.config.x, b]] = 1", {"config-write": 1, "core-config": 1}),
        # not writes: reads, locals named config, config not reached from the core
        ("x = self._ledfx.config.virtuals.copy()", {"core-config": 1}),
        ("config = {}\nconfig['a'] = 1\nconfig.update(b)", {}),
        ("self.config.x = 1\nself.config.items.append(1)", {}),
        ("effect.config.x = 1\neffect.config.d.update(b)", {}),
        ("self._ledfx.virtuals.config.x = 1", {}),
        ("self._ledfx.devices.update(a)", {}),
    ],
)
def test_rules(source: str, expected: dict[str, int]) -> None:
    assert dict(violations(source)) == expected


@pytest.mark.parametrize(
    "source", ["self._ledfx.config_store.request_save()", "self._ledfx.config.a = 1"]
)
def test_owners_may_manage_config(source: str) -> None:
    assert dict(violations(source, api=False, owner=True)) == {}


def test_a_read_outside_api_is_allowed() -> None:
    assert dict(violations("x = self._ledfx.config.port", api=False)) == {}


def test_other_modules_may_not_manage_config() -> None:
    src = "self._ledfx.config_store.request_save()\nself._ledfx.config.a = 1"
    assert dict(violations(src, api=False)) == {"config-store": 1, "config-write": 1}


def test_owners_exist() -> None:
    assert [o for o in OWNERS if not (ROOT / o).exists()] == []
    assert [o for o in OWNERS if o.startswith(API_PREFIX)] == []


def test_no_new_violations() -> None:
    allowed = load_allowlist()
    new = {k: n for k, n in scan().items() if n > allowed.get(k, 0)}
    assert new == {}, (
        "Config was managed outside the config owners (or API code reached "
        "into core internals); go through a manager method instead"
    )


def test_allowlist_is_not_stale() -> None:
    current = scan()
    stale = {k: n for k, n in load_allowlist().items() if current.get(k, 0) < n}
    assert stale == {}, (
        "Violations were removed: shrink the allowlist with "
        "`uv run python -m tests.test_config_boundary > tests/config_boundary_allowlist.txt`"
    )


def test_v2_is_never_allowlisted() -> None:
    assert [k for k in load_allowlist() if k.startswith(V2_PREFIX)] == []


def test_v2_has_no_pyrefly_baseline_entries() -> None:
    """Code under ledfx/api/v2/ is strict-clean, never baselined."""
    errors = json.loads(PYREFLY_BASELINE.read_text("utf-8"))["errors"]
    assert [e["path"] for e in errors if e["path"].startswith(V2_PREFIX)] == []


if __name__ == "__main__":
    for key, count in scan().items():
        print(f"{key}:{count}")
