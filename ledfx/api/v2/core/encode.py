"""Response encoding and response validation.

Response models use alias=, never serialization_alias= alone: validated
responses are round-tripped through their declared type.
"""

import json
import os

from pydantic import TypeAdapter


def validate_responses_enabled() -> bool:
    """LEDFX_API_VALIDATE_RESPONSES=1 checks every v2 response against its
    declared type and status. The test suite sets it; it is independent of
    dev_mode."""
    return os.environ.get("LEDFX_API_VALIDATE_RESPONSES") == "1"


def encode(adapter: TypeAdapter[object], value: object) -> bytes:
    """JSON bytes for value. NaN and Infinity raise ValueError (a 500): dump_json
    would quietly send null for them, a value the declared type does not allow."""
    data = adapter.dump_python(value, mode="json", by_alias=True)
    return json.dumps(
        data, allow_nan=False, ensure_ascii=False, separators=(",", ":")
    ).encode()
