"""API-boundary ratchet: ledfx/api/** goes through the managers.

An AST walk counts, per file:
- config-store: any ``.config_store`` attribute;
- core-config: ``.config`` read off the core (``self._ledfx``, ``self.ledfx``,
  ``ledfx`` or ``_ledfx``);
- private: a ``_private`` (not dunder) attribute of the core or of anything
  reached from it by attributes (``self._ledfx.virtuals._paused``).

tests/config_boundary_allowlist.txt holds today's counts as ``path:rule:count``.
It may only shrink, and never names a file under ledfx/api/v2/. After moving
logic into a manager, regenerate it:
    uv run python -m tests.test_config_boundary > tests/config_boundary_allowlist.txt
"""

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "ledfx" / "api"
ALLOWLIST = Path(__file__).with_name("config_boundary_allowlist.txt")
PYREFLY_BASELINE = ROOT / "pyrefly_errors.json"
V2_PREFIX = "ledfx/api/v2/"
CORE_NAMES = frozenset({"ledfx", "_ledfx"})


def _is_core(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in CORE_NAMES
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


def violations(source: str) -> Counter[str]:
    """Rule name -> number of violations in source."""
    found = Counter[str]()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr == "config_store":
            found["config-store"] += 1
        elif node.attr == "config" and _is_core(node.value):
            found["core-config"] += 1
        elif (
            node.attr.startswith("_")
            and not node.attr.startswith("__")
            and _reached_from_core(node.value)
        ):
            found["private"] += 1
    return found


def scan() -> dict[str, int]:
    """``path:rule`` -> count for every violation under ledfx/api."""
    out: dict[str, int] = {}
    for path in sorted(API_DIR.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for rule, count in sorted(violations(path.read_text("utf-8")).items()):
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
    ],
)
def test_rules(source: str, expected: dict[str, int]) -> None:
    assert dict(violations(source)) == expected


def test_no_new_violations() -> None:
    allowed = load_allowlist()
    new = {k: n for k, n in scan().items() if n > allowed.get(k, 0)}
    assert new == {}, (
        "API code reached into the config store or core internals; add or "
        "use a manager method instead"
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
