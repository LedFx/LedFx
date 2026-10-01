import logging
from collections.abc import Iterator

import pytest
import sentry_sdk
import sentry_sdk.client
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from ledfx.sentry_config import setup_sentry


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """Run setup_sentry, recording events instead of sending them."""
    events: list[object] = []

    class Recorder(Transport):
        def capture_envelope(self, envelope: Envelope) -> None:
            if (event := envelope.get_event()) is not None:
                events.append(event)

    monkeypatch.setenv("IS_RELEASE", "true")
    monkeypatch.setattr(sentry_sdk.client, "make_transport", Recorder)
    setup_sentry()
    yield events
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)


@pytest.mark.parametrize("error", [ConnectionResetError, ConnectionAbortedError])
def test_client_disconnects_are_not_sent(
    sent: list[object], error: type[OSError]
) -> None:
    try:
        raise error("peer went away")
    except error:
        logging.getLogger("ledfx.core").exception("Exception in core event loop")
    sentry_sdk.capture_exception(error("peer went away"))
    assert sent == []


def test_other_errors_are_still_sent(sent: list[object]) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logging.getLogger("ledfx.core").exception("Exception in core event loop")
    assert len(sent) == 1
