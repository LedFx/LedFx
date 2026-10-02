"""v1 goldens for the virtuals family.

Recorded before the family's logic moved into the Virtuals manager; every
later change must keep these bytes, except where a commit re-records a
golden on purpose and says so. Regenerate with:

    LEDFX_UPDATE_GOLDENS=1 uv run pytest tests/v1_golden -q
"""

import random
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.effects import EffectsEndpoint as GlobalEffectsEndpoint
from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint as VirtualEffectsEndpoint
from ledfx.api.virtual_effects_delete import EffectsEndpoint as EffectDeleteEndpoint
from ledfx.api.virtual_effects_fallback import EffectsEndpoint as FallbackEndpoint
from ledfx.api.virtual_tools import VirtualToolsEndpoint
from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.api.virtuals_tools import VirtualsToolsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import EffectEntry
from ledfx.configuration.plugin import PluginConfig
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core
from tests.v1_golden.harness import (
    Raw,
    Step,
    build_app,
    check,
    golden_names,
    replay,
    updating,
)

ENDPOINTS: tuple[type[RestEndpoint], ...] = (
    VirtualsEndpoint,
    VirtualEndpoint,
    VirtualEffectsEndpoint,
    EffectDeleteEndpoint,
    FallbackEndpoint,
    GlobalEffectsEndpoint,
    VirtualsToolsEndpoint,
    VirtualToolsEndpoint,
)

V = "/api/virtuals"
BIRD = "/api/virtuals/dj%20bird"
SINGLE = {"type": "singleColor"}

