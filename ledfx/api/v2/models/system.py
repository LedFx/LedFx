"""System models. SystemInfo is minimal until the system family lands."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SystemInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    api_versions: list[Literal["v1", "v2"]]
