# Sendspin Audio Streaming

[**Sendspin**](https://www.sendspin-audio.com/) is a synchronized multi-room audio system, integrated with [**Music Assistant**](https://www.music-assistant.io/) and [**Home Assistant**](https://www.home-assistant.io/).

LedFx can connect to a Sendspin server as a client to receive audio for real-time visualization — no local microphone or loopback device required.

:::: note
::: title
**WARNING**
:::
Sendspin support requires **Python 3.12 or later**.
If you are running an older Python version, Sendspin will not appear as an option.
Check `http://your-ledfx-ip:8888/api/info` — the `sendspin` feature flag should be `true`.
::::

:::: note
::: title
**VERSION COMPATIBILITY (MUSIC ASSISTANT)**
:::
Sendspin client/server protocol changes can break interoperability across major `aiosendspin` lines.

LedFx main requires `aiosendspin>=9.1.1,<9.2.0` (Python 3.12+). Music Assistant
must use a compatible Sendspin protocol version; check the version in your
Music Assistant installation if the connection fails. Older LedFx releases use `aiosendspin>=6.0.5,<7.0.0` instead.

LedFx 2.2.0 moved to 9.1.1 but did not support the required api contracts.

As of 2.2.1 LedFx operates with unpaired_access_enabled=true

Repeated handshake failures can indicate a client/server version mismatch.
::::

## Overview

Instead of capturing audio from a local sound device, LedFx connects to a Sendspin server over the network via WebSocket. Audio is streamed in real-time and fed directly into LedFx's audio processing pipeline, enabling visualizations that are perfectly synchronized with the playback on other Sendspin clients.

**Key benefits:**

- No virtual audio cables, loopback devices, or OS-specific configuration needed
- Works across machines on the same network
- Audio stays in sync with other Sendspin rooms/clients
- Automatic server discovery via mDNS

## Requirements

- Python 3.12+
- A running [Sendspin server](https://www.sendspin-audio.com/) on your network
- Network connectivity between LedFx and the Sendspin server

## Adding a Sendspin Server

Open the LedFx UI and navigate to **Settings** → **Features**.
If Sendspin is available, you will see an option to manage Sendspin servers.

![Look Ma, no hands](/_static/settings/sendspin/sendspin_feature.png)

Select Manage to open the Sendspin management dialog

![Falling down the hole](/_static/settings/sendspin/sendspin_servers1.png)

### Manual Sendspin Server

A server can be manually added with the **+ADD SERVER** button

![If you must](/_static/settings/sendspin/sendspin_servers2.png)

1. ID Name which will be used to display the Sendspin server in the audio devices list.
2. Server URL (e.g. `ws://192.168.1.12:8927/sendspin`) which must begin with ws:// or wss://
3. Client Name, which defines how Ledfx will be identified to the Sendspin server.

![If you must](/_static/settings/sendspin/sendspin_servers3.png)

4. Click **ADD** to save the server configuration.

![yes, that button there](/_static/settings/sendspin/sendspin_servers4.png)

This Sendspin server will now be available as an audio source in the Settings / Audio drop down.

### Auto-Discover Sendspin Servers

Ledfx can auto discover multiple Sendspin Servers present on your network using mDNS.

Click **AUTO-DISCOVER** to scan for available servers.

After a short period of time all discovered networks will be displayed. Those already configured will have a green tick in the Configured column.

![the easy way](/_static/settings/sendspin/sendspin_servers5.png)

Each discovered server can be added by clicking the **ADD** action button.

Details can then be modified before final commit with the **ADD** button.

![Last chance motel](/_static/settings/sendspin/sendspin_servers6.png)

## Selecting a Sendspin Server as Audio Input

Once a server has been added, it will appear as a selectable audio input device in **Settings** → **Audio**. Select it the same way you would select any other audio device.

![Pick me, pick me](/_static/settings/sendspin/sendspin_servers7.png)

In Music Assistant, find the Sendspin player with the **Client Name** configured
above. Enable the player there, then select it for playback or add it to a
playing group. Merely seeing the client connected or listed in a group does not
guarantee Music Assistant is sending it audio. When playback starts, LedFx logs
`Sendspin stream started` and begins receiving audio chunks.

When activated, LedFx will:

1. Connect to the Sendspin server via WebSocket
2. Negotiate for FLAC Mono, with a fallback to PCM Mono
3. Begin receiving audio chunks with timing information
4. Feed the audio into the visualization pipeline synchronized with all other sendspin audio end points.
5. If the connection drops, LedFx will automatically attempt to reconnect with exponential backoff.

## Pairing and Security

LedFx currently enables Sendspin **unpaired access** when connecting. No pairing
token is needed for this path: LedFx does not offer a token or pairing-code UI.
If Music Assistant shows a `pairing_token` field, that is a request for a token
generated by the client, not a key to type literally. Return to the Sendspin
player in Music Assistant and enable it for unpaired playback instead.

The Sendspin connection is encrypted, but without pairing neither side has
cryptographic proof of the other's identity. An attacker with access to the
local network could impersonate a peer or intercept the connection. Use this
mode only on a network you trust. LedFx retains a persistent Sendspin identity
and pairing store for the protocol; unpaired access does not remove existing
pairing records or force a previously paired connection to become unpaired.

## Always-On Mode

Sendspin Always On is enabled by default. With this setting enabled, the Sendspin connection can stay active regardless of whether any effects are running.

This is a global setting found in the sendspin server management dialog (`sendspin_always_on`).

When enabled:

- The Sendspin audio stream starts immediately when a Sendspin device is selected, even without active effects.
- The stream remains active if all effects are removed.
- On boot, if a Sendspin device was previously selected and this setting is `true`, the stream starts automatically.

When disabled, Sendspin follows normal audio lifecycle behavior and may deactivate when no audio-reactive effects are subscribed.

This is useful for integrations where you want LedFx to be ready to visualize audio the moment playback begins, without requiring an effect to be pre-configured.


