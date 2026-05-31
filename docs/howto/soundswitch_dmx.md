# How to: Control LedFx from SoundSwitch (DMX Input)

The **DMX Input** integration lets an external DMX source drive LedFx in
real time. It was built for [SoundSwitch](https://www.soundswitch.com/), but
works with any controller that can emit
[Art-Net](https://art-net.org.uk/) (QLC+, lighting consoles, DMX-over-Art-Net
software, etc.).

The key idea: you do **not** need any extra hardware or a separate bridge.
SoundSwitch can output Art-Net over the network **at the same time** as it
drives your real fixtures through its USB-DMX interface. LedFx simply listens
to that Art-Net stream on `127.0.0.1` and maps DMX channels to LedFx actions.

## What you can do with it

Each *mapping* connects one or more DMX channels to a LedFx target. There are
three mapping types:

1. **Trigger** &mdash; a button / static-look channel toggles a **venue color
   pad override**. When the channel goes high the pad's color or gradient is
   applied to every virtual in the venue; when it goes low the override is
   released. Edge detection uses hysteresis (separate on/off thresholds) so a
   noisy channel does not flicker.
2. **Color** &mdash; live **R/G/B passthrough**. The target's effect keeps
   animating, but its colors are recolored to the incoming DMX color in real
   time (the same mechanism as a venue color override).
3. **Fixture / wash** &mdash; treat a virtual like a dumb DMX wash. A
   **mode-toggle** channel switches the virtual between "run the LedFx effect"
   and "act as a solid wash" driven by a **dimmer** channel and **R/G/B**
   channels. Toggle it back off and the current effect is revealed again.

## Step 1 &mdash; Enable Art-Net output in SoundSwitch

In SoundSwitch, add an **Art-Net** output **in addition to** your existing
USB-DMX interface, and mirror the universe(s) you want LedFx to see:

- **Destination IP:** `127.0.0.1` (loopback &mdash; LedFx runs on the same PC).
  If LedFx runs on another machine, use that machine's IP instead.
- **Universe:** match the universe(s) your fixtures / buttons use. Note
  whether SoundSwitch numbers universes from 0 or 1 &mdash; LedFx mappings use
  the raw Art-Net Port-Address (0-based) by default.
- Keep your USB-DMX interface enabled so your real fixtures are unaffected.

> SoundSwitch's "signal" is just DMX. By mirroring it over Art-Net you get a
> clean, documented copy of exactly what your faders and buttons are sending.

## Step 2 &mdash; Add the DMX Input integration in LedFx

1. Go to **Settings &rarr; Integrations** and add a **DMX Input** integration.
2. Configuration options:
   - **bind_address** (default `127.0.0.1`) &mdash; the local address LedFx
     listens on. Use `0.0.0.0` to accept Art-Net from other machines.
   - **port** (default `6454`) &mdash; the standard Art-Net UDP port. If
     LedFx's own Art-Net *output* or another Art-Net node already uses this
     port, you will see a bind error in the log; free the port or change it.
   - **update_fps** (default `60`) &mdash; how often incoming DMX is applied.
   - **stale_timeout** (default `2.0` s) &mdash; if the Art-Net stream stops,
     LedFx releases any overrides/washes it owns after this many seconds.
   - **hold_last_look** (default off) &mdash; keep the last look instead of
     releasing it when the stream stops.
3. Toggle the integration **on**. The log should show
   `DMX Input listening for Art-Net on 127.0.0.1:6454`.

## Step 3 &mdash; Find the right channel (DMX learn)

Not sure which channel a SoundSwitch button uses? Watch the **live DMX**
values while you press it:

- The integration exposes the latest DMX values per universe via its REST
  endpoint, so you can see which channel jumps when you press a button or push
  a fader. Use that channel number in your mapping.

## Step 4 &mdash; Create mappings

Add a mapping for each control you want to bridge.

**Trigger (button &rarr; venue pad override)**

| Field          | Example         |
| -------------- | --------------- |
| type           | `trigger`       |
| universe       | `0`             |
| channel        | `1`             |
| venue          | your venue      |
| pad            | pad index       |
| on / off       | `128` / `96`    |

**Color (live recolor)**

| Field          | Example             |
| -------------- | ------------------- |
| type           | `color`             |
| universe       | `0`                 |
| channels       | R, G, B (e.g. 1-3)  |
| target         | a venue or virtual  |

**Fixture / wash**

| Field          | Example                       |
| -------------- | ----------------------------- |
| type           | `fixture`                     |
| universe       | `1`                           |
| channels       | mode, dimmer, R, G, B         |
| target virtual | the LED run to use as a wash  |
| on / off       | `128` / `96` (mode toggle)    |

When the **mode** channel is high the virtual outputs a solid `RGB x dimmer`
wash; when it is low the virtual's normal LedFx effect plays again.

## Tips

- LedFx only changes the **color** of the running effect for trigger/color
  mappings &mdash; the animation keeps playing. Fixture mode is the only mode
  that replaces the effect with a solid wash.
- LedFx releases only the overrides/washes **it** owns, so you can still
  control effects normally from the LedFx UI alongside DMX control.
- If a channel is already high when LedFx starts, it will **not** auto-fire;
  LedFx waits for a fresh low&rarr;high edge.

## Optional: wireless / USB DMX input

The same mapping engine is transport-agnostic. A future option is to capture
physical or wireless DMX with a USB DMX-input interface and feed it to the
same mappings &mdash; useful if you would rather add LedFx as another
"fixture" in SoundSwitch and steer it with a DMX wash channel.
