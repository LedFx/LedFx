"""Convert plugin modules from voluptuous CONFIG_SCHEMA to typed Config classes.

For each Effect/Device/Integration subclass in FILE (parents must already be
converted):
  * CONFIG_SCHEMA (assignment or @staticmethod @property) becomes
    ``class Config(<parent Configs>): <fields>`` + ``config = TypedConfig(Config)``;
    an existing ``config = TypedConfig(...)`` in the class (layer 9 put
    ``TypedConfig(PluginConfig)`` on Effect/Device/Integration) is replaced, so
    the class never ends up with two ``config`` descriptors;
  * a class with no CONFIG_SCHEMA but two or more parent Configs gets
    ``class Config(A.Config, B.Config): pass`` + the descriptor;
  * self._config["k"], self._config.get("k"[, d]), self.config["k"] and, in
    config_updated(self, config), config["k"]/config.get(...) become self.config.k.
Imports the file already has are not added twice.
Any construct it cannot translate is reported and the file is left untouched.
Afterwards run: uv run ruff check --fix FILE && uv run ruff format FILE
"""

import argparse
import ast
import importlib
import inspect
import os
import sys
from dataclasses import dataclass

SIMPLE = {"bool": "bool", "str": "str", "int": "int", "float": "float"}
BY_NAME = {
    "validate_color": "Color",
    "validate_gradient": "Gradient",
    "fps_validator": "Fps",
    "virtual_id_validator": "VirtualId",
    "validate_ipv4_address": "IPv4",
}


class Unsupported(Exception):
    pass


@dataclass(frozen=True)
class Edit:
    start: tuple[int, int]  # (lineno, col_offset) as reported by ast (utf-8 bytes)
    end: tuple[int, int]
    text: str


def _src(node: ast.AST, source: str) -> str:
    text = ast.get_source_segment(source, node)
    if text is None:
        raise Unsupported(f"no source for {ast.dump(node)}")
    return text


def _vol_call(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "vol"
    )


def _element_type(options: list[object] | None) -> str:
    kinds = {type(o).__name__ for o in options or []}
    return kinds.pop() if len(kinds) == 1 and kinds <= {"str", "int"} else "object"


def translate_validator(
    node: ast.expr, source: str, options: list[object] | None
) -> tuple[str, dict[str, str], dict[str, str], set[str]]:
    names: set[str] = set()
    if isinstance(node, ast.Name) and node.id in SIMPLE:
        return SIMPLE[node.id], {}, {}, names
    if isinstance(node, ast.Name) and node.id in ("list", "dict"):
        return (
            ("list[object]" if node.id == "list" else "dict[str, object]"),
            {},
            {},
            names,
        )
    if isinstance(node, ast.Name) and node.id in BY_NAME:
        return BY_NAME[node.id], {}, {}, {BY_NAME[node.id]}
    if isinstance(node, ast.Attribute) and node.attr == "device_index_validator":
        return "AudioDeviceIndex", {}, {}, {"AudioDeviceIndex"}
    if _vol_call(node, "Coerce") and isinstance(node.args[0], ast.Name):
        target = node.args[0].id
        if target not in ("int", "float"):
            raise Unsupported(f"vol.Coerce({target})")
        alias = "CoercedInt" if target == "int" else "CoercedFloat"
        return alias, {}, {}, {alias}
    if _vol_call(node, "Range"):
        if any(k.arg in ("min_included", "max_included", "msg") for k in node.keywords):
            raise Unsupported(_src(node, source))
        bounds = dict(zip(("min", "max"), node.args))
        bounds.update({k.arg: k.value for k in node.keywords if k.arg})
        kwargs = {}
        for vol_key, pyd_key in (("min", "ge"), ("max", "le")):
            value = bounds.get(vol_key)
            if value is not None and not (
                isinstance(value, ast.Constant) and value.value is None
            ):
                kwargs[pyd_key] = _src(value, source)
        return "", kwargs, {}, names
    if _vol_call(node, "In"):
        (container,) = node.args
        if (
            isinstance(container, (ast.List, ast.Tuple))
            and all(isinstance(e, ast.Constant) for e in container.elts)
            and container.elts
        ):
            values = ", ".join(_src(e, source) for e in container.elts)
            return f"Literal[{values}]", {}, {}, {"Literal"}
        element = _element_type(options)
        return (
            f"Annotated[{element}, OneOf({_src(container, source)})]",
            {},
            {},
            {"Annotated", "OneOf"},
        )
    if _vol_call(node, "All"):
        type_src, kwargs, extra = "", {}, {}
        for part in node.args:
            part_type, part_kwargs, part_extra, part_names = translate_validator(
                part, source, options
            )
            names |= part_names
            kwargs.update(part_kwargs)
            extra.update(part_extra)
            if part_type.startswith(("Literal[", "Annotated[")):
                if type_src and part_type.startswith("Annotated[object"):
                    part_type = part_type.replace(
                        "Annotated[object", f"Annotated[{type_src}", 1
                    )
                type_src = part_type
            elif part_type and not type_src.startswith(("Literal[", "Annotated[")):
                type_src = part_type
        if not type_src:
            raise Unsupported(_src(node, source))
        return type_src, kwargs, extra, names
    raise Unsupported(_src(node, source))


