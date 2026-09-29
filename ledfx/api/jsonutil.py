"""JSON encoding for API/websocket payloads that may contain config models."""

import json

from pydantic import BaseModel


def default(obj: object) -> object:
    """`json.dumps(default=...)` hook: models serialise as their JSON dump."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(obj: object) -> str:
    return json.dumps(obj, default=default)
