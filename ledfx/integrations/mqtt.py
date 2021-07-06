import asyncio
import logging
import aiohttp
import voluptuous as vol
# from ledfx.events import Event
from ledfx.integrations import Integration
import paho.mqtt.client as mqtt
from ledfx.events import SceneSetEvent
import json
import ast

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
        
        client.subscribe(f"{self._config['topic']}/#")
        #client.publish(self._config['topic'], "connected")
        #client.publish(f"{self._config['topic']}/STAT", "online")
        #client.publish(f"{self._config['topic']}/SCENES", str(self._ledfx.config["scenes"]))
        #client.publish(f"{self._config['topic']}/DEVICES", str(self._ledfx.config["virtuals"]))
        client.subscribe("homeassistant/light/ledfxscene/set")
        client.publish("homeassistant/light/ledfxscene/config", json.dumps({
            "~": "homeassistant/light/ledfxscene",
            "name": "LedFx Scene-Selector",
            "unique_id": "ledfxscene",
            "cmd_t": "~/set",
            "stat_t": "~/state",
            "schema": "json",
            "brightness": False,
            "brightness_scale": 1000,
            "icon":  "mdi:image-outline",
            #"color_mode": True,
            #"supported_color_modes": ["rgb"],
            #"optimistic": True,
            "effect": True,
            "effect_list": list(self._ledfx.config["scenes"].keys()),
            "device": {
                "identifiers": [
                    "yzlights"
                ],
                "name": "LedFx",
                "model": "BladeMOD",
                "manufacturer": "Yeon",
                "sw_version": "0.9.0"
            }
        }))
        
        for virtual in self._ledfx.virtuals.values():
            if virtual.config["icon_name"].startswith("mdi:"):
                icon=virtual.config["icon_name"]
            else:
                icon="mdi:led-strip"
            client.publish(f"homeassistant/light/{virtual.id}/config", json.dumps({
                "~": f"homeassistant/light/{virtual.id}",
                "name": "⮑ " + virtual.config["name"],
                "unique_id": virtual.id,
                "cmd_t": "~/set",
                "stat_t": "~/state",
                "schema": "json",
                "brightness": True,
                "brightness_scale": 1000,
                "icon": icon,
                "color_mode": True,
                "supported_color_modes": ["rgb"],
                "effect": True,
                "effect_list": [
                    "effect 1",
                    "effect 2",
                    "effect 3"
                ],
                "device": {
                    "identifiers": [
                        "yzlights"
                    ],
                    "name": "LedFx",
                    "model": "BladeMOD",
                    "manufacturer": "Yeon",
                    "sw_version": "0.9.0"
                }
            }))
            client.subscribe(f"homeassistant/light/{virtual.id}/set")


    def on_message(self, client, userdata, msg):
        _LOGGER.info(msg.topic+" "+str(msg.payload))

        if msg.topic.endswith("/set"):
            segs=msg.topic.split("/")
            virtualid=segs[2]
            _LOGGER.info("BOOOM "+virtualid)
            if virtualid == "ledfxscene":
                mydict = ast.literal_eval(msg.payload.decode('utf-8'))
                _LOGGER.info("BOOOM 2"+str(mydict))
                if "effect" in mydict:
                    _LOGGER.info("BOOOM 3: "+mydict["effect"])
                    scene_id = mydict["effect"]
                    ## SET SCENE not_matt plz do a callable function like set_scene(scene_id) ###
                    if scene_id is None:
                        response = {
                            "status": "failed",
                            "reason": 'Required attribute "scene_id" was not provided',
                        }
                        return _LOGGER.warning(response)
                    _LOGGER.warning(str(self._ledfx.config["scenes"].keys()))
                    if scene_id not in self._ledfx.config["scenes"].keys():
                        response = {
                            "status": "failed",
                            "reason": f'Scene "{scene_id}" does not exist',
                        }
                        return _LOGGER.warning(response)

                    scene = self._ledfx.config["scenes"][scene_id]

                    for virtual in self._ledfx.virtuals.values():
                        # Check virtual is in scene, make no changes if it isn't
                        if virtual.id not in scene["virtuals"].keys():
                            _LOGGER.info(
                                ("virtual with id {} has no data in scene {}").format(
                                    virtual.id, scene_id
                                )
                            )
                            continue

                        # Set effect of virtual to that saved in the scene,
                        # clear active effect of virtual if no effect in scene
                        if scene["virtuals"][virtual.id]:
                            # Create the effect and add it to the virtual
                            effect = self._ledfx.effects.create(
                                ledfx=self._ledfx,
                                type=scene["virtuals"][virtual.id]["type"],
                                config=scene["virtuals"][virtual.id]["config"],
                            )
                            virtual.set_effect(effect)
                        else:
                            virtual.clear_effect()

                    self._ledfx.events.fire_event(SceneSetEvent(scene["name"]))
                    ## SET SCENE END ###
            else:
                if: 

            # ToDo: Set Virtual On/Off, maybe effect_list, maybe color



            client.publish(f"homeassistant/light/{virtualid}/state", msg.payload)



        if msg.topic == f"{self._config['topic']}/SCENE":
            
            scene_id = msg.payload.decode("utf8")
            ## SET SCENE not_matt plz do a callable function like set_scene(scene_id) ###
            if scene_id is None:
                response = {
                    "status": "failed",
                    "reason": 'Required attribute "scene_id" was not provided',
                }
                return _LOGGER.warning(response)
            _LOGGER.warning(str(self._ledfx.config["scenes"].keys()))
            if scene_id not in self._ledfx.config["scenes"].keys():
                response = {
                    "status": "failed",
                    "reason": f'Scene "{scene_id}" does not exist',
                }
                return _LOGGER.warning(response)

            scene = self._ledfx.config["scenes"][scene_id]

            for virtual in self._ledfx.virtuals.values():
                # Check virtual is in scene, make no changes if it isn't
                if virtual.id not in scene["virtuals"].keys():
                    _LOGGER.info(
                        ("virtual with id {} has no data in scene {}").format(
                            virtual.id, scene_id
                        )
                    )
                    continue

                # Set effect of virtual to that saved in the scene,
                # clear active effect of virtual if no effect in scene
                if scene["virtuals"][virtual.id]:
                    # Create the effect and add it to the virtual
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=scene["virtuals"][virtual.id]["type"],
                        config=scene["virtuals"][virtual.id]["config"],
                    )
                    virtual.set_effect(effect)
                else:
                    virtual.clear_effect()

            self._ledfx.events.fire_event(SceneSetEvent(scene["name"]))
            ## SET SCENE END ###


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



