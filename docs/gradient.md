# **Global Gradient**

> **Scope:** Apply a single gradient to **all active effects that support `gradient`**.
> **Base URL:** `http://<host>:<port>/api`
> **Version:** 0.1-draft

---

## Overview

This API lets a client set one **global gradient** across every **active** effect that natively supports a `gradient` config key.
Effects **without** a `gradient` field are **ignored** (no fallback mapping yet).

This operation is exposed as a bulk action on the existing **effects collection** endpoint.

---

## Endpoint

**PUT** `/api/effects`

---

## Request Body

| Field      | Type   | Required | Description |
|------------|--------|----------|-------------|
| `action`   | string | yes      | Must be `"apply_global_gradient"`. |
| `gradient` | string | yes      | A gradient key (e.g., `"Viridis"`, `"MyCustomGradient"`) **or** a full gradient definition (e.g., `"linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)"`). |

**Notes**
- `gradient` is validated using the same logic as effect configs (`validate_gradient` / `parse_gradient`).
- Keys resolve via `LedFxCore.gradients` (user + built-ins).

---

## Examples

### Apply a predefined gradient to all active gradient-capable effects
```bash
curl -X PUT http://localhost:8888/api/effects   -H "Content-Type: application/json"   -d '{
    "action": "apply_global_gradient",
    "gradient": "Viridis"
  }'
```

### Apply a custom linear gradient string
```bash
curl -X PUT http://localhost:8888/api/effects   -H "Content-Type: application/json"   -d '{
    "action": "apply_global_gradient",
    "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)"
  }'
```

---

## Behavior

- **Targets:** Only **active** effects that include a `gradient` key in their schema.
- **Non-target effects:** If an active effect does **not** expose `gradient`, it is **skipped** (no changes).
- **Validation:** The `gradient` string may be a **name** or a **definition**; it’s validated exactly like per-effect config.
- **Persistence:** Each updated effect is merged via `effect.update_config({"gradient": <str>})` and saved through `virtual.update_effect_config(effect)`; configuration is then persisted.
- **Idempotent:** Reapplying the same gradient results in no effective change.

---

## Responses

### Success
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Applied gradient to 3 active effects with gradient support"
  },
  "data": {
    "updated": 3
  }
}
```

### Failure (invalid or unknown gradient)
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Invalid gradient: linear-gradient(90deg, badcolor 0%)"
  }
}
```

*Note: Returns HTTP 200 status code by default for frontend snackbar compatibility.*

### Failure (bad input)
```json
{
  "status": "error",
  "message": "Required attribute \"gradient\" was not provided"
}
```

---

## Future Extensions (not implemented yet)

- Support for non-gradient effects (mapping gradient → `colors`, `foreground/background`, or `color`).
