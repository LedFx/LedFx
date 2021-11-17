# ToDo:
# - handle per virtual Pause/Unpause (state: on/off) see error below
# - handle global Pause/Unpause
# - enable free color mode
# - effect-list: replace color-names with effect-names
# - react to all accordingly
# - make Name&Description static and remove from schema

# # Exception in thread Thread-68 (thread_function):
# # Traceback (most recent call last):
# #   File "C:\Program Files\Python310\lib\threading.py", line 1009, in _bootstrap_inner
# # [INFO    ] ledfx.effects                  : Effect Single Color activated.
# #     self.run()
# #   File "C:\Program Files\Python310\lib\threading.py", line 946, in run
# #     self._target(*self._args, **self._kwargs)
# #   File "c:\ledfx\ledfx-git\ledfx\virtuals.py", line 354, in thread_function
# # [INFO    ] ledfx.config                   : Saving configuration file to C:\Users\Blade\AppData\Roaming\.ledfx
# #     self.assembled_frame = self.assemble_frame()
# #   File "c:\ledfx\ledfx-git\ledfx\virtuals.py", line 389, in assemble_frame
# #     transition_frame = self._transition_effect.get_pixels()
# #   File "c:\ledfx\ledfx-git\ledfx\effects\__init__.py", line 352, in get_pixels
# #     pixels += np.multiply(
# # ValueError: non-broadcastable output operand with shape () doesn't match the broadcast shape (292,3)


import ast
import json
import logging
import socket

import paho.mqtt.client as mqtt
import voluptuous as vol

from ledfx.events import Event
from ledfx.color import COLORS
from ledfx.config import save_config
from ledfx.events import SceneActivatedEvent
from ledfx.integrations import Integration
from ledfx.consts import ( PROJECT_VERSION )

_LOGGER = logging.getLogger(__name__)

