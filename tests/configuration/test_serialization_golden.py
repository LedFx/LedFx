"""v1 dumps stay byte-identical, pinned by recorded goldens."""

import json

import pytest

from tests.configuration.serialization_golden import (
    CONFIG_DUMPS,
    SCHEMAS_DUMP,
    render_config_dumps,
    render_core_schemas,
)
from tests.configuration.test_plugin_model_snapshot import PLATFORM_OPTIONAL


def _load(path: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def config_dumps() -> dict[str, dict[str, str]]:
    return render_config_dumps()


def test_config_dumps_are_unchanged(config_dumps: dict[str, dict[str, str]]) -> None:
    expected = _load(CONFIG_DUMPS)
    assert sorted(config_dumps) == sorted(expected)
    optional_types = {key.rsplit(":", 1)[-1] for key in PLATFORM_OPTIONAL}
    for name, digests in config_dumps.items():
        recorded = expected[name]
        assert isinstance(recorded, dict)
        # Only a platform-optional plugin may be missing from this registry.
        missing = set(recorded) - set(digests)
        assert {key.split(":", 1)[1] for key in missing} <= optional_types, name
        assert set(digests) <= set(recorded), f"{name}: new plugin dumps"
        for key, digest in digests.items():
            assert digest == recorded[key], f"{name}: dump drift in {key}"


def test_core_schemas_are_unchanged() -> None:
    current = json.loads(json.dumps(render_core_schemas()))
    expected = _load(SCHEMAS_DUMP)
    assert current == expected
    assert json.dumps(current) == json.dumps(expected)  # key order too
