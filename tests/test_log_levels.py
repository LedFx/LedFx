"""Bad client input is logged as a warning, never as an error."""

import logging
from types import SimpleNamespace

import pytest

from ledfx.color import parse_gradient
from ledfx.virtuals import Virtual


@pytest.mark.parametrize("segment", [["no-such-device", 0, 9, False], ["too", "short"]])
def test_invalid_segment_logs_a_warning(
    caplog: pytest.LogCaptureFixture, segment: list[object]
) -> None:
    virtual = Virtual.__new__(Virtual)
    virtual._ledfx = SimpleNamespace(devices={})
    with pytest.raises(ValueError):
        virtual.validate_segment(segment)
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_invalid_gradient_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ValueError):
        parse_gradient("#ff2a2a #ff8c00 #ffd166")
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