def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:       
        st.connect(('10.255.255.255', 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        st.close()
    return IP

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
                default="",
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

    TRANSITION_MAPPING = {
        "ledfxtransitiontype": "transition_mode",
        "ledfxtransitiontime": "transition_time"
    }

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._client = None
        self._data = []
        self._listeners = []

    def publish_virtual_config(self, virtual_id, client):
            virtual = self._ledfx.virtuals.get(virtual_id)
            client.publish(
                f"{self._config['topic']}/light/{virtual_id}/meta",
                json.dumps(virtual.config)
            )

    def on_connect(self, client, userdata, flags, rc):

        client.subscribe("ledfx/state")

        def publish_scene_actived(event):
            client.publish(
                f"{self._config['topic']}/select/ledfxsceneselect/state",
                event.scene_id
            )

        def publish_single_colour_updated(event):
            color = COLORS[event.effect_config.get("color")]
            client.publish(
                f"{self._config['topic']}/light/{event.virtual_id}/state",
                json.dumps({
                    "state": "on",
                    "color": [
                        color.red,
                        color.green,
                        color.blue
                    ],
                    "effect": event.effect_config.get("color")
                })
            )
            # publish_virtual_config(event.virtual_id)

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_scene_actived,
                Event.SCENE_ACTIVATED,
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_single_colour_updated,
                Event.EFFECT_SET,
                event_filter = {"effect_name": "Single Color"}
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                lambda event: self.publish_virtual_config(event.virtual_id, client),
                Event.VIRTUAL_CONFIG_UPDATE
            )
        )

        hass_device = {
            "identifiers": ["yzlights"],
            "configuration_url": f"http://{extract_ip()}:{self._ledfx.port}/#/Integrations",
            "name": "LedFx",
            "model": "BladeMOD",
            "manufacturer": "Yeon",
            "sw_version": f"{PROJECT_VERSION}",
        }

        # SCENE SELECTOR
        client.subscribe(
            f"{self._config['topic']}/select/ledfxsceneselect/set"
        )
        client.publish(
            f"{self._config['topic']}/select/ledfxsceneselect/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/select/ledfxsceneselect",
                    "name": "Scene Selector",
                    "unique_id": "ledfxsceneselect",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:image-multiple-outline",
                    "options": list(self._ledfx.scenes._scenes.keys()),
                    "entity_category": "config",
                    "device": hass_device,
                }
            ),
        )

        
        # TRANSITION TYPE
        
        client.subscribe(
            f"{self._config['topic']}/select/ledfxtransitiontype/set"
        )
        client.publish(
            f"{self._config['topic']}/select/ledfxtransitiontype/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/select/ledfxtransitiontype",
                    "name": "Transition_Type",
                    "unique_id": "ledfxtransitiontype",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:transfer-right",
                    "entity_category": "config",
                    "options": list(
                        [
                            "Add",
                            "Dissolve",
                            "Push",
                            "Slide",
                            "Iris",
                            "Through White",
                            "Through Black",
                            "None",
                        ]
                    ),
                    "device": hass_device,
                }
            ),
        )
        
        
        # TRANSITION TIME
        client.subscribe(
            f"{self._config['topic']}/number/ledfxtransitiontime/set"
        )
        client.publish(
            f"{self._config['topic']}/number/ledfxtransitiontime/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/number/ledfxtransitiontime",
                    "name": "Transition Time",
                    "unique_id": "ledfxtransitiontime",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:camera-timer",
                    "min": 0,
                    "max": 5,
                    "step": 0.1,
                    "unit_of_measurement": "s",
                    "entity_category": "config",
                    "device": hass_device,
                }
            ),
        )        
    
        
        # SWITCH
        client.subscribe(f"{self._config['topic']}/switch/ledfxplay/set")
        client.publish(
            f"{self._config['topic']}/switch/ledfxplay/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/switch/ledfxplay",
                    "name": "Play / Pause",
                    "unique_id": "ledfxplay",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:play-pause",
                    "entity_category": "diagnostic",
                    "device": hass_device,
                }
            ),
        )

        # Create Virtuals as Light in HomeAssistant
        for virtual in self._ledfx.virtuals.values():
            if virtual.config["icon_name"].startswith("mdi:"):
                icon = virtual.config["icon_name"]
            else:
                icon = "mdi:led-strip"
            client.publish(
                f"{self._config['topic']}/light/{virtual.id}/config",
                json.dumps(
                    {
                        "~": f"{self._config['topic']}/light/{virtual.id}",
                        "name": "⮑ " + virtual.config["name"],
                        "unique_id": virtual.id,
                        "cmd_t": "~/set",
                        "stat_t": "~/state",
                        "state_template": "{{ value_json.state | lower }}",
                        "state_value_template": "{{ value_json.state | lower }}",
                        "schema": "template",
                        "brightness": False,
                        "enabled_by_default": True,                       
                        "command_on_template": """{
    "state": "on"                        
    {%- if red is defined and green is defined and blue is defined -%}
    , "color": [{{ red }}, {{ green }}, {{ blue }}]
    {%- endif -%}
    {%- if effect is defined -%}
    , "effect": "{{ effect }}"
    {%- endif -%}
}""",
                        "command_off_template": "{\"state\": \"off\"}",
                        "red_template": "{{ value_json.color[0] }}",
                        "green_template": "{{ value_json.color[1] }}",
                        "blue_template": "{{ value_json.color[2] }}",
                        "effect_template": "{{ value_json.effect }}",
                        "json_attributes_topic": "~/meta",
                        "icon": icon,
                        "effect": True,
                        "effect_list": list(COLORS.keys()),
                        "device": hass_device,
                    }
                ),
            )            

            client.subscribe(f"{self._config['topic']}/light/{virtual.id}/set")
        
        client.publish("ledfx/state", "HomeAssistant initialized")
       

    def on_message(self, client, userdata, msg):
        _LOGGER.info("MSGS: " + str(msg.payload))
        segs = msg.topic.split("/")
        try:
            payload = json.loads(msg.payload)
        except json.decoder.JSONDecodeError:
            payload = msg.payload.decode("utf-8")
        
        # React to LedFx State commands
        if segs[0] == "ledfx":
            _LOGGER.info("YOOOOOOO: " + str(msg.payload))
            if payload == "HomeAssistant initialized":
                virtual = self._ledfx.virtuals.get(next(iter(self._ledfx.virtuals)))
                client.publish(
                    f"{self._config['topic']}/select/ledfxtransitiontype/state",
                    virtual.config["transition_mode"]
                )
                client.publish(
                    f"{self._config['topic']}/number/ledfxtransitiontime/state",
                    virtual.config["transition_time"]
                )
                # publish all virtual data on connect (meta)
                for virtual in self._ledfx.virtuals.values():
                    self.publish_virtual_config(virtual.id, client)
            return
        
        # React to SET commands
        if segs[3] != "set":
            return
        virtualid = segs[2]        

        # React to Transition-Type
        if virtualid in self.TRANSITION_MAPPING.keys():

            _LOGGER.info("Transitions: " + str(payload))
            prior_state = self._ledfx.config["global_transitions"]
            self._ledfx.config["global_transitions"] = True
            virtual = self._ledfx.virtuals.get(next(iter(self._ledfx.virtuals)))
            key = self.TRANSITION_MAPPING[virtualid]
            if key == "transition_time":
                try:
                    val = float(payload)
                except ValueError as e:
                    _LOGGER.warning(e)
                    val = 0.5
            else:
                val = payload

            virtual.update_config({key: val})
            self._ledfx.config["global_transitions"] = prior_state

        # React to Scene-Selector
        elif virtualid == "ledfxsceneselect":
            self._ledfx.scenes.activate(payload)

        # React to Virtuals
        elif isinstance(payload, dict):
            virtual = self._ledfx.virtuals.get(virtualid, None)
            if virtual:
                # SET VIRTUAL COLOR AND ACTIVE
                colour = payload.get("effect", "orange")
                
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx,
                    type="singleColor",
                    config={"color": colour},
                )
                try:
                    virtual.set_effect(effect)
                    virtual.active = payload["state"] == "on"
                except (ValueError, RuntimeError) as msg:
                    _LOGGER.warning(msg)

                # Save to config
                for idx, item in enumerate(self._ledfx.config["virtuals"]):
                    if item["id"] == virtual.id:
                        item["active"] = virtual.active
                        item["effect"] = {}
                        item["effect"]["type"] = "singleColor"
                        item["effect"]["config"] = {
                            "color": colour
                        }
                        self._ledfx.config["virtuals"][idx] = item
                        break

                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )

        client.publish(
            f"{self._config['topic']}/light/{virtualid}/state",
            msg.payload,
        )

    # Clean up HomeAssistant
    async def on_delete(self):
        self._client.publish(
            f"{self._config['topic']}/light/ledfxscene/config", json.dumps({})
        )
        self._client.publish(
            f"{self._config['topic']}/light/ledfxtransition/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self._config['topic']}/select/ledfxsceneselect/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self._config['topic']}/select/ledfxtransitiontype/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self._config['topic']}/number/ledfxtransitiontime/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self._config['topic']}/switch/ledfxplay/config", json.dumps({})
        )
        for virtual in self._ledfx.virtuals.values():
            self._client.publish(
                f"{self._config['topic']}/light/{virtual.id}/config",
                json.dumps({}),
            )
    
    async def on_disconnect(self):
        for remove_listener in self._listeners:
            remove_listener()
        self._listeners = []

    async def connect(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        self._client = client
        if self._config["username"] is not None:
            client.username_pw_set(
                self._config["username"], password=self._config["password"]
            )
        client.connect_async(
            self._config["ip_address"], self._config["port"], 60
        )
        client.loop_start()
