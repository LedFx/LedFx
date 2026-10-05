"""Contract tests: the live LedFx answers every v2 operation as its OpenAPI
spec says: no 500s, bodies match their schemas, and every status it
returns is documented.

They run against the LedFx subprocess that tests/conftest.py starts (offline,
on BASE_PORT), and run last, so the operations they exercise cannot disturb
the other live-server tests.
"""

import time
from typing import TYPE_CHECKING, cast

import pytest
import requests
import schemathesis
from hypothesis import settings
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import (
    response_schema_conformance,
    status_code_conformance,
)

from tests.test_utilities.consts import BASE_PORT

if TYPE_CHECKING:
    from schemathesis.specs.openapi.schemas import OpenApiCase

BASE_URL = f"http://127.0.0.1:{BASE_PORT}"
SPEC_URL = f"{BASE_URL}/api/v2/openapi.json"
STARTUP_TIMEOUT_S = 60

# schemathesis.check is typed as returning a function or a check class; these
# three are functions.
CHECKS = cast(
    "list[schemathesis.CheckFunction]",
    [not_a_server_error, response_schema_conformance, status_code_conformance],
)


def _fetch_spec() -> dict[str, object]:
    """Wait for the live server to serve its spec, then return it."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            response = requests.get(SPEC_URL, timeout=2)
        except requests.RequestException:
            response = None
        if response is not None and response.status_code == 200:
            spec: dict[str, object] = response.json()
            return spec
        time.sleep(0.5)
    pytest.fail(f"LedFx did not serve {SPEC_URL} within {STARTUP_TIMEOUT_S} s")


@pytest.fixture(scope="module")
def live_v2_schema() -> schemathesis.BaseSchema:
    # The coverage phase sends ~30,000 requests for the schema-heavy effect
    # routes (about 50 s on manager-clients); fuzzing finds the same server
    # errors, schema mismatches and undocumented statuses in a few seconds.
    config = schemathesis.config.SchemathesisConfig.from_dict(
        {"phases": {"coverage": {"enabled": False}}}
    )
    return schemathesis.openapi.from_dict(_fetch_spec(), config=config)


# Lazy: the spec is fetched when the test runs, not at collection, when the
# live server may still be starting.
schema = schemathesis.pytest.from_fixture("live_v2_schema")


@pytest.mark.order(-1)
@pytest.mark.timeout(180)
@schema.parametrize()
@settings(max_examples=5, deadline=None, derandomize=True, database=None)
def test_v2_contract(case: "OpenApiCase") -> None:
    response = case.call(base_url=BASE_URL)
    case.validate_response(response, checks=CHECKS)