def field_line(
    key: ast.expr, value: ast.expr, source: str, options: list[object] | None
) -> tuple[str, set[str]]:
    if not (
        isinstance(key, ast.Call)
        and (_vol_call(key, "Optional") or _vol_call(key, "Required"))
    ):
        raise Unsupported(f"schema key {_src(key, source)}")
    required = _vol_call(key, "Required")
    name_node = key.args[0]
    if not isinstance(name_node, ast.Constant) or not isinstance(name_node.value, str):
        raise Unsupported(f"non-literal key {_src(key, source)}")
    keywords = {k.arg: k.value for k in key.keywords if k.arg}
    type_src, kwargs, extra, names = translate_validator(value, source, options)
    names |= {"Field"}
    args: list[str] = []
    if "default" in keywords:
        default = keywords["default"]
        empty = (isinstance(default, ast.Name) and default.id in ("list", "dict")) or (
            isinstance(default, (ast.List, ast.Dict))
            and not _src(default, source).strip("[]{} ")
        )
        if isinstance(default, ast.Lambda):
            raise Unsupported(f"lambda default on {name_node.value}")
        if empty and type_src.startswith(("list[", "dict[")):
            # A typed empty default: pyrefly cannot infer `[]`/`{}` (implicit Any).
            args.append(f"{type_src}()")
        elif isinstance(default, ast.Name) and default.id in ("list", "dict"):
            args.append("[]" if default.id == "list" else "{}")
        else:
            args.append(_src(default, source))
    elif not required:
        args.append("None")
        type_src = f"{type_src} | None"
        extra["X_OMIT_DEFAULT"] = "True"
    description = keywords.get("description")
    if description is not None:
        if isinstance(description, ast.Constant) and description.value is False:
            extra["X_LEGACY"] = '{"description": False}'
        else:
            args.append(f"description={_src(description, source)}")
    if required:
        extra = {"X_REQUIRED": "True", **extra}
    args += [f"{k}={v}" for k, v in kwargs.items()]
    if extra:
        args.append(
            "json_schema_extra={"
            + ", ".join(f"{k}: {v}" for k, v in extra.items())
            + "}"
        )
        names |= set(extra)
    return f"{name_node.value}: {type_src} = Field({', '.join(args)})", names


