import ast
import importlib.util
import os

import pytest

SPEC = importlib.util.spec_from_file_location(
    "config_codemod",
    os.path.join(os.path.dirname(__file__), "..", "..", "tools", "config_codemod.py"),
)
assert SPEC is not None and SPEC.loader is not None
codemod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codemod)


def _entry(src: str) -> tuple[ast.expr, ast.expr, str]:
    node = ast.parse("{" + src + "}", mode="eval").body
    assert isinstance(node, ast.Dict) and node.keys[0] is not None
    return node.keys[0], node.values[0], "{" + src + "}"


@pytest.mark.parametrize(
    "src,expected",
    [
        (
            'vol.Optional("flip", description="Flip", default=False): bool',
            'flip: bool = Field(False, description="Flip")',
        ),
        (
            'vol.Optional("blur", description="Blur", default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10))',
            'blur: CoercedFloat = Field(0.0, description="Blur", ge=0.0, le=10)',
        ),
        (
            'vol.Required("name", description="Name"): str',
            'name: str = Field(description="Name", json_schema_extra={X_REQUIRED: True})',
        ),
        (
            'vol.Optional("advanced", description=False): bool',
            'advanced: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True, X_LEGACY: {"description": False}})',
        ),
        (
            'vol.Optional("mode", default="a"): vol.In(["a", "b"])',
            'mode: Literal["a", "b"] = Field("a")',
        ),
        (
            'vol.Optional("power", default="x"): vol.In(list(MAPPING.keys()))',
            'power: Annotated[str, OneOf(list(MAPPING.keys()))] = Field("x")',
        ),
        (
            'vol.Optional("color", default="#000000"): validate_color',
            'color: Color = Field("#000000")',
        ),
        (
            'vol.Optional("tags", default=list): list',
            "tags: list[object] = Field(list[object]())",
        ),
    ],
)
def test_field_line(src: str, expected: str) -> None:
    key, value, source = _entry(src)
    options = ["x"] if "MAPPING" in src else None
    line, _names = codemod.field_line(key, value, source, options)
    assert line == expected


def test_unsupported_validator_is_reported() -> None:
    key, value, source = _entry('vol.Optional("x", default=1): vol.Any(int, str)')
    with pytest.raises(codemod.Unsupported):
        codemod.field_line(key, value, source, None)


def test_access_edits_rewrite_reads() -> None:
    source = (
        "class E:\n"
        "    def render(self):\n"
        '        a = self._config["speed"]\n'
        '        b = self._config.get("mode", "x")\n'
        '        c = self._config.get("label", "none")\n'
        "    def config_updated(self, config):\n"
        '        d = config["speed"]\n'
    )
    tree = ast.parse(source)
    edits = codemod.access_edits(
        tree.body[0], source, {"speed", "mode", "label"}, {"label"}
    )
    out = codemod.apply_edits(source, edits)
    assert "a = self.config.speed" in out
    assert "b = self.config.mode" in out
    assert 'c = (self.config.label if self.config.label is not None else "none")' in out
    assert "d = self.config.speed" in out


def test_access_to_unknown_key_is_reported() -> None:
    source = (
        'class E:\n    def f(self):\n        return self._config["gradient_name"]\n'
    )
    tree = ast.parse(source)
    with pytest.raises(codemod.Unsupported):
        codemod.access_edits(tree.body[0], source, {"speed"}, set())


def test_assignment_to_typed_config_is_reported() -> None:
    source = "class E:\n    def f(self, config):\n        self.config = config\n"
    tree = ast.parse(source)
    with pytest.raises(codemod.Unsupported):
        codemod.access_edits(tree.body[0], source, {"speed"}, set())


def test_storage_assignment_is_allowed() -> None:
    source = "class E:\n    def f(self, config):\n        self._config = config\n"
    tree = ast.parse(source)
    assert codemod.access_edits(tree.body[0], source, {"speed"}, set()) == []


def test_existing_descriptor_and_imports_are_not_duplicated() -> None:
    # Layer 9 put `config = TypedConfig(PluginConfig)` (and its import) on the
    # base classes; converting one must leave exactly one descriptor and one import.
    source = (
        "from ledfx.configuration.plugin import PluginConfig, TypedConfig\n"
        "\n"
        "\n"
        "class Base:\n"
        "    config = TypedConfig(PluginConfig)\n"
        "    CONFIG_SCHEMA = None\n"
    )
    tree = ast.parse(source)
    class_node = tree.body[1]
    assert isinstance(class_node, ast.ClassDef)
    schema = class_node.body[1]
    assert schema.end_lineno is not None and schema.end_col_offset is not None
    edits = codemod.descriptor_edits(class_node) + [
        codemod.Edit(
            (schema.lineno, schema.col_offset),
            (schema.end_lineno, schema.end_col_offset),
            "class Config(PluginConfig):\n        pass\n\n    config = TypedConfig(Config)",
        )
    ]
    out = codemod.rewrite(source, tree, edits, {"TypedConfig", "PluginConfig"})
    ast.parse(out)  # still valid Python
    assert out.count("config = TypedConfig(") == 1
    assert "TypedConfig(Config)" in out and "TypedConfig(PluginConfig)" not in out
    assert out.count("from ledfx.configuration.plugin import") == 1


def test_insert_at_deleted_descriptor_keeps_the_insert() -> None:
    # A Config inserted where the old descriptor starts must survive its deletion.
    source = "class E:\n    config = TypedConfig(PluginConfig)\n"
    tree = ast.parse(source)
    class_node = tree.body[0]
    assert isinstance(class_node, ast.ClassDef)
    anchor = class_node.body[0]
    pos = (anchor.lineno, anchor.col_offset)
    edits = [codemod.Edit(pos, pos, "config = TypedConfig(Config)")]
    edits += codemod.descriptor_edits(class_node)
    out = codemod.apply_edits(source, edits)
    assert out == "class E:\n    config = TypedConfig(Config)\n"


def test_missing_imports_are_added_once() -> None:
    source = "import os\n\n\nclass E:\n    pass\n"
    tree = ast.parse(source)
    out = codemod.rewrite(source, tree, [], {"TypedConfig", "PluginConfig"})
    assert (
        out.count("from ledfx.configuration.plugin import PluginConfig, TypedConfig")
        == 1
    )


def test_existing_imports_are_left_alone() -> None:
    # A name the file already imports is not imported a second time.
    source = "from ledfx.configuration.fields import fps_validator\n\n\nX = 1\n"
    tree = ast.parse(source)
    out = codemod.rewrite(source, tree, [], {"Fps", "fps_validator"})
    assert out.startswith("from ledfx.configuration.fields import fps_validator\n")
    assert "from ledfx.configuration.fields import Fps\n" in out
