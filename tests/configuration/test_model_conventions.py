import re

import pytest
from pydantic.json_schema import JsonSchemaValue

from tests.configuration.model_schema import (
    _registry_by_kind,
    _registry_classes,
    render_model_schemas,
)

SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_registry_is_not_silently_shrinking() -> None:
    by_kind = _registry_by_kind()
    assert all(by_kind.values()), {k: len(v) for k, v in by_kind.items()}
    assert len(_registry_classes()) >= 80


@pytest.mark.parametrize("key,schema", sorted(render_model_schemas().items()))
def test_config_keys_are_snake_case_and_use_color(
    key: str, schema: JsonSchemaValue
) -> None:
    for field in schema["properties"]:
        assert SNAKE.match(field), f"{key}.{field} is not snake_case"
        assert "colour" not in field, f"{key}.{field}: use 'color'"
