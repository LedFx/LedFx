# Global Configuration API

## Overview

This API lets a client set global configuration values across every **active** effect that natively supports the specified configuration keys.
Effects **without** a specified configuration field or where the field is in the effect's `HIDDEN_KEYS` list are **ignored**.

This operation is exposed as a bulk action on the existing **effects collection** endpoint.

## Behavior

- **Targets:** Only **active** effects that include the requested configuration keys in their schema.
- **Key Filtering:** Each configuration key is checked independently - effects are only updated for keys they support.
- **Hidden Keys:** Configuration keys in an effect's `HIDDEN_KEYS` list are skipped for that specific effect.
- **Non-target effects:** If an active effect does not expose any of the requested configuration keys, it is completely skipped.
- **Validation:** Each configuration value is validated using the same logic as per-effect configuration updates.
- **Toggle Support:** Boolean fields support `"toggle"` to flip the current state of each individual effect.
- **Persistence:** Each updated effect is merged via `effect.update_config({keys})` and saved through `virtual.update_effect_config(effect)`.
- **Color handling:** Individual effect colors except background_color which must be explicitly configured, will be extracted from the gradient and mapped accordingly. Rough mapping into gradient of Low = 0.0, Mid = 0.5, High = 1.0.
- **Idempotent:** Reapplying the same configuration results in no effective change (except for toggle operations which always flip state).
- **Virtual filter:** You may provide a `virtuals` field (list of virtual ids). When present the operation is restricted to only those virtuals; if omitted the operation works across all active effects.

---

## Endpoint

**PUT** `/api/effects`

---

## Request Body

| Field                    | Type              | Required | Description |
|--------------------------|-------------------|----------|-------------|
| `action`                 | string            | yes      | Must be `"apply_global"`. |
| `gradient`               | string            | no       | A gradient key (e.g., `"Viridis"`, `"MyCustomGradient"`) **or** a full gradient definition (e.g., `"linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)"`). |
| `background_color`       | string            | no       | A color value (e.g., `"red"`, `"#ff0000"`, `"rgb(255,0,0)"`). |
| `background_brightness`  | number            | no       | Background brightness value between 0.0 and 1.0. |
| `brightness`             | number            | no       | Main brightness value between 0.0 and 1.0. |
| `flip`                   | boolean or string | no       | `true`, `false`, or `"toggle"` to flip the current state. |
| `mirror`                 | boolean or string | no       | `true`, `false`, or `"toggle"` to flip the current state. |
| `virtuals`               | array of strings  | no       | Optional list of virtual ids to restrict the operation to. When present only virtuals with matching `virtual.id` values will be updated. |

**Notes**

- At least one configuration field must be provided.
- `gradient` supports built-in gradients, user-defined gradients, and full gradient definitions. Preset names are resolved to full definitions for storage.
- Gradient keys resolve via `LedFxCore.gradients` (user + built-ins).
- `background_color` is validated using `validate_color`.
- Boolean fields (`flip`, `mirror`) support `"toggle"` to flip the current state of each effect.
- Fields in an effect's `HIDDEN_KEYS` list are ignored for that specific effect.

---

## Examples

### Apply a predefined gradient to all active gradient and color capable effects
```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "gradient": "Viridis"
  }'
```

### Apply a gradient only to a specific list of virtuals
```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "gradient": "Viridis",
    "virtuals": ["virtual-1-id", "virtual-2-id"]
  }'
```

### Apply multiple configuration values
```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)",
    "background_color": "black",
    "background_brightness": 0.3,
    "brightness": 0.7,
    "flip": true
  }'
```

### Toggle boolean values
```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "mirror": "toggle",
    "flip": "toggle"
  }'
```

---

## Responses

### Success
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Applied global configuration to 3 effects (skipped 1)"
  }
}
```

### Failure (invalid or unknown value)
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Invalid value for \"gradient\": linear-gradient(90deg, badcolor 0%)"
  }
}
```

*Note: Returns HTTP 200 status code by default for frontend snackbar compatibility.*

### Failure (bad input)
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "At least one of the following attributes must be provided: gradient, background_color, background_brightness, brightness, flip, mirror"
  }
}
```

*Note: Returns HTTP 200 status code by default for frontend snackbar compatibility.*

