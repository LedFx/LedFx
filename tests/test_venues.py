"""Tests for the Venues system: CRUD, exclusive virtual membership, and
color/gradient override activation."""

import json
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from aiohttp import web
from pydantic import ValidationError

from ledfx.api.venues import VenuesEndpoint
from ledfx.configuration.models import VENUE_GRID_MAX, LedFxConfig, VenuePad
from ledfx.core import LedFxCore
from ledfx.venues import VenueManager, _hsl_auto_palette
from ledfx.virtuals import Virtual


def _make_ledfx() -> MagicMock:
    """Build a minimal ledfx stand-in with an in-memory config and a
    virtuals registry mock."""
    ledfx = MagicMock()
    ledfx.config = LedFxConfig()
    ledfx.virtuals = MagicMock()
    virtuals_by_id: dict[str, MagicMock] = {}
    ledfx._virtuals_by_id = virtuals_by_id
    ledfx.virtuals.get.side_effect = virtuals_by_id.get
    return ledfx


def _add_virtual(ledfx: MagicMock, virtual_id: str) -> MagicMock:
    v = MagicMock()
    ledfx._virtuals_by_id[virtual_id] = v
    return v


@pytest.fixture
def ledfx() -> MagicMock:
    return _make_ledfx()


@pytest.fixture
def mgr(ledfx: MagicMock) -> VenueManager:
    return VenueManager(ledfx)


def test_hsl_auto_palette_length_and_shape() -> None:
    pads = _hsl_auto_palette(6)
    assert len(pads) == 6
    for pad in pads:
        assert pad.color is not None
        assert pad.color.startswith("#")
        assert len(pad.color) == 7


def test_create_venue_defaults(mgr: VenueManager) -> None:
    _, venue = mgr.create(name="Living Room")
    assert venue.name == "Living Room"
    assert venue.virtual_ids == []
    assert venue.color_pads.rows == 4
    assert venue.color_pads.cols == 4
    assert len(venue.color_pads.pads) == 16


def test_create_venue_dedupes_id(mgr: VenueManager) -> None:
    v1_id, _ = mgr.create(name="Patio")
    v2_id, _ = mgr.create(name="Patio")
    assert v1_id != v2_id


def test_list_and_get_venue(mgr: VenueManager) -> None:
    venue_id, _ = mgr.create(name="Deck", rows=2, cols=2)

    listed = mgr.list_venues()
    assert venue_id in listed

    fetched = mgr.get(venue_id)
    assert fetched is not None
    assert fetched.name == "Deck"
    assert mgr.get("does-not-exist") is None


def test_update_venue_name_and_grid(mgr: VenueManager) -> None:
    venue_id, _ = mgr.create(name="Garage", rows=2, cols=2)

    updated = mgr.update(venue_id, {"name": "Garage 2"})
    assert updated.name == "Garage 2"

    resized = mgr.update(venue_id, {"color_pads": {"rows": 3, "cols": 3}})
    assert resized.color_pads.rows == 3
    assert resized.color_pads.cols == 3
    assert len(resized.color_pads.pads) == 9


def test_update_missing_venue_raises(mgr: VenueManager) -> None:
    with pytest.raises(KeyError):
        mgr.update("nope", {"name": "x"})


def test_add_virtual_success(mgr: VenueManager, ledfx: MagicMock) -> None:
    venue_id, _ = mgr.create(name="Studio")
    _add_virtual(ledfx, "v1")

    updated = mgr.add_virtual(venue_id, "v1")
    assert "v1" in updated.virtual_ids


def test_add_virtual_missing_virtual_raises(mgr: VenueManager) -> None:
    venue_id, _ = mgr.create(name="Studio2")
    with pytest.raises(ValueError):
        mgr.add_virtual(venue_id, "ghost")


def test_add_virtual_exclusive_membership(mgr: VenueManager, ledfx: MagicMock) -> None:
    venue_a_id, _ = mgr.create(name="A")
    venue_b_id, _ = mgr.create(name="B")
    _add_virtual(ledfx, "v1")

    mgr.add_virtual(venue_a_id, "v1")
    with pytest.raises(ValueError):
        mgr.add_virtual(venue_b_id, "v1")


