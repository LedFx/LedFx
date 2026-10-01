"""Tests for the Venues system: CRUD, exclusive virtual membership, and
color/gradient override activation."""

from unittest.mock import MagicMock

import pytest

from ledfx.configuration.models import LedFxConfig, VenuePad
from ledfx.venues import VenueManager, _hsl_auto_palette


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
