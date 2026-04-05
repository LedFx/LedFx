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

This Sendspin server will now be available as an audio source in the Setttings / Audio drop down.

### Auto-Discover Sendspin Servers

Ledfx can auto discover multiple Sendspin Servers present on your network using mDNS.

Click **AUTO-DISCOVER** to scan for available servers.

After a short period of time all discovered networks will be displayed. Those already configured will have a green tick in the Configured column.

![the easy way](/_static/settings/sendspin/sendspin_servers5.png)

Each discoved server can be added by clicking the **ADD** action button.

Details can then be modified before final commit with the **ADD** button.

![Last chance motel](/_static/settings/sendspin/sendspin_servers6.png)

## Selecting a Sendspin Server as Audio Input

Once a server has been added, it will appear as a selectable audio input device in **Settings** → **Audio**. Select it the same way you would select any other audio device.

![Pick me, pick me](/_static/settings/sendspin/sendspin_servers7.png)

When activated, LedFx will:

1. Connect to the Sendspin server via WebSocket
2. Negotiate for FLAC Mono, with a fallback to PCM Mono
3. Begin receiving audio chunks with timing information
4. Feed the audio into the visualization pipeline synchronized with all other sendspin audio end points.
5. If the connection drops, LedFx will automatically attempt to reconnect with exponential backoff.


