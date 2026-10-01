import json

from tests.configuration.legacy_schema import (
    SNAPSHOT,
    normalise,
    property_orders,
    render_legacy_schema,
)

PLUGIN_KINDS = ("devices", "effects", "integrations")


def test_legacy_schema_is_unchanged() -> None:
    with open(SNAPSHOT, encoding="utf-8") as file:
        expected = json.load(file)
    current = normalise(render_legacy_schema())
    assert sorted(current) == sorted(expected)
    for kind in expected:
        if kind in PLUGIN_KINDS:
            # Some plugins only register where their optional deps import
            # (platform/Python version): compare what exists here, and refuse
            # plugins that are missing from the snapshot.
            assert set(current[kind]) <= set(expected[kind]), (
                f"new {kind} not in snapshot"
            )
            for name in current[kind]:
                assert current[kind][name] == expected[kind][name], (
                    f"drift in {kind}.{name}"
                )
                assert property_orders(current[kind][name]) == property_orders(
                    expected[kind][name]
                )
        else:
            assert current[kind] == expected[kind], f"legacy schema drift in {kind}"
            assert property_orders(current[kind]) == property_orders(expected[kind])