def test_remove_virtual_clears_override(mgr: VenueManager, ledfx: MagicMock) -> None:
    venue_id, _ = mgr.create(name="C")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    mgr.remove_virtual(venue_id, "v1")
    v1.clear_color_override.assert_called_once()
    assert "v1" not in mgr._venues[venue_id].virtual_ids


def test_cleanup_virtual_removes_from_owning_venue(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="D")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    mgr.cleanup_virtual("v1")
    assert "v1" not in mgr._venues[venue_id].virtual_ids
    v1.clear_color_override.assert_called_once()


def test_delete_venue_clears_overrides_and_removes(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="E")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    assert mgr.delete(venue_id) is True
    v1.clear_color_override.assert_called_once()
    assert mgr.get(venue_id) is None
    assert mgr.delete(venue_id) is False


def test_activate_override_solid_color(mgr: VenueManager, ledfx: MagicMock) -> None:
    venue_id, _ = mgr.create(name="F", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    pad_color = mgr._venues[venue_id].color_pads.pads[0].color
    mgr.activate_override(venue_id, 0)
    v1.set_color_override.assert_called_once_with(pad_color)


def test_activate_override_gradient_pad(mgr: VenueManager, ledfx: MagicMock) -> None:
    venue_id, _ = mgr.create(name="G", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    gradient = "linear-gradient(90deg, #ff0000, #0000ff)"
    mgr._venues[venue_id].color_pads.pads[0] = VenuePad(gradient=gradient)

    mgr.activate_override(venue_id, 0)
    v1.set_color_override.assert_called_once_with(gradient)


def test_activate_override_invalid_pad_index_raises(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="H", rows=1, cols=1)
    _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")

    with pytest.raises(IndexError):
        mgr.activate_override(venue_id, 99)


def test_clear_override_calls_clear_on_all_virtuals(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="I")
    v1 = _add_virtual(ledfx, "v1")
    v2 = _add_virtual(ledfx, "v2")
    mgr.add_virtual(venue_id, "v1")
    mgr.add_virtual(venue_id, "v2")

    mgr.clear_override(venue_id)
    v1.clear_color_override.assert_called_once()
    v2.clear_color_override.assert_called_once()


def test_clear_override_missing_venue_raises(mgr: VenueManager) -> None:
    with pytest.raises(KeyError):
        mgr.clear_override("nope")


# Review-feedback regressions


async def _post_venue(ledfx: MagicMock, body: dict[str, object]):
    request = MagicMock(spec=web.Request, method="POST", path="/api/venues")
    request.headers = dict[str, str]()
    request.has_body = True
    request.content_type = "application/json"
    request.json = AsyncMock(return_value=body)
    request.match_info = dict[str, str]()
    response = await VenuesEndpoint(ledfx).handler(request)
    return response.status, json.loads(response.text or "")


@pytest.mark.parametrize(
    "grid", [{"rows": "abc"}, {"cols": None}, {"rows": 0}, {"cols": VENUE_GRID_MAX + 1}]
)
async def test_create_venue_bad_grid_is_a_validation_error(
    ledfx: MagicMock, grid: dict[str, object]
) -> None:
    ledfx.venues = VenueManager(ledfx)
    status, body = await _post_venue(ledfx, {"name": "Bad", **grid})
    assert status == 400
    assert body["errors"]
    assert ledfx.config.venues == {}


@pytest.mark.parametrize("axis", ["rows", "cols"])
def test_oversized_grid_is_rejected_before_building_pads(
    mgr: VenueManager, axis: str
) -> None:
    huge = {"rows": 4, "cols": 4, axis: 100_000}
    venue_id, _ = mgr.create(name="Small")
    with patch("ledfx.venues._hsl_auto_palette") as palette:
        with pytest.raises(ValidationError):
            mgr.create(name="Huge", **huge)
        with pytest.raises(ValidationError):
            mgr.update(venue_id, {"color_pads": huge})
    palette.assert_not_called()
    venue = mgr.get(venue_id)
    assert venue is not None and venue.color_pads.rows == 4
    assert mgr.create(name="Max", rows=VENUE_GRID_MAX, cols=VENUE_GRID_MAX)


def test_core_creates_the_venue_manager(tmp_path: Path) -> None:
    # Deleting a virtual before any venue request must still clean venues.
    with patch("ledfx.core.HttpServer"):  # other tests register stub endpoints
        core = LedFxCore(config_dir=str(tmp_path))
    try:
        assert isinstance(core.venues, VenueManager)
    finally:
        core.loop.close()


def test_solid_override_matches_the_grouped_frame_size() -> None:
    virtual = object.__new__(Virtual)
    virtual._config = {"grouping": 4, "preview_only": True}
    virtual.lock = threading.Lock()
    virtual._active_effect = MagicMock(is_active=True, pixels=None)
    virtual._paused = False
    virtual._wash_active = False
    virtual.fallback_fire = False
    virtual._last_render_error = 0.0
    virtual._fire_update_event = MagicMock()

    def assemble() -> np.ndarray:
        virtual._active = False  # render a single frame
        return np.full((virtual.effective_pixel_count, 3), 255.0)

    virtual.assemble_frame = assemble
    with (
        patch.object(Virtual, "pixel_count", 10),
        patch.object(Virtual, "refresh_rate", 1000),
        patch.object(Virtual, "id", "v"),
    ):
        virtual.set_color_override("#ff0000")
        virtual._active = True
        virtual.thread_function()
        frame = virtual.assembled_frame
        assert frame is not None
        np.testing.assert_array_equal(frame, [[255, 0, 0]] * 3)

        # Changing the grouping reactivates the effect; the override follows.
        virtual._config["grouping"] = 2
        for prop in ("group_size", "effective_pixel_count"):
            virtual.__dict__.pop(prop)
        virtual.clear_transition_effect = MagicMock()
        with patch("ledfx.virtuals.Transitions"):
            virtual._reactivate_effect()
        assert virtual._color_override_frame is not None
        assert virtual._color_override_frame.shape == (5, 3)


def test_invalid_override_falls_back_to_white_for_gradient_effects() -> None:
    # GradientEffect takes the override natively; a bad pad string must still
    # become white, as it does for every other effect.
    from ledfx.effects.gradient import GradientEffect

    virtual = object.__new__(Virtual)
    virtual._color_override = "not-a-colour"
    virtual._active_effect = MagicMock(spec=GradientEffect)
    with patch.object(Virtual, "id", "v"):
        virtual._apply_color_override_to_effect()
    virtual._active_effect.set_gradient_override.assert_called_once_with("#ffffff")


def test_set_paused_clears_override_and_persists(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="J", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")
    mgr.activate_override(venue_id, 0)

    updated = mgr.set_paused(venue_id, True)
    assert updated.paused is True
    v1.clear_color_override.assert_called_once()
    assert mgr.is_paused(venue_id) is True


def test_set_paused_false_does_not_clear_override(
    mgr: VenueManager, ledfx: MagicMock
) -> None:
    venue_id, _ = mgr.create(name="K", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue_id, "v1")
    mgr.activate_override(venue_id, 0)
    v1.clear_color_override.reset_mock()

    updated = mgr.set_paused(venue_id, False)
    assert updated.paused is False
    v1.clear_color_override.assert_not_called()
    assert mgr.is_paused(venue_id) is False


def test_set_paused_missing_venue_raises(mgr: VenueManager) -> None:
    with pytest.raises(KeyError):
        mgr.set_paused("nope", True)


def test_is_paused_defaults_false_for_new_venue_and_missing_venue(
    mgr: VenueManager,
) -> None:
    venue_id, _ = mgr.create(name="L")
    assert mgr.is_paused(venue_id) is False
    assert mgr.is_paused("nope") is False
