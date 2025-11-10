# Name: TypeScript Generator
# Description: Generates TypeScript interfaces dynamically from voluptuous schemas in LedFx.
# Author: YeonV

import logging
import traceback
from typing import Any, Callable

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

# --- Helper Functions ---


def get_class_name_for_ts(name_parts):
    """Helper to create a PascalCase TS interface name from snake_case or other parts."""
    if isinstance(name_parts, str):
        name_parts = name_parts.replace("-", "_").split("_")
    valid_parts = [part for part in name_parts if part]
    if not valid_parts:
        return "UnknownSchema"
    return "".join(part.capitalize() for part in valid_parts)


# Forward declaration for recursive type hint
ForwardRefVoluptuousValidatorToTsType = Callable[[Any, bool], str]


def generate_inline_interface_body(
    schema_dict: dict,
    type_converter: ForwardRefVoluptuousValidatorToTsType,
    indent_level: int = 1,
) -> str:
    """Generates the body (properties) of an inline interface."""
    indent = "  " * (indent_level + 1)
    body_parts = []
    processed_keys = set()

    if not isinstance(schema_dict, dict):
        _LOGGER.warning(
            f"generate_inline_interface_body expected dict, got {type(schema_dict)}"
        )
        return f"{indent}// Error: Expected dict for inline schema\n{indent}[key: string]: any;"

    for key_marker, validator in schema_dict.items():
        default_value = None
        key_schema_obj = key_marker
        original_key_marker = key_marker
        if isinstance(key_marker, (vol.Required, vol.Optional)):
            key_schema_obj = key_marker.schema
            if (
                isinstance(key_marker, vol.Optional)
                and key_marker.default is not vol.UNDEFINED
            ):
                default_value = key_marker.default
        key_name_str = str(key_schema_obj)
        if key_name_str in processed_keys:
            continue
        processed_keys.add(key_name_str)
        # Generate type recursively, use for_universal=False for inline specifics
        ts_type_str = type_converter(validator, for_universal=False)

        js_doc_parts = []
        if (
            hasattr(original_key_marker, "description")
            and original_key_marker.description
        ):
            desc_lines = (
                str(original_key_marker.description).strip().split("\n")
            )
            js_doc_parts.extend([f"* {line.strip()}" for line in desc_lines])
        if default_value is not None:
            default_str = (
                f"'{default_value}'"
                if isinstance(default_value, str)
                else str(default_value)
            )
            if "<function default_factory" not in default_str:
                js_doc_parts.append(f"* @default {default_str}")
            else:
                js_doc_parts.append("* @default (computed)")
        constraints_doc = []
        constraint_validators = (
            validator.validators
            if isinstance(validator, vol.All)
            else [validator]
        )
        for sub_validator in constraint_validators:
            if isinstance(sub_validator, vol.Range):
                if sub_validator.min is not None:
                    constraints_doc.append(f"@minimum {sub_validator.min}")
                if sub_validator.max is not None:
                    constraints_doc.append(f"@maximum {sub_validator.max}")
            if isinstance(sub_validator, vol.Length):
                if sub_validator.min is not None:
                    constraints_doc.append(f"@minLength {sub_validator.min}")
                if sub_validator.max is not None:
                    constraints_doc.append(f"@maxLength {sub_validator.max}")
        if constraints_doc:
            js_doc_parts.extend([f"* {doc}" for doc in constraints_doc])

        ts_property_name = key_name_str  # Use snake_case
        is_optional_char = (
            "?" if isinstance(original_key_marker, vol.Optional) else ""
        )
        js_doc_string = ""
        if js_doc_parts:
            js_doc_string = (
                indent
                + "/**\n"
                + "\n".join([indent + f" {part}" for part in js_doc_parts])
                + "\n"
                + indent
                + " */\n"
            )

        body_parts.append(
            f"{js_doc_string}{indent}{ts_property_name}{is_optional_char}: {ts_type_str};"
        )

    return "\n".join(body_parts)