def _is_self_config(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in ("_config", "config")
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_public_self_config(node: ast.AST) -> bool:
    return (
        _is_self_config(node)
        and isinstance(node, ast.Attribute)
        and node.attr == "config"
    )


def access_edits(
    class_node: ast.ClassDef, source: str, fields: set[str], omit_default: set[str]
) -> list[Edit]:
    edits: list[Edit] = []

    def key_of(slice_node: ast.AST) -> str:
        if not (
            isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str)
        ):
            raise Unsupported(f"dynamic config key {_src(slice_node, source)}")
        if slice_node.value not in fields:
            raise Unsupported(
                f"config key '{slice_node.value}' is not a field (UI-only extra?)"
            )
        return slice_node.value

    def visit(node: ast.AST, config_param: bool) -> None:
        for child in ast.iter_child_nodes(node):
            in_hook = config_param or (
                isinstance(child, ast.FunctionDef)
                and child.name == "config_updated"
                and len(child.args.args) >= 2
                and child.args.args[1].arg == "config"
            )

            def target_ok(n: ast.AST, in_hook: bool = in_hook) -> bool:
                return _is_self_config(n) or (
                    in_hook and isinstance(n, ast.Name) and n.id == "config"
                )

            targets = (
                child.targets
                if isinstance(child, ast.Assign)
                else [child.target]
                if isinstance(child, (ast.AugAssign, ast.AnnAssign))
                else []
            )
            if any(_is_public_self_config(t) for t in targets):
                # TypedConfig is read-only; route through update_config/_set_config_values
                raise Unsupported(f"assignment to self.config: {_src(child, source)}")
            if isinstance(child, ast.Subscript) and target_ok(child.value):
                if not isinstance(child.ctx, ast.Load):
                    raise Unsupported(f"config write {_src(child, source)}")
                key = key_of(child.slice)
                edits.append(
                    Edit(
                        (child.lineno, child.col_offset),
                        (child.end_lineno, child.end_col_offset),
                        f"self.config.{key}",
                    )
                )
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "get"
                and target_ok(child.func.value)
            ):
                key = key_of(child.args[0])
                text = f"self.config.{key}"
                if len(child.args) > 1 and key in omit_default:
                    text = f"({text} if {text} is not None else {_src(child.args[1], source)})"
                edits.append(
                    Edit(
                        (child.lineno, child.col_offset),
                        (child.end_lineno, child.end_col_offset),
                        text,
                    )
                )
                continue
            if (
                isinstance(child, ast.Compare)
                and any(isinstance(op, (ast.In, ast.NotIn)) for op in child.ops)
                and any(target_ok(c) for c in child.comparators)
            ):
                raise Unsupported(f"membership test {_src(child, source)}")
            visit(child, in_hook)

    visit(class_node, False)
    return edits


def apply_edits(source: str, edits: list[Edit]) -> str:
    raw = source.encode("utf-8")
    starts = [0]
    for line in raw.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))

    def offset(pos: tuple[int, int]) -> int:
        return starts[pos[0] - 1] + pos[1]

    # Right to left; at a shared start, the wider (deleting) edit goes first so
    # an insertion at that position is not swallowed by the deletion.
    for edit in sorted(
        edits, key=lambda e: (offset(e.start), offset(e.end)), reverse=True
    ):
        raw = (
            raw[: offset(edit.start)]
            + edit.text.encode("utf-8")
            + raw[offset(edit.end) :]
        )
    return raw.decode("utf-8")


# ---- whole-file driver -------------------------------------------------------
def _module_name(path: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), os.getcwd())
    return rel[:-3].replace(os.sep, ".").removesuffix(".__init__")


def _schema_dict(stmt: ast.stmt) -> tuple[ast.Dict, int]:
    """Return (dict node, first line) of a CONFIG_SCHEMA definition."""
    if isinstance(stmt, ast.Assign):
        call = stmt.value
        first = stmt.lineno
    elif isinstance(stmt, ast.FunctionDef):
        if len(stmt.body) != 1 or not isinstance(stmt.body[0], ast.Return):
            raise Unsupported(
                f"CONFIG_SCHEMA property at line {stmt.lineno} has logic; convert by hand"
            )
        call = stmt.body[0].value
        first = (
            min(d.lineno for d in stmt.decorator_list)
            if stmt.decorator_list
            else stmt.lineno
        )
    else:
        raise Unsupported("unexpected CONFIG_SCHEMA form")
    if not (_vol_call(call, "Schema") and isinstance(call.args[0], ast.Dict)):
        raise Unsupported(f"CONFIG_SCHEMA at line {first} is not vol.Schema({{...}})")
    return call.args[0], first


