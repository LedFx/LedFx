# from ledfx.utils import RegistryLoader, async_fire_and_forget, async_fire_and_return, async_callback
# from ledfx.events import Event
# import importlib
# import pkgutil
import logging

# import aiohttp
# import asyncio
import voluptuous as vol

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
    DESCRIPTION = "Activate scenes with Spotify Connect [BETA]. Requires Spotify Premium."

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default="Spotify",
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default="Activate scenes with Spotify",
            ): str,
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._data = {}

        self.restore_from_data(self._ledfx.config["scenes"])

    def restore_from_data(self, data):
        """Might be used in future"""
        self._data = data

    def get_triggers(self):
        return self._data

    def add_trigger(self, scene_id, song_id, song_name, song_position):
        """Add a trigger to saved triggers"""
        trigger_id = f"{song_id}-{str(song_position)}"
        if scene_id not in self._data.keys():
            self._data[scene_id] = {}
        self._data[scene_id][trigger_id] = [song_id, song_name, song_position]

    def delete_trigger(self, trigger_id):
        """Delete a trigger from saved triggers"""
        for scene_id in self._data.keys():
            if trigger_id in self._data[scene_id].keys():
                del self._data[scene_id][trigger_id]

    async def connect(self, msg=None):
        await super().connect()

    async def disconnect(self, msg=None):
        await super().disconnect()
