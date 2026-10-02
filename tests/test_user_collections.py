"""The colours and gradients collections the real core wires up."""

import inspect

import pytest

from ledfx.core import LedFxCore
from ledfx.utils import build_user_collections
from tests.test_utilities.fake_ledfx import fake_ledfx


def test_a_list_colour_still_loads_and_is_stored() -> None:
    """v1 clients send list colours; a strict validator would refuse them."""
    ledfx = fake_ledfx()
    colors, _ = build_user_collections(ledfx)
    colors["mine"] = [1, 2, 3]
    assert colors["mine"] == (1, 2, 3)
    assert ledfx.config.user_colors["mine"] == "#010203"


def test_gradients_validate() -> None:
    _, gradients = build_user_collections(fake_ledfx())
    with pytest.raises(ValueError):
        gradients["bad"] = "not a gradient"


def test_collections_own_their_config_sections() -> None:
    ledfx = fake_ledfx({"user_colors": {"a": "#010203"}})
    colors, gradients = build_user_collections(ledfx)
    assert colors.get_all()[1] is ledfx.config.user_colors
    assert gradients.get_all()[1] is ledfx.config.user_gradients


def test_the_core_builds_them_with_the_shared_builder() -> None:
    assert "build_user_collections(self)" in inspect.getsource(LedFxCore)