def voluptuous_validator_to_ts_type(validator, for_universal=False) -> str:
    """Converts voluptuous validator to TS type string."""
    # Custom Validators first
    if hasattr(validator, "__name__"):
        validator_name = validator.__name__
        if validator_name == "validate_color":
            return "string /* Color */"
        if validator_name == "validate_gradient":
            return "string /* Gradient */"
        if validator_name == "fps_validator":
            return "number /* FPS */"

    # Standard Types
    if validator is str:
        return "string"
    elif validator is int:
        return "number"
    elif validator is float:
        return "number"
    elif validator is bool:
        return "boolean"
    elif isinstance(validator, vol.Coerce):
        if validator.type is int:
            return "number"
        if validator.type is float:
            return "number"
        if validator.type is str:
            return "string"
        return "any"
    elif isinstance(validator, vol.In):
        if for_universal:
            possible_types = []
            if any(isinstance(opt, str) for opt in validator.container):
                possible_types.append("string")
            if any(
                isinstance(opt, (int, float)) for opt in validator.container
            ):
                possible_types.append("number")
            if any(isinstance(opt, bool) for opt in validator.container):
                possible_types.append("boolean")
            return " | ".join(possible_types) if possible_types else "any"
        else:
            opts_str = [
                (
                    '"{}"'.format(opt.replace('"', '\\"'))
                    if isinstance(opt, str)
                    else (
                        str(opt).lower() if isinstance(opt, bool) else str(opt)
                    )
                )
                for opt in validator.container
            ]
            return " | ".join(opts_str) if opts_str else "never"

    elif isinstance(validator, vol.All):
        primary_ts_type = "any"
        priority_validators = [
            v
            for v in validator.validators
            if isinstance(v, vol.Schema)
            or v in (str, int, float, bool)
            or isinstance(v, vol.Coerce)
        ]
        if priority_validators:
            primary_ts_type = voluptuous_validator_to_ts_type(
                priority_validators[-1], for_universal
            )
        else:
            for sub_validator in validator.validators:
                if not isinstance(sub_validator, (vol.Range, vol.Length)):
                    primary_ts_type = voluptuous_validator_to_ts_type(
                        sub_validator, for_universal
                    )
                    break
        if primary_ts_type == "any" and validator.validators:
            _LOGGER.debug(
                f"Could not determine primary type in vol.All: {validator}."
            )
        return primary_ts_type

    elif isinstance(validator, vol.Schema):
        # --- Handle Nested Schemas ---
        if isinstance(validator.schema, dict):
            # Generate inline object type recursively
            inline_body = generate_inline_interface_body(
                validator.schema,
                voluptuous_validator_to_ts_type,
                indent_level=1,
            )
            return f"{{\n{inline_body}\n  }}"  # Returns an inline object literal type
        elif isinstance(validator.schema, list):
            # Handle arrays
            if validator.schema:
                item_validator = validator.schema[0]
                # Check if this is a reference to a named schema (like PlaylistItem)
                if hasattr(
                    item_validator, "__name__"
                ) and item_validator.__name__.endswith("Item"):
                    # Generate interface name from the schema class name
                    item_type_name = item_validator.__name__
                    if item_type_name and not item_type_name[0].isupper():
                        item_type_name = get_class_name_for_ts(item_type_name)
                    return f"{item_type_name}[]"
                else:
                    item_type = voluptuous_validator_to_ts_type(
                        item_validator, for_universal
                    )
                    return f"{item_type}[]"
            return "any[]"
        else:
            _LOGGER.warning(
                f"Unhandled vol.Schema type: {type(validator.schema)}. Defaulting 'any'."
            )
            return "any"
    elif isinstance(validator, list):
        # Handle direct list validators like [PlaylistItem]
        if validator:
            item_validator = validator[0]
            # Special case: check if this looks like PlaylistItem schema
            if (
                isinstance(item_validator, vol.Schema)
                and isinstance(item_validator.schema, dict)
                and "scene_id" in str(item_validator.schema)
            ):
                return "PlaylistItem[]"
            # Check if the item is a schema reference or a direct schema
            elif hasattr(
                item_validator, "__name__"
            ) and item_validator.__name__.endswith("Item"):
                # This is likely a reference to a schema class like PlaylistItem
                # Generate the corresponding TypeScript interface name
                item_type_name = item_validator.__name__
                if item_type_name and not item_type_name[0].isupper():
                    item_type_name = get_class_name_for_ts(item_type_name)

                return f"{item_type_name}[]"
            else:
                # Handle as a normal validator
                item_type = voluptuous_validator_to_ts_type(
                    item_validator, for_universal
                )
                return f"{item_type}[]"
        return "any[]"

    elif isinstance(validator, (vol.Range, vol.Length)):
        return "any"
    elif callable(validator):
        _LOGGER.warning(
            f"Unsupported function validator: {getattr(validator, '__name__', 'func')}. Defaulting 'any'."
        )
        return "any"
    else:
        _LOGGER.warning(
            f"Unsupported voluptuous validator type: {type(validator)}. Defaulting 'any'."
        )
        return "any"


def generate_ts_interface_from_voluptuous(
    schema_name: str,
    voluptuous_schema: vol.Schema,
    extends_interface: str = None,
    base_schema_keys: set = None,
) -> str:
    """Generates TS interface string, using snake_case properties."""
    base_schema_keys = (
        base_schema_keys if base_schema_keys is not None else set()
    )
    extends_clause = (
        f" extends {extends_interface}" if extends_interface else ""
    )
    interface_parts = [f"export interface {schema_name}{extends_clause} {{"]
    if not isinstance(voluptuous_schema.schema, dict):
        _LOGGER.error(f"Schema not dict for {schema_name}")
        interface_parts.extend(
            ["  [key: string]: any; // Error: Schema not dict", "}"]
        )
        return "\n".join(interface_parts)
    processed_keys = set()
    for key_marker, validator in voluptuous_schema.schema.items():
        is_optional = isinstance(key_marker, vol.Optional)
        key_schema_obj = (
            key_marker.schema
            if isinstance(key_marker, (vol.Required, vol.Optional))
            else key_marker
        )
        key_name_str = str(key_schema_obj)

        if key_name_str in processed_keys:
            continue
        processed_keys.add(key_name_str)
        if base_schema_keys and key_name_str in base_schema_keys:
            continue

        ts_type_str = voluptuous_validator_to_ts_type(
            validator, for_universal=False
        )
        js_doc_parts = []

        # --- Description ---
        if hasattr(key_marker, "description") and key_marker.description:
            desc_lines = str(key_marker.description).strip().split("\n")
            js_doc_parts.extend([f"* {line.strip()}" for line in desc_lines])

        # --- Default Value Handling (Revised Logic) ---
        if is_optional and hasattr(key_marker, "default"):
            default_value_attr = key_marker.default
            if default_value_attr is not vol.UNDEFINED:
                # Assume it's the value or a factory we might need to call
                actual_default = default_value_attr
                is_computed = False
                if callable(default_value_attr):
                    try:
                        potential_value = default_value_attr()
                        if (
                            not callable(potential_value)
                            and potential_value is not default_value_attr
                        ):
                            actual_default = potential_value
                        else:
                            is_computed = True
                    except Exception:
                        is_computed = True

                if is_computed:
                    js_doc_parts.append("* @default (computed)")
                else:
                    # Format the literal default value
                    default_str_val = (
                        f"'{actual_default}'"
                        if isinstance(actual_default, str)
                        else str(actual_default)
                    )
                    js_doc_parts.append(f"* @default {default_str_val}")
            # else: No default specified (it was vol.UNDEFINED)
        # --- End Default Handling ---

        # --- Constraints ---
        constraints_doc = []
        constraint_validators = (
            validator.validators
            if isinstance(validator, vol.All)
            else [validator]
        )
        for sub_validator in constraint_validators:
            if isinstance(sub_validator, vol.Range):
                if sub_validator.min is not None:
                    constraints_doc.append(f"@minimum {sub_validator.min}")
                if sub_validator.max is not None:
                    constraints_doc.append(f"@maximum {sub_validator.max}")
            if isinstance(sub_validator, vol.Length):
                if sub_validator.min is not None:
                    constraints_doc.append(f"@minLength {sub_validator.min}")
                if sub_validator.max is not None:
                    constraints_doc.append(f"@maxLength {sub_validator.max}")
        if constraints_doc:
            js_doc_parts.extend([f"* {doc}" for doc in constraints_doc])

        # --- Assemble ---
        ts_property_name = key_name_str
        is_optional_char = "?" if is_optional else ""
        js_doc_string = ""
        if js_doc_parts:
            js_doc_string = (
                "  /**\n"
                + "\n".join([f"   {part}" for part in js_doc_parts])
                + "\n   */\n"
            )
        interface_parts.append(
            f"{js_doc_string}  {ts_property_name}{is_optional_char}: {ts_type_str};"
        )

    interface_parts.append("}")
    return "\n".join(interface_parts)


