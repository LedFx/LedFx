# Name: TypeScript Generator
# Description: Generates TypeScript interfaces dynamically from voluptuous schemas in LedFx.
# Author: YeonV

import logging
import traceback
from typing import Any, Callable

import voluptuous as vol

script_logger = logging.getLogger("ledfx.tools.ts_generator")
logging.basicConfig(
    level=logging.INFO, format="%(name)s:%(levelname)s: %(message)s"
)

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
        script_logger.warning(
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
    if validator == str:
        return "string"
    elif validator == int:
        return "number"
    elif validator == float:
        return "number"
    elif validator == bool:
        return "boolean"
    elif isinstance(validator, vol.Coerce):
        if validator.type == int:
            return "number"
        if validator.type == float:
            return "number"
        if validator.type == str:
            return "string"
        return "any"
    elif isinstance(validator, vol.In):
        if for_universal:
            types = {type(opt) for opt in validator.container}
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
                    f'"{opt.replace("\"", "\\\"")}"'
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
            script_logger.debug(
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
                item_type = voluptuous_validator_to_ts_type(
                    validator.schema[0], for_universal
                )
                return f"{item_type}[]"
            return "any[]"
        else:
            script_logger.warning(
                f"Unhandled vol.Schema type: {type(validator.schema)}. Defaulting 'any'."
            )
            return "any"

    elif isinstance(validator, (vol.Range, vol.Length)):
        return "any"
    elif callable(validator):
        script_logger.warning(
            f"Unsupported function validator: {getattr(validator, '__name__', 'func')}. Defaulting 'any'."
        )
        return "any"
    else:
        script_logger.warning(
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
        script_logger.error(f"Schema not dict for {schema_name}")
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
                        # Try calling it - maybe it's a factory like next()
                        potential_value = default_value_attr()
                        # If calling returns something different and not a function, use it
                        if (
                            not callable(potential_value)
                            and potential_value is not default_value_attr
                        ):
                            actual_default = potential_value
                        else:
                            # Calling didn't help or returned a function, mark as computed
                            is_computed = True
                    except Exception:
                        # Calling failed, assume the original was the intended (maybe complex) default representation
                        is_computed = True  # Mark as computed if call fails

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
        # ... (constraint extraction logic - unchanged) ...
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
def generate_all_types_string_dual_effect() -> str:
    # --- Access Registries ---
    device_registry = {}
    effect_registry = {}
    try:
        script_logger.info(
            "Attempting to access registries via class methods..."
        )
        from ledfx.devices import Device
        from ledfx.effects import Effect
        from ledfx.virtuals import Virtual

        script_logger.info(
            "Imported managers to potentially trigger registry loading."
        )
        if hasattr(Device, "registry") and callable(Device.registry):
            device_registry = Device.registry()
            script_logger.info(
                f"Accessed device registry: {len(device_registry)} types."
            )
        else:
            script_logger.error("Could not find/call Device.registry().")
        if hasattr(Effect, "registry") and callable(Effect.registry):
            effect_registry = Effect.registry()
            script_logger.info(
                f"Accessed effect registry: {len(effect_registry)} types."
            )
        else:
            script_logger.error("Could not find/call Effect.registry().")
    except Exception as e:
        script_logger.error(f"Failed imports/registry access: {e}")
        return f"// Error accessing registries: {e}"
    if not device_registry:
        script_logger.warning("Device registry empty!")
    if not effect_registry:
        script_logger.warning("Effect registry empty!")

    output_ts_string = "/**\n * Type: AUTO-GENERATED FILE\n * Tool: LedFx TypeScript Generator\n * Author: YeonV\n */\n\n/* eslint-disable */\n\n"

    # --- 0. Generate Base Device Config ---
    base_device_config_interface_name = "BaseDeviceConfig"
    base_device_schema_object = None
    base_schema_keys = set()
    output_ts_string += "// --- Base Device Schema Generation --- \n"
    try:
        script_logger.info(
            "Manually defining Base Device Schema based on source..."
        )

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
            script_logger.info("Base schema dict created. Extracting keys...")
            for k in base_schema_dict.keys():
                key_name = str(
                    k.schema
                    if isinstance(k, (vol.Required, vol.Optional))
                    else k
                )
                base_schema_keys.add(key_name)
            script_logger.info(f"Base schema keys: {base_schema_keys}")
            output_ts_string += "/**\n * Base configuration shared by all devices\n * @category DeviceSpecificConfigs\n */\n"
            output_ts_string += generate_ts_interface_from_voluptuous(
                base_device_config_interface_name, base_device_schema_object
            )
            output_ts_string += "\n\n"
            script_logger.info(
                f"Successfully generated {base_device_config_interface_name}"
            )
        else:
            script_logger.error(
                "Manually created base schema's '.schema' attribute is not dict?"
            )
            base_device_schema_object = None
            base_device_config_interface_name = "Record<string, any>"
            output_ts_string += f"// Manual base schema dict failed\nexport type {base_device_config_interface_name} = Record<string, any>;\n\n"

    except Exception as e:
        script_logger.error(
            f"Error manually processing base Device schema: {e}"
        )
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
            script_logger.error("Virtual.CONFIG_SCHEMA not found/invalid.")
            output_ts_string += f"// Virtual config schema not found\nexport interface {virtual_config_interface_name} {{ [key: string]: any; }}\n\n"
    except Exception as e:
        script_logger.error(f"Failed VirtualConfig: {e}")
        output_ts_string += f"// Failed VirtualConfig\nexport interface {virtual_config_interface_name} {{ [key: string]: any; }}\n\n"

    # --- 2. Generate Specific Device Configs & DeviceType Union ---
    all_device_config_interface_names = []
    all_device_type_strings = sorted(device_registry.keys())
    script_logger.info(
        f"Generating TS for {len(device_registry)} device types..."
    )
    for device_type_str in all_device_type_strings:
        device_class = device_registry[device_type_str]
        device_schema_to_use = getattr(device_class, "CONFIG_SCHEMA", None)
        if callable(device_schema_to_use) and not isinstance(
            device_schema_to_use, vol.Schema
        ):
            try:
                device_schema_to_use = device_schema_to_use()
            except Exception as e:
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
                script_logger.error(
                    f"Failed gen TS Device '{device_type_str}': {e}"
                )
                output_ts_string += f"// Failed gen for {device_config_ts_name}\nexport interface {device_config_ts_name} {{ [key: string]: any; }}\n\n"
        else:
            script_logger.warning(
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
        script_logger.warning(
            "No specific device config interfaces for union."
        )
        output_ts_string += f"export type {device_config_union_name} = {base_device_config_interface_name};\n\n"

    # --- 2.5 Collect ALL Device Properties for Universal Interface ---
    all_device_properties = {}  # prop_name -> basic_ts_type
    script_logger.info(
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
            except Exception as e:
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
                        script_logger.debug(
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
    script_logger.info(
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
                script_logger.error(
                    f"Failed gen SPECIFIC TS Effect '{effect_type_str}': {e}"
                )
                output_ts_string += f'// Failed gen for {effect_config_ts_name}\nexport interface {effect_config_ts_name} {{ type: "{effect_type_str}"; [key: string]: any; }}\n\n'
        else:
            script_logger.warning(
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
        script_logger.warning(
            "No specific effect config interfaces for discriminated union."
        )

    # --- 4. Collect ALL Effect Properties for Universal Interface ---
    all_effect_properties = {}
    script_logger.info("Collecting properties for universal interface...")
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
                        script_logger.debug(
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

    # --- 7. Generate Convenience Type Aliases ---

    output_ts_string += "// Convenience Type Aliases using Universal Configs\n"
    # Effect alias
    # output_ts_string += "/**\n * Convenience type for effect details using the universal EffectConfig.\n * @category General\n */\n"
    # output_ts_string += "export type Effect = Omit<Omit<EffectSpecific, 'config'> & { config: EffectConfig | null }, 'type'> & { type?: EffectType | null };\n"
    # Virtual alias
    # output_ts_string += "/**\n * Convenience type for a Virtual object using the universal Effect type.\n * @category General\n */\n"
    # output_ts_string += "export type Virtual = Omit<VirtualSpecific, 'effect' | 'last_effect'> & { effect: Partial<Effect>; last_effect?: EffectType | null };\n"
    # Virtuals alias
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Virtual objects.\n * @category General\n */\n"
    output_ts_string += "export type Virtuals = Omit<GetVirtualsApiResponse, 'virtuals'> & { virtuals: Record<string, Virtual> };\n"
    # Device alias
    # output_ts_string += "/**\n * Convenience type for a Device object using the universal DeviceConfig.\n * @category General\n */\n"
    # output_ts_string += f"export type Device = Omit<DeviceSpecific, 'config'> & {{ config: {universal_device_config_name} }};\n"  # Uses universal DeviceConfig
    # Devices alias (uses universal Device alias)
    output_ts_string += "/**\n * Convenience type for the API response containing multiple Device objects.\n * @category General\n */\n"
    output_ts_string += "export type Devices = Omit<GetDevicesApiResponse, 'devices'> & { devices: Record<string, Device> };\n"
    output_ts_string += "\n"

    script_logger.info("TypeScript generation finished.")
    return output_ts_string
