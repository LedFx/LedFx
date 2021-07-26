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
from ledfx.config import save_config
from ledfx.color import COLORS
from ledfx.transitions import Transitions
_LOGGER = logging.getLogger(__name__)

class MQTT_HASS(Integration):
    """MQTT HomeAssistant Integration"""
    
    NAME = "Home Assistant MQTT"
    DESCRIPTION = "MQTT Integration for Home Assistant"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this HomeAssistant instance",
                default="Home Assistant",
            ): str,
            vol.Required(
                "topic",
                description="HomeAssistant's discovery prefix",
                default="homeassistant",
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
                default="",
            ): str,
            vol.Optional(
                "description",
                description="Internal Description",
                default="MQTT Integration with auto-discovery",
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

    def on_connect(self, client, userdata, flags, rc):
        ### Create Scene-Selector and Transition-Config as Light in HomeAssistant      
        

        # SCENE SELECTOR
        client.subscribe(f"{self._config['topic']}/select/ledfxsceneselect/set")
        client.publish(f"{self._config['topic']}/select/ledfxsceneselect/config", json.dumps({
            "~": f"{self._config['topic']}/select/ledfxsceneselect",
            "name": "1 Scene Selector",
            "unique_id": "ledfxsceneselect",
            "cmd_t": "~/set",
            "stat_t": "~/state",
            "icon":  "mdi:image-multiple-outline",
            "options": list(self._ledfx.config["scenes"].keys()),
            "device": {
                "identifiers": [
                    "yzlights"
                ],
                "name": "LedFx",
                "model": "BladeMOD",
                "manufacturer": "Yeon",
                "sw_version": self._ledfx.config['configuration_version']
            }
        }))

        # TRANSITION TYPE
        client.subscribe(f"{self._config['topic']}/select/ledfxtransitiontype/set")
        client.publish(f"{self._config['topic']}/select/ledfxtransitiontype/config", json.dumps({
            "~": f"{self._config['topic']}/select/ledfxtransitiontype",
            "name": "2 Transition Type",
            "unique_id": "ledfxtransitiontype",
            "cmd_t": "~/set",
            "stat_t": "~/state",
            "icon":  "mdi:transfer-right",
            "options": list([
                "Add",
                "Dissolve",
                "Push",
                "Slide",
                "Iris",
                "Through White",
                "Through Black",
                "None",
            ]),
            "device": {
                "identifiers": [
                    "yzlights"
                ],
                "name": "LedFx",
                "model": "BladeMOD",
                "manufacturer": "Yeon",
                "sw_version": self._ledfx.config['configuration_version']
            }
        }))


        # TRANSITION TIME
        client.subscribe(f"{self._config['topic']}/number/ledfxtransitiontime/set")
        client.publish(f"{self._config['topic']}/number/ledfxtransitiontime/config", json.dumps({
            "~": f"{self._config['topic']}/number/ledfxtransitiontime",
            "name": "3 Transition Time",
            "unique_id": "ledfxtransitiontime",
            "cmd_t": "~/set",
            "stat_t": "~/state",
            "icon":  "mdi:camera-timer",
            "min": 0,
            "max": 10,
            "step": 0.1,
            "device": {
                "identifiers": [
                    "yzlights"
                ],
                "name": "LedFx",
                "model": "BladeMOD",
                "manufacturer": "Yeon",
                "sw_version": self._ledfx.config['configuration_version']
            }
        }))


        # SWITCH
        client.subscribe(f"{self._config['topic']}/switch/ledfxplay/set")
        client.publish(f"{self._config['topic']}/switch/ledfxplay/config", json.dumps({
            "~": f"{self._config['topic']}/switch/ledfxplay",
            "name": "4 Play / Pause",
            "unique_id": "ledfxplay",
            "cmd_t": "~/set",
            "stat_t": "~/state",
            "icon":  "mdi:play-pause",
            "device": {
                "identifiers": [
                    "yzlights"
                ],
                "name": "LedFx",
                "model": "BladeMOD",
                "manufacturer": "Yeon",
                "sw_version": self._ledfx.config['configuration_version']
            }
        }))

        ### Create Virtuals as Light in HomeAssistant
        for virtual in self._ledfx.virtuals.values():
            if virtual.config["icon_name"].startswith("mdi:"):
                icon=virtual.config["icon_name"]
            else:
                icon="mdi:led-strip"
            client.publish(f"{self._config['topic']}/light/{virtual.id}/config", json.dumps({
                "~": f"{self._config['topic']}/light/{virtual.id}",
                "name": "⮑ " + virtual.config["name"],
                "unique_id": virtual.id,
                "cmd_t": "~/set",
                "stat_t": "~/state",
                "schema": "json",
                "brightness": False,
                "icon": icon,
                #"color_mode": True,                    ### LATER: WAIT FOR COLOR TO BECOME UNIVERSAL
                #"supported_color_modes": ["rgb"],
                "effect": True,
                "effect_list": list(COLORS.keys()),
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
            client.subscribe(f"{self._config['topic']}/light/{virtual.id}/set")


    def on_message(self, client, userdata, msg):
        ### React to SET commands
        if msg.topic.endswith("/set"):
            segs=msg.topic.split("/")
            virtualid=segs[2]
            _LOGGER.warning(f"YZ{virtualid}")

            ### React to Transition-Type
            if virtualid == "ledfxtransitiontype":
                _LOGGER.info("Transitions: " + str(msg.payload))
                # mydict = ast.literal_eval(msg.payload.decode('utf-8'))
                # if "effect" in mydict:
                #     _LOGGER.info("Change Transition Effect: " + mydict["effect"])
                #     ### Todo: set Global Transition Effect to mydict["effect"]
                # if "brightness" in mydict:
                #     _LOGGER.info("Change Transition Time to " + str(mydict["brightness"]*10) + "ms")
                #     ### Todo: set Global Transition Time to mydict["brightness"]*10 ms
                client.publish(f"{self._config['topic']}/light/{virtualid}/state", msg.payload)
                return



            ### React to Transition-Time
            if virtualid == "ledfxtransitiontime":
                _LOGGER.info("Transitions: " + str(msg.payload))
                # mydict = ast.literal_eval(msg.payload.decode('utf-8'))
                # if "effect" in mydict:
                #     _LOGGER.info("Change Transition Effect: " + mydict["effect"])
                #     ### Todo: set Global Transition Effect to mydict["effect"]
                # if "brightness" in mydict:
                #     _LOGGER.info("Change Transition Time to " + str(mydict["brightness"]*10) + "ms")
                #     ### Todo: set Global Transition Time to mydict["brightness"]*10 ms
                client.publish(f"{self._config['topic']}/light/{virtualid}/state", msg.payload)
                return



            ### React to Scene-Selector-v2
            if virtualid == "ledfxsceneselect":
                scene_id = msg.payload.decode('utf-8')            
                _LOGGER.warning(f"YZ{scene_id}")
                if scene_id not in self._ledfx.config["scenes"].keys():
                    response = {
                        "status": "failed",
                        "reason": f'Scene "{scene_id}" does not exist',
                    }
                    return _LOGGER.warning(response)

                scene = self._ledfx.config["scenes"][scene_id]

                for virtual in self._ledfx.virtuals.values():
                    if virtual.id not in scene["virtuals"].keys():
                        _LOGGER.warning(
                            ("virtual with id {} has no data in scene {}").format(
                                virtual.id, scene_id
                            )
                        )
                        continue

                    if scene["virtuals"][virtual.id]:
                        effect = self._ledfx.effects.create(
                            ledfx=self._ledfx,
                            type=scene["virtuals"][virtual.id]["type"],
                            config=scene["virtuals"][virtual.id]["config"],
                        )
                        virtual.set_effect(effect)
                    else:
                        virtual.clear_effect()

                self._ledfx.events.fire_event(SceneSetEvent(scene["name"]))
            
            ### React to Virtuals
            for virtual in self._ledfx.virtuals.values():

                if virtual.id == virtualid:
                    mydict = ast.literal_eval(msg.payload.decode('utf-8'))      
                    virt = self._ledfx.virtuals.get(virtualid)
                    ### SET VIRTUAL COLOR ###
                    if "effect" in mydict:                        
                        effect = self._ledfx.effects.create(
                            ledfx=self._ledfx, type="singleColor", config={"color":  mydict["effect"]}
                        )
                        try:
                            virt.set_effect(effect)
                        except (ValueError, RuntimeError) as msg:
                            response = {
                                "status": "failed",
                                "payload": {"type": "warning", "reason": str(msg)},
                            }
                            return _LOGGER.warning(response)
                        for virt in self._ledfx.config["virtuals"]:
                            if virt["id"] == virtualid:
                                virt["effect"] = {}
                                virt["effect"]["type"] = "singleColor"
                                virt["effect"]["config"] = {"color":  mydict["effect"]}
                                break
                        save_config(
                            config=self._ledfx.config,
                            config_dir=self._ledfx.config_dir,
                        )
                        client.publish(f"{self._config['topic']}/light/{virtualid}/state", msg.payload)
                        return
                    ### Fallback if no active effect 
                    if not virt.active_effect:                        
                        effect = self._ledfx.effects.create(
                            ledfx=self._ledfx, type="singleColor", config={"color":  "orange"}
                        )
                        try:
                            virt.set_effect(effect)
                        except (ValueError, RuntimeError) as msg:
                            response = {
                                "status": "failed",
                                "payload": {"type": "warning", "reason": str(msg)},
                            }
                            return _LOGGER.warning(response)
                        for virt in self._ledfx.config["virtuals"]:
                            if virt["id"] == virtualid:
                                virt["effect"] = {}
                                virt["effect"]["type"] = "singleColor"
                                virt["effect"]["config"] = {"color":  "orange"}
                                break
                        save_config(
                            config=self._ledfx.config,
                            config_dir=self._ledfx.config_dir,
                        )
                        client.publish(f"{self._config['topic']}/light/{virtualid}/state", msg.payload)
                        return
                    ### SET VIRTUAL ACTIVE ###
                    if mydict["state"] == "ON":
                        active = True
                    else:
                        active = False
                    virtual = self._ledfx.virtuals.get(virtualid)                   
                    
                    try:
                        virtual.active = active
                    except ValueError as msg:
                        response = {
                            "status": "failed",
                            "payload": {"type": "warning", "reason": str(msg)},
                        }
                        return _LOGGER.warning(response)
                    for idx, item in enumerate(self._ledfx.config["virtuals"]):
                        if item["id"] == virtual.id:
                            item["active"] = virtual.active
                            self._ledfx.config["virtuals"][idx] = item
                            break

                    save_config(
                        config=self._ledfx.config,
                        config_dir=self._ledfx.config_dir,
                    )     

            client.publish(f"{self._config['topic']}/light/{virtualid}/state", msg.payload)


    ### Clean up HomeAssistant
    async def on_delete(self):
        self._client.publish(f"{self._config['topic']}/light/ledfxscene/config", json.dumps({}))
        self._client.publish(f"{self._config['topic']}/light/ledfxtransition/config", json.dumps({}))
        self._client.publish(f"{self._config['topic']}/select/ledfxsceneselect/config", json.dumps({}))        
        self._client.publish(f"{self._config['topic']}/select/ledfxtransitiontype/config", json.dumps({}))        
        self._client.publish(f"{self._config['topic']}/number/ledfxtransitiontime/config", json.dumps({}))        
        self._client.publish(f"{self._config['topic']}/switch/ledfxplay/config", json.dumps({}))        
        for virtual in self._ledfx.virtuals.values():
            self._client.publish(f"{self._config['topic']}/light/{virtual.id}/config", json.dumps({}))

    async def connect(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        self._client = client
        if self._config["username"] is not None:
            client.username_pw_set(self._config["username"], password=self._config["password"])
        client.connect_async(self._config["ip_address"], self._config['port'], 60)
        client.loop_start()