def _find_schema_stmt(class_node: ast.ClassDef) -> ast.stmt | None:
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CONFIG_SCHEMA" for t in stmt.targets
        ):
            return stmt
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "CONFIG_SCHEMA":
            return stmt
    return None


def convert_file(path: str) -> list[str]:
    from ledfx.devices import Device
    from ledfx.effects import Effect
    from ledfx.integrations import Integration

    with open(path, encoding="utf-8") as file:
        source = file.read()
    tree = ast.parse(source)
    module = importlib.import_module(_module_name(path))
    problems: list[str] = []
    edits: list[Edit] = []
    names: set[str] = {"TypedConfig"}

    for class_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        cls = getattr(module, class_node.name, None)
        if not (
            inspect.isclass(cls) and issubclass(cls, (Effect, Device, Integration))
        ):
            continue
        if "Config" in cls.__dict__:
            continue
        try:
            registry_parents = [
                (base_node, live)
                for base_node, live in zip(class_node.bases, cls.__bases__)
                if issubclass(live, (Effect, Device, Integration))
            ]
            for _, live in registry_parents:
                for ancestor in inspect.getmro(live):
                    needs = (
                        "CONFIG_SCHEMA" in ancestor.__dict__
                        and "Config" not in ancestor.__dict__
                    )
                    if needs and ancestor.__module__ != module.__name__:
                        raise Unsupported(
                            f"convert parent {ancestor.__qualname__} first"
                        )

            # Same-file parents are converted in this pass (defined above us), so
            # pick bases from the class hierarchy, not from live Config objects. A
            # parent is represented by the nearest class in its MRO that owns a
            # schema (AudioReactiveEffect.Config *is* Effect.Config), and owners
            # already covered by another kept owner's subclass are dropped, so the
            # generated Config bases always have a consistent MRO.
            def owner(live: type) -> type | None:
                return next(
                    (
                        a
                        for a in inspect.getmro(live)
                        if "CONFIG_SCHEMA" in a.__dict__ or "Config" in a.__dict__
                    ),
                    None,
                )

            owners = {id(live): owner(live) for _, live in registry_parents}
            kept: list[tuple[ast.expr, type]] = []
            seen: set[type] = set()
            for base_node, live in registry_parents:
                own = owners[id(live)]
                if own is None or own in seen:
                    continue
                if any(
                    o is not None and o is not own and issubclass(o, own)
                    for o in owners.values()
                ):
                    continue
                seen.add(own)
                kept.append((base_node, live))
            base_list = (
                ", ".join(f"{_src(b, source)}.Config" for b, _ in kept)
                or "PluginConfig"
            )
            if base_list == "PluginConfig":
                names.add("PluginConfig")

            model = cls.config_model()
            fields = set(model.model_fields)
            omit = {
                n
                for n, info in model.model_fields.items()
                if isinstance(info.json_schema_extra, dict)
                and info.json_schema_extra.get("x-ledfx-omit-default")
            }
            stmt = _find_schema_stmt(class_node)
            indent = " " * class_node.body[0].col_offset
            if stmt is not None:
                schema, first = _schema_dict(stmt)
                if any(k is None for k in schema.keys):
                    raise Unsupported(
                        "CONFIG_SCHEMA splats another schema (**X.CONFIG_SCHEMA.schema)"
                    )
                class_names = {
                    t.id
                    for st in class_node.body
                    if isinstance(st, (ast.Assign, ast.AnnAssign))
                    for t in (st.targets if isinstance(st, ast.Assign) else [st.target])
                    if isinstance(t, ast.Name)
                } - {"CONFIG_SCHEMA"}
                used = {
                    n.id for n in ast.walk(schema) if isinstance(n, ast.Name)
                } & class_names
                if used:
                    # A nested `class Config` body cannot see the enclosing class body.
                    raise Unsupported(
                        f"schema uses class attributes {sorted(used)}; move them to module level"
                    )
                lines = []
                for key, value in zip(schema.keys, schema.values):
                    options = None
                    field_name = (
                        key.args[0].value
                        if isinstance(key, ast.Call) and key.args
                        else None
                    )
                    info = model.model_fields.get(field_name) if field_name else None
                    if info is not None:
                        for meta in info.metadata:
                            if type(meta).__name__ == "OneOf":
                                options = meta.values()
                    line, field_names = field_line(key, value, source, options)
                    names |= field_names
                    lines.append(f"{indent}    {line}")
                body = "\n".join(lines) or f"{indent}    pass"
                text = f"class Config({base_list}):\n{body}\n\n{indent}config = TypedConfig(Config)"
                edits.append(
                    Edit(
                        (first, stmt.col_offset),
                        (stmt.end_lineno, stmt.end_col_offset),
                        text,
                    )
                )
                edits.extend(descriptor_edits(class_node))
            elif len(kept) >= 2:
                anchor = class_node.body[0]
                if isinstance(anchor, ast.Expr) and isinstance(
                    anchor.value, ast.Constant
                ):
                    pos = (anchor.end_lineno, anchor.end_col_offset)
                    text = f"\n\n{indent}class Config({base_list}):\n{indent}    pass\n\n{indent}config = TypedConfig(Config)"
                else:
                    pos = (anchor.lineno, anchor.col_offset)
                    text = f"class Config({base_list}):\n{indent}    pass\n\n{indent}config = TypedConfig(Config)\n\n{indent}"
                edits.append(Edit(pos, pos, text))
                edits.extend(descriptor_edits(class_node))
            edits.extend(access_edits(class_node, source, fields, omit))
        except Unsupported as err:
            problems.append(f"{path}:{class_node.lineno} {class_node.name}: {err}")

    if problems:
        return problems
    if not edits:
        return []
    with open(path, "w", encoding="utf-8") as file:
        file.write(rewrite(source, tree, edits, names))
    return []


