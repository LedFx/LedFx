"""v1 goldens for the scenes family.

Recorded before Scenes moved onto the Virtuals manager; every later change
must keep these bytes, except where a commit re-records a golden on purpose
and says so. Regenerate with:

    LEDFX_UPDATE_GOLDENS=1 uv run pytest tests/v1_golden -q
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.config import ConfigEndpoint
from ledfx.api.scenes import ScenesEndpoint
from ledfx.api.scenes_id import SceneEndpoint
from ledfx.api.virtual import VirtualEndpoint
from ledfx.configuration.models import Scene
from ledfx.scenes import Scenes
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core
from tests.v1_golden.harness import (
    Step,
    build_app,
    check,
    golden_names,
    replay,
    updating,
)

ENDPOINTS: tuple[type[RestEndpoint], ...] = (
    ScenesEndpoint,
    SceneEndpoint,
    VirtualEndpoint,
    ConfigEndpoint,
)

S = "/api/scenes"
BIRD = "/api/virtuals/dj%20bird"
RED = {"color": "#ff0000"}


def put(scene_id: str, action: str) -> Step:
    return ("PUT", S, {"id": scene_id, "action": action})


SCENE_CONFIGS: dict[str, dict[str, object]] = {
    "plain": {
        "name": "Plain",
        "virtuals": {
            "dj bird": {"type": "singleColor", "config": RED},
            "matrix": {"type": "rainbow", "config": {}},
        },
    },
    # The first entry of every list below is refused by the empty virtual
    # (no segments); the others must still be applied.
    "refused": {
        "name": "Refused",
        "virtuals": {
            "empty": {"type": "singleColor", "config": RED},
            "dj bird": {"type": "singleColor", "config": RED},
            "matrix": {"type": "rainbow", "config": {}},
        },
    },
    "ghost": {
        "name": "Ghost",
        "virtuals": {
            "ghost": {"type": "singleColor", "config": RED},
            "dj bird": {"type": "singleColor", "config": RED},
        },
    },
    "presets": {
        "name": "Presets",
        "virtuals": {
            "dj bird": {"type": "singleColor", "preset": "black"},
            "matrix": {"type": "rainbow", "preset": "no-such-preset"},
        },
    },
    "actions": {
        "name": "Actions",
        "virtuals": {
            "dj bird": {"action": "forceblack"},
            "matrix": {"action": "ignore"},
            "mirror": {"action": "stop"},
        },
    },
    "stopper": {
        "name": "Stopper",
        "virtuals": {"dj bird": {"action": "stop"}, "matrix": {}},
    },
}

# An unregistered type and a config its model refuses: both are skipped.
BAD_ENTRIES: dict[str, object] = {
    "name": "Bad entries",
    "virtuals": {
        "mirror": {"type": "nosuchtype", "config": {}},
        "matrix": {"type": "rainbow", "config": {"speed": "x"}},
        "dj bird": {"type": "singleColor", "config": RED},
    },
}

SCENARIOS: dict[str, list[Step]] = {
    "activate": [
        ("GET", S, None),
        put("plain", "activate"),
        ("GET", BIRD, None),
        ("GET", f"{S}/plain", None),
        put("plain", "deactivate"),
        ("GET", BIRD, None),
        ("GET", f"{S}/plain", None),
        put("plain", "activate"),
        put("stopper", "activate"),
        ("GET", BIRD, None),
        put("actions", "activate"),
        ("GET", BIRD, None),
        ("GET", S, None),
    ],
    # A virtual with no segments refuses its entry.
    "refused": [
        put("refused", "activate"),
        ("GET", BIRD, None),
        ("GET", "/api/virtuals/matrix", None),
        ("GET", f"{S}/refused", None),
        put("refused", "deactivate"),
        ("GET", BIRD, None),
    ],
    "unknown_virtual": [
        put("ghost", "activate"),
        ("GET", BIRD, None),
        put("ghost", "deactivate"),
        put("nothere", "activate"),
        put("nothere", "deactivate"),
    ],
    "presets": [
        put("presets", "activate"),
        ("GET", BIRD, None),
        ("GET", "/api/virtuals/matrix", None),
        ("GET", f"{S}/presets", None),
    ],
    "bad_entries": [
        put("bad-entries", "activate"),
        ("GET", BIRD, None),
        ("GET", "/api/virtuals/matrix", None),
        ("GET", "/api/virtuals/mirror", None),
    ],
    # What /api/config stores after a scene stops or deactivates an effect.
    "stored_effect": [
        put("plain", "activate"),
        ("GET", "/api/config", None),
        put("plain", "deactivate"),
        ("GET", "/api/config", None),
        put("plain", "activate"),
        put("stopper", "activate"),
        ("GET", "/api/config", None),
    ],
    "safe_mode": [
        put("plain", "activate"),
        ("GET", BIRD, None),
        put("plain", "deactivate"),
        put("stopper", "activate"),
        ("PUT", S, {"id": "plain", "action": "activate_in", "ms": 5}),
        ("GET", BIRD, None),
        ("GET", S, None),
    ],
}


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
async def test_v1_scenes_family_is_unchanged(
    name: str, ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.scenes = Scenes(ledfx)
    for scene_id, config in SCENE_CONFIGS.items():
        ledfx.config.scenes[scene_id] = Scene.model_validate(config)
    if name == "bad_entries":
        ledfx.config.scenes["bad-entries"] = Scene.model_validate(BAD_ENTRIES)
    if name == "stored_effect":
        # GET /api/config dumps every key in set order: keep only the virtuals.
        monkeypatch.setattr("ledfx.api.config.CONFIG_KEYS", frozenset({"virtuals"}))
    if name == "safe_mode":
        enter_safe_mode(ledfx)
    records = await replay(build_app(ledfx, ENDPOINTS), SCENARIOS[name])
    check("scenes", name, records)


def test_every_golden_has_a_scenario() -> None:
    if not updating():
        assert golden_names("scenes") == set(SCENARIOS)
