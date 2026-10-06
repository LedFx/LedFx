"""Regressions for clearing a virtual's effect slots (LEDFX-V2-REL-1NZ, 3QJ)."""

import threading
from unittest.mock import MagicMock, patch

from ledfx.configuration.models import VirtualConfig
from ledfx.utils import RegistryLoader
from ledfx.virtuals import Virtual


def _virtual(registered: dict[str, object]) -> Virtual:
    effects = object.__new__(RegistryLoader)
    effects._objects = registered
    virtual = object.__new__(Virtual)
    virtual.lock = threading.Lock()
    virtual._output_lock = threading.RLock()
    virtual._retired_effects = []
    virtual._source_generation = 0
    virtual._render_token = 0
    virtual._ledfx = MagicMock()
    virtual._ledfx.effects = effects
    return virtual


def test_clear_effect_missing_from_registry() -> None:
    # The id is gone from the registry; clearing must still empty the slots,
    # or every later clear_frame raises and the virtual is wedged.
    virtual = _virtual({})
    active, transition = MagicMock(id="gradient"), MagicMock(id="gradient-1")
    virtual._active_effect, virtual._transition_effect = active, transition

    virtual.clear_active_effect()
    virtual.clear_transition_effect()

    assert virtual._active_effect is None
    assert virtual._transition_effect is None
    active._deactivate.assert_called_once()
    transition._deactivate.assert_called_once()


def test_clear_effect_leaves_reused_id_alone() -> None:
    # Ids are reused once destroyed, so a stale effect must not destroy the
    # registry entry of the newer effect that now holds its id.
    newer = MagicMock(id="gradient")
    registered: dict[str, object] = {"gradient": newer}
    virtual = _virtual(registered)
    virtual._active_effect = MagicMock(id="gradient")
    virtual._transition_effect = MagicMock(id="gradient")

    virtual.clear_active_effect()
    virtual.clear_transition_effect()

    assert registered == {"gradient": newer}


def test_clear_effect_destroys_registered_effect() -> None:
    active, transition = MagicMock(id="gradient"), MagicMock(id="gradient-1")
    registered: dict[str, object] = {"gradient": active, "gradient-1": transition}
    virtual = _virtual(registered)
    virtual._active_effect, virtual._transition_effect = active, transition

    virtual.clear_active_effect()
    virtual.clear_transition_effect()

    assert registered == {}


def test_config_change_restarts_effect_outside_producing_lock() -> None:
    # The render thread clears a finished transition under the lock; an
    # unlocked restart could clear and destroy the same effect concurrently.
    virtual = _virtual({})
    virtual.lock = threading.Lock()
    virtual._config = VirtualConfig.model_validate({"name": "v"})
    virtual._active_effect = MagicMock()
    virtual.complex_segments = False
    held: list[bool] = []

    def reactivate(self: Virtual) -> None:
        held.append(self.lock.locked())

    with patch.object(Virtual, "_reactivate_effect", reactivate):
        virtual.update_config({"grouping": 2})
    assert held == [False]
