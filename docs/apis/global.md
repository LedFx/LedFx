# Global Configuration API

## apply_global

This API lets a client set global configuration values across every **active** effect that natively supports the specified configuration keys.
Effects **without** a specified configuration field or where the field is in the effect's `HIDDEN_KEYS` list are **ignored**.

This operation is exposed as a bulk action on the existing **effects collection** endpoint.

### Behavior

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

### Endpoint

**PUT** `/api/effects` with `action: "apply_global"`

### Request body:

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

**Notes:**

- At least one configuration field must be provided.
- `gradient` supports built-in gradients, user-defined gradients, and full gradient definitions. Preset names are resolved to full definitions for storage.
- Gradient keys resolve via `LedFxCore.gradients` (user + built-ins).
- `background_color` is validated using `validate_color`.
- Boolean fields (`flip`, `mirror`) support `"toggle"` to flip the current state of each effect.
- Fields in an effect's `HIDDEN_KEYS` list are ignored for that specific effect.

### Examples

#### Apply a predefined gradient to all active gradient and color capable effects:

```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "gradient": "Viridis"
  }'
```

#### Apply a gradient only to a specific list of virtuals:

```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "gradient": "Viridis",
    "virtuals": ["virtual-1-id", "virtual-2-id"]
  }'
```

#### Apply multiple configuration values:

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

#### Toggle boolean values:

```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global",
    "mirror": "toggle",
    "flip": "toggle"
  }'
```

### Responses

#### Success (snackbar-friendly):

```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Applied global configuration to 3 effects (skipped 1)"
  }
}
```

#### Failure (invalid or unknown value):

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

---

## apply_global_effect

A bulk action that lets a client apply a single effect (type + config) to a specific list of virtuals.

### Behavior:

- The call attempts to set the requested effect on each listed virtual id in order. Non-existent ids are skipped.
- If `config` is omitted or empty the effect is created using default configuration (this is treated as a reset).
- `RANDOMIZE` is intentionally not supported for this bulk action.
- `fallback` uses the same `process_fallback` semantics as the per-virtual endpoint. If a fallback is provided and a virtual is currently streaming, that virtual is blocked and skipped (the operation continues for other virtuals).
- Any failure to create or set an effect on a particular virtual is recorded as a failure and does not abort the overall operation.

### Endpoint:

**PUT** `/api/effects` with `action: "apply_global_effect"`

### Request body:

| Field      | Type             | Required | Description |
|------------|------------------|----------|-------------|
| `action`   | string           | yes      | Must be `"apply_global_effect"`. |
| `virtuals` | array[string]    | no       | Optional list of virtual ids to target. When omitted the operation targets all known virtuals. If provided, must be a non-empty list. |
| `type`     | string           | yes      | Effect type to apply (same strings used by per-virtual endpoints). |
| `config`   | object           | no       | Effect configuration. If omitted or empty, the effect will be created with its defaults (reset behavior). `"RANDOMIZE"` is not supported for this action. |
| `fallback` | bool|number|null   | no       | Same semantics as the per-virtual endpoints; controls fallback timeout behavior. When a fallback value is provided and a virtual is currently streaming, that virtual will be blocked (skipped) rather than cause the whole operation to fail. |

### Response:

#### Success
On success the endpoint returns a summary with counts to help the client understand what happened across the batch. Example:

```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Applied effect 'sparkle' to 10 virtuals (skipped 2, blocked 1, failed 1)"
  }
}
```

- `applied` – number of virtuals successfully updated
- `skipped` – number of virtual ids that did not exist in the system
- `blocked` – number of virtuals skipped because they were actively streaming and a `fallback` was provided
- `failed` – number of virtuals where creating or setting the effect raised an error

#### Failure (bad input)
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "At least one of the following attributes must be provided: gradient, background_color, background_brightness, brightness, flip, mirror"
  }
}
```

### Examples

#### Apply an effect to all virtuals (omit `virtuals`)

```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global_effect",
    "type": "sparkle",
    "config": { "density": 0.5 }
  }'
```

#### Apply an effect with fallback — blocked virtuals are skipped

If some virtuals are actively streaming and you provide a `fallback` value, those virtuals will be skipped and counted as `blocked` in the response.

```bash
curl -X PUT http://localhost:8888/api/effects \
  -H "Content-Type: application/json" \
  -d '{
    "action": "apply_global_effect",
    "virtuals": ["v1","v2","v3"],
    "type": "sparkle",
    "config": { "density": 0.5 },
    "fallback": true
  }'
```

*Note: Returns HTTP 200 status code by default for frontend snackbar compatibility.*