SCENARIOS: dict[str, list[Step]] = {
    "virtuals": [
        ("GET", V, None),
        ("POST", V, {"config": {"name": "Küche"}}),
        ("POST", V, {"config": {"name": "Küche"}}),
        ("POST", V, {"config": {"name": "x", "max_brightness": 5}}),
        ("POST", V, {"config": {}}),
        ("POST", V, {}),
        ("POST", V, {"config": 5}),
        ("POST", V, {"id": {}, "config": {}}),
        ("POST", V, {"id": "dj bird", "config": {"max_brightness": 0.5}}),
        ("POST", V, {"id": "dj bird", "config": {"frequency_min": 900}}),
        ("POST", V, {"id": "dj bird", "config": {"frequency_max": 100}}),
        ("POST", V, {"id": "dj bird", "config": {"rows": 1, "rotate": 2}}),
        ("POST", V, {"id": "dj bird", "config": {"mapping": "bogus"}}),
        ("POST", V, {"id": "nope", "config": {}}),
        ("POST", V, Raw("not json")),
        ("POST", V, [1, 2]),
        ("PUT", V, None),
        ("GET", V, None),
        ("PUT", V, None),
        ("PATCH", V, None),
        # The ids of the v2 collection paths /virtuals/oneshot and /force-color.
        ("POST", V, {"config": {"name": "oneshot"}}),
        ("POST", V, {"config": {"name": "Force Color"}}),
    ],
    "virtual": [
        ("GET", BIRD, None),
        ("GET", f"{V}/nope", None),
        (
            "POST",
            BIRD,
            {"segments": [["strip", 0, 24, False], ["matrix", 0, 63, True]]},
        ),
        ("POST", BIRD, {"segments": [["strip", 0, 99, False]]}),
        ("POST", BIRD, {}),
        ("POST", BIRD, {"segments": 5}),
        ("POST", BIRD, {"segments": [["ghost", 0, 1, False]]}),
        ("POST", f"{V}/nope", {"segments": []}),
        ("PUT", BIRD, {"active": True}),
        ("PUT", BIRD, {"active": "yes"}),
        ("PUT", BIRD, {"config": {"name": "x"}}),
        ("PUT", BIRD, Raw("not json")),
        ("PUT", f"{V}/nope", {"active": True}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("PUT", BIRD, {"active": False}),
        ("PUT", BIRD, {"active": True}),
        ("GET", BIRD, None),
        ("DELETE", BIRD, None),
        ("GET", BIRD, None),
        ("DELETE", BIRD, None),
        ("DELETE", f"{V}/matrix", None),
        ("GET", V, None),
    ],
    # Input the manager used to repair: the repair stays on the v1 wire.
    "virtual_repair": [
        ("POST", BIRD, {"segments": [["strip", 30, 10, False]]}),
        ("POST", BIRD, {"segments": [["strip", -5, 10, True]]}),
        ("POST", BIRD, {"segments": [["strip", 60, 70, False]]}),
        ("POST", BIRD, {"segments": [["gap-1", 0, 500, False]]}),
        ("POST", BIRD, {"segments": "strip"}),
        ("POST", BIRD, {"segments": {"device": "strip"}}),
        ("POST", BIRD, {"segments": [5]}),
        ("POST", BIRD, {"segments": [["strip", 0, "a", False]]}),
        ("POST", BIRD, {"segments": [["strip", 0, 9, False], ["ghost", 0, 1, False]]}),
        ("GET", BIRD, None),
        ("POST", V, {"id": "dj bird", "config": {"frequency_min": 500}}),
        (
            "POST",
            V,
            {"id": "dj bird", "config": {"frequency_min": 500, "frequency_max": 500}},
        ),
        (
            "POST",
            V,
            {"id": "dj bird", "config": {"frequency_min": 900, "frequency_max": 100}},
        ),
        (
            "POST",
            V,
            {
                "id": "dj bird",
                "config": {"frequency_min": 15000, "frequency_max": 15000},
            },
        ),
        ("POST", V, {"id": "dj bird", "config": {"rows": 3, "rotate": 2}}),
        ("POST", V, {"id": "dj bird", "config": {"rows": 1}}),
        ("POST", V, {"id": "dj bird", "config": {"rotate": 3}}),
        ("POST", V, {"id": "dj bird", "config": {"rows": 1, "rotate": 0}}),
        ("GET", BIRD, None),
        (
            "POST",
            V,
            {"config": {"name": "r1", "frequency_min": 900, "frequency_max": 100}},
        ),
        (
            "POST",
            V,
            {"config": {"name": "r2", "frequency_min": 500, "frequency_max": 500}},
        ),
        ("POST", V, {"config": {"name": "r3", "rows": 1, "rotate": 2}}),
        ("POST", V, {"config": {"name": "r4", "rows": 3, "rotate": 2}}),
        ("GET", V, None),
    ],
    "virtual_effects": [
        ("GET", f"{BIRD}/effects", None),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": 3}}),
        ("POST", f"{BIRD}/effects", {"type": "nope"}),
        ("POST", f"{BIRD}/effects", {"type": 5}),
        ("POST", f"{BIRD}/effects", {}),
        ("POST", f"{BIRD}/effects", {"type": "singleColor", "config": 5}),
        ("POST", f"{BIRD}/effects", {"type": "singleColor", "config": {"speed": "x"}}),
        (
            "POST",
            BIRD,
            {"segments": [["strip", 0, 49, False], ["matrix", 0, 63, False]]},
        ),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("GET", f"{BIRD}/effects", None),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": 3}}),
        ("PUT", f"{BIRD}/effects", {"config": {"color": "#00ff00"}}),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": 99}}),
        ("PUT", f"{BIRD}/effects", {"config": [1]}),
        ("PUT", f"{BIRD}/effects", {"type": "nope"}),
        ("PUT", f"{BIRD}/effects", {"config": "RANDOMIZE"}),
        ("PUT", f"{BIRD}/effects", {"type": "rainbow", "config": {"speed": 2}}),
        ("POST", f"{BIRD}/effects", {"type": "rainbow", "config": "RANDOMIZE"}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("GET", BIRD, None),
        ("POST", f"{V}/matrix/effects", {**SINGLE, "fallback": True}),
        ("POST", f"{V}/mirror/effects", {**SINGLE, "fallback": True}),
        ("POST", f"{V}/empty/effects", SINGLE),
        ("PUT", f"{V}/empty/effects", {"config": {}}),
        ("POST", f"{V}/nope/effects", SINGLE),
        ("DELETE", f"{BIRD}/effects", None),
        ("GET", f"{BIRD}/effects", None),
        ("DELETE", f"{V}/nope/effects", None),
    ],
    "effect_history": [
        ("POST", f"{BIRD}/effects", {"type": "rainbow"}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("POST", f"{BIRD}/effects/delete", {"type": "rainbow"}),
        ("POST", f"{BIRD}/effects/delete", {"type": "singleColor"}),
        ("POST", f"{BIRD}/effects/delete", {"type": "never-set"}),
        ("POST", f"{BIRD}/effects/delete", {"type": {}}),
        ("POST", f"{BIRD}/effects/delete", Raw("not json")),
        ("POST", f"{V}/nope/effects/delete", {"type": "rainbow"}),
        ("GET", BIRD, None),
    ],
    "fallback": [
        ("POST", f"{BIRD}/effects", SINGLE),
        ("POST", f"{BIRD}/effects", {"type": "rainbow", "fallback": 30}),
        ("GET", f"{BIRD}/fallback", None),
        ("GET", f"{V}/nope/fallback", None),
        ("POST", f"{BIRD}/fallback", None),
    ],
    "effects": [
        ("GET", "/api/effects", None),
        ("PUT", "/api/effects", {}),
        ("PUT", "/api/effects", {"action": "nope"}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("POST", f"{V}/matrix/effects", {"type": "rainbow"}),
        ("GET", "/api/effects", None),
        ("PUT", "/api/effects", {"action": "apply_global"}),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "brightness": 0.5, "flip": "toggle"},
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global",
                "gradient": "Rainbow",
                "background_color": "blue",
            },
        ),
        ("PUT", "/api/effects", {"action": "apply_global", "gradient": "nope("}),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "background_color": "notacolor"},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "brightness": "x", "gradient": "nope("},
        ),
        ("PUT", "/api/effects", {"action": "apply_global", "flip": 3}),
        ("PUT", "/api/effects", {"action": "apply_global", "gradient": 5}),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "type": "rainbow", "config": [1, 2]},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "mirror": True, "virtuals": "dj bird"},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "mirror": True, "virtuals": ["dj bird", 7]},
        ),
        ("GET", "/api/effects", None),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "virtuals": ["dj bird"]},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "type": "rainbow", "virtuals": []},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "type": "rainbow", "config": "RANDOMIZE"},
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "config": {"speed": 3},
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "singleColor",
                "virtuals": ["dj bird", "ghost", "mirror"],
                "fallback": True,
            },
        ),
        ("PUT", "/api/effects", {"action": "clear_all_effects"}),
        ("GET", "/api/effects", None),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "type": "nope", "virtuals": ["dj bird"]},
        ),
    ],
    "tools": [
        ("GET", "/api/virtuals_tools", None),
        ("GET", "/api/virtuals_tools/dj%20bird", None),
        ("POST", f"{V}_tools/dj%20bird", {"tool": "oneshot"}),
        ("POST", f"{BIRD}/effects", SINGLE),
        (
            "POST",
            f"{V}_tools/dj%20bird",
            {
                "tool": "oneshot",
                "color": "red",
                "ramp": 10,
                "hold": 20,
                "fade": 30,
                "brightness": 5,
            },
        ),
        ("POST", f"{V}_tools/dj%20bird", {"tool": "oneshot", "hold": -1}),
        ("POST", f"{V}_tools/dj%20bird", {"tool": "force_color", "color": "red"}),
        ("POST", f"{V}_tools/dj%20bird", {}),
        ("POST", f"{V}_tools/nope", {"tool": "oneshot"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "oneshot"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "oneshot"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "force_color", "color": "red"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "force_color"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "force_color", "color": "notacolor"}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 0, "stop": 9},
        ),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "on"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "maybe"}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 0, "stop": 9},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": "a"},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "ghost", "start": 0, "stop": 1},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 0, "stop": 99},
        ),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "state": False}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "off"}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "copy", "target": ["mirror", "ghost"]},
        ),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": "mirror"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": ["ghost"]}),
        ("PUT", f"{V}_tools/empty", {"tool": "copy", "target": ["mirror"]}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "nope"}),
        ("PUT", f"{V}_tools/nope", {"tool": "oneshot"}),
        ("GET", f"{V}/mirror", None),
        ("POST", "/api/virtuals_tools", {"tool": "oneshot", "color": "blue"}),
        ("POST", "/api/virtuals_tools", {"tool": "force_color", "color": "red"}),
        ("POST", "/api/virtuals_tools", {"tool": "oneshot", "brightness": "x"}),
        ("PUT", "/api/virtuals_tools", {"tool": "oneshot"}),
        ("PUT", "/api/virtuals_tools", {"tool": "oneshot"}),
        ("PUT", "/api/virtuals_tools", {"tool": "force_color", "color": "red"}),
        ("PUT", "/api/virtuals_tools", {"tool": "force_color", "color": "notacolor"}),
        ("PUT", "/api/virtuals_tools", {"tool": "force_color"}),
        ("PUT", "/api/virtuals_tools", {"tool": "nope"}),
        # dj bird is no longer calibrating: v1 refuses turning its highlight off.
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "state": False}),
        # A cleared effect leaves a placeholder (DummyEffect) while it fades out.
        ("DELETE", f"{BIRD}/effects", None),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": ["mirror"]}),
    ],
    # Copy and highlight refusals: what is a typo, what refused, and which
    # message wins.
    "conflicts": [
        ("PUT", f"{V}_tools/empty", {"tool": "copy", "target": ["ghost"]}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": ["mirror"]}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": []}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": ["empty"]}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "copy", "target": ["ghost", "empty"]},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "copy", "target": ["empty", "mirror"]},
        ),
        ("GET", f"{V}/mirror/effects", None),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "device": "strip"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "on"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "device": "strip"}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "STRIP", "start": 0, "stop": 5},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "GHOST", "start": 0, "stop": 5},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 99, "stop": 0},
        ),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "state": False}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "state": False}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "off"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "highlight", "state": False}),
    ],
    # Highlight ranges the manager no longer accepts, and unknown ids in bulk.
    "ranges": [
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "calibration", "mode": "on"}),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 10, "stop": 5},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": -5, "stop": -2},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 3, "stop": 3},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "start": 2},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "strip", "stop": 2},
        ),
        (
            "PUT",
            f"{V}_tools/dj%20bird",
            {"tool": "highlight", "device": "ghost", "start": 10, "stop": 5},
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "mirror": True, "virtuals": ["ghost"]},
        ),
        ("PUT", "/api/effects", {"action": "clear_all_effects"}),
    ],
    # "toggle" inverts each effect's own value; counts for skipped effects.
    "apply_toggle": [
        ("POST", BIRD, {"segments": [["strip", 0, 49, False]]}),
        ("POST", f"{BIRD}/effects", {**SINGLE, "config": {"flip": False}}),
        (
            "POST",
            f"{V}/matrix/effects",
            {"type": "rainbow", "config": {"flip": True, "mirror": False}},
        ),
        ("PUT", "/api/effects", {"action": "apply_global", "flip": "toggle"}),
        ("GET", "/api/effects", None),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global",
                "flip": "TOGGLE",
                "mirror": "toggle",
                "virtuals": ["matrix"],
            },
        ),
        ("GET", "/api/effects", None),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "mirror": "toggle", "virtuals": []},
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global",
                "flip": "toggle",
                "virtuals": ["ghost", "empty"],
            },
        ),
        ("PUT", "/api/effects", {"action": "apply_global", "gradient": "Rainbow"}),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global", "flip": "toggle", "gradient": "Rainbow"},
        ),
        ("GET", "/api/effects", None),
    ],
    # Activation refused for a stale stored config.
    "activation": [
        ("PUT", BIRD, {"active": True}),
        ("GET", BIRD, None),
    ],
    # Safe mode: config.json could not be loaded, so changes can't be saved.
    "safe_mode": [
        ("GET", V, None),
        ("POST", V, {"config": {"name": "Küche"}}),
        ("POST", V, {"id": "dj bird", "config": {"max_brightness": 0.5}}),
        ("PUT", V, None),
        ("POST", BIRD, {"segments": [["strip", 0, 24, False]]}),
        ("POST", f"{BIRD}/effects", SINGLE),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": 3}}),
        ("PUT", BIRD, {"active": False}),
        ("POST", f"{BIRD}/effects/delete", {"type": "rainbow"}),
        ("PUT", "/api/effects", {"action": "apply_global", "brightness": 0.5}),
        ("PUT", "/api/effects", {"action": "apply_global", "flip": "toggle"}),
        ("PUT", "/api/effects", {"action": "apply_global_effect", "type": "rainbow"}),
        ("PUT", f"{V}_tools/dj%20bird", {"tool": "copy", "target": ["mirror"]}),
        ("DELETE", f"{BIRD}/effects", None),
        ("GET", BIRD, None),
        ("DELETE", BIRD, None),
        ("GET", V, None),
    ],
    # Effect configs and the bulk effect: error order and the counts on the wire.
    "effect_typing": [
        (
            "POST",
            BIRD,
            {"segments": [["strip", 0, 49, False], ["matrix", 0, 63, False]]},
        ),
        ("POST", f"{BIRD}/effects", SINGLE),
        # A bad config answers before the streamed-to refusal.
        (
            "POST",
            f"{V}/matrix/effects",
            {**SINGLE, "config": {"speed": "x"}, "fallback": True},
        ),
        ("POST", f"{V}/matrix/effects", {**SINGLE, "fallback": True}),
        ("POST", f"{V}/matrix/effects", SINGLE),
        # PUT: the streamed-to refusal answers before the config is looked at.
        (
            "PUT",
            f"{V}/matrix/effects",
            {"config": {"speed": "x"}, "fallback": True},
        ),
        ("PUT", f"{V}/matrix/effects", {"config": {"color": "red"}, "fallback": True}),
        # A stale stored config on POST without config.
        ("POST", f"{BIRD}/effects", {"type": "rainbow"}),
        # A colour change with a fallback restarts the effect as a fallback.
        ("POST", f"{BIRD}/effects", SINGLE),
        ("PUT", f"{BIRD}/effects", {"config": {"color": "#00ff00"}, "fallback": 30}),
        ("GET", f"{BIRD}/effects", None),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": 4}, "fallback": 30}),
        (
            "PUT",
            f"{BIRD}/effects",
            {"config": {"color": "#0000ff", "speed": "x"}, "fallback": 30},
        ),
        (
            "PUT",
            f"{BIRD}/effects",
            {"type": "singleColor", "config": {"color": "red"}, "fallback": 30},
        ),
        ("PUT", f"{BIRD}/effects", {"config": {"color": "nocolour"}}),
        ("GET", f"{BIRD}/effects", None),
        ("POST", f"{BIRD}/effects", SINGLE),
        # The bulk effect: counts for a bad config, unknown and refusing ids.
        # (matrix is streamed to again once it holds no effect of its own.)
        ("PUT", f"{V}/matrix", {"active": False}),
        ("DELETE", f"{BIRD}/effects", None),
        ("POST", f"{BIRD}/effects", SINGLE),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "config": {"speed": "x"},
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "config": {"speed": "x"},
                "virtuals": ["dj bird", "ghost", "empty"],
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "config": {"speed": "x"},
                "virtuals": ["dj bird", "matrix"],
                "fallback": True,
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "virtuals": ["ghost"],
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "virtuals": ["dj bird", "empty", "ghost", "matrix"],
                "fallback": True,
            },
        ),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": 5,
                "virtuals": ["dj bird"],
            },
        ),
        ("GET", BIRD, None),
        ("POST", f"{BIRD}/effects", SINGLE),
    ],
    # The bulk effect with an id listed twice.
    "repeated_ids": [
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "virtuals": ["dj bird", "dj bird", "mirror"],
            },
        ),
    ],
    # Safe mode answers before a bad config is looked at.
    "safe_mode_effects": [
        ("POST", f"{BIRD}/effects", {**SINGLE, "config": {"speed": "x"}}),
        ("PUT", f"{BIRD}/effects", {"config": {"speed": "x"}}),
        (
            "PUT",
            "/api/effects",
            {
                "action": "apply_global_effect",
                "type": "rainbow",
                "config": {"speed": "x"},
            },
        ),
        (
            "PUT",
            "/api/effects",
            {"action": "apply_global_effect", "type": "nope"},
        ),
    ],
    # Safe mode entered while an effect runs: it answers before a bad config.
    "safe_mode_running": [
        ("PUT", f"{BIRD}/effects", {"config": {"speed": "x"}}),
        ("PUT", f"{BIRD}/effects", {"config": {"color": "red"}, "fallback": 30}),
        ("PUT", f"{BIRD}/effects", {"type": "rainbow", "config": {"speed": "x"}}),
        ("POST", f"{BIRD}/effects", {"type": "rainbow", "config": {"speed": "x"}}),
        ("GET", f"{BIRD}/effects", None),
    ],
}


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
async def test_v1_virtuals_family_is_unchanged(name: str, ledfx: MagicMock) -> None:
    if name == "safe_mode_running":
        ledfx.virtuals.set_effect(
            VirtualIdStr("dj bird"), "singleColor", PluginConfig.model_validate({})
        )
    if name.startswith("safe_mode"):
        enter_safe_mode(ledfx)
    if name == "activation":
        entry = ledfx.virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
        assert entry is not None
        entry.last_effect = "rainbow"
        entry.effects["rainbow"] = EffectEntry(type="rainbow", config={"speed": "x"})
    if name == "effect_typing":
        # A stored config that no longer validates.
        entry = ledfx.virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
        assert entry is not None
        entry.effects["rainbow"] = EffectEntry(type="rainbow", config={"speed": "x"})
    random.seed(0)  # RANDOMIZE
    records = await replay(build_app(ledfx, ENDPOINTS), SCENARIOS[name])
    check("virtuals", name, records)


def test_every_golden_has_a_scenario() -> None:
    if not updating():
        assert golden_names("virtuals") == set(SCENARIOS)
