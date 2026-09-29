import logging

import paho.mqtt.client as mqtt
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED, CoercedInt
from ledfx.configuration.plugin import PluginConfig, TypedConfig
from ledfx.events import SceneActivatedEvent

# from ledfx.events import Event
from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)


class MQTT(Integration):
    """MQTT Integration"""

    NAME = "MQTT"
    DESCRIPTION = "MQTT Integration"

    class Config(PluginConfig):
        name: str = Field(
            "MQTT",
            description="Name of this integration instance and associated settings",
            json_schema_extra={X_REQUIRED: True},
        )
        topic: str = Field(
            "",
            description="Description of this integration",
            json_schema_extra={X_REQUIRED: True},
        )
        ip_address: str = Field(
            "127.0.0.1",
            description="MQTT ip address",
            json_schema_extra={X_REQUIRED: True},
        )
        port: CoercedInt = Field(
            1883,
            description="MQTT port",
            ge=1,
            le=65535,
            json_schema_extra={X_REQUIRED: True},
        )
        username: str = Field("", description="MQTT username")
        password: str = Field("", description="MQTT password")

    config = TypedConfig(Config)

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._client = None
        self._data = []
        self._listeners = []
        _LOGGER.info("CONFIG: %s", self._config)

    def on_connect(self, client, userdata, flags, rc):
        """paho network thread: hand the connect event to the event loop."""
        self._call_on_loop(self._handle_connect, client, rc)

    def _handle_connect(self, client, rc):
        _LOGGER.info("Connecting2")
        _LOGGER.info("Connected with result code %s", rc)

        client.subscribe(f"{self.config.topic}/#")
        # client.publish(self.config.topic, "connected")
        client.publish(f"{self.config.topic}/STAT", "online")
        client.publish(
            f"{self.config.topic}/SCENES",
            str({sid: s.model_dump() for sid, s in self._ledfx.config.scenes.items()}),
        )
        client.publish(
            f"{self.config.topic}/DEVICES",
            str([v.model_dump() for v in self._ledfx.config.virtuals]),
        )

    def on_message(self, client, userdata, msg):
        """paho network thread: hand the message to the event loop."""
        self._call_on_loop(self._handle_message, msg)

    def _handle_message(self, msg):
        _LOGGER.info("%s %s", msg.topic, msg.payload)

        if msg.topic == f"{self.config.topic}/SCENE":
            scene_id = msg.payload.decode("utf8")
            # SET SCENE not_matt plz do a callable function like set_scene(scene_id)
            if scene_id is None:
                response = {
                    "status": "failed",
                    "reason": 'Required attribute "scene_id" was not provided',
                }
                _LOGGER.warning("%s", response)
                return
            _LOGGER.warning("%s", self._ledfx.config.scenes.keys())
            if scene_id not in self._ledfx.config.scenes:
                response = {
                    "status": "failed",
                    "reason": f'Scene "{scene_id}" does not exist',
                }
                _LOGGER.warning("%s", response)
                return

            scene = self._ledfx.config.scenes[scene_id]

            for virtual in self._ledfx.virtuals.values():
                # Check virtual is in scene, make no changes if it isn't
                if virtual.id not in scene.virtuals:
                    _LOGGER.info(
                        "virtual with id %s has no data in scene %s",
                        virtual.id,
                        scene_id,
                    )
                    continue

                # Set effect of virtual to that saved in the scene,
                # clear active effect of virtual if no effect in scene
                scene_virtual = scene.virtuals[virtual.id]
                if scene_virtual.type is not None:
                    # Create the effect and add it to the virtual
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=scene_virtual.type,
                        config=scene_virtual.config or {},
                    )
                    virtual.set_effect(effect)
                else:
                    virtual.clear_effect()

            self._ledfx.events.fire_event(SceneActivatedEvent(scene.name))
            # SET SCENE END

    async def connect(self):
        _LOGGER.info("Connecting1")
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        if self.config.username is not None:
            client.username_pw_set(self.config.username, password=self.config.password)
        client.connect_async(self.config.ip_address, self.config.port, 60)
        client.loop_start()
        _LOGGER.info("%s", client)
