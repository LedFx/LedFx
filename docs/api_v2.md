# API v2 reference

LedFx serves a typed REST API under `/api/v2`, next to the v1 API described
in the other pages of this section. v1 keeps working, and new work goes into v2.

- A running LedFx serves the contract, an OpenAPI 3.1 document, at
  `/api/v2/openapi.json`, and this reference at `/api/v2/docs` (for example
  <http://localhost:8888/api/v2/docs>).
- The repository keeps the same document at `openapi/ledfx-v2.json`, and the
  reference below renders that copy. Its `info.version` is the contract
  version, not the LedFx release, and changes only when the API does (minor
  for additions, major for a break).
- Requests are strict, and responses may gain fields: ignore response fields
  you do not know.
- Errors are RFC 9457 problems (`application/problem+json`) with a stable
  `type` such as `urn:ledfx:problem:not-found`.

## Using v2

Every v2 path starts with `/api/v2`. Ids go in the path percent-encoded: the
virtual `dj bird` is `/api/v2/virtuals/dj%20bird`. Request bodies are JSON and
are checked strictly: unknown keys, wrong types (`"0.5"` for a number) and
out-of-range values are refused with a 422 problem whose `errors` name each
field, for example `["body", "config", "max_brightness"]`.

Virtuals:

| Method and path | What it does |
|---|---|
| `GET /virtuals`, `GET /virtuals/{virtual_id}` | List virtuals, or read one: settings, segments, state and the running effect |
| `POST /virtuals` | Create a virtual (`{"config": {"name": "Küche"}}`); the id comes from the name (`k-che`) and is in the `Location` header |
| `PATCH /virtuals/{virtual_id}` | Change only what you send: `config` settings, `segments`, `active` |
| `DELETE /virtuals/{virtual_id}` | Delete a virtual |
| `GET`, `PUT`, `PATCH`, `DELETE /virtuals/{virtual_id}/effect` | Read, start (`{"type": "rainbow", "config": {…}}`), adjust (`{"config": {"speed": 2}}`) or clear the effect |
| `POST /virtuals/{virtual_id}/effect/randomize`, `…/effect/reset` | Random or default settings for the running effect |
| `GET /virtuals/{virtual_id}/effects`, `DELETE …/effects/{effect_type}` | The effect types this virtual remembers settings for |
| `POST /virtuals/{virtual_id}/fallback` | Return now to the effect a timed effect replaced |
| `POST /virtuals/clear-effects`, `/virtuals/apply-config`, `/virtuals/set-effect` | Act on many virtuals (default: all) |
| `POST`/`DELETE /virtuals/oneshot`, `/virtuals/{virtual_id}/oneshot` | Flash all virtuals or one, or end the flashes |
| `POST /virtuals/force-color`, `/virtuals/{virtual_id}/force-color` | Show one colour |
| `PUT /virtuals/{virtual_id}/calibration`, `PUT`/`DELETE …/highlight`, `POST …/copy-effect` | Calibration tools, and copying an effect to other virtuals |

A stored effect whose type is no longer installed shows as
`{"type": "…", "config": {…}, "available": false}`; it cannot run until the
type is installed again. In safe mode every change that would be saved answers
409 (`urn:ledfx:problem:safe-mode`); reads keep working, and so do the runtime
tools that save nothing: clear-effects, flashes, force-color, calibration,
highlight and fallback (ending a temporary effect).

Behaviour worth knowing:

- v2 shares the server's app-wide origin middleware; there is no separate CORS
  setup. Its 403 refusals on `/api/v2` are problems too
  (`urn:ledfx:problem:forbidden`).
- A request body over the size limit answers 413, and a mutating route that
  gets a non-JSON body answers 415.
- `PATCH` is all-or-nothing: if any part is refused, nothing changes. Arrays in
  a `PATCH` replace the stored array wholesale, so send every item complete.
- v2 never adjusts a value it was sent. A segment must name a known device and
  pixels inside it (start not after end; gap devices are exempt), `frequency_min`
  must be below `frequency_max`, and `rotate` needs more than one row. Anything
  else is a 422 at the offending field and nothing changes.
- Responses show stored values even when they lie outside the bounds v2 accepts
  in a request.
- New plugins add new branches to response unions. This is additive, so a
  client must treat an unknown `type` as `UnknownPlugin` and not fail.
- The ids `oneshot` and `force-color` are reserved for the paths
  `/virtuals/oneshot` and `/virtuals/force-color`, which act on every virtual:
  a name that gives one of them is a 422 at `body.config.name`. A virtual that
  already has the id `oneshot` (from an older config, or a device's own virtual)
  can be read and changed, but `DELETE /virtuals/oneshot` ends every flash
  instead of deleting it.
- `DELETE …/highlight` is idempotent. `PUT …/highlight` on a virtual that is not
  calibrating is a 409; an unknown device or a range past its end is a 422 at
  `body.device_id` or `body.end`, and a negative or reversed range is a 422 at
  `body.start`.
- `copy-effect` with an unknown target is a 404 and nothing is copied. A target
  that refuses the effect is passed over; if none takes it, or the source runs
  nothing, that is a 409.
- Activating a virtual that cannot run (no segments, no effect to restore, a
  stored setting that no longer passes) is a 409, on `PATCH` and on starting an
  effect alike. Starting an effect makes the virtual active.
- `set-effect` without a `config` starts the effect type's defaults. In
  `set-effect`, `clear-effects` and `apply-config`, an unknown id in
  `virtual_ids` is a 404 naming each unknown id once, and nothing changes.
- `PUT …/effect` without a `config` restores the settings the virtual last used
  for the type; if one of them no longer passes the type's checks, that is a 409
  naming the field, and nothing starts.

<iframe src="_static/api-v2/index.html" title="LedFx API v2 reference"
        style="width: 100%; height: 80vh; border: 0;"></iframe>
