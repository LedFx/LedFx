import logging

from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)


class Spotify(Integration):
    """Spotify Integration"""

    NAME = "Spotify"
    DESCRIPTION = "Activate scenes with Spotify Connect [BETA]. Requires Spotify Premium."

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)
        self._ledfx = ledfx
        self._config = config
        self._name = self.NAME
        self._description = self.DESCRIPTION
        self._published = True
        self._data = {}
        self._config['name'] = self._name

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

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def published(self):
        return self._published