def generate_specific_api_response_types(
    virtual_config_type_name: str,
    specific_effect_config_union_name: str,
    specific_device_config_union_name: str,
    effect_type_literal_union: str,
    device_type_literal_union: str,
) -> str:
    """Generates TS definitions for API responses."""
    segment_type_alias = """
/**
* Literal union of all known effect type strings
* @category Types
*/
export type Segment = [
  device: string,
  start: number,
  end: number,
  reverse: boolean
];"""
    active_effect_type_str = f"""
/**
 * Represents the active effect details within a virtual's API response.
 * Uses the specific effect config discriminated union.
 * @category Specific
 */
export interface EffectSpecific {{
  config: {specific_effect_config_union_name};
  name: string;
  type: {effect_type_literal_union};
}}"""
    active_effect_type_str += f"""
/**
 * Convenience type for effect details using the universal EffectConfig.
 * @category General
 */
export interface Effect {{
  config: EffectConfig | null;
  name: string;
  type: {effect_type_literal_union} | null;
}}"""
    virtual_api_item_type_str = "/**\n * Convenience type for the API response containing multiple Virtual objects.\n * @category Specific\n */\n"
    virtual_api_item_type_str += f"\n export interface VirtualSpecific {{\n  config: {virtual_config_type_name};\n  id: string;\n  is_device: string | boolean; \n  auto_generated: boolean;\n  segments: Segment[];\n  pixel_count: number;\n  active: boolean;\n  streaming: boolean;\n  last_effect?: {effect_type_literal_union} | null;\n  effect: Partial<EffectSpecific>; \n}}\n"
    virtual_api_item_type_str += "/**\n * Convenience type for a Virtual object using the universal Effect type.\n * @category General\n */\n"
    virtual_api_item_type_str += f"\n export interface Virtual {{\n  config: {virtual_config_type_name};\n  id: string;\n  is_device: string | boolean; \n  auto_generated: boolean;\n  segments: Segment[];\n  pixel_count: number;\n  active: boolean;\n  streaming: boolean;\n  last_effect?: EffectType | null;\n  effect: Effect; \n}}"  # Changed segments type
    get_virtuals_response_type_str = (
        "/**\n * Response for GET /api/virtuals.\n * @category REST\n */\n"
    )
    get_virtuals_response_type_str += '\n export interface GetVirtualsApiResponse {\n  status: "success" | "error";\n  virtuals: Record<string, VirtualSpecific>;\n  paused: boolean;\n  message?: string;\n}'
    get_single_virtual_response_type_str = "/**\n * Raw response for GET /api/virtuals/{{virtual_id}}.\n * @category REST\n */\n"
    get_single_virtual_response_type_str += '\n export interface GetSingleVirtualApiResponse {\n  status: "success" | "error";\n  [virtualId: string]: VirtualSpecific | string | undefined; \n  message?: string;\n}\n\n'
    get_single_virtual_response_type_str += "/**\n * Transformed type for GET /api/virtuals/{virtual_id}.\n * @category REST\n */\n"
    get_single_virtual_response_type_str += '\n export type FetchedVirtualResult = \n  | { status: "success"; data: VirtualSpecific }\n  | { status: "error"; message: string };\n'
    device_api_item_type_str = "/**\n * Represents a single Device object using specific config types.\n * @category Specific\n */\n"
    device_api_item_type_str += f"export interface DeviceSpecific {{\n  config: {specific_device_config_union_name};\n  id: string;\n  type: {device_type_literal_union};\n  online: boolean;\n  virtuals: string[]; \n  active_virtuals: string[]; \n}}"
    device_universal_type_str = "/**\n * Convenience type for a Device object using the universal DeviceConfig.\n * @category General\n */\n"
    device_universal_type_str += f"export interface Device {{\n  config: DeviceConfig;\n  id: string;\n  type: {device_type_literal_union};\n  online: boolean;\n  virtuals: string[]; \n  active_virtuals: string[]; \n}}"
    get_devices_response_type_str = "/**\n * Response for GET /api/devices using specific config types.\n * @category REST\n */\n"
    get_devices_response_type_str += '\n export interface GetDevicesApiResponse {\n  status: "success" | "error";\n  devices: Record<string, DeviceSpecific>;\n  message?: string;\n}'

    return (
        f"{segment_type_alias}\n\n{active_effect_type_str}\n\n{virtual_api_item_type_str}\n\n"
        f"{get_virtuals_response_type_str}\n\n{get_single_virtual_response_type_str}\n\n"
        f"{device_api_item_type_str}\n\n{get_devices_response_type_str}\n\n{device_universal_type_str}\n\n"
    )


