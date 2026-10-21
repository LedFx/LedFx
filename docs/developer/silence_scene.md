# Silence Scene Recovery

Silence-scene handling is backend-only and disabled by default. Configure it in
`config.json` or through `PUT /api/config`:

```json
{
  "silence_scene": {
    "enabled": true,
    "scene_id": "quiet-room",
    "timeout_seconds": 5.0
  }
}
```

`scene_id` is a scene key from `scenes`; it may be `null` while the feature is
disabled or when no silence scene is selected. With the feature enabled and no
scene selected, the timeout still applies: all virtual effects are cleared and
the virtuals are deactivated. `timeout_seconds` must be finite and non-negative.
The existing filtered audio volume and `audio.min_volume` are the only acoustic
threshold: values strictly greater than the threshold are active, and values at
or below it are silent. Missing measurements remain unknown until a sample or
source lifecycle event arrives.

`GET /api/config` includes the typed settings. `GET /api/info` includes a
`silence_scene` status object with enabled state, selected scene, timeout,
current audio classification, pending timeout, active override, restoration,
and recovery-journal status. When no scene is selected, each virtual emits its
normal final zero-pixel visualization frame before deactivation.
WebSocket clients may subscribe to `silence_scene_entered` and
`silence_scene_exited`. These are signal-only events; clients can fetch current
status or virtual configuration as needed.

## Runtime Behavior

A continuous silent classification starts one monotonic timeout. Activity cancels
the pending timeout and restores the captured state immediately if an override
is active. Sendspin stream end, pause metadata, mute, established-connection
loss, and audio watchdog timeout feed the same controller. An established
Sendspin connection with no active stream is silent; stream start or reconnection
does not claim activity. Classification remains unknown until measured volume is
available, and the first received chunk also clears idle silence if a stream-start
notification was missed. Source initialization and device changes alone do not
count as silence.

Before changing runtime state, the controller captures every virtual's actual
active effect type/configuration and active state, plus playlist runtime state.
When a scene is selected, it uses the normal scene manager/action implementation
with persistence disabled, so `activate`, `forceblack`, `stop`, and `ignore`
retain their usual meaning without writing temporary effects to virtual
configuration. With no scene selected, it clears effects and deactivates all
virtuals instead. Activity restores the captured virtual and playlist state in
either mode.

Playlist recovery captures the playlist ID, current position, shuffle order,
runtime-resolved items, runtime mode/timing overrides, sampled duration, and
remaining time. Playlist progression is paused during the override and resumes
without reactivating the current playlist scene.

## Recovery Journal

The controller writes `silence_scene_recovery.json` in the configuration
directory before changing runtime effects. Version 1 contains:

- `version`, `phase` (`pending`, `active`, or `restoring`), and `silence_scene_id`.
- `virtuals`: virtual ID to `active`, `effect_type`, and `effect_config` values.
- `playlist`: an `active` flag and, when active, the playlist checkpoint fields
  listed above.

Writes use a same-directory temporary file, file `fsync`, atomic replacement,
and directory `fsync` where supported. A missing/unwritable journal prevents
the silence override. The journal remains through shutdown and is removed only after
all available virtual and playlist state has been restored. Deleted virtuals
require no further restoration; a failed playlist restoration keeps recovery
incomplete. Startup distinguishes no journal, successful recovery, incomplete
recovery, and failed journal reads/validation. A valid but incomplete journal is
retained and retried on a later activity change; it blocks a new silence
override. Corrupt, unreadable, and unsupported-version journals are preserved
with an actionable error, and automatic silence overrides remain disabled for
that run. LedFx continues starting, but skips configured startup scene and
playlist activation so neither can overwrite the unresolved operational state.
The normal configured runtime remains available for manual operation and
diagnosis. A missing journal keeps normal startup behavior unchanged. After
successful recovery, normal silence monitoring starts even if the source is
still silent, while the restored journal-free state is eligible for a new
silence timeout.

A deliberate scene/effect/playlist operation supersedes the temporary override
and invalidates its journal. Disabling the feature or changing/deleting the
selected silence scene restores the prior state first. Runtime status is not
written to `config.json`.

## Frontend Follow-up

The frontend implementation belongs in a separate PR. Its configuration UI
should expose the existing `silence_scene` settings:

- `enabled`: toggle, default off.
- `scene_id`: optional scene selection. `null` means clear effects and
  deactivate all virtuals after the timeout.
- `timeout_seconds`: non-negative duration, default 5 seconds.

Do not add a second audio threshold control. Silence classification uses the
existing filtered volume and `audio.min_volume` setting. Save settings through
`PUT /api/config`.

For live status, read `silence_scene` from `GET /api/info`. It contains
`enabled`, `scene_id`, `timeout_seconds`, `audio_silent`, `timeout_pending`,
`silence_scene_active`, `restoring`, `state`, `reason`, and `recovery_pending`.

Subscribe to `silence_scene_entered` and `silence_scene_exited`. These are
signal-only events containing only `event_type`; do not expect a status payload.
On either event, refetch `/api/info` and `/api/virtuals` so virtual active/effect
state and matrix layout/configuration are authoritative. Also refresh playlist
runtime state with `PUT /api/playlists` and `{"action":"state"}` so playlist
widgets reflect the pause or resumed checkpoint. Refetch playlist definitions
with `GET /api/playlists` only if the UI needs them. Do not rely on
`scene_activated` for this refresh: it is a separate named-scene notification.
