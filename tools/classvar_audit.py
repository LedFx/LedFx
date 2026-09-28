"""AST audit: ClassVar annotations must structurally match their literal.

Ruff's RUF012 only asks for *a* ClassVar annotation; it cannot tell whether
the annotation describes the value. Two reviews of #1934 caught the same
class of mistake (a set literal annotated ``ClassVar[dict]``). This hook
turns that error class into a pre-commit failure instead of a review
comment.

For every ``ClassVar[...]`` annotated assignment whose value is a known
literal, the annotation is checked against the value structurally:

- ``list[E]`` / ``set[E]``: the value is that container and every element
  matches ``E``.
- ``dict[K, V]``: every key matches ``K`` and every value matches ``V``;
  ``**`` unpacking of a dict literal is checked recursively, other
  unpacking is trusted.
- ``tuple[A, B, ...]``: fixed length, positional. ``tuple[T, ...]`` is
  variadic (all elements match ``T``). ``tuple[T]`` is exactly one element.
- Scalars (``str``, ``int``, ``float``, ``bool``, ``bytes``) are checked
  against literal constants, with Python's numeric assignability (int and
  bool are acceptable where float is annotated; bool where int).
- Signed literals (``-1``, ``+2.5``) are unwrapped before checking.

Anything the audit cannot resolve — calls, names, attributes, enum
``.value`` members, comprehensions, forward references, unions, custom
classes, bare containers — is trusted rather than guessed, so it stays
silent on code it cannot judge.

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

# numeric tower: int and bool are assignable where float is annotated,
# bool where int is annotated (https://typing.python.org spec).
_NUMERIC_TOWER = {"float": {"int", "bool"}, "int": {"bool"}}


def _signed_constant(value: ast.expr) -> ast.Constant | None:
    """Unwrap ``+1`` / ``-1.5`` style unary constants to the inner Constant."""
    if isinstance(value, ast.Constant):
        return value
    if (
        isinstance(value, ast.UnaryOp)
        and isinstance(value.op, (ast.UAdd, ast.USub))
        and isinstance(value.operand, ast.Constant)
    ):
        return value.operand
    return None


def _is_known_literal(value: ast.expr) -> bool:
    """Constants (incl. signed), and dict/list/set/tuple literals."""
    return _signed_constant(value) is not None or isinstance(
        value, (ast.Dict, ast.List, ast.Set, ast.Tuple)
    )


def _is_classvar(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "ClassVar"
    if isinstance(node, ast.Attribute):
        return node.attr == "ClassVar"  # typing.ClassVar
    return False


def strip_classvar(annotation: ast.expr) -> ast.expr:
    if isinstance(annotation, ast.Subscript) and _is_classvar(annotation.value):
        return annotation.slice
    return annotation


def _scalar_ok(ann_name: str, const: ast.Constant) -> bool:
    type_name = type(const.value).__name__
    return type_name == ann_name or type_name in _NUMERIC_TOWER.get(ann_name, ())


def _dict_pairs_ok(value: ast.Dict, k_ann: ast.expr, v_ann: ast.expr) -> bool:
    for key, val in zip(value.keys, value.values):
        if key is None:
            # ``**`` unpacking: if the unpacked value is a dict literal we
            # can check its pairs recursively; otherwise trust it.
            if isinstance(val, ast.Dict) and not _dict_pairs_ok(val, k_ann, v_ann):
                return False
            continue
        if not (matches(key, k_ann) and matches(val, v_ann)):
            return False
    return True


def matches(value: ast.expr, annotation: ast.expr) -> bool:
    """Does a literal value node structurally match its annotation node?"""
    if not _is_known_literal(value):
        return True  # calls, names, attributes, comprehensions, ...: trust

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
        if name == "tuple":
            return isinstance(value, ast.Tuple)
        if name in SCALARS:
            const = _signed_constant(value)
            return const is not None and _scalar_ok(name, const)
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
        return _dict_pairs_ok(value, k_ann, v_ann)
    if base == "tuple":
        if not isinstance(value, ast.Tuple):
            return False
        if not isinstance(slc, ast.Tuple):
            # ``tuple[T]``: exactly one element of T
            return len(value.elts) == 1 and matches(value.elts[0], slc)
        if (
            len(slc.elts) == 2
            and isinstance(slc.elts[1], ast.Constant)
            and slc.elts[1].value is Ellipsis
        ):
            # ``tuple[T, ...]``: variadic, every element is T
            return all(matches(e, slc.elts[0]) for e in value.elts)
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
