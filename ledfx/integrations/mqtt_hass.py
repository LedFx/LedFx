import json
import logging
import socket

import paho.mqtt.client as mqtt
import voluptuous as vol

from ledfx.color import parse_color
from ledfx.config import save_config
from ledfx.consts import PROJECT_VERSION
from ledfx.effects.audio import AudioInputSource
from ledfx.events import Event
from ledfx.integrations import Integration

_LOGGER = logging.getLogger(__name__)


def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(("10.255.255.255", 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
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
        "ledfxtransitiontime": "transition_time",
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
            json.dumps(virtual.config),
        )

    def publish_virtual_paused(self, virtual_id, client):
        virtual = self._ledfx.virtuals.get(virtual_id)
        paused_state = "OFF"
        if virtual.active:
            paused_state = "ON"
        client.publish(
            f"{self._config['topic']}/light/{virtual_id}/state",
            json.dumps({"state": paused_state}),
        )

    def publish_audio_input_changed(self, client, event):
        client.publish(
            f"{self._config['topic']}/select/ledfxaudio/state",
            event.audio_input_device_name,
        )

    def on_connect(self, client, userdata, flags, rc):
        total_pixels = 0
        for device in self._ledfx.devices.values():
            total_pixels += device.pixel_count
        active_pixels = 0
        for virtual in self._ledfx.virtuals.values():
            if virtual.active:
                active_pixels += virtual.pixel_count
        _LOGGER.debug(
            "active_pixels/total_pixels:"
            + str(active_pixels)
            + "/"
            + str(total_pixels)
        )
        # ToDo create sensor with total_pixels

        # Internal State-Handler
        client.subscribe("ledfx/state")

        # Events
        def publish_scene_actived(event):
            client.publish(
                f"{self._config['topic']}/select/ledfxsceneselect/state",
                event.scene_id,
            )

        def publish_global_paused_state(event):
            paused_state = "OFF"
            if self._ledfx.virtuals._paused:
                paused_state = "OFF"
            else:
                paused_state = "ON"
            client.publish(
                f"{self._config['topic']}/switch/ledfxplay/state",
                paused_state,
            )

        def publish_single_color_updated(event):
            color = parse_color(event.effect_config.get("color"))
            client.publish(
                f"{self._config['topic']}/light/{event.virtual_id}/state",
                json.dumps(
                    {
                        "state": "on",
                        "color": [color.red, color.green, color.blue],
                        "effect": event.effect_config.get("color"),
                    }
                ),
            )

        def publish_paused_state(event):
            virtual = self._ledfx.virtuals.get(event.virtual_id)
            paused_state = "OFF"
            if virtual.active:
                paused_state = "ON"
            client.publish(
                f"{self._config['topic']}/light/{event.virtual_id}/state",
                json.dumps({"state": paused_state}),
            )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_scene_actived,
                Event.SCENE_ACTIVATED,
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_single_color_updated,
                Event.EFFECT_SET,
                event_filter={"effect_name": "Single Color"},
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                lambda event: self.publish_virtual_config(
                    event.virtual_id, client
                ),
                Event.VIRTUAL_CONFIG_UPDATE,
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_global_paused_state, Event.GLOBAL_PAUSE
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_paused_state, Event.VIRTUAL_PAUSE
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                lambda event: self.publish_audio_input_changed(client, event),
                Event.AUDIO_INPUT_DEVICE_CHANGED,
            )
        )

        # HomeAssistant Device Entity
        hass_device = {
            "identifiers": ["yzlights"],
            "configuration_url": f"http://{extract_ip()}:{self._ledfx.port}/#/Integrations",
            "name": "LedFx",
            "model": "BladeMOD",
            "manufacturer": "Yeon",
            "sw_version": f"{PROJECT_VERSION}",
        }

        # SENSOR
        client.subscribe(
            f"{self._config['topic']}/sensor/ledfxpixelsensor/set"
        )
        client.publish(
            f"{self._config['topic']}/sensor/ledfxpixelsensor/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/sensor/ledfxpixelsensor",
                    "name": "Used Pixels",
                    "unique_id": "ledfxpixelsensor",
                    "entity_category": "diagnostic",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:led-variant-outline",
                    "device": hass_device,
                }
            ),
        )

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

        # AUDIO SELECTOR
        client.subscribe(f"{self._config['topic']}/select/ledfxaudio/set")
        client.publish(
            f"{self._config['topic']}/select/ledfxaudio/config",
            json.dumps(
                {
                    "~": f"{self._config['topic']}/select/ledfxaudio",
                    "name": "Audio Selector",
                    "unique_id": "ledfxaudio",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:volume-high",
                    "entity_category": "diagnostic",
                    "options": [*AudioInputSource.input_devices().values()],
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
                    "name": "Transition Type",
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
                    "name": "Transition_Time",
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
                    "device": hass_device,
                }
            ),
        )

        command_template = """{
    "state": "on"
    {%- if red is defined and green is defined and blue is defined -%}
    , "color": [{{ red }}, {{ green }}, {{ blue }}]
    {%- endif -%}
    {%- if effect is defined -%}
    , "effect": "{{ effect }}"
    {%- endif -%}
}
"""

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
                        "command_on_template": command_template,
                        "command_off_template": '{"state": "off"}',
                        "red_template": "{{ value_json.color[0] }}",
                        "green_template": "{{ value_json.color[1] }}",
                        "blue_template": "{{ value_json.color[2] }}",
                        "effect_template": "{{ value_json.effect }}",
                        "json_attributes_topic": "~/meta",
                        "icon": icon,
                        "effect": True,
                        # "effect_list": list(COLORS.keys()),
                        # "effect_list": list(self._ledfx.effects.keys()),
                        "device": hass_device,
                    }
                ),
            )

            client.subscribe(f"{self._config['topic']}/light/{virtual.id}/set")
        client.publish("ledfx/state", "HomeAssistant initialized")

    def on_message(self, client, userdata, msg):
        _LOGGER.debug(
            "MQTT-Message incoming: \n[MQTT    ] Topic: "
            + msg.topic
            + "\n[MQTT    ] Payload: "
            + str(msg.payload)
        )
        segs = msg.topic.split("/")
        try:
            payload = json.loads(msg.payload)
        except json.decoder.JSONDecodeError:
            payload = msg.payload.decode("utf-8")

        paused_state = "OFF"
        if self._ledfx.virtuals._paused:
            paused_state = "OFF"
        else:
            paused_state = "ON"

        # React to Internal State-Handler
        total_pixels = 0
        for device in self._ledfx.devices.values():
            total_pixels += device.pixel_count
        active_pixels = 0
        for virtual in self._ledfx.virtuals.values():
            if virtual.active:
                active_pixels += virtual.pixel_count
        if segs[0] == "ledfx":
            if payload == "HomeAssistant initialized":
                virtual = self._ledfx.virtuals.get(
                    next(iter(self._ledfx.virtuals))
                )
                client.publish(
                    f"{self._config['topic']}/select/ledfxtransitiontype/state",
                    virtual.config["transition_mode"],
                )
                client.publish(
                    f"{self._config['topic']}/number/ledfxtransitiontime/state",
                    virtual.config["transition_time"],
                )
                # PausedState
                client.publish(
                    f"{self._config['topic']}/switch/ledfxplay/state",
                    paused_state,
                )
                # AudioSelector
                client.publish(
                    f"{self._config['topic']}/select/ledfxaudio/state",
                    AudioInputSource.input_devices()[
                        self._ledfx.config.get("audio", {}).get(
                            "audio_device", {}
                        )
                    ],
                )
                # Pixel-Sensor
                client.publish(
                    f"{self._config['topic']}/sensor/ledfxpixelsensor/state",
                    str(active_pixels) + " / " + str(total_pixels),
                )
                # publish all virtual data on connect (meta)
                for virtual in self._ledfx.virtuals.values():
                    self.publish_virtual_config(virtual.id, client)
                    self.publish_virtual_paused(virtual.id, client)
            return

        # React to SET commands
        if segs[3] != "set":
            return
        virtualid = segs[2]

        # React to Global-PlayPause
        if virtualid == "ledfxplay":
            # _LOGGER.info("Paused: " + str(self._ledfx.virtuals._paused) + str(payload))
            self._ledfx.virtuals.pause_all()
            paused_state = "OFF"
            if self._ledfx.virtuals._paused:
                paused_state = "OFF"
            else:
                paused_state = "ON"
            client.publish(
                f"{self._config['topic']}/switch/{virtualid}/state",
                paused_state,
            )
            return

        # React to Transition-Type
        if virtualid in self.TRANSITION_MAPPING.keys():
            # _LOGGER.info("Transitions: " + str(payload))
            prior_state = self._ledfx.config["global_transitions"]
            self._ledfx.config["global_transitions"] = True
            virtual = self._ledfx.virtuals.get(
                next(iter(self._ledfx.virtuals))
            )
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

        # React to Audio-Selector
        elif virtualid == "ledfxaudio":
            _LOGGER.debug("AUDIO DEVICE BROOOO: " + str(payload))
            if hasattr(self._ledfx, "audio") and self._ledfx.audio is not None:
                # index = self._ledfx.audio.get_device_index_by_name(payload)
                index = -1
                for key, value in AudioInputSource.input_devices().items():
                    if str(payload) == value:
                        index = key

                new_config = self._ledfx.config.get("audio", {})
                new_config["audio_device"] = int(index)
                self._ledfx.config["audio"] = new_config
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
                self._ledfx.audio.update_config(new_config)
            return

        # React to Virtuals
        elif isinstance(payload, dict):
            virtual = self._ledfx.virtuals.get(virtualid, None)
            if virtual:
                # SET VIRTUAL COLOR AND ACTIVE
                color = payload.get("effect", "orange")
                color = payload.get("color", None)

                if color is not None:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type="singleColor",
                        config={"color": color},
                    )
                else:
                    _LOGGER.debug("COLOR: %s", color)
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type="singleColor",
                        config={"color": "orange"},
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
                        item["effect"]["config"] = {"color": color}
                        self._ledfx.config["virtuals"][idx] = item
                        break

                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )

        # client.publish(
        #     f"{self._config['topic']}/light/{virtualid}/state",
        #     msg.payload,
        # )

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
            f"{self._config['topic']}/select/ledfxaudio/config", json.dumps({})
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
            f"{self._config['topic']}/sensor/ledfxpixelsensor/config",
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
