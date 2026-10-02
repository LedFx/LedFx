"""v1 goldens for the virtual presets endpoint.

Recorded before the endpoint moved onto the Virtuals manager; every later
change must keep these bytes, except where a commit re-records a golden on
purpose and says so. Regenerate with:

    LEDFX_UPDATE_GOLDENS=1 uv run pytest tests/v1_golden -q
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtual_presets import VirtualPresetsEndpoint
from ledfx.configuration.models import Preset
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core
from tests.v1_golden.harness import (
    Step,
    build_app,
    check,
    golden_names,
    replay,
    updating,
)

ENDPOINTS: tuple[type[RestEndpoint], ...] = (VirtualPresetsEndpoint, VirtualEndpoint)

BIRD = "/api/virtuals/dj%20bird"
PRESETS = f"{BIRD}/presets"


def apply(effect_id: str, preset_id: str, category: str = "ledfx_presets") -> Step:
    return (
        "PUT",
        PRESETS,
        {"category": category, "effect_id": effect_id, "preset_id": preset_id},
    )


SCENARIOS: dict[str, list[Step]] = {
    "apply": [
        apply("singleColor", "reset"),
        ("GET", BIRD, None),
        ("GET", PRESETS, None),
        apply("rainbow", "reset"),
        ("GET", BIRD, None),
        ("POST", PRESETS, {"name": "My Rainbow"}),
        apply("rainbow", "my-rainbow", "user_presets"),
        ("GET", PRESETS, None),
        apply("singleColor", "reset"),
        apply("rainbow", "my-rainbow", "user_presets"),
        ("GET", BIRD, None),
    ],
    "apply_errors": [
        apply("nosuchtype", "reset"),
        apply("singleColor", "no-such-preset"),
        apply("singleColor", "reset", "elsewhere"),
        ("PUT", "/api/virtuals/ghost/presets", {}),
        ("PUT", PRESETS, {"category": "ledfx_presets"}),
        ("GET", BIRD, None),
    ],
    # A virtual with no segments refuses every effect.
    "refused": [
        ("PUT", "/api/virtuals/empty/presets", apply("singleColor", "reset")[2]),
        ("GET", "/api/virtuals/empty", None),
        apply("singleColor", "reset"),
        ("PUT", "/api/virtuals/empty/presets", apply("rainbow", "reset")[2]),
        ("GET", "/api/virtuals/empty", None),
        ("GET", BIRD, None),
    ],
    # A stored user preset whose config the effect refuses.
    "bad_preset": [
        apply("rainbow", "broken", "user_presets"),
        ("GET", BIRD, None),
        apply("rainbow", "reset"),
        apply("rainbow", "broken", "user_presets"),
        ("GET", BIRD, None),
    ],
    "clear": [
        apply("singleColor", "reset"),
        ("DELETE", PRESETS, None),
        ("GET", BIRD, None),
        ("DELETE", PRESETS, None),
        ("DELETE", "/api/virtuals/ghost/presets", None),
    ],
    "safe_mode": [
        apply("singleColor", "reset"),
        ("GET", BIRD, None),
        ("DELETE", PRESETS, None),
        ("GET", BIRD, None),
    ],
}


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
async def test_v1_virtual_presets_are_unchanged(name: str, ledfx: MagicMock) -> None:
    if name == "bad_preset":
        ledfx.config.user_presets["rainbow"] = {
            "broken": Preset(name="broken", config={"speed": "fast"})
        }
    if name == "safe_mode":
        # Start from a running effect, then lock the config.
        ledfx.virtuals.set_effect("dj bird", "rainbow", None)
        enter_safe_mode(ledfx)
    records = await replay(build_app(ledfx, ENDPOINTS), SCENARIOS[name])
    check("virtual_presets", name, records)


def test_every_golden_has_a_scenario() -> None:
    if not updating():
        assert golden_names("virtual_presets") == set(SCENARIOS)
