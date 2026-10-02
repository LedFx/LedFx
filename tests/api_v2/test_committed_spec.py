"""openapi/ledfx-v2.json is the spec this code builds.

Only the canonical environment sets LEDFX_CANONICAL_SPEC=1: Linux, Python
3.12, every extra (the CI openapi job). Elsewhere optional plugins may be
missing, and the build is then a subset of the committed spec.
"""

import json
import os
from pathlib import Path

import pytest

from ledfx.api.v2.core.registry import build_standalone_spec

COMMITTED = Path(__file__).resolve().parents[2] / "openapi" / "ledfx-v2.json"

canonical_only = pytest.mark.skipif(
    os.environ.get("LEDFX_CANONICAL_SPEC") != "1",
    reason="the committed spec is generated on Linux, Python 3.12, all extras "
    "(the CI openapi job sets LEDFX_CANONICAL_SPEC=1)",
)


@canonical_only
def test_committed_spec_is_current() -> None:
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    built = json.loads(json.dumps(build_standalone_spec()))
    assert built == committed, (
        "openapi/ledfx-v2.json is stale: run "
        "`uv run ledfx --dump-openapi openapi/ledfx-v2.json` "
        "(Linux, Python 3.12, uv sync --all-extras --dev). "
        "info.version is API_VERSION in ledfx/api/v2/core/app.py: bump it by hand "
        "when the contract changes."
    )


# The spec-size budget: first set to twice the first measured size,
# rounded up to the next 100 KB. Raise it deliberately, with the reason in the PR.
# Raised to 800 KB with the virtuals routes (367 KB measured): every effect type
# adds an EffectConfig_<type> and an EffectState_<type> component (63 each).
SPEC_BUDGET_BYTES = 800_000


def test_committed_spec_size_within_budget() -> None:
    size = COMMITTED.stat().st_size
    assert size <= SPEC_BUDGET_BYTES, (
        f"openapi/ledfx-v2.json is {size} bytes, over the {SPEC_BUDGET_BYTES}-byte "
        "budget; check for duplicated components before raising it"
    )
