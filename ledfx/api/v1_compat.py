"""Helpers shared by v1 handlers that keep v1's behaviour on top of the strict,
typed managers. Everything here is deleted with v1 (find users with
``grep -rn "v1-compat"``)."""

from typing import TYPE_CHECKING

from ledfx.color import parse_color
from ledfx.configuration.plugin import PluginConfig

if TYPE_CHECKING:
    from ledfx.core import LedFxCore


def effect_config(ledfx: "LedFxCore", type_id: str, raw: object) -> PluginConfig:
    """v1-compat: v1 sends raw JSON settings and answers a bad value with
    pydantic's error list (HTTP 400), so it validates against the type's own
    model before it calls the manager. Raises ValidationError; type_id must be
    registered."""
    return ledfx.effects.get_class(type_id).config_model().model_validate(raw)


def v1_color(value: object) -> str:
    """v1-compat: v1 takes a colour as a name, a hex string or an [r, g, b]
    list, and answers anything else with "Invalid color: ...". The managers
    and v2 take only the string form (validate_color). Raises ValueError."""
    if isinstance(value, (str, list, tuple)):
        return "#{:02x}{:02x}{:02x}".format(*parse_color(value))
    # ValueError, like parse_color: v1 callers catch it.
    raise ValueError(f"Invalid color: {value}")
