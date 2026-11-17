# Architecture notes

For a general overview read [copilot-instructions.md](https://github.com/LedFx/LedFx/blob/main/.github/copilot-instructions.md) in the .github directory.

This file is also used to prime your copilot context if working in VS Code.

The following are generated via AI assisted spelunking, but are then hand curated for relevance.

## LedFx runtime flow

```mermaid
sequenceDiagram
    autonumber
    participant Core as LedFxCore
    participant Config as Config Loader
    participant API as HTTP/API Server
    participant Audio as Audio Manager
    participant Virtuals as Virtual Manager
    participant Effects as Effect Engine
    participant Segments as Segment Mapper
    participant Devices as Physical Devices

    Core->>Config: Load configuration
    Core->>Virtuals: Initialize virtuals
    Core->>Effects: Initialize effects
    Core->>Devices: Initialize output devices
    Core->>Audio: Start audio input stream
    Core->>API: Start API and Web UI

    loop Runtime Frame (~60 FPS)
        Audio->>Audio: Process incoming audio frame
        Audio-->>Effects: Audio state (FFT, volume, beats)

        Core->>Virtuals: Get each active virtual
        Virtuals->>Effects: Generate effect
        Effects-->>Virtuals: Return pixel array

        Virtuals->>Segments: Apply mapping (span/copy/grouping)
        Segments->>Devices: Pixel data to device
        Devices->>Devices: Flush frame to hardware
    end
```
## Preview sampling

Websocket clients see pixels through `visualisation_update` events, built by
the core-owned `PreviewSampler` (`ledfx/preview.py`):

- After rendering a frame, a virtual (in `_fire_update_event`) and a device
  (in `update_pixels`, before `flush`) ask the sampler whether a
  `visualisation_update` subscriber could match that source. Only then do
  they copy the frame and submit the copy, from the render thread.
- The sampler keeps only the newest frame per source, keyed by
  `(is_device, id)`. Older frames that were not yet sent are dropped.
- One tick on the event loop encodes each due frame and fires it, at most
  `visualisation_fps` times a second per source. The schedule advances on a
  fixed grid, so a 62 FPS source still previews at 60 FPS, and a source that
  was idle does not get a burst of old frames. Only that tick creates timers.
- If one source's frame fails to encode, the tick skips it and still sends
  the others. The failure is logged at ERROR at most once a second per
  exception type, with a count of the failures in between.
- `visualisation_maxlen`, `ui_brightness_boost` and `transmission_mode` are
  read when encoding, so changing them needs no restart.
- When the last matching subscriber leaves, the pending frame is dropped at
  the next tick. Deleting a virtual or device drops its pending frame.
- The raw `virtual_update` and `device_update` events are built only when an
  in-process listener has subscribed to them.

## Threads and locks

### Devices

- The render thread of a device's priority virtual is the only caller of
  `Device.flush`. Other virtuals sharing the device only write their segments
  into its buffer.
- `Device._frame_lock` guards the pixel buffer (`_pixels`) and `_active`. It
  is a leaf: while it is held, nothing calls `flush`, subclass code, a
  virtual, the preview sampler, the event bus or the logger, and no other
  lock is taken.
- `update_pixels` writes the segments and, for the priority virtual, composes
  a new frame (rotated by `center_offset`) under `_frame_lock`. It then
  releases the lock and, outside it, submits a preview copy, calls `flush`
  and fires `device_update`. A slow sender never blocks a writer or a
  lifecycle call on the frame lock, and the frame it sends is never written
  to afterwards. `assemble_frame` returns the same kind of owned copy.
- Subclass sender locks (`device_lock` in the E1.31, WLED, DDP, Art-Net,
  Nanoleaf and native packet devices, `_publication_lock` in Hue) sit above
  `_frame_lock`. A subclass may hold its sender lock while calling
  `Device.activate` or `Device.deactivate`, which take `_frame_lock` only to
  swap the buffer. `flush` may take the sender lock because no base lock is
  held when it runs.
- `Device.activate` and `Device.deactivate` hold no lock across IO. The
  blocking work in subclasses (Govee's wake sleeps, Twinkly's HTTP calls,
  Hue's HTTPS and DTLS setup) runs before or after the base call, so it never
  holds `_frame_lock`.
