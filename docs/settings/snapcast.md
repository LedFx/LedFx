# Snapcast Audio Streaming

[**Snapcast**](https://github.com/badaix/snapcast) is a synchronous multi-room audio player. A snapserver distributes audio to any number of snapclients, which all play it in sync.

LedFx has a built-in Snapcast client. It connects to your snapserver like any other snapclient and uses the received audio for visualization — no separate snapclient, loopback device or PulseAudio setup required, including in the LedFx Docker image.

## Overview

- Each configured snapserver appears in the LedFx audio device list as `SNAPCAST: <server id>`.
- LedFx appears in the snapserver's client list (for example in Snapweb) under its client name, and can be assigned to groups and streams like any other client.
- Audio is released to the effects at the moment the snapserver schedules it to play, so the lights stay in sync with the speakers of the other clients.
- Volume changes from the snapserver are ignored, so the visualization does not depend on the listening volume. Muting the LedFx client from the snapserver silences the visualization.
- The client reconnects automatically if the snapserver restarts or the network drops.

## Supported codecs

The codec is chosen by the snapserver per stream (the `codec` setting in `snapserver.conf`, or `codec=` on the stream source).

| Codec | Supported |
|-------|-----------|
| `flac` (snapserver default) | Yes (requires pyFLAC, installed with LedFx on Python 3.12+) |
| `pcm` | Yes |
| `ogg`, `opus` | No — LedFx reports an audio source error. Change the stream codec to `flac` or `pcm`. |

## Adding a snapserver

Snapcast servers are managed through the [Snapcast Servers API](/apis/snapcast_servers.md). For example, to add a snapserver at `192.168.1.20`:

```bash
curl -X POST http://localhost:8888/api/snapcast/servers \
  -H "Content-Type: application/json" \
  -d '{"id": "living-room", "host": "192.168.1.20", "client_name": "Living Room LEDs"}'
```

Then select `SNAPCAST: living-room` as the audio device in LedFx's audio settings.

The same settings can also be written directly into `config.json` while LedFx is stopped:

```json
"snapcast_servers": {
  "living-room": {
    "host": "192.168.1.20",
    "port": 1704,
    "client_name": "Living Room LEDs"
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `host` | — | Hostname or IP address of the snapserver |
| `port` | `1704` | Snapserver stream port |
| `client_name` | `LedFx` | Name LedFx shows up as in the snapserver's client list |

## Always on

By default (`snapcast_always_on: true` in the global configuration), LedFx stays connected to the selected snapserver even when no audio-reactive effect is running, just like a regular snapclient. LedFx then always appears in the snapserver's client list.

With `snapcast_always_on: false`, LedFx only connects while an audio-reactive effect is active, and disconnects shortly after the last one stops.

## Troubleshooting

- **LedFx is not listed in Snapweb**: check that the audio device is set to the `SNAPCAST:` source and that `ledfx.log` shows `Connected to snapserver`. The snapserver's stream port (1704) must be reachable from the LedFx machine or container.
- **Lights react late or early**: adjust the latency of the LedFx client in Snapweb, the same way as for any other snapclient.
- **"uses the 'opus' codec" error**: see [Supported codecs](#supported-codecs).
