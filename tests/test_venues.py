"""Tests for the Venues system: CRUD, exclusive virtual membership, and
color/gradient override activation."""

from unittest.mock import MagicMock, patch

import pytest

from ledfx.venues import VenueManager, _hsl_auto_palette


def _make_ledfx():
    """Build a minimal ledfx stand-in with an in-memory config and a
    virtuals registry mock."""
    ledfx = MagicMock()
    ledfx.config = {}
    ledfx.virtuals = MagicMock()
    ledfx._virtuals_by_id = {}
    ledfx.virtuals.get.side_effect = lambda vid: ledfx._virtuals_by_id.get(vid)
    return ledfx


@pytest.fixture(autouse=True)
def _no_disk_writes():
    """VenueManager persists to config.json on every mutation; these are
    pure logic tests so stub out the disk write."""
    with patch("ledfx.venues.save_config"):
        yield


def _add_virtual(ledfx, virtual_id):
    v = MagicMock()
    ledfx._virtuals_by_id[virtual_id] = v
    return v


@pytest.fixture
def ledfx():
    return _make_ledfx()


@pytest.fixture
def mgr(ledfx):
    return VenueManager(ledfx)


def test_hsl_auto_palette_length_and_shape():
    pads = _hsl_auto_palette(6)
    assert len(pads) == 6
    for pad in pads:
        assert "color" in pad
        assert pad["color"].startswith("#")
        assert len(pad["color"]) == 7


def test_create_venue_defaults(mgr):
    venue = mgr.create(name="Living Room")
    assert venue["name"] == "Living Room"
    assert venue["virtual_ids"] == []
    assert venue["color_pads"]["rows"] == 4
    assert venue["color_pads"]["cols"] == 4
    assert len(venue["color_pads"]["pads"]) == 16


def test_create_venue_dedupes_id(mgr):
    v1 = mgr.create(name="Patio")
    v2 = mgr.create(name="Patio")
    assert v1["id"] != v2["id"]


def test_list_and_get_venue(mgr):
    created = mgr.create(name="Deck", rows=2, cols=2)
    venue_id = created["id"]

    listed = mgr.list_venues()
    assert venue_id in listed

    fetched = mgr.get(venue_id)
    assert fetched["name"] == "Deck"
    assert mgr.get("does-not-exist") is None


def test_update_venue_name_and_grid(mgr):
    created = mgr.create(name="Garage", rows=2, cols=2)
    venue_id = created["id"]

    updated = mgr.update(venue_id, {"name": "Garage 2"})
    assert updated["name"] == "Garage 2"

    resized = mgr.update(venue_id, {"color_pads": {"rows": 3, "cols": 3}})
    assert resized["color_pads"]["rows"] == 3
    assert resized["color_pads"]["cols"] == 3
    assert len(resized["color_pads"]["pads"]) == 9


def test_update_missing_venue_raises(mgr):
    with pytest.raises(KeyError):
        mgr.update("nope", {"name": "x"})


def test_add_virtual_success(mgr, ledfx):
    venue = mgr.create(name="Studio")
    _add_virtual(ledfx, "v1")

    updated = mgr.add_virtual(venue["id"], "v1")
    assert "v1" in updated["virtual_ids"]


def test_add_virtual_missing_virtual_raises(mgr):
    venue = mgr.create(name="Studio2")
    with pytest.raises(ValueError):
        mgr.add_virtual(venue["id"], "ghost")


def test_add_virtual_exclusive_membership(mgr, ledfx):
    venue_a = mgr.create(name="A")
    venue_b = mgr.create(name="B")
    _add_virtual(ledfx, "v1")

    mgr.add_virtual(venue_a["id"], "v1")
    with pytest.raises(ValueError):
        mgr.add_virtual(venue_b["id"], "v1")


def test_remove_virtual_clears_override(mgr, ledfx):
    venue = mgr.create(name="C")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    mgr.remove_virtual(venue["id"], "v1")
    v1.clear_color_override.assert_called_once()
    assert "v1" not in mgr.get(venue["id"])["virtual_ids"]


def test_cleanup_virtual_removes_from_owning_venue(mgr, ledfx):
    venue = mgr.create(name="D")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    mgr.cleanup_virtual("v1")
    assert "v1" not in mgr.get(venue["id"])["virtual_ids"]
    v1.clear_color_override.assert_called_once()


def test_delete_venue_clears_overrides_and_removes(mgr, ledfx):
    venue = mgr.create(name="E")
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    assert mgr.delete(venue["id"]) is True
    v1.clear_color_override.assert_called_once()
    assert mgr.get(venue["id"]) is None
    assert mgr.delete(venue["id"]) is False


def test_activate_override_solid_color(mgr, ledfx):
    venue = mgr.create(name="F", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    pad_color = mgr.get(venue["id"])["color_pads"]["pads"][0]["color"]
    mgr.activate_override(venue["id"], 0)
    v1.set_color_override.assert_called_once_with(pad_color)


def test_activate_override_gradient_pad(mgr, ledfx):
    venue = mgr.create(name="G", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    gradient = "linear-gradient(90deg, #ff0000, #0000ff)"
    mgr._venues[venue["id"]]["color_pads"]["pads"][0] = {"gradient": gradient}

    mgr.activate_override(venue["id"], 0)
    v1.set_color_override.assert_called_once_with(gradient)


def test_activate_override_invalid_pad_index_raises(mgr, ledfx):
    venue = mgr.create(name="H", rows=1, cols=1)
    _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")

    with pytest.raises(IndexError):
        mgr.activate_override(venue["id"], 99)


def test_clear_override_calls_clear_on_all_virtuals(mgr, ledfx):
    venue = mgr.create(name="I")
    v1 = _add_virtual(ledfx, "v1")
    v2 = _add_virtual(ledfx, "v2")
    mgr.add_virtual(venue["id"], "v1")
    mgr.add_virtual(venue["id"], "v2")

    mgr.clear_override(venue["id"])
    v1.clear_color_override.assert_called_once()
    v2.clear_color_override.assert_called_once()


def test_clear_override_missing_venue_raises(mgr):
    with pytest.raises(KeyError):
        mgr.clear_override("nope")


def test_set_paused_clears_override_and_persists(mgr, ledfx):
    venue = mgr.create(name="J", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")
    mgr.activate_override(venue["id"], 0)

    updated = mgr.set_paused(venue["id"], True)
    assert updated["paused"] is True
    v1.clear_color_override.assert_called_once()
    assert mgr.is_paused(venue["id"]) is True


def test_set_paused_false_does_not_clear_override(mgr, ledfx):
    venue = mgr.create(name="K", rows=1, cols=1)
    v1 = _add_virtual(ledfx, "v1")
    mgr.add_virtual(venue["id"], "v1")
    mgr.activate_override(venue["id"], 0)
    v1.clear_color_override.reset_mock()

    updated = mgr.set_paused(venue["id"], False)
    assert updated["paused"] is False
    v1.clear_color_override.assert_not_called()
    assert mgr.is_paused(venue["id"]) is False


def test_set_paused_missing_venue_raises(mgr):
    with pytest.raises(KeyError):
        mgr.set_paused("nope", True)


def test_is_paused_defaults_false_for_new_venue_and_missing_venue(mgr):
    venue = mgr.create(name="L")
    assert mgr.is_paused(venue["id"]) is False
    assert mgr.is_paused("nope") is False
