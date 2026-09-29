# from ledfx.utils import RegistryLoader, async_fire_and_forget, async_fire_and_return, async_callback
# from ledfx.events import Event
# import importlib
# import pkgutil
import logging

# import aiohttp
# import asyncio
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import PluginConfig, TypedConfig
from ledfx.integrations import Integration

# import numpy as np


# import time
# import os
# import re

_LOGGER = logging.getLogger(__name__)


class Spotify(Integration):
    """Spotify Integration"""

    beta = False

    NAME = "Spotify"
    DESCRIPTION = (
        "Activate scenes with Spotify Connect [BETA]. Requires Spotify Premium."
    )

    class Config(PluginConfig):
        name: str = Field(
            "Spotify",
            description="Name of this integration instance and associated settings",
            json_schema_extra={X_REQUIRED: True},
        )
        description: str = Field(
            "Activate scenes with Spotify",
            description="Description of this integration",
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        # {scene_id: {trigger_id: [song_id, song_name, song_position]}},
        # persisted as this integration's entry data.
        self.restore_from_data(data)

    def restore_from_data(self, data):
        self._data: dict[str, dict[str, object]] = (
            data if isinstance(data, dict) else {}
        )

    @property
    def triggers(self):
        """The raw trigger dict, as stored in the integration entry."""
        return self._data

    @property
    @override
    def data(self):
        return self.get_triggers()

    def get_triggers(self):
        """Triggers per existing scene, with the scene name (the UI reads it)."""
        scenes = self._ledfx.config.scenes
        return {
            scene_id: {"name": scenes[scene_id].name, **triggers}
            for scene_id, triggers in self._data.items()
            if scene_id in scenes
        }

    def add_trigger(self, scene_id, song_id, song_name, song_position):
        """Add a trigger to saved triggers"""
        trigger_id = f"{song_id}-{song_position!s}"
        if scene_id not in self._data:
            self._data[scene_id] = {}
        self._data[scene_id][trigger_id] = [song_id, song_name, song_position]

    def delete_trigger(self, trigger_id):
        """Delete a trigger from saved triggers"""
        for scene_id in self._data:
            if trigger_id in self._data[scene_id]:
                del self._data[scene_id][trigger_id]

    async def connect(self, msg=None):
        await super().connect()

    async def disconnect(self, msg=None):
        await super().disconnect()
