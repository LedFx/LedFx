"""Clone must release native screen-capture resources, not just Python objects."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ledfx.effects import clone as clone_module
from ledfx.effects.clone import Clone


def capture() -> Mock:
    result = Mock()
    result.monitors = [{"top": 0, "left": 0}]
    result.grab.return_value = SimpleNamespace(size=(8, 8), bgra=bytes(8 * 8 * 4))
    return result


def effect() -> Clone:
    result = Clone(None, {"width": 8, "height": 8})
    result.r_width = result.r_height = 8
    return result


def test_discarded_clone_closes_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    screen = capture()
    monkeypatch.setattr(clone_module.mss, "mss", lambda: screen)
    clone = effect()
    clone.draw()
    clone.deactivate()
    clone.deactivate()
    screen.close.assert_called_once()
    assert clone.sct is None
    assert clone.grab is None
    assert not clone.is_active


def test_reconfiguration_closes_capture_before_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = capture(), capture()
    factory = Mock(side_effect=[first, second])
    monkeypatch.setattr(clone_module.mss, "mss", factory)
    clone = effect()
    clone.draw()
    clone.update_config({"width": 16})
    first.close.assert_called_once()
    assert clone.sct is None
    clone.draw()
    assert clone.sct is second
    clone.deactivate()
    second.close.assert_called_once()


@pytest.mark.parametrize("stage", ["setup", "grab"])
def test_capture_errors_release_resources_before_retry(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    first, second = capture(), capture()
    if stage == "setup":
        first.monitors = list[dict[str, int]]()
    else:
        first.grab.side_effect = RuntimeError("capture failed")
    monkeypatch.setattr(clone_module.mss, "mss", Mock(side_effect=[first, second]))
    clone = effect()
    clone.draw()
    first.close.assert_called_once()
    assert clone.sct is None
    assert clone.fails == 1
    clone.draw()
    assert clone.sct is second
    assert clone.fails == 0
    clone.deactivate()
    second.close.assert_called_once()


def test_capture_close_failure_does_not_skip_effect_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screen = capture()
    screen.close.side_effect = RuntimeError("capture close failed")
    monkeypatch.setattr(clone_module.mss, "mss", lambda: screen)
    clone = effect()
    clone.draw()
    clone._active = True
    clone.deactivate()
    assert not clone.is_active
    assert clone.logsec.effect is None
    assert clone.sct is None
