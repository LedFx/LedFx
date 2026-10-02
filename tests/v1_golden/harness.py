"""Record raw v1 responses and compare them with committed goldens.

A scenario is a list of requests replayed through a real aiohttp server that
serves the family's v1 endpoints over a fake core. Each response is kept as
its status and exact body text. Set LEDFX_UPDATE_GOLDENS=1 to rewrite the
golden files instead of comparing, and review the diff before committing.
"""

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api import RestEndpoint

GOLDEN_ROOT = Path(__file__).parent
# Object reprs in some v1 reasons carry a memory address.
_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")
# pydantic error texts link to docs for the installed version.
_PYDANTIC_DOCS = re.compile(r"https://errors\.pydantic\.dev/[0-9.]+/")


@dataclass(frozen=True)
class Raw:
    """A request body sent as-is (e.g. invalid JSON)."""

    text: str


# Mapping, not dict: dict is invariant, so a dict[str, str] literal would not fit.
Body = Raw | Mapping[str, object] | Sequence[object] | None
Step = tuple[str, str, Body]


def updating() -> bool:
    return os.environ.get("LEDFX_UPDATE_GOLDENS") == "1"


def build_app(
    ledfx: MagicMock, endpoints: Sequence[type[RestEndpoint]]
) -> web.Application:
    app = web.Application()
    for endpoint in endpoints:
        path: str = endpoint.ENDPOINT_PATH
        app.router.add_route("*", path, endpoint(ledfx).handler)
    return app


async def replay(app: web.Application, steps: Sequence[Step]) -> list[object]:
    records: list[object] = []
    async with TestClient(TestServer(app)) as client:
        for method, path, body in steps:
            if isinstance(body, Raw):
                response = await client.request(
                    method,
                    path,
                    data=body.text,
                    headers={"Content-Type": "application/json"},
                )
                sent: object = {"raw": body.text}
            elif body is None:
                response = await client.request(method, path)
                sent = None
            else:
                response = await client.request(method, path, json=body)
                sent = body
            text = _ADDRESS.sub(" at 0x0", await response.text())
            text = _PYDANTIC_DOCS.sub("https://errors.pydantic.dev/X/", text)
            records.append(
                {
                    "request": [method, path, sent],
                    "status": response.status,
                    "body": text,
                }
            )
    return records


def check(family: str, name: str, records: list[object]) -> None:
    """Compare records with tests/v1_golden/<family>/<name>.json (or write it)."""
    path = GOLDEN_ROOT / family / f"{name}.json"
    if updating():
        path.parent.mkdir(exist_ok=True)
        text = json.dumps(records, indent=2, ensure_ascii=False)
        path.write_text(text + "\n", encoding="utf-8")
        return
    assert path.exists(), f"no golden {path}; record it with LEDFX_UPDATE_GOLDENS=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert records == expected


def golden_names(family: str) -> set[str]:
    return {path.stem for path in (GOLDEN_ROOT / family).glob("*.json")}
