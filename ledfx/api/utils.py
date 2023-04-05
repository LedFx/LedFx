"""Module to convert voluptuous schemas to dictionaries."""
import collections

import voluptuous as vol

from ledfx.config import _default_wled_settings
from ledfx.effects.audio import AudioInputSource
from ledfx.utils import AVAILABLE_FPS, generate_title

TYPES_MAP = {
    int: "integer",
    str: "string",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "dict",
}

PERMITTED_KEYS = {
    "audio": ("min_volume", "audio_device", "delay_ms"),
    "melbanks": (
        "max_frequencies",
        "min_frequency",
    ),
    "wled_preferences": tuple(_default_wled_settings.keys()),
    "core": (
        "host",
        "port",
        "port_s",
        "dev_mode",
        "scan_on_startup",
        "create_segments",
        "visualisation_fps",
        "visualisation_maxlen",
        "global_transitions",
        "global_brightness",
    ),
}


def createRegistrySchema(registry):
    """Create a JSON Schema for an entire registry."""

    class_schema_list = []
    for class_type, class_obj in registry.classes().items():
        obj_schema = convertToJsonSchema(class_obj.schema())
        obj_schema["properties"]["registry_type"] = {"enum": [class_type]}
        class_schema_list.append(obj_schema)

    return {
        "type": "object",
        "properties": {
            "registry_type": {
                "title": "Registry Type",
                "type": "string",
                "enum": list(registry.classes().keys()),
            }
        },
        "required": ["registry_type"],
        "dependencies": {"registry_type": {"oneOf": class_schema_list}},
    }


def convertToJsonSchema(schema):
    """
    Converts a voluptuous schema to a JSON schema compatible
    with the schema REST API. This should be kept in line with
    the frontends "SchemaForm" component.
    """
    if isinstance(schema, vol.Schema):
        schema = schema.schema

    if isinstance(schema, collections.abc.Mapping):
        val = {"properties": {}}
        required_vals = []

        for key, value in schema.items():
            description = None
            if isinstance(key, vol.Marker):
                pkey = key.schema
                description = key.description
            else:
                pkey = key

            pval = convertToJsonSchema(value)
            pval["title"] = generate_title(pkey)
            if description is not None:
                pval["description"] = description

            if key.default is not vol.UNDEFINED:
                pval["default"] = key.default()

            if isinstance(key, vol.Required):
                required_vals.append(pkey)

            val["properties"][pkey] = pval

        if required_vals:
            val["required"] = required_vals

        return val

    if (
        callable(schema)
        and getattr(schema, "__name__", None) == "fps_validator"
    ):
        return {"type": "int", "enum": list(AVAILABLE_FPS)}

    elif (
        callable(schema)
        and getattr(schema, "__name__", None) == "device_index_validator"
    ):
        return {"type": "string", "enum": AudioInputSource.input_devices()}

    elif (
        callable(schema)
        and getattr(schema, "__name__", None) == "validate_color"
    ):
        return {"type": "color", "gradient": False}

    elif (
        callable(schema)
        and getattr(schema, "__name__", None) == "validate_gradient"
    ):
        return {"type": "color", "gradient": True}

    elif isinstance(schema, vol.All):
        val = {}
        for validator in schema.validators:
            val.update(convertToJsonSchema(validator))
        return val

    elif isinstance(schema, vol.Length):
        val = {}
        if schema.min is not None:
            val["minLength"] = schema.min
        if schema.max is not None:
            val["maxLength"] = schema.max
        return val

    elif isinstance(schema, (vol.Clamp, vol.Range)):
        val = {}
        if schema.min is not None:
            val["minimum"] = schema.min
        if schema.max is not None:
            val["maximum"] = schema.max
        return val

    elif isinstance(schema, vol.Datetime):
        return {
            "type": "datetime",
            "format": schema.format,
        }

    elif isinstance(schema, vol.In):
        if isinstance(schema.container, dict):
            return {"type": "string", "enum": dict(schema.container)}
        else:
            return {"type": "string", "enum": list(schema.container)}
        # val = {'type': 'string', 'enum': dict()}
        # for item in schema.container:
        #     val['enum'][item] = item
        # return val

    elif isinstance(schema, vol.Coerce):
        schema = schema.type

    elif isinstance(schema, list):
        val = {
            "type": "list",
            "validators": list(
                convertToJsonSchema(validator) for validator in schema
            ),
        }
        return val

    if schema in TYPES_MAP:
        return {"type": TYPES_MAP[schema]}

    raise ValueError(f"Unable to convert schema: {schema}")
