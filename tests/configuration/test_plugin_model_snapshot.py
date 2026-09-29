import json

from tests.configuration.model_schema import MODEL_SNAPSHOT, render_model_schemas

# Plugins whose module imports a dependency that may not install everywhere;
# only these may be missing from the current registry.
PLATFORM_OPTIONAL = {
    "ledfx.devices.launchpad:launchpad",  # python-rtmidi (needs ALSA to build)
}


def test_plugin_model_schemas_unchanged() -> None:
    with open(MODEL_SNAPSHOT, encoding="utf-8") as file:
        expected = json.load(file)
    current = render_model_schemas()
    # New plugins must be snapshotted; only platform-optional ones may be absent.
    assert set(current) <= set(expected)
    assert PLATFORM_OPTIONAL <= set(expected)
    assert set(expected) - set(current) <= PLATFORM_OPTIONAL
    for key in current:
        assert current[key] == expected[key], f"model schema drift in {key}"
        assert list(current[key]["properties"]) == list(expected[key]["properties"]), (
            key
        )
