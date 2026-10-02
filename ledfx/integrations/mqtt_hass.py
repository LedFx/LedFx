import json
import logging
import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ClassVar

import paho.mqtt.client as mqtt
from pydantic import Field

from ledfx.api.jsonutil import dumps
from ledfx.color import coerce_color, parse_color
from ledfx.configuration.fields import X_REQUIRED, CoercedInt, VirtualIdStr
from ledfx.configuration.models import replace_model
from ledfx.configuration.plugin import PluginConfig, TypedConfig
from ledfx.consts import PROJECT_VERSION
from ledfx.effects.audio import AudioInputSource
from ledfx.errors import Conflict, Invalid, NotFound, SafeMode
from ledfx.events import EffectSetEvent, Event
from ledfx.integrations import Integration
from ledfx.presets import ledfx_presets

_LOGGER = logging.getLogger(__name__)


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


def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(("10.255.255.255", 1))
        IP = st.getsockname()[0]
    except Exception:  # noqa: BLE001
        IP = "127.0.0.1"
    finally:
        st.close()
    return IP


class MQTT_HASS(Integration):
    """MQTT HomeAssistant Integration"""

    NAME = "Home Assistant MQTT"
    DESCRIPTION = "MQTT Integration for Home Assistant"

    class Config(PluginConfig):
        name: str = Field(
            "Home Assistant",
            description="Name of this HomeAssistant instance",
            json_schema_extra={X_REQUIRED: True},
        )
        topic: str = Field(
            "homeassistant",
            description="HomeAssistant's discovery prefix",
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
        description: str = Field(
            "MQTT Integration with auto-discovery", description="Internal Description"
        )

    config = TypedConfig(Config)

    TRANSITION_MAPPING: ClassVar[dict[str, str]] = {
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
        if virtual is None:  # deleted since the event was fired
            _LOGGER.debug("Virtual %s is gone, not publishing its config", virtual_id)
            return
        client.publish(
            f"{self.config.topic}/light/{virtual_id}/meta",
            dumps(virtual.config),
        )

    def publish_virtual_paused(self, virtual_id, client):
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:  # deleted since the event was fired
            _LOGGER.debug("Virtual %s is gone, not publishing its state", virtual_id)
            return
        paused_state = "OFF"
        if virtual.active:
            paused_state = "ON"
        client.publish(
            f"{self.config.topic}/light/{virtual_id}/state",
            json.dumps({"state": paused_state}),
        )

    def publish_audio_input_changed(self, client, event):
        client.publish(
            f"{self.config.topic}/select/ledfxaudio/state",
            event.audio_input_device_name,
        )

    def publish_single_color(self, client: mqtt.Client, event: EffectSetEvent) -> None:
        # Listeners run later on the loop, so the virtual may have moved on to
        # another effect: use the event's effect, and skip it if it is gone.
        effect = self._ledfx.effects.get(event.effect_id)
        color = getattr(getattr(effect, "config", None), "color", None)
        if color is None:
            return
        rgb = parse_color(color)
        client.publish(
            f"{self.config.topic}/light/{event.virtual_id}/state",
            json.dumps(
                {
                    "state": "on",
                    "color": [rgb.red, rgb.green, rgb.blue],
                    "effect": color,
                }
            ),
        )

    def on_connect(self, client, userdata, flags, rc):
        """paho network thread: hand the connect event to the event loop."""
        self._call_on_loop(self._handle_connect, client, rc)

    def _handle_connect(self, client, rc):
        total_pixels = 0
        for device in self._ledfx.devices.values():
            total_pixels += device.pixel_count
        active_pixels = 0
        for virtual in self._ledfx.virtuals.values():
            if virtual.active:
                active_pixels += virtual.pixel_count
        _LOGGER.debug("active_pixels/total_pixels:%s/%s", active_pixels, total_pixels)
        # ToDo create sensor with total_pixels

        # Internal State-Handler
        client.subscribe("ledfx/state")

        # Events
        def publish_scene_actived(event):
            client.publish(
                f"{self.config.topic}/select/ledfxsceneselect/state",
                event.scene_id,
            )

        def publish_global_paused_state(event):
            paused_state = "OFF"
            if self._ledfx.virtuals._paused:
                paused_state = "OFF"
            else:
                paused_state = "ON"
            client.publish(
                f"{self.config.topic}/switch/ledfxplay/state",
                paused_state,
            )

        def publish_paused_state(event):
            self.publish_virtual_paused(event.virtual_id, client)

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_scene_actived,
                Event.SCENE_ACTIVATED,
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                lambda event: self.publish_single_color(client, event),
                Event.EFFECT_SET,
                event_filter={"effect_name": "Single Color"},
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                lambda event: self.publish_virtual_config(event.virtual_id, client),
                Event.VIRTUAL_CONFIG_UPDATE,
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(
                publish_global_paused_state, Event.GLOBAL_PAUSE
            )
        )

        self._listeners.append(
            self._ledfx.events.add_listener(publish_paused_state, Event.VIRTUAL_PAUSE)
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
        client.subscribe(f"{self.config.topic}/sensor/ledfxpixelsensor/set")
        client.publish(
            f"{self.config.topic}/sensor/ledfxpixelsensor/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/sensor/ledfxpixelsensor",
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
        client.subscribe(f"{self.config.topic}/select/ledfxsceneselect/set")
        client.publish(
            f"{self.config.topic}/select/ledfxsceneselect/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/select/ledfxsceneselect",
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
        client.subscribe(f"{self.config.topic}/select/ledfxaudio/set")
        client.publish(
            f"{self.config.topic}/select/ledfxaudio/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/select/ledfxaudio",
                    "name": "Audio Selector",
                    "unique_id": "ledfxaudio",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:volume-high",
                    "options": [*AudioInputSource.input_devices().values()],
                    "entity_category": "config",
                    "device": hass_device,
                }
            ),
        )

        # TRANSITION TYPE
        client.subscribe(f"{self.config.topic}/select/ledfxtransitiontype/set")
        client.publish(
            f"{self.config.topic}/select/ledfxtransitiontype/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/select/ledfxtransitiontype",
                    "name": "Transition Type",
                    "unique_id": "ledfxtransitiontype",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:transfer-right",
                    "entity_category": "config",
                    "options": [
                        "Add",
                        "Dissolve",
                        "Push",
                        "Slide",
                        "Iris",
                        "Through White",
                        "Through Black",
                        "None",
                    ],
                    "device": hass_device,
                }
            ),
        )

        # TRANSITION TIME
        client.subscribe(f"{self.config.topic}/number/ledfxtransitiontime/set")
        client.publish(
            f"{self.config.topic}/number/ledfxtransitiontime/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/number/ledfxtransitiontime",
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
        client.subscribe(f"{self.config.topic}/switch/ledfxplay/set")
        client.publish(
            f"{self.config.topic}/switch/ledfxplay/config",
            json.dumps(
                {
                    "~": f"{self.config.topic}/switch/ledfxplay",
                    "name": "Play / Pause",
                    "unique_id": "ledfxplay",
                    "cmd_t": "~/set",
                    "stat_t": "~/state",
                    "icon": "mdi:play-pause",
                    "device": hass_device,
                }
            ),
        )

        # Create Virtuals as Light in HomeAssistant
        for virtual in self._ledfx.virtuals.values():
            name = virtual.config.name
            if name.startswith("gap-") or name.endswith(
                ("-background", "-mask", "-foreground")
            ):
                continue

            if virtual.config.icon_name.startswith("mdi:"):
                icon = virtual.config.icon_name
            else:
                icon = "mdi:led-strip"
            client.publish(
                f"{self.config.topic}/light/{virtual.id}/config",
                json.dumps(
                    {
                        "~": f"{self.config.topic}/light/{virtual.id}",
                        "name": "⮑ " + name,
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
                        "effect_list": list(self._ledfx.effects.classes().keys()),
                        "device": hass_device,
                    }
                ),
            )

            client.subscribe(f"{self.config.topic}/light/{virtual.id}/set")
        client.publish("ledfx/state", "HomeAssistant initialized")

    def on_message(self, client, userdata, msg):
        """paho network thread: hand the message to the event loop."""
        self._call_on_loop(self._handle_message, msg)

    @contextmanager
    def _refusals(self, what: str) -> Iterator[None]:
        """Log a refused change instead of raising: safe mode quietly, a typed
        refusal as a warning. The rest of the with block is skipped. Parse an
        HA payload before entering it: a ValueError here is a bug, not a refusal."""
        try:
            yield
        except SafeMode:
            _LOGGER.debug("Not changing the %s: safe mode", what)
        except (Invalid, NotFound, Conflict) as err:
            _LOGGER.warning("Could not change the %s: %s", what, err)
        except Exception:
            _LOGGER.exception("Failed to change the %s", what)

    @staticmethod
    def _settings(what: str, values: Callable[[], object]) -> PluginConfig | None:
        """Parse the settings of an HA payload; a bad payload is one warning
        (a colour list with a non-number raises TypeError)."""
        try:
            return PluginConfig.model_validate(values())
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not change the %s: %s", what, err)
            return None

    def _handle_message(self, msg):
        client = self._client
        if client is None:
            return
        _LOGGER.debug(
            "MQTT-Message incoming: \n[MQTT    ] Topic: %s\n[MQTT    ] Payload: %s",
            msg.topic,
            msg.payload,
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
                virtual = next(iter(self._ledfx.virtuals.values()), None)
                if virtual is not None:
                    client.publish(
                        f"{self.config.topic}/select/ledfxtransitiontype/state",
                        virtual.config.transition_mode,
                    )
                    client.publish(
                        f"{self.config.topic}/number/ledfxtransitiontime/state",
                        virtual.config.transition_time,
                    )
                # PausedState
                client.publish(
                    f"{self.config.topic}/switch/ledfxplay/state",
                    paused_state,
                )
                # AudioSelector
                client.publish(
                    f"{self.config.topic}/select/ledfxaudio/state",
                    AudioInputSource.input_devices()[
                        self._ledfx.config.audio.audio_device
                    ],
                )
                # Pixel-Sensor
                client.publish(
                    f"{self.config.topic}/sensor/ledfxpixelsensor/state",
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
            # _LOGGER.info("Paused: %s%s", self._ledfx.virtuals._paused, payload)
            self._ledfx.virtuals.pause_all()
            paused_state = "OFF"
            if self._ledfx.virtuals._paused:
                paused_state = "OFF"
            else:
                paused_state = "ON"
            client.publish(
                f"{self.config.topic}/switch/{virtualid}/state",
                paused_state,
            )
            return

        # React to Transition-Type
        if virtualid in self.TRANSITION_MAPPING:
            key = self.TRANSITION_MAPPING[virtualid]
            if key == "transition_time":
                try:
                    val = float(payload)
                except (TypeError, ValueError) as err:
                    _LOGGER.warning("Could not change the transition: %s", err)
                    return
            else:
                val = payload

            # Every virtual takes the transition. Build every new config first,
            # so a bad value is one warning and changes no virtual. Nothing runs
            # after this branch, so it can return.
            try:
                changes = [
                    (virtual.id, replace_model(virtual.config, **{key: val}))
                    for virtual in self._ledfx.virtuals.values()
                ]
            except ValueError as err:
                _LOGGER.warning("Could not change the transition: %s", err)
                return
            for virtual_id, config in changes:
                with self._refusals(f"transition of virtual {virtual_id}"):
                    self._ledfx.virtuals.set_config(virtual_id, config)

        # React to Scene-Selector
        elif virtualid == "ledfxsceneselect":
            try:
                self._ledfx.scenes.activate(str(payload))
            except SafeMode:
                _LOGGER.debug("Scene %s not activated: safe mode", payload)

        # React to Audio-Selector
        elif virtualid == "ledfxaudio":
            _LOGGER.debug("AUDIO DEVICE BROOOO: %s", payload)
            if hasattr(self._ledfx, "audio") and self._ledfx.audio is not None:
                # index = self._ledfx.audio.get_device_index_by_name(payload)
                index = -1
                for key, value in AudioInputSource.input_devices().items():
                    if str(payload) == value:
                        index = key

                cfg = self._ledfx.config
                cfg.audio = cfg.audio.model_copy(update={"audio_device": int(index)})
                self._ledfx.config_store.request_save()
                self._ledfx.audio.update_config(cfg.audio.model_dump())
            return

        # React to Virtuals
        elif isinstance(payload, dict):
            virtual = self._ledfx.virtuals.get(virtualid, None)
            if virtual:
                # SET VIRTUAL COLOR AND ACTIVE
                color = payload.get("color", None)

                if color is not None:
                    what = f"colour of virtual {virtualid}"
                    settings = self._settings(
                        what, lambda: {"color": coerce_color(color)}
                    )
                    if settings is not None:
                        with self._refusals(what):
                            self._ledfx.virtuals.set_effect(
                                VirtualIdStr(virtualid), "singleColor", settings
                            )
                            self._ledfx.virtuals.set_active(
                                VirtualIdStr(virtualid),
                                payload.get("state", "off") == "on",
                            )
                else:
                    _LOGGER.debug("COLOR: %s", color)

                # Handle effect selection
                selected_effect_or_preset = payload.get("effect")
                if selected_effect_or_preset:
                    if selected_effect_or_preset == "back":
                        effect_list = list(self._ledfx.effects.classes().keys())
                    elif selected_effect_or_preset in self._ledfx.effects.classes():
                        # If an effect is selected, show its presets
                        system_presets = ledfx_presets.get(
                            selected_effect_or_preset, {}
                        )
                        user_presets = self._ledfx.config.user_presets.get(
                            selected_effect_or_preset, {}
                        )
                        effect_list = (
                            ["back"]
                            + list(system_presets.keys())
                            + list(user_presets.keys())
                        )
                        what = f"effect of virtual {virtualid}"
                        settings = self._settings(
                            what, lambda: payload.get("effect_config", {})
                        )
                        if settings is not None:
                            with self._refusals(what):
                                self._ledfx.virtuals.set_effect(
                                    VirtualIdStr(virtualid),
                                    selected_effect_or_preset,
                                    settings,
                                )
                    else:
                        # If a preset is selected, apply it
                        effect_type = getattr(virtual.active_effect, "type", "")
                        system_presets = ledfx_presets.get(effect_type, {})
                        user_presets = self._ledfx.config.user_presets.get(
                            effect_type, {}
                        )
                        if selected_effect_or_preset in system_presets:
                            preset_config = system_presets[selected_effect_or_preset][
                                "config"
                            ]
                        elif selected_effect_or_preset in user_presets:
                            preset_config = user_presets[
                                selected_effect_or_preset
                            ].config
                        else:
                            preset_config = None
                        effect_list = (
                            ["back"]
                            + list(system_presets.keys())
                            + list(user_presets.keys())
                        )
                        if preset_config is not None:
                            what = f"preset of virtual {virtualid}"
                            settings = self._settings(what, lambda: preset_config)
                            if settings is not None:
                                with self._refusals(what):
                                    self._ledfx.virtuals.set_effect(
                                        VirtualIdStr(virtualid), effect_type, settings
                                    )
                        return
                    name = virtual.config.name
                    if name.startswith("gap-") or name.endswith(
                        ("-background", "-mask", "-foreground")
                    ):
                        return

                    if virtual.config.icon_name.startswith("mdi:"):
                        icon = virtual.config.icon_name
                    else:
                        icon = "mdi:led-strip"
                    hass_device = {
                        "identifiers": ["yzlights"],
                        "configuration_url": f"http://{extract_ip()}:{self._ledfx.port}/#/Integrations",
                        "name": "LedFx",
                        "model": "BladeMOD",
                        "manufacturer": "Yeon",
                        "sw_version": f"{PROJECT_VERSION}",
                    }
                    client.publish(
                        f"{self.config.topic}/light/{virtual.id}/config",
                        json.dumps(
                            {
                                "~": f"{self.config.topic}/light/{virtual.id}",
                                "name": "⮑ " + name,
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
                                "effect_list": effect_list,
                                "device": hass_device,
                            }
                        ),
                    )

        # client.publish(
        #     f"{self.config.topic}/light/{virtualid}/state",
        #     msg.payload,
        # )

    # Clean up HomeAssistant
    async def on_delete(self):
        # Never connected (e.g. created inactive): nothing to clean up in HA.
        if self._client is None:
            return
        self._client.publish(
            f"{self.config.topic}/light/ledfxscene/config", json.dumps({})
        )
        self._client.publish(
            f"{self.config.topic}/light/ledfxtransition/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self.config.topic}/select/ledfxaudio/config", json.dumps({})
        )
        self._client.publish(
            f"{self.config.topic}/select/ledfxsceneselect/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self.config.topic}/select/ledfxtransitiontype/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self.config.topic}/number/ledfxtransitiontime/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self.config.topic}/sensor/ledfxpixelsensor/config",
            json.dumps({}),
        )
        self._client.publish(
            f"{self.config.topic}/switch/ledfxplay/config", json.dumps({})
        )
        for virtual in self._ledfx.virtuals.values():
            self._client.publish(
                f"{self.config.topic}/light/{virtual.id}/config",
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
        if self.config.username is not None:
            client.username_pw_set(self.config.username, password=self.config.password)
        client.connect_async(self.config.ip_address, self.config.port, 60)
        client.loop_start()
