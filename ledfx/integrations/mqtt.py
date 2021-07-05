import asyncio
import logging
import aiohttp
import voluptuous as vol
# from ledfx.events import Event
from ledfx.integrations import Integration
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class MQTT(Integration):
    """MQTT Integration"""
    
    NAME = "MQTT"
    DESCRIPTION = "MQTT Integration"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default="MQTT",
            ): str,
            vol.Required(
                "topic",
                description="Description of this integration",
                default="blade",
            ): str,
            vol.Required(
                "ip_address",
                description="MQTT ip address",
                default="127.0.0.1",
            ): str,
            vol.Required(
                "port", description="MQTT port", default=1883
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                "username",
                description="MQTT username",
                default="blade",
            ): str,
            vol.Optional(
                "password",
                description="MQTT password",
                default="test",
            ): str,

        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._client = None
        self._data = []
        self._listeners = []
        _LOGGER.info(f"CONFIG: {self._config}")


    def on_connect(self, client, userdata, flags, rc):
        _LOGGER.info("Connecting2")
        _LOGGER.info("Connected with result code "+str(rc))
        
        client.subscribe(self._config['topic'])
        client.publish(self._config['topic'], "connected")
        client.publish(f"{self._config['topic']}/STAT", "online")
        # client.publish(f"{self._config['topic']}/SCENES/GET", self._ledfx.scenes)


    def on_message(self, client, userdata, msg):
        _LOGGER.info(msg.topic+" "+str(msg.payload))
        
    async def connect(self):
        _LOGGER.info("Connecting1")
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        if self._config["username"] is not None:
            client.username_pw_set(self._config["username"], password=self._config["password"])
        client.connect_async(self._config["ip_address"], self._config['port'], 60)
        client.loop_start()
        _LOGGER.info(client)



