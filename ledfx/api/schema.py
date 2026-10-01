import logging
from json import JSONDecodeError
from typing import ClassVar

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.jsonutil import dumps
from ledfx.api.utils import PERMITTED_KEYS
from ledfx.configuration.models import (
    AudioAnalysisConfig,
    AudioInputConfig,
    LedFxConfig,
    MelbankConfig,
    MelbanksConfig,
    VirtualConfig,
    WledPreferences,
)
from ledfx.configuration.schema import legacy_schema
from ledfx.consts import LEGACY_CONFIGURATION_VERSION

_LOGGER = logging.getLogger(__name__)

# Pre-overhaul core schema key order and runtime-only keys (legacy endpoint only).
LEGACY_CORE_ORDER = (
    "host", "hosts", "port", "port_s", "dev_mode", "devices", "virtuals", "audio",
    "melbank_collection", "melbanks", "ledfx_presets", "user_presets", "scenes",
    "playlists", "integrations", "transmission_mode", "visualisation_fps",
    "visualisation_maxlen", "global_transitions", "user_colors", "user_gradients",
    "scan_on_startup", "create_segments", "flush_on_deactivate", "wled_preferences",
    "configuration_version", "global_brightness", "ui_brightness_boost",
    "startup_scene_id", "startup_playlist_id", "lifx_broadcast_address",
    "lifx_discovery_timeout", "instance_id", "sendspin_servers",
    "sendspin_always_on", "now_playing",
)  # fmt: skip
LEGACY_CORE_EXTRAS: dict[str, dict[str, object]] = {
    "hosts": {"type": "array", "title": "Hosts", "default": []},
    "ledfx_presets": {"type": "dict", "title": "Ledfx Presets", "default": {}},
    "configuration_version": {
        "type": "string",
        "title": "Configuration Version",
        "default": LEGACY_CONFIGURATION_VERSION,
    },
}


class SchemaEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/schema"

    VALID_SCHEMAS: ClassVar[set[str]] = {
        "devices",
        "effects",
        "integrations",
        "virtuals",
        "audio",
        "melbanks",
        "melbank_collection",
        "wled_preferences",
        "core",
    }

    async def get(self, request: web.Request) -> web.Response:
        """
        Get ledfx schemas.
        You may ask for a specific schema/schemas in the request body
        eg. "audio" will return audio schema
        eg. ["audio", "melbanks"] will return audio and melbanks schema
        """
        schemas = set()
        response = {}

        if request.can_read_body:
            try:
                wanted_schemas = await request.json()
            except JSONDecodeError:
                return await self.json_decode_error()

            if isinstance(wanted_schemas, list):
                schemas.update(wanted_schemas)
            elif isinstance(wanted_schemas, str):
                schemas.add(wanted_schemas)

            schemas = schemas & self.VALID_SCHEMAS

        # if no schemas left after filtering, or none requested, send them all
        if not schemas:
            schemas = self.VALID_SCHEMAS

        for schema in schemas:
            if schema == "devices":
                response["devices"] = {}
                # Generate all the device schema
                for (
                    device_type,
                    device,
                ) in self._ledfx.devices.classes().items():
                    response["devices"][device_type] = {
                        "schema": legacy_schema(device.config_model()),
                        "id": device_type,
                    }

            elif schema == "effects":
                response["effects"] = {}
                # Generate all the effect schema
                for (
                    effect_type,
                    effect,
                ) in self._ledfx.effects.classes().items():
                    response["effects"][effect_type] = {
                        "schema": legacy_schema(effect.config_model()),
                        "id": effect_type,
                        "name": effect.NAME,
                        "category": effect.CATEGORY,
                        "uses_melbank_range": effect.USES_MELBANK_RANGE,
                    }

                    if effect.HIDDEN_KEYS:
                        response["effects"][effect_type]["hidden_keys"] = (
                            effect.HIDDEN_KEYS
                        )
                    if effect.ADVANCED_KEYS:
                        response["effects"][effect_type]["advanced_keys"] = (
                            effect.ADVANCED_KEYS
                        )
                    if effect.PERMITTED_KEYS:
                        response["effects"][effect_type]["permitted_keys"] = (
                            effect.PERMITTED_KEYS
                        )

            elif schema == "integrations":
                # Generate all the integrations schema
                response["integrations"] = {}
                for (
                    integration_type,
                    integration,
                ) in self._ledfx.integrations.classes().items():
                    response["integrations"][integration_type] = {
                        "schema": legacy_schema(integration.config_model()),
                        "id": integration_type,
                        "name": integration.NAME,
                        "description": integration.DESCRIPTION,
                        "beta": integration.beta,
                    }

            elif schema == "virtuals":
                response["virtuals"] = {"schema": legacy_schema(VirtualConfig)}

            elif schema == "audio":
                audio_input_schema = legacy_schema(AudioInputConfig)
                audio_analysis_schema = legacy_schema(AudioAnalysisConfig)
                merged_schema = {**audio_input_schema, **audio_analysis_schema}
                for key in audio_input_schema.keys() & audio_analysis_schema.keys():
                    if isinstance(audio_input_schema[key], dict) and isinstance(
                        audio_analysis_schema[key], dict
                    ):
                        merged_schema[key] = {
                            **audio_input_schema[key],
                            **audio_analysis_schema[key],
                        }
                response["audio"] = {
                    "schema": {
                        **merged_schema,
                        "permitted_keys": PERMITTED_KEYS["audio"],
                    }
                }
            elif schema == "melbanks":
                response["melbanks"] = {
                    "schema": {
                        **legacy_schema(MelbanksConfig),
                        "permitted_keys": PERMITTED_KEYS["melbanks"],
                    }
                }
            elif schema == "melbank_collection":
                response["melbank_collection"] = {
                    "schema": {
                        **legacy_schema(MelbankConfig),
                        "permitted_keys": PERMITTED_KEYS["melbank_collection"],
                    }
                }
            elif schema == "wled_preferences":
                response["wled_preferences"] = {
                    "schema": {
                        **legacy_schema(WledPreferences),
                        "permitted_keys": PERMITTED_KEYS["wled_preferences"],
                    }
                }

            elif schema == "core":
                response["core"] = {
                    "schema": {
                        **legacy_schema(
                            LedFxConfig,
                            order=LEGACY_CORE_ORDER,
                            extra_properties=LEGACY_CORE_EXTRAS,
                        ),
                        "permitted_keys": PERMITTED_KEYS["core"],
                    },
                }

        return web.json_response(data=response, status=200, dumps=dumps)
