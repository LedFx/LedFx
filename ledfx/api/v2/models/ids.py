"""Ids as the v2 API accepts them: opaque strings of 1 to 128 characters.

The constraints live here, not on the shared aliases, so stored configs and
v1 never see them. Ids have no pattern: ``dj bird``,
``Rainbow-lr`` and ``Küche`` are all valid.
"""

from typing import Annotated

from pydantic import StringConstraints

from ledfx.configuration.fields import (
    DeviceId,
    JobId,
    VirtualId,
)

_ID = StringConstraints(min_length=1, max_length=128)

VirtualIdParam = Annotated[VirtualId, _ID]
DeviceIdParam = Annotated[DeviceId, _ID]
JobIdParam = Annotated[
    JobId,
    StringConstraints(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
]
