# Frontend

## Overview

Frontend is a **matrix passthrough effect** that displays pixel data captured directly from the LedFx frontend visualiser onto an LED matrix.

Rather than generating its own visuals, the effect receives real-time pixel frames sent by the browser over the WebSocket connection and renders them onto the virtual. This allows any visualisation visible in the LedFx UI — including other virtuals' output as seen in the frontend — to be mirrored back to physical hardware.

Incoming frames are automatically resized to match the target matrix dimensions using bilinear interpolation, so the source resolution does not need to match the physical device.

The effect supports all standard Twod matrix transforms — rotation (0°, 90°, 180°, 270°) and horizontal/vertical flip — via the shared matrix settings.

---

## How It Works

1. The LedFx frontend captures a visualiser frame and sends it to the backend as a raw binary WebSocket frame containing the pixel dimensions, source identifier, and interleaved RGB bytes.
2. The backend unpacks the frame, reconstructs a pixel array, and fires an internal event.
3. The effect receives the event and stores the pixel data; on the next matrix render tick the frame is pasted into the Twod pipeline and written to the LED pixels.

### Multiple Frontends

If more than one browser tab or client is sending visualiser data, the effect locks to the **first client** to send a frame. All other clients are ignored with a one-time log warning.

If the active client stops sending (e.g. the page is refreshed or closed), the effect will automatically accept the next client after a **3-second timeout**.

---

## Settings

The Frontend effect has no effect-specific settings beyond the shared matrix controls.

### Shared Matrix Settings

| Setting | Description |
|---|---|
| **ROTATE** | Rotate the output 0°, 90°, 180°, or 270° |
| **FLIP HORIZONTAL** | Mirror the image left-to-right |
| **FLIP VERTICAL** | Flip the image top-to-bottom |
| **BRIGHTNESS** | Overall output brightness multiplier |

---

## Notes

- The effect requires the frontend to be actively capturing and sending visualiser frames. If the frontend is not running or the visualiser is disabled, the matrix will remain blank.
- Frame rate is determined by the frontend capture rate; no upsampling or frame interpolation is applied.
- The effect is intended for use with 2D matrix virtuals. It will work on 1D strips but the resize from a 2D source will result in a single row of pixels.