# --- Main Generation Function ---
def generate_typescript_types() -> str:
    # --- Access Registries ---
    device_registry = {}
    effect_registry = {}
    try:
        _LOGGER.info("Attempting to access registries via class methods...")
        from ledfx.devices import Device
        from ledfx.effects import Effect
        from ledfx.virtuals import Virtual

        _LOGGER.info(
            "Imported managers to potentially trigger registry loading."
        )
        if hasattr(Device, "registry") and callable(Device.registry):
            device_registry = Device.registry()
            _LOGGER.info(
                f"Accessed device registry: {len(device_registry)} types."
            )
        else:
            _LOGGER.error("Could not find/call Device.registry().")
        if hasattr(Effect, "registry") and callable(Effect.registry):
            effect_registry = Effect.registry()
            _LOGGER.info(
                f"Accessed effect registry: {len(effect_registry)} types."
            )
        else:
            _LOGGER.error("Could not find/call Effect.registry().")
    except Exception:
        _LOGGER.exception("Failed imports/registry access.")
        return "// Error accessing registries. Please check the server logs for more details."
    if not device_registry:
        _LOGGER.warning("Device registry empty!")
    if not effect_registry:
        _LOGGER.warning("Effect registry empty!")

    output_ts_string = "/**\n * Type: AUTO-GENERATED FILE\n * Tool: LedFx TypeScript Generator\n * Author: YeonV\n */\n\n/* eslint-disable */\n\n"

    # --- 0. Generate Base Device Config ---
    base_device_config_interface_name = "BaseDeviceConfig"
    base_device_schema_object = None
    base_schema_keys = set()
    output_ts_string += "// --- Base Device Schema Generation --- \n"
    try:
        _LOGGER.info("Manually defining Base Device Schema based on source...")

        # Replicate the schema definition from ledfx/devices/__init__.py
        # Need to import fps_validator or handle it
        from ledfx.devices import (
            fps_validator,  # Import the validator if needed
        )

        base_schema_dict_def = {
            vol.Required(
                "name", description="Friendly name for the device"
            ): str,
            vol.Optional(
                "icon_name",
                description="https://material-ui.com/components/material-icons/",
                default="mdi:led-strip",
            ): str,
            vol.Optional(
                "center_offset",
                description="Number of pixels from the perceived center of the device",
                default=0,
            ): int,
            vol.Optional(
                "refresh_rate",
                description="Target rate that pixels are sent to the device",
                default=60,  # Use a static default, can't easily call the next() logic here
            ): fps_validator,  # Use the imported validator
        }
        base_device_schema_object = vol.Schema(base_schema_dict_def)

        # Now process this manually created schema object
        if isinstance(base_device_schema_object.schema, dict):
            base_schema_dict = base_device_schema_object.schema
            _LOGGER.info("Base schema dict created. Extracting keys...")
            for k in base_schema_dict.keys():
                key_name = str(
                    k.schema
                    if isinstance(k, (vol.Required, vol.Optional))
                    else k
                )
                base_schema_keys.add(key_name)
            _LOGGER.info(f"Base schema keys: {base_schema_keys}")
            output_ts_string += "/**\n * Base configuration shared by all devices\n * @category DeviceSpecificConfigs\n */\n"
            output_ts_string += generate_ts_interface_from_voluptuous(
                base_device_config_interface_name, base_device_schema_object
            )
            output_ts_string += "\n\n"
            _LOGGER.info(
                f"Successfully generated {base_device_config_interface_name}"
            )
        else:
            _LOGGER.error(
                "Manually created base schema's '.schema' attribute is not dict?"
            )
            base_device_schema_object = None
            base_device_config_interface_name = "Record<string, any>"
            output_ts_string += f"// Manual base schema dict failed\nexport type {base_device_config_interface_name} = Record<string, any>;\n\n"

    except Exception as e:
        _LOGGER.error(f"Error manually processing base Device schema: {e}")
        traceback.print_exc()
        base_device_config_interface_name = "Record<string, any>"
        output_ts_string += f"// Error manual base device schema\nexport type {base_device_config_interface_name} = Record<string, any>;\n\n"
        base_device_schema_object = None  # Ensure reset on error

    base_device_name_to_extend_final = (
        base_device_config_interface_name
        if base_device_schema_object
        else None
    )

    # --- 1. Generate Virtual Config ---
    virtual_config_interface_name = "VirtualConfig"
    try:
        if hasattr(Virtual, "CONFIG_SCHEMA") and isinstance(
            Virtual.CONFIG_SCHEMA, vol.Schema
        ):
            output_ts_string += "/**\n * Configuration for Virtual Strips/Segments\n * @category Configs\n */\n"
            output_ts_string += generate_ts_interface_from_voluptuous(
                virtual_config_interface_name, Virtual.CONFIG_SCHEMA
            )
            output_ts_string += "\n\n"
        else:
            _LOGGER.error("Virtual.CONFIG_SCHEMA not found/invalid.")
            output_ts_string += f"// Virtual config schema not found\nexport interface {virtual_config_interface_name} {{ [key: string]: any; }}\n\n"
    except Exception as e:
        _LOGGER.error(f"Failed VirtualConfig: {e}")
        output_ts_string += f"// Failed VirtualConfig\nexport interface {virtual_config_interface_name} {{ [key: string]: any; }}\n\n"

    # --- 2. Generate Specific Device Configs & DeviceType Union ---
    all_device_config_interface_names = []
    all_device_type_strings = sorted(device_registry.keys())
    _LOGGER.info(f"Generating TS for {len(device_registry)} device types...")
    for device_type_str in all_device_type_strings:
        device_class = device_registry[device_type_str]
        device_schema_to_use = getattr(device_class, "CONFIG_SCHEMA", None)
        if callable(device_schema_to_use) and not isinstance(
            device_schema_to_use, vol.Schema
        ):
            try:
                device_schema_to_use = device_schema_to_use()
            except Exception:
                device_schema_to_use = None
        if isinstance(device_schema_to_use, vol.Schema):
            device_config_ts_name = (
                f"{get_class_name_for_ts(device_type_str)}DeviceConfig"
            )
            all_device_config_interface_names.append(device_config_ts_name)
            try:
                output_ts_string += f"/**\n * Configuration for device type: {device_type_str}\n * @category DeviceSpecificConfigs\n */\n"
                output_ts_string += generate_ts_interface_from_voluptuous(
                    schema_name=device_config_ts_name,
                    voluptuous_schema=device_schema_to_use,
                    extends_interface=base_device_name_to_extend_final,
                    base_schema_keys=base_schema_keys,
                )
                output_ts_string += "\n\n"
            except Exception as e:
                _LOGGER.error(f"Failed gen TS Device '{device_type_str}': {e}")
                output_ts_string += f"// Failed gen for {device_config_ts_name}\nexport interface {device_config_ts_name} {{ [key: string]: any; }}\n\n"
        else:
            _LOGGER.warning(
                f"Device class {getattr(device_class, '__name__', 'UnknownClass')} type '{device_type_str}' has no valid CONFIG_SCHEMA. Skipping..."
            )

    device_type_literal_union = "string"
    if all_device_type_strings:
        device_type_literal_union = " | ".join(
            [f'"{dtype}"' for dtype in all_device_type_strings]
        )
    output_ts_string += "/**\n * Literal union of all known device type strings\n * @category Types\n */\n"
    output_ts_string += (
        f"export type DeviceType = {device_type_literal_union};\n\n"
    )
    output_ts_string += (
        "/**\n * Device specific configurations\n * @category Specific\n */\n"
    )
    device_config_union_name = "DeviceSpecificConfig"
    if all_device_config_interface_names:
        output_ts_string += f"export type {device_config_union_name} = {' | '.join(all_device_config_interface_names)};\n\n"
    else:
        _LOGGER.warning("No specific device config interfaces for union.")
        output_ts_string += f"export type {device_config_union_name} = {base_device_config_interface_name};\n\n"

    # --- 2.5 Collect ALL Device Properties for Universal Interface ---
    all_device_properties = {}  # prop_name -> basic_ts_type
    _LOGGER.info(
        f"Collecting properties from {len(device_registry)} device types for universal interface..."
    )

    # Include base schema properties first
    if base_device_schema_object and isinstance(
        base_device_schema_object.schema, dict
    ):
        for key_marker, validator in base_device_schema_object.schema.items():
            key_schema_obj = (
                key_marker.schema
                if isinstance(key_marker, (vol.Required, vol.Optional))
                else key_marker
            )
            key_name_str = str(key_schema_obj)
            ts_property_name = key_name_str
            basic_ts_type = voluptuous_validator_to_ts_type(
                validator, for_universal=True
            )
            all_device_properties[ts_property_name] = basic_ts_type

    # Add/overwrite with specific properties
    for device_type_str, device_class in device_registry.items():
        device_schema_to_use = getattr(device_class, "CONFIG_SCHEMA", None)
        if callable(device_schema_to_use) and not isinstance(
            device_schema_to_use, vol.Schema
        ):
            try:
                device_schema_to_use = device_schema_to_use()
            except Exception:
                device_schema_to_use = None

        if isinstance(device_schema_to_use, vol.Schema) and isinstance(
            device_schema_to_use.schema, dict
        ):
            for key_marker, validator in device_schema_to_use.schema.items():
                key_schema_obj = (
                    key_marker.schema
                    if isinstance(key_marker, (vol.Required, vol.Optional))
                    else key_marker
                )
                key_name_str = str(key_schema_obj)
                ts_property_name = key_name_str
                # Skip base keys already processed? Optional, overwriting is okay too.
                # if ts_property_name in base_schema_keys: continue

                basic_ts_type = voluptuous_validator_to_ts_type(
                    validator, for_universal=True
                )
                if ts_property_name in all_device_properties:
                    # Fix: Check against all_DEVICE_properties, not all_EFFECT_properties
                    if (
                        all_device_properties[ts_property_name]
                        != basic_ts_type
                        and all_device_properties[ts_property_name] != "any"
                        and basic_ts_type != "any"
                    ):
                        _LOGGER.debug(
                            f"Widening universal device type for '{ts_property_name}'."
                        )
                        all_device_properties[ts_property_name] = (
                            "any"  # Widen to any on conflict
                        )
                else:
                    all_device_properties[ts_property_name] = basic_ts_type

    # --- Generate Universal Device Config Interface ---
    universal_device_config_name = "DeviceConfig"  # Use simple name
    output_ts_string += "/**\n * Universal interface merging all possible *optional* device properties (using snake_case)\n * @category Configs\n */\n"
    output_ts_string += f"export interface {universal_device_config_name} {{\n"
    # Add 'type' property using the DeviceType union we generated
    output_ts_string += (
        "  type?: DeviceType; // Optional device type identifier\n"
    )

    for prop_name in sorted(all_device_properties.keys()):
        # Avoid adding 'type' again if it was somehow in a schema
        if prop_name == "type":
            continue
        ts_type = all_device_properties[prop_name]
        output_ts_string += (
            f"  {prop_name}?: {ts_type};\n"  # snake_case, optional
        )

    output_ts_string += "}\n\n"
    # --- 3. Generate SPECIFIC Effect Config Schemas & EffectType Union ---
    all_effect_config_interface_names = []
    all_effect_type_strings = sorted(effect_registry.keys())
    _LOGGER.info(
        f"Generating SPECIFIC TS for {len(effect_registry)} effect types..."
    )
    output_ts_string += (
        "// Specific Effect Configurations (for Discriminated Union)\n"
    )
    for effect_type_str in all_effect_type_strings:
        effect_class = effect_registry[effect_type_str]
        effect_schema_to_use = getattr(effect_class, "CONFIG_SCHEMA", None)
        if isinstance(effect_schema_to_use, vol.Schema):
            effect_config_ts_name = (
                f"{get_class_name_for_ts(effect_type_str)}EffectConfig"
            )
            all_effect_config_interface_names.append(effect_config_ts_name)
            try:
                interface_str = generate_ts_interface_from_voluptuous(
                    effect_config_ts_name, effect_schema_to_use
                )
                type_literal_line = f'  type: "{effect_type_str}";'
                lines = interface_str.splitlines()
                if len(lines) > 1:
                    lines.insert(1, type_literal_line)
                output_ts_string += f"/**\n * Specific configuration for the '{effect_type_str}' effect.\n * @category EffectSpecificConfigs\n */\n"
                output_ts_string += "\n".join(lines) + "\n\n"
            except Exception as e:
                _LOGGER.error(
                    f"Failed gen SPECIFIC TS Effect '{effect_type_str}': {e}"
                )
                output_ts_string += f'// Failed gen for {effect_config_ts_name}\nexport interface {effect_config_ts_name} {{ type: "{effect_type_str}"; [key: string]: any; }}\n\n'
        else:
            _LOGGER.warning(
                f"Effect class {getattr(effect_class, '__name__', 'UnknownClass')} type '{effect_type_str}' has no valid CONFIG_SCHEMA."
            )

    effect_type_literal_union = "string"
    if all_effect_type_strings:
        effect_type_literal_union = " | ".join(
            [f'"{etype}"' for etype in all_effect_type_strings]
        )
    output_ts_string += "/**\n * Literal union of all known effect type strings\n * @category Types\n */\n"
    output_ts_string += (
        f"export type EffectType = {effect_type_literal_union};\n\n"
    )
    output_ts_string += (
        "/**\n * Effect specific configurations\n * @category Specific\n */\n"
    )
    specific_effect_config_union_name = "EffectSpecificConfig"
    if all_effect_config_interface_names:
        output_ts_string += f"export type {specific_effect_config_union_name} = {' | '.join(all_effect_config_interface_names)};\n\n"
    else:
        fallback_effect_config_name = "BaseEffectConfig"
        output_ts_string += f"// Fallback Base Effect Config\nexport interface {fallback_effect_config_name} {{ type?: EffectType; [key: string]: any; }}\n\n"
        specific_effect_config_union_name = fallback_effect_config_name
        _LOGGER.warning(
            "No specific effect config interfaces for discriminated union."
        )

    # --- 4. Collect ALL Effect Properties for Universal Interface ---
    all_effect_properties = {}
    _LOGGER.info("Collecting properties for universal interface...")

    # First, collect properties from the base Effect class
    try:
        from ledfx.effects import Effect

        base_effect_schema = getattr(Effect, "CONFIG_SCHEMA", None)
        if isinstance(base_effect_schema, vol.Schema) and isinstance(
            base_effect_schema.schema, dict
        ):
            _LOGGER.info(
                "Adding base Effect class properties to universal interface..."
            )
            for key_marker, validator in base_effect_schema.schema.items():
                key_schema_obj = (
                    key_marker.schema
                    if isinstance(key_marker, (vol.Required, vol.Optional))
                    else key_marker
                )
                key_name_str = str(key_schema_obj)
                ts_property_name = key_name_str
                basic_ts_type = voluptuous_validator_to_ts_type(
                    validator, for_universal=True
                )
                all_effect_properties[ts_property_name] = basic_ts_type
                _LOGGER.debug(
                    f"Added base Effect property: {ts_property_name} -> {basic_ts_type}"
                )
    except Exception as e:
        _LOGGER.warning(f"Could not process base Effect schema: {e}")

    # Then collect properties from specific effect classes
    for effect_type_str, effect_class in effect_registry.items():
        effect_schema_to_use = getattr(effect_class, "CONFIG_SCHEMA", None)
        if isinstance(effect_schema_to_use, vol.Schema) and isinstance(
            effect_schema_to_use.schema, dict
        ):
            for key_marker, validator in effect_schema_to_use.schema.items():
                key_schema_obj = (
                    key_marker.schema
                    if isinstance(key_marker, (vol.Required, vol.Optional))
                    else key_marker
                )
                key_name_str = str(key_schema_obj)
                ts_property_name = key_name_str
                basic_ts_type = voluptuous_validator_to_ts_type(
                    validator, for_universal=True
                )
                if ts_property_name in all_effect_properties:
                    if (
                        all_effect_properties[ts_property_name]
                        != basic_ts_type
                        and all_effect_properties[ts_property_name] != "any"
                        and basic_ts_type != "any"
                    ):
                        _LOGGER.debug(
                            f"Widening universal type for '{ts_property_name}'."
                        )
                        all_effect_properties[ts_property_name] = "any"
                else:
                    all_effect_properties[ts_property_name] = basic_ts_type

    # --- 5. Generate Universal Effect Config Interface ---
    universal_effect_config_name = "EffectConfig"
    output_ts_string += "/**\n * Universal interface merging all possible *optional* effect properties.\n * Use this for convenience when strict type checking per effect is not required.\n * @category Configs\n */\n"
    output_ts_string += f"export interface {universal_effect_config_name} {{\n"
    output_ts_string += (
        "  type?: EffectType; // Use the literal union for the optional type\n"
    )
    for prop_name in sorted(all_effect_properties.keys()):
        ts_type = all_effect_properties[prop_name]
        output_ts_string += f"  {prop_name}?: {ts_type};\n"
    output_ts_string += "}\n\n"

    # --- 6. Generate API Response specific types ---
    virtual_config_name_to_use = (
        virtual_config_interface_name
        if "Virtual" in locals() and hasattr(Virtual, "CONFIG_SCHEMA")
        else "Record<string, any>"
    )
    device_union_name_to_use = (
        device_config_union_name
        if all_device_config_interface_names
        else base_device_config_interface_name
    )
    output_ts_string += (
        "// API Response Types using the SPECIFIC Effect Config Union\n"
    )
    output_ts_string += generate_specific_api_response_types(
        virtual_config_name_to_use,
        specific_effect_config_union_name,
        device_union_name_to_use,
        effect_type_literal_union,
        device_type_literal_union,
    )

    # --- 6.5. Generate Scene Config and API Response Types ---
    scene_config_interface_name = "SceneConfig"
    try:
        _LOGGER.info("Generating Scene config interface...")
        from ledfx.scenes import Scenes

        # Create a dummy Scenes instance to access the schema
        # We need to pass a minimal ledfx object with the required structure
        class DummyLedFx:
            def __init__(self):
                self.config = {"scenes": {}}
                self.virtuals = type(
                    "obj", (object,), {"get": lambda x: None}
                )()

        dummy_ledfx = DummyLedFx()
        scenes_instance = Scenes(dummy_ledfx)
        scene_schema = scenes_instance.SCENE_SCHEMA

        if isinstance(scene_schema, vol.Schema):
            output_ts_string += "// Scene Configuration\n"
            scene_interface = generate_ts_interface_from_voluptuous(
                scene_config_interface_name,
                scene_schema,
            )
            output_ts_string += f"{scene_interface}\n\n"
        else:
            _LOGGER.warning("Scene schema is not a voluptuous Schema")
            output_ts_string += f"// Fallback Scene Config\nexport interface {scene_config_interface_name} {{ name: string; [key: string]: any; }}\n\n"
    except Exception as e:
        _LOGGER.error(f"Failed to generate Scene config: {e}")
        output_ts_string += f"// Failed Scene Config\nexport interface {scene_config_interface_name} {{ name: string; [key: string]: any; }}\n\n"

    # --- 6.6. Generate Playlist Config and API Response Types ---
    playlist_config_interface_name = "PlaylistConfig"
    playlist_item_interface_name = "PlaylistItem"
    timing_jitter_interface_name = "TimingJitter"
    timing_interface_name = "PlaylistTiming"
    try:
        _LOGGER.info("Generating Playlist config interfaces...")
        from ledfx.playlists import (
            JitterSchema,
            PlaylistItem,
            PlaylistSchema,
            TimingSchema,
        )

        # Generate TimingJitter interface
        if isinstance(JitterSchema, vol.Schema):
            output_ts_string += "// Playlist Timing Jitter Configuration\n"
            timing_jitter_interface = generate_ts_interface_from_voluptuous(
                timing_jitter_interface_name,
                JitterSchema,
            )
            output_ts_string += f"{timing_jitter_interface}\n\n"
        else:
            _LOGGER.warning("JitterSchema is not a voluptuous Schema")
            output_ts_string += f"// Fallback Timing Jitter Config\nexport interface {timing_jitter_interface_name} {{ enabled?: boolean; factor_min?: number; factor_max?: number; }}\n\n"

        # Generate PlaylistTiming interface
        if isinstance(TimingSchema, vol.Schema):
            output_ts_string += "// Playlist Timing Configuration\n"
            timing_interface = generate_ts_interface_from_voluptuous(
                timing_interface_name,
                TimingSchema,
            )
            output_ts_string += f"{timing_interface}\n\n"
        else:
            _LOGGER.warning("TimingSchema is not a voluptuous Schema")
            output_ts_string += f"// Fallback Timing Config\nexport interface {timing_interface_name} {{ jitter?: {timing_jitter_interface_name}; }}\n\n"

        # Generate PlaylistItem interface
        if isinstance(PlaylistItem, vol.Schema):
            output_ts_string += "// Playlist Item Configuration\n"
            playlist_item_interface = generate_ts_interface_from_voluptuous(
                playlist_item_interface_name,
                PlaylistItem,
            )
            output_ts_string += f"{playlist_item_interface}\n\n"
        else:
            _LOGGER.warning("PlaylistItem is not a voluptuous Schema")
            output_ts_string += f"// Fallback Playlist Item Config\nexport interface {playlist_item_interface_name} {{ scene_id: string; duration_ms?: number; }}\n\n"

        # Generate main PlaylistConfig interface
        if isinstance(PlaylistSchema, vol.Schema):
            output_ts_string += "// Playlist Configuration\n"
            playlist_interface = generate_ts_interface_from_voluptuous(
                playlist_config_interface_name,
                PlaylistSchema,
            )
            output_ts_string += f"{playlist_interface}\n\n"
        else:
            _LOGGER.warning("PlaylistSchema is not a voluptuous Schema")
            output_ts_string += f"// Fallback Playlist Config\nexport interface {playlist_config_interface_name} {{ id: string; name: string; items: {playlist_item_interface_name}[]; [key: string]: any; }}\n\n"

    except Exception as e:
        _LOGGER.error(f"Failed to generate Playlist config: {e}")
        output_ts_string += f"// Failed Playlist Config\nexport interface {playlist_config_interface_name} {{ id: string; name: string; items: any[]; [key: string]: any; }}\n\n"

    # Generate Scene API Response Types
    output_ts_string += "// Scene API Response Types\n"
    output_ts_string += "/**\n * Represents the effect configuration stored in a scene for a virtual.\n * @category Scenes\n */\n"
    output_ts_string += "export interface SceneVirtualEffect {\n"
    output_ts_string += "  type?: EffectType;\n"
    output_ts_string += "  config?: EffectConfig;\n"
    output_ts_string += "}\n\n"

    output_ts_string += "/**\n * Represents a stored scene configuration with actual effect data.\n * This is the structure used in the API responses and storage.\n * @category Scenes\n */\n"
    output_ts_string += "export interface StoredSceneConfig {\n"
    output_ts_string += "  name: string;\n"
    output_ts_string += "  scene_image?: string;\n"
    output_ts_string += "  scene_tags?: string;\n"
    output_ts_string += "  scene_puturl?: string;\n"
    output_ts_string += "  scene_payload?: string;\n"
    output_ts_string += "  scene_midiactivate?: string;\n"
    output_ts_string += "  virtuals?: Record<string, SceneVirtualEffect>; // virtual_id -> effect config\n"
    output_ts_string += "}\n\n"

    output_ts_string += "/**\n * Represents a single Scene with its effect configurations.\n * @category Scenes\n */\n"
    output_ts_string += "export interface Scene {\n"
    output_ts_string += "  id: string;\n"
    output_ts_string += "  config: StoredSceneConfig;\n"
    output_ts_string += "}\n\n"

    output_ts_string += "/**\n * Stored scene plus runtime state that LedFx exposes via the API.\n * @category Scenes\n */\n"
    output_ts_string += (
        "export interface SceneState extends StoredSceneConfig {\n"
    )
    output_ts_string += "  active: boolean;\n"
    output_ts_string += "}\n\n"

    output_ts_string += (
        "/**\n * Response for GET /api/scenes.\n * @category REST\n */\n"
    )
    output_ts_string += "export interface GetScenesApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += "  scenes: Record<string, SceneState>;\n"
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    output_ts_string += "/**\n * Response for POST /api/scenes (scene creation).\n * @category REST\n */\n"
    output_ts_string += "export interface CreateSceneApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += "  scene?: Scene;\n"
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # --- 6.7. Generate Playlist API Response Types ---
    output_ts_string += "// Playlist API Response Types\n"

    # Playlist runtime state type
    output_ts_string += "/**\n * Runtime state of an active playlist (ephemeral data).\n * @category Playlists\n */\n"
    output_ts_string += "export interface PlaylistRuntimeState {\n"
    output_ts_string += "  active_playlist: string;\n"
    output_ts_string += "  index: number;\n"
    output_ts_string += "  order: number[];\n"
    output_ts_string += "  scenes: string[];\n"
    output_ts_string += "  scene_id: string;\n"
    output_ts_string += "  mode: 'sequence' | 'shuffle';\n"
    output_ts_string += "  paused: boolean;\n"
    output_ts_string += "  remaining_ms: number;\n"
    output_ts_string += "  effective_duration_ms: number;\n"
    output_ts_string += f"  timing: {timing_interface_name};\n"
    output_ts_string += "}\n\n"

    # Playlist object with proper typing
    output_ts_string += "/**\n * Represents a single Playlist with its configuration.\n * @category Playlists\n */\n"
    output_ts_string += "export interface Playlist {\n"
    output_ts_string += "  id: string;\n"
    output_ts_string += f"  config: {playlist_config_interface_name};\n"
    output_ts_string += "}\n\n"

    # GET /api/playlists response
    output_ts_string += (
        "/**\n * Response for GET /api/playlists.\n * @category REST\n */\n"
    )
    output_ts_string += "export interface GetPlaylistsApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += (
        f"  playlists: Record<string, {playlist_config_interface_name}>;\n"
    )
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # GET /api/playlists/{id} response
    output_ts_string += "/**\n * Response for GET /api/playlists/{id}.\n * @category REST\n */\n"
    output_ts_string += "export interface GetSinglePlaylistApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += (
        f"  data?: {{ playlist: {playlist_config_interface_name} }};\n"
    )
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # POST /api/playlists response (create/replace)
    output_ts_string += "/**\n * Response for POST /api/playlists (playlist creation/replacement).\n * @category REST\n */\n"
    output_ts_string += "export interface CreatePlaylistApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += (
        f"  data?: {{ playlist: {playlist_config_interface_name} }};\n"
    )
    output_ts_string += "  payload?: {\n"
    output_ts_string += '    type: "success" | "error";\n'
    output_ts_string += "    reason: string;\n"
    output_ts_string += "  };\n"
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # PUT /api/playlists control actions request types
    output_ts_string += "/**\n * Request body for playlist control actions via PUT /api/playlists.\n * @category REST\n */\n"
    output_ts_string += "export type PlaylistControlRequest = \n"
    output_ts_string += "  | {\n"
    output_ts_string += '      action: "start";\n'
    output_ts_string += "      id: string;\n"
    output_ts_string += "      mode?: 'sequence' | 'shuffle';\n"
    output_ts_string += f"      timing?: {timing_interface_name};\n"
    output_ts_string += "    }\n"
    output_ts_string += '  | { action: "stop" }\n'
    output_ts_string += '  | { action: "pause" }\n'
    output_ts_string += '  | { action: "resume" }\n'
    output_ts_string += '  | { action: "next" }\n'
    output_ts_string += '  | { action: "prev" }\n'
    output_ts_string += '  | { action: "state" };\n\n'

    # PUT /api/playlists control response
    output_ts_string += "/**\n * Response for PUT /api/playlists control actions.\n * @category REST\n */\n"
    output_ts_string += "export interface PlaylistControlApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += "  data?: { state: PlaylistRuntimeState };\n"
    output_ts_string += "  payload?: {\n"
    output_ts_string += '    type: "success" | "error";\n'
    output_ts_string += "    reason: string;\n"
    output_ts_string += "  };\n"
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # DELETE /api/playlists request/response
    output_ts_string += "/**\n * Request body for DELETE /api/playlists.\n * @category REST\n */\n"
    output_ts_string += "export interface DeletePlaylistRequest {\n"
    output_ts_string += "  id: string;\n"
    output_ts_string += "}\n\n"

    output_ts_string += (
        "/**\n * Response for DELETE /api/playlists.\n * @category REST\n */\n"
    )
    output_ts_string += "export interface DeletePlaylistApiResponse {\n"
    output_ts_string += '  status: "success" | "error";\n'
    output_ts_string += "  payload?: {\n"
    output_ts_string += '    type: "success" | "error";\n'
    output_ts_string += "    reason: string;\n"
    output_ts_string += "  };\n"
    output_ts_string += "  message?: string;\n"
    output_ts_string += "}\n\n"

    # Playlist events
    output_ts_string += "// Playlist Event Types\n"
    output_ts_string += (
        "/**\n * Base payload for playlist events.\n * @category Events\n */\n"
    )
    output_ts_string += "export interface PlaylistEventPayload {\n"
    output_ts_string += "  playlist_id: string;\n"
    output_ts_string += "  index?: number;\n"
    output_ts_string += "  scene_id?: string;\n"
    output_ts_string += "  effective_duration_ms?: number;\n"
    output_ts_string += "  remaining_ms?: number;\n"
    output_ts_string += "}\n\n"

    # --- 7. Generate Convenience Type Aliases ---

    output_ts_string += "// Convenience Type Aliases using Universal Configs\n"
    # Virtuals alias
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Virtual objects.\n * @category General\n */\n"
    output_ts_string += "export type Virtuals = Omit<GetVirtualsApiResponse, 'virtuals'> & { virtuals: Record<string, Virtual> };\n"
    # Devices alias (uses universal Device alias)
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Device objects.\n * @category General\n */\n"
    output_ts_string += "export type Devices = Omit<GetDevicesApiResponse, 'devices'> & { devices: Record<string, Device> };\n"
    # Scenes alias
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Scene objects.\n * @category General\n */\n"
    output_ts_string += "export type Scenes = GetScenesApiResponse;\n"
    # Playlists alias
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Playlist objects.\n * @category General\n */\n"
    output_ts_string += "export type Playlists = GetPlaylistsApiResponse;\n"
    output_ts_string += "\n"

    _LOGGER.info("TypeScript generation finished.")
    return output_ts_string
