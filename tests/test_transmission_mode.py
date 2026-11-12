"""transmission_mode: changeable live, binary by default, migrated once."""

from ledfx.configuration.models import RESTART_FIELDS


def test_changing_it_needs_no_restart():
    assert "transmission_mode" not in RESTART_FIELDS
