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
disabled or unconfigured. `timeout_seconds` must be finite and non-negative.
The existing filtered audio volume and `audio.min_volume` are the only acoustic
threshold: values strictly greater than the threshold are active, and values at
or below it are silent. Missing measurements remain unknown until a sample or
source lifecycle event arrives.

`GET /api/config` includes the typed settings. `GET /api/info` includes a
`silence_scene` status object with enabled state, selected scene, timeout,
current audio classification, pending timeout, active override, restoration,
and recovery-journal status.

## Runtime Behavior

A continuous silent classification starts one monotonic timeout. Activity cancels
the pending timeout and restores the captured state immediately if an override
is active. Sendspin stream end, pause metadata, mute, established-connection
loss, and audio watchdog timeout feed the same controller. Source initialization
and device changes do not count as silence by themselves.

Before scene activation, the controller captures every virtual's actual active
effect type/configuration and active state, plus playlist runtime state. It uses
the normal scene manager/action implementation with persistence disabled, so
`activate`, `forceblack`, `stop`, and `ignore` retain their usual meaning without
writing temporary effects to virtual configuration.

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
scene activation. The journal remains through shutdown and is removed only after
all available virtual and playlist state has been restored. Unsupported,
corrupt, or incomplete journals are preserved and logged rather than silently
discarded. Recovery runs before the configured startup scene or playlist; after
a successful recovery, normal silence monitoring starts even if the source is
still silent.

A deliberate scene/effect/playlist operation supersedes the temporary override
and invalidates its journal. Disabling the feature or changing/deleting the
selected silence scene restores the prior state first. Runtime status is not
written to `config.json`.
