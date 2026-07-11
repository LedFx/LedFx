"""Venue manager for LedFx.

A venue is a named collection of virtuals. It provides:
  - a filtered view: only that venue's virtuals are shown in the UI
  - a color-override pad grid (NxM): each pad holds a solid color or gradient
    string; activating a pad overpaints all venue virtuals until cleared.

Venues are persisted in config.json under the "venues" key as a dict keyed
by venue ID.  Each value has the shape:

    {
        "name": str,
        "virtual_ids": [str, ...],          # virtuals belonging to this venue
        "color_pads": {
            "rows": int,                    # grid height
            "cols": int,                    # grid width
            "pads": [                       # flat list, row-major order
                {"color": "#rrggbb"},       # solid color pad
                {"gradient": "linear-gradient(...)"},  # gradient pad
                ...
            ]
        }
    }

Exclusive membership is enforced: a virtual may belong to at most one venue.
"""

from __future__ import annotations

import colorsys
import logging
from typing import Optional

from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


def _hsl_auto_palette(n: int) -> list[dict]:
    """Return *n* evenly-spaced hue colors as pad dicts."""
    pads = []
    for i in range(n):
        hue = i / n
        r, g, b = colorsys.hls_to_rgb(hue, 0.5, 1.0)
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )
        pads.append({"color": hex_color})
    return pads


class VenueManager:
    """Manages venues in LedFx config."""

    def __init__(self, ledfx):
        self._ledfx = ledfx

    @property
    def _venues(self) -> dict:
        return self._ledfx.config.setdefault("venues", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_venue_for_virtual(self, virtual_id: str) -> Optional[str]:
        """Return the venue ID that owns *virtual_id*, or None."""
        for vid, cfg in self._venues.items():
            if virtual_id in cfg.get("virtual_ids", []):
                return vid
        return None

    def _save(self):
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_venues(self) -> dict:
        return dict(self._venues)

    def get(self, venue_id: str) -> Optional[dict]:
        return self._venues.get(venue_id)

    def create(self, name: str, rows: int = 4, cols: int = 4) -> dict:
        """Create a new venue with an auto-filled color pad grid."""
        venue_id = generate_id(name)
        # Deduplicate ID
        base_id = venue_id
        idx = 1
        while venue_id in self._venues:
            venue_id = f"{base_id}-{idx}"
            idx += 1

        n_pads = rows * cols
        venue_cfg = {
            "name": name,
            "virtual_ids": [],
            "color_pads": {
                "rows": rows,
                "cols": cols,
                "pads": _hsl_auto_palette(n_pads),
            },
        }
        self._venues[venue_id] = venue_cfg
        self._save()
        _LOGGER.info("Created venue '%s' (%s)", name, venue_id)
        return {"id": venue_id, **venue_cfg}

    def update(self, venue_id: str, data: dict) -> dict:
        """Update name and/or color_pads config for a venue.

        Supported keys in *data*: ``name``, ``color_pads``.
        To resize the grid pass ``color_pads`` with ``rows``/``cols``; the pads
        list will be re-initialised to an auto-palette unless ``pads`` is also
        supplied.
        """
        cfg = self._venues.get(venue_id)
        if cfg is None:
            raise KeyError(f"Venue '{venue_id}' not found")

        if "name" in data:
            cfg["name"] = str(data["name"])

        if "color_pads" in data:
            cp = data["color_pads"]
            rows = int(cp.get("rows", cfg["color_pads"]["rows"]))
            cols = int(cp.get("cols", cfg["color_pads"]["cols"]))
            n_pads = rows * cols
            if "pads" in cp and len(cp["pads"]) == n_pads:
                pads = list(cp["pads"])
            else:
                pads = _hsl_auto_palette(n_pads)
            cfg["color_pads"] = {"rows": rows, "cols": cols, "pads": pads}

        self._save()
        return {"id": venue_id, **cfg}

    def delete(self, venue_id: str) -> bool:
        """Delete a venue and clear any active overrides on its virtuals."""
        cfg = self._venues.pop(venue_id, None)
        if cfg is None:
            return False
        # Clear any active color overrides
        for vid in cfg.get("virtual_ids", []):
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                v.clear_color_override()
        self._save()
        _LOGGER.info("Deleted venue '%s'", venue_id)
        return True

    # ------------------------------------------------------------------
    # Virtual membership
    # ------------------------------------------------------------------

    def add_virtual(self, venue_id: str, virtual_id: str) -> dict:
        """Add *virtual_id* to *venue_id* (exclusive membership enforced)."""
        cfg = self._venues.get(venue_id)
        if cfg is None:
            raise KeyError(f"Venue '{venue_id}' not found")

        if self._ledfx.virtuals.get(virtual_id) is None:
            raise ValueError(f"Virtual '{virtual_id}' not found")

        existing = self._find_venue_for_virtual(virtual_id)
        if existing and existing != venue_id:
            raise ValueError(
                f"Virtual '{virtual_id}' already belongs to venue '{existing}'"
            )

        if virtual_id not in cfg["virtual_ids"]:
            cfg["virtual_ids"].append(virtual_id)
            self._save()

        return {"id": venue_id, **cfg}

    def remove_virtual(self, venue_id: str, virtual_id: str) -> dict:
        """Remove *virtual_id* from *venue_id* and clear its override."""
        cfg = self._venues.get(venue_id)
        if cfg is None:
            raise KeyError(f"Venue '{venue_id}' not found")

        if virtual_id in cfg["virtual_ids"]:
            cfg["virtual_ids"].remove(virtual_id)
            v = self._ledfx.virtuals.get(virtual_id)
            if v is not None:
                v.clear_color_override()
            self._save()

        return {"id": venue_id, **cfg}

    def cleanup_virtual(self, virtual_id: str):
        """Remove *virtual_id* from whichever venue owns it (called on virtual delete)."""
        owner = self._find_venue_for_virtual(virtual_id)
        if owner:
            self.remove_virtual(owner, virtual_id)

    # ------------------------------------------------------------------
    # Override helpers
    # ------------------------------------------------------------------

    def activate_override(self, venue_id: str, pad_index: int):
        """Apply the color/gradient from pad *pad_index* to all venue virtuals."""
        cfg = self._venues.get(venue_id)
        if cfg is None:
            raise KeyError(f"Venue '{venue_id}' not found")

        pads = cfg["color_pads"]["pads"]
        if pad_index < 0 or pad_index >= len(pads):
            raise IndexError(
                f"Pad index {pad_index} out of range (0-{len(pads) - 1})"
            )

        pad = pads[pad_index]
        color_or_gradient = pad.get("gradient") or pad.get("color", "#ffffff")

        for vid in cfg["virtual_ids"]:
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                v.set_color_override(color_or_gradient)

    def clear_override(self, venue_id: str):
        """Clear the color override from all virtuals in *venue_id*."""
        cfg = self._venues.get(venue_id)
        if cfg is None:
            raise KeyError(f"Venue '{venue_id}' not found")

        for vid in cfg["virtual_ids"]:
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                v.clear_color_override()