def descriptor_edits(class_node: ast.ClassDef) -> list[Edit]:
    """Delete `config = TypedConfig(...)` from the class body (the caller adds the
    replacement), so the class never has two `config` descriptors (ruff PIE794)."""
    return [
        Edit(
            (stmt.lineno, stmt.col_offset),
            (stmt.end_lineno, stmt.end_col_offset),
            "",
        )
        for stmt in class_node.body
        if isinstance(stmt, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "config" for t in stmt.targets)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Name)
        and stmt.value.func.id == "TypedConfig"
    ]


def rewrite(source: str, tree: ast.Module, edits: list[Edit], names: set[str]) -> str:
    """Apply the edits, then add the imports the file doesn't already have."""
    new_source = apply_edits(source, edits)
    existing = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    header = _imports(names - existing)
    body_start = max(
        (
            n.end_lineno
            for n in tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
        ),
        default=0,
    )
    lines = new_source.splitlines(keepends=True)
    return "".join(lines[:body_start]) + header + "".join(lines[body_start:])


def _imports(names: set[str]) -> str:
    fields_names = sorted(
        names
        & {
            "AudioDeviceIndex",
            "CoercedFloat",
            "CoercedInt",
            "Color",
            "Fps",
            "Gradient",
            "IPv4",
            "OneOf",
            "VirtualId",
            "X_LEGACY",
            "X_OMIT_DEFAULT",
            "X_REQUIRED",
        }
    )
    plugin_names = sorted(names & {"PluginConfig", "TypedConfig"})
    typing_names = sorted(names & {"Annotated", "Literal"})
    out = []
    if "Field" in names:
        out.append("from pydantic import Field\n")
    if typing_names:
        out.append(f"from typing import {', '.join(typing_names)}\n")
    if fields_names:
        out.append(
            f"from ledfx.configuration.fields import {', '.join(fields_names)}\n"
        )
    if plugin_names:
        out.append(
            f"from ledfx.configuration.plugin import {', '.join(plugin_names)}\n"
        )
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    problems = [p for f in args.files for p in convert_file(f)]
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
