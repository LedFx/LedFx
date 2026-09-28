"""AST audit: ClassVar annotations must structurally match their literal.

Ruff's RUF012 only asks for *a* ClassVar annotation; it cannot tell whether
the annotation describes the value. Two reviews of #1934 caught the same
class of mistake (a set literal annotated ``ClassVar[dict]``). This hook
turns that error class into a pre-commit failure instead of a review
comment.

For every ``ClassVar[...]`` annotated assignment whose value is a container
literal, the annotation is checked against the literal structurally:

- ``list[E]`` / ``set[E]``: the value is that container and every element
  matches ``E``.
- ``dict[K, V]``: the value is a dict and every key matches ``K``, every
  value matches ``V``.
- ``tuple[A, B, ...]``: same length, positional matches.
- Bare names (``str``, ``int``, a custom class, ``Any``), parameterised
  non-containers (``Callable[[], None]``, ``type[X]``), unions and forward
  references are trusted: they are not structurally checkable without a
  type checker.

Scope note: this is a structural audit, not a type checker. It knows
nothing about class hierarchies or imports; a real checker is the
follow-up if the project wants that.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

SKIP_PARTS = {".venv", ".git", "__pycache__", "ledfx_frontend", "build", "dist"}

SCALARS = {"str", "int", "float", "bool", "bytes"}


def ann_base(annotation: ast.expr) -> str | None:
    """Base name of a (possibly subscripted) annotation, else None."""
    node: ast.expr = annotation
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def strip_classvar(annotation: ast.expr) -> ast.expr:
    if (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id == "ClassVar"
    ):
        return annotation.slice
    return annotation


def matches(value: ast.expr, annotation: ast.expr) -> bool:
    """Does a literal value node structurally match its annotation node?"""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return True  # forward reference: not resolvable here

    if isinstance(annotation, ast.Name):
        name = annotation.id
        if name == "dict":
            return isinstance(value, ast.Dict)
        if name == "list":
            return isinstance(value, ast.List)
        if name == "set":
            return isinstance(value, ast.Set)
        if name in SCALARS:
            if isinstance(value, ast.Constant):
                return type(value.value).__name__ == name
            # a container literal can never be a scalar; other non-literal
            # nodes (enum .value, calls, computed) can be anything: trust
            return not isinstance(value, (ast.Dict, ast.List, ast.Set, ast.Tuple))
        return True  # other bare names (classes, enums, Any): trust them

    if not isinstance(annotation, ast.Subscript):
        return True  # unions, expressions, anything non-structural: trust it

    base = annotation.value.id if isinstance(annotation.value, ast.Name) else None
    slc = annotation.slice

    if base == "list":
        return isinstance(value, ast.List) and all(matches(e, slc) for e in value.elts)
    if base == "set":
        return isinstance(value, ast.Set) and all(matches(e, slc) for e in value.elts)
    if base == "dict":
        if not (
            isinstance(value, ast.Dict)
            and isinstance(slc, ast.Tuple)
            and len(slc.elts) == 2
        ):
            return False
        k_ann, v_ann = slc.elts
        return all(matches(k, k_ann) for k in value.keys if k is not None) and all(
            matches(v, v_ann) for v in value.values
        )
    if base == "tuple":
        if not (isinstance(value, ast.Tuple) and isinstance(slc, ast.Tuple)):
            return False
        if len(value.elts) != len(slc.elts):
            return False
        return all(matches(v, a) for v, a in zip(value.elts, slc.elts))

    # type[X], Callable[...], custom generics, ...: not structurally checkable
    return True


def audit_file(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    problems: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AnnAssign) and node.value is not None):
            continue
        annotation = node.annotation
        if "ClassVar" not in ast.unparse(annotation):
            continue
        stripped = strip_classvar(annotation)
        if not matches(node.value, stripped):
            problems.append(
                f"{path}:{node.lineno}: value of {ast.unparse(node.target)} "
                f"does not match its annotation {ast.unparse(annotation)}"
            )
    return problems


def iter_python_files(raw: str) -> list[Path]:
    root = Path(raw)
    if root.is_file():
        return [root]
    return [p for p in root.rglob("*.py") if not (SKIP_PARTS & set(p.parts))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=["ledfx", "tests", "docs"])
    args = parser.parse_args(argv)

    failures: list[str] = []
    checked = 0
    for raw in args.paths:
        for f in iter_python_files(raw):
            checked += 1
            failures.extend(audit_file(f))

    for line in failures:
        print(line, file=sys.stderr)
    print(f"classvar-audit: checked {checked} files, {len(failures)} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise sys.exit(main())
