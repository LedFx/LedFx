import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import PERMITTED_KEYS, convertToJsonSchema
from ledfx.config import CORE_CONFIG_SCHEMA, WLED_CONFIG_SCHEMA
from ledfx.effects.audio import AudioAnalysisSource, AudioInputSource
from ledfx.effects.melbank import Melbank, Melbanks

_LOGGER = logging.getLogger(__name__)


class SchemaEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/schema"

    VALID_SCHEMAS = {
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
                        "schema": convertToJsonSchema(device.schema()),
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
                        "schema": convertToJsonSchema(effect.schema()),
                        "id": effect_type,
                        "name": effect.NAME,
                        "category": effect.CATEGORY,
                    }

                    if effect.HIDDEN_KEYS:
                        response["effects"][effect_type][
                            "hidden_keys"
                        ] = effect.HIDDEN_KEYS
                    if effect.ADVANCED_KEYS:
                        response["effects"][effect_type][
                            "advanced_keys"
                        ] = effect.ADVANCED_KEYS
                    if effect.PERMITTED_KEYS:
                        response["effects"][effect_type][
                            "permitted_keys"
                        ] = effect.PERMITTED_KEYS

            elif schema == "integrations":
                # Generate all the integrations schema
                response["integrations"] = {}
                for (
                    integration_type,
                    integration,
                ) in self._ledfx.integrations.classes().items():
                    response["integrations"][integration_type] = {
                        "schema": convertToJsonSchema(integration.schema()),
                        "id": integration_type,
                        "name": integration.NAME,
                        "description": integration.DESCRIPTION,
                        "beta": integration.beta,
                    }

            elif schema == "virtuals":
                # Get virtuals schema
                response["virtuals"] = {
                    "schema": convertToJsonSchema(
                        self._ledfx.virtuals.schema()
                    ),
                }

            elif schema == "audio":
                # Get audio schema
                audio_input_schema = convertToJsonSchema(
                    AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
                )
                audio_analysis_schema = convertToJsonSchema(
                    AudioAnalysisSource.CONFIG_SCHEMA
                )
                # drop the tempo method from the audio input schema
                # TODO: figure out a better way to handle this in the frontend
                # permitted_keys isn't working
                del audio_analysis_schema["properties"]["tempo_method"]
                merged_schema = {**audio_input_schema, **audio_analysis_schema}

                for key in (
                    audio_input_schema.keys() & audio_analysis_schema.keys()
                ):
                    if isinstance(
                        audio_input_schema[key], dict
                    ) and isinstance(audio_analysis_schema[key], dict):
                        merged_schema[key] = {
                            **audio_input_schema[key],
                            **audio_analysis_schema[key],
                        }

                response["audio"] = {
                    "schema": {
                        **merged_schema,
                        **{"permitted_keys": PERMITTED_KEYS["audio"]},
                    }
                }
            elif schema == "melbanks":
                # Get melbanks schema
                response["melbanks"] = {
                    "schema": {
                        **convertToJsonSchema(
                            Melbanks.CONFIG_SCHEMA,
                        ),
                        **{"permitted_keys": PERMITTED_KEYS["melbanks"]},
                    },
                }
            elif schema == "melbank_collection":
                # Get melbank collection schema
                response["melbank_collection"] = {
                    "schema": {
                        **convertToJsonSchema(Melbank.CONFIG_SCHEMA),
                        **{
                            "permitted_keys": PERMITTED_KEYS[
                                "melbank_collection"
                            ]
                        },
                    },
                }
            elif schema == "wled_preferences":
                # Get wled schema
                response["wled_preferences"] = {
                    "schema": {
                        **convertToJsonSchema(WLED_CONFIG_SCHEMA),
                        **{
                            "permitted_keys": PERMITTED_KEYS[
                                "wled_preferences"
                            ]
                        },
                    },
                }

            elif schema == "core":
                # Get core config schema
                response["core"] = {
                    "schema": {
                        **convertToJsonSchema(CORE_CONFIG_SCHEMA),
                        **{"permitted_keys": PERMITTED_KEYS["core"]},
                    },
                }

        return web.json_response(data=response, status=200)
