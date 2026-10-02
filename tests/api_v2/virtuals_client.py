"""Shared by the virtuals route tests: the core behind v2_client, and a
typed check of Problem responses."""

from typing import NotRequired, TypedDict
from unittest.mock import MagicMock

from aiohttp import web
from aiohttp.client import ClientResponse
from aiohttp.test_utils import TestClient

from ledfx.api.v2.core.binding import LEDFX_KEY
from ledfx.api.v2.core.problem import PROBLEM_MEDIA_TYPE, PROBLEM_PREFIX

Client = TestClient[web.Request, web.Application]
V = "/api/v2/virtuals"
BIRD = f"{V}/dj%20bird"  # the seeded virtual whose id has a space


class ProblemErrorJson(TypedDict):
    loc: list[str | int]
    msg: str
    type: str


class ProblemJson(TypedDict):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: NotRequired[list[ProblemErrorJson]]


class EffectJson(TypedDict):
    """An effect as the routes show it (EffectState_<type> or UnknownPlugin)."""

    type: str
    config: dict[str, object]
    available: NotRequired[bool]


def core_of(client: Client) -> MagicMock:
    """The running_core() behind the client (the module's v2_ledfx)."""
    core = client.app[LEDFX_KEY]
    assert isinstance(core, MagicMock)
    return core


async def expect_problem(resp: ClientResponse, status: int, suffix: str) -> ProblemJson:
    assert resp.status == status, await resp.text()
    assert resp.content_type == PROBLEM_MEDIA_TYPE
    body: ProblemJson = await resp.json()
    assert body["type"] == PROBLEM_PREFIX + suffix
    return body
