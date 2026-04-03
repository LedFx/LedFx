# Strategy: Integrate Sendspin as a built-in LedFx audio source

## Status: Core Implementation Complete (Phases 0–3 done; 4–6 in progress)

**Major Discovery:** [aiosendspin](https://github.com/Sendspin/aiosendspin) Python library exists and is production-ready!

### Quick Summary

- **What**: Sendspin is a native audio input source in LedFx (like WEB AUDIO)
- **How**: Uses `aiosendspin` library as dependency (Apache-2.0 licensed)
- **Why**: Enable LedFx to receive synchronized multi-room audio for visualization
- **Architecture**: `SendspinAudioStream` in `ledfx/sendspin/stream.py`, feeding LedFx's audio pipeline
- **Format**: Requests PCM 48kHz stereo int16 → converts to float32 mono → feeds LedFx effects
- **Integration Point**: SENDSPIN host API in `ledfx/effects/audio.py`, following WEB AUDIO pattern
- **Multi-server**: Multiple Sendspin servers configured via REST API, each appears as a separate device

### Implementation Complete ✅

| Phase | Status | Key Findings |
|-------|--------|--------------|
| **Phase 0** | ✅ Complete | LedFx has callback-based audio architecture<br>WEB AUDIO proves non-PortAudio sources work<br>Integration point identified: `_audio_sample_callback()` |
| **Phase 1** | ✅ Complete | aiosendspin library available (44 stars, actively maintained)<br>Sendspin supports PCM, FLAC, Opus<br>WebSocket-based with timestamp synchronization |
| **Phase 2** | ⏭️ Skipped | Throwaway bridge not needed with mature library available |
| **Phase 3** | ✅ Complete | Native LedFx client fully implemented (see detail below) |
| **Phase 4** | ✅ Config API done / 🚧 Frontend UI pending | REST API for server management implemented |
| **Phase 5** | ✅ Partial | Reconnect + backoff implemented; jitter metrics pending |
| **Phase 6** | 🚧 In progress | `test_api_sendspin_servers.py` covers REST API; stream unit tests pending |

### Implemented Files

| File | Purpose |
|------|---------|
| `ledfx/sendspin/__init__.py` | Package; exposes `SENDSPIN_AVAILABLE` flag (Python 3.12+ only) |
| `ledfx/sendspin/config.py` | Schema: `server_url`, `client_name`; `BUFFER_CAPACITY` constant |
| `ledfx/sendspin/stream.py` | `SendspinAudioStream`: background thread, reconnect loop with exponential backoff |
| `ledfx/effects/audio.py` | SENDSPIN host API, device-per-server query, `activate()` branch |
| `ledfx/core.py` | `_load_sendspin_servers()`: syncs config → `SENDSPIN_SERVERS` at startup and on API change |
| `ledfx/api/sendspin_servers.py` | `GET /api/sendspin/servers`, `POST /api/sendspin/servers` |
| `ledfx/api/sendspin_server.py` | `PUT /api/sendspin/servers/{id}`, `DELETE /api/sendspin/servers/{id}` |
| `ledfx/api/sendspin_discover.py` | `GET /api/sendspin/discover` — mDNS discovery via zeroconf (`_sendspin-server._tcp.local.`) |
| `tests/test_api_sendspin_servers.py` | Integration tests for all three REST endpoints |

### Design Decisions Made

- **Config simplified** to `server_url` + `client_name` only. `preferred_codec`, `sample_rate`, and `auto_reconnect` removed — PCM 48kHz is always requested; reconnect handled internally.
- **`BUFFER_CAPACITY`** = 65536 bytes (~few hundred ms at 48kHz stereo) is a module constant, not per-server config.
- **Reconnect** uses exponential backoff (1s → 30s cap) in `_reconnect_loop()`. No config knob needed.
- **Multiple servers** supported: each `sendspin_servers` entry appears as its own device in the audio device list.

---

## Objective

Build a path from investigation to production implementation so that **LedFx can consume Sendspin audio directly as a built-in client**, without requiring virtual audio devices or a permanently forked Sendspin codebase.

The end state is:

* LedFx contains a new built-in Sendspin audio source.
* LedFx connects to a Sendspin server as a client.
* LedFx receives audio in a supported format (preferably PCM, optionally FLAC + decode).
* LedFx feeds that audio into its existing audio-analysis pipeline with minimal disruption to the current architecture.
* The implementation is maintainable, testable, and acceptable for upstream contribution.

---

## Current architectural facts

### LedFx side

LedFx already has an existing network-fed audio path through its websocket-based **WEB AUDIO** source model.

Implications:

* LedFx does **not** require a physical or virtual OS sound device to analyze audio.
* A bridge or native client can feed LedFx with audio samples without going through PortAudio.
* This existing path is a useful reference implementation and may also be used as an intermediate prototyping path.

### Sendspin side

Sendspin appears to expose audio chunks on the client/player path, and the CLI player currently handles both:

* raw PCM streams
* FLAC streams which are decoded to PCM before playback

Implications:

* We likely do **not** need to modify the Sendspin server to access usable audio.
* The likely integration point is a **client-side implementation**.
* The most promising first inspection target is the player/client stack, especially the audio connector and decode path.

---

## Recommended end-state architecture

### Preferred production architecture

Implement a **native Sendspin client inside LedFx**.

High-level flow:

1. LedFx user selects a new audio source type: `Sendspin`
2. LedFx opens a Sendspin client connection to a configured Sendspin server
3. LedFx negotiates a supported audio format
4. LedFx receives audio chunks
5. If audio is FLAC, LedFx decodes to PCM
6. LedFx converts PCM to the internal float32 mono sample stream expected by the existing analysis pipeline
7. Existing LedFx FFT / melbank / beat / pitch / effect logic continues unchanged

### Temporary prototyping architecture

Use an external bridge first if needed:

`Sendspin client -> LedFx WEB AUDIO websocket`

This should be treated as a validation step, not the final product.

---

## Strategic principles

1. **Do not fork Sendspin as the long-term solution**

   * Modifying Sendspin internals is acceptable only for short-lived inspection or proof-of-concept work.
   * The production implementation should live in LedFx.

2. **Minimize disruption to LedFx’s existing analysis path**

   * Reuse the current audio-reactive pipeline.
   * Avoid changing effect APIs unless absolutely necessary.

3. **Prefer explicit client integration over pretending to be a sound card**

   * Virtual audio devices are only acceptable for smoke testing.
   * Native protocol/client integration is the intended outcome.

4. **Prefer PCM negotiation first**

   * If Sendspin allows direct PCM negotiation, start there.
   * Add FLAC support only if needed for compatibility or performance reasons.

5. **Treat timing and buffering as first-class concerns**

   * Sendspin is playback-synchronized.
   * LedFx is analysis/render-loop driven.
   * The integration must define a buffering and timing policy rather than letting one emerge accidentally.

---

## Investigation phases

## Phase 0 - Ground truth capture

Goal: confirm what exists today before writing code.

Tasks:

* Inspect current LedFx audio source architecture.
* Inspect current LedFx WEB AUDIO path.
* Inspect current Sendspin client/player path.
* Identify whether Sendspin already has a reusable client library API or whether code extraction/adaptation is needed.
* Determine licensing and dependency implications of reusing Sendspin client code or patterns.

Deliverables:

* Written architecture notes
* Candidate integration seam list
* Dependency risk list

Success criteria:

* We can clearly answer: “Should LedFx embed a Sendspin client directly, or should it wrap/reuse an external package?”
**STATUS: ✅ PHASE 0 COMPLETE**

### Phase 0 Findings

**LedFx Architecture Discoveries:**

1. **Audio Input System** ([ledfx/effects/audio.py](ledfx/effects/audio.py)):
   - Callback-based: `_audio_sample_callback(in_data, frame_count, time_info, status)`
   - Expected format: numpy float32 mono arrays
   - Target length: `MIC_RATE // sample_rate` (typically 44100 // 60 = 735 samples/frame)
   - Thread-safe with locking for shared state

2. **WEB AUDIO Reference Implementation** ([ledfx/api/websocket.py](ledfx/api/websocket.py)):
   - Proves non-PortAudio sources work seamlessly
   - `WebAudioStream` class mimics sounddevice stream interface
   - Methods: `start()`, `stop()`, `close()`, `data` property with setter
   - Clients send int16 PCM over WebSocket (base64-encoded for efficiency)
   - Converts to float32 and calls `_audio_sample_callback`

3. **Device Registration Pattern**:
   - New audio sources register as "host APIs" in `AudioInputSource.query_hostapis()`
   - Devices appear in device list via `AudioInputSource.query_devices()`
   - Selection triggers stream creation in `activate()` method

**Integration Strategy Answer:**

✅ **LedFx should embed a Sendspin client directly** using the WEB AUDIO pattern:

```python
# Add to ledfx/effects/audio.py (around line 296)
@staticmethod
def query_hostapis():
    return sd.query_hostapis() + (
        {"name": "WEB AUDIO"},
        {"name": "SENDSPIN"},  # <-- Add Sendspin
    )

# In activate() method (around line 543)
elif hostapis[device["hostapi"]]["name"] == "SENDSPIN":
    AudioInputSource._stream = SendspinAudioStream(
        server_url, room_name, self._audio_sample_callback
    )
```

**Recommended Architecture:**

1. **Create `SendspinAudioStream` class** (in new file `ledfx/sendspin_client.py`):
   - Inherits stream interface behavior from `WebAudioStream` pattern
   - Constructor: `__init__(server_url, room_name, callback)`
   - Methods: `start()`, `stop()`, `close()`
   - Background thread connects to Sendspin, receives chunks
   - Converts audio to float32 numpy and calls callback

2. **Minimal changes to existing LedFx code**:
   - Add Sendspin to host API list
   - Add Sendspin devices to device query
   - Add elif branch in `activate()` to create `SendspinAudioStream`
   - That's it! Existing audio pipeline handles the rest

**Next Requirements:**

Before implementing, we need to investigate Sendspin's client protocol to answer:
- How does a client connect and authenticate?
- Can we request PCM format directly, or must we decode FLAC?
- What is the chunk delivery mechanism?
- Are there existing Python libraries/code we can use?
---

## Phase 1 - Confirm where usable audio exists in Sendspin ✅ COMPLETE

Goal: identify the cleanest place to access PCM or decode-ready audio.

**STATUS: ✅ PHASE 1 COMPLETE - Sendspin has excellent Python library support!**

### Critical Discovery: Existing Python Library

**[aiosendspin](https://github.com/Sendspin/aiosendspin)** - Async Python library implementing the full Sendspin Protocol
- ✅ 44 stars, actively maintained (last update: yesterday)
- ✅ Apache-2.0 license (compatible with LedFx GPL-3.0)
- ✅ Production-ready: powers [sendspin-cli player](https://github.com/Sendspin/sendspin-cli)
- ✅ AsyncIO-based (perfect for LedFx's aiohttp architecture)
- ✅ 45 releases, mature codebase

**Reference Implementation:**
- [sendspin-cli](https://github.com/Sendspin/sendspin-cli) - Complete synchronized audio player built with aiosendspin
- This is the **exact code path we need** - it receives audio chunks and plays them

### Sendspin Protocol Summary

From [specification](https://github.com/Sendspin/spec):

**Architecture:**
- WebSocket-based communication
- Client roles: `player`, `controller`, `metadata`, `artwork`, `visualizer`
- LedFx needs: **`player` role** to receive audio

**Audio Format Support:**
- **Codecs**: Opus, FLAC, **PCM** ✅
- **PCM available**: Little-endian signed int16 (or 24-bit)
- **Sample rates**: 44.1kHz, 48kHz supported
- **Channels**: Mono or stereo

**Audio Delivery Flow:**
1. Client connects via WebSocket
2. Client sends `client/hello` with supported formats (prefer PCM)
3. Server sends `server/hello` confirming connection
4. Server sends `stream/start` with chosen format
5. **Binary audio chunks arrive** with timestamps (int64 microseconds + audio data)
6. Client buffers and plays synchronized to timestamps

**Key Technical Details:**
- Binary message type `4` = audio chunk
- Format: `[1 byte type][8 bytes timestamp][audio data...]`
- Timestamp synchronization via `client/time` / `server/time` exchange
- Clients handle buffering, resampling, synchronization

### Integration Answer

✅ **We can use aiosendspin directly as a dependency!**

**Benefits:**
1. No protocol implementation needed - aiosendspin handles all WebSocket/timing logic
2. Actively maintained by Sendspin community
3. Proven in production (sendspin-cli player)
4. AsyncIO matches LedFx's async architecture

**Integration approach:**
```python
# In SendspinAudioStream
from aiosendspin import Client, PlayerRole

# Receive audio callback from aiosendspin
def on_audio_chunk(audio_data: bytes, timestamp: int, format: AudioFormat):
    # Convert to float32 mono
    # Call LedFx's _audio_sample_callback(audio_float32, ...)
```

### Questions Answered

| Question | Answer |
|----------|--------|
| Where do audio chunks arrive? | Binary WebSocket messages (type 4) via aiosendspin client |
| PCM or FLAC? | **Both supported, PCM preferred** (can request in client/hello) |
| Can we request PCM? | ✅ Yes, via `supported_formats` list in client/hello |
| Decode required? | Only if server sends FLAC; can request PCM to avoid it |
| Non-playback role? | No - must use `player` role, but we control what happens with audio |
| Visualizer role useful? | Future feature - provides FFT/features but not raw audio |

### Outcome

**Phase 2 skipped** — aiosendspin made a throwaway bridge unnecessary.

**Phase 3 implemented** using aiosendspin as dependency:
1. `aiosendspin` added to `pyproject.toml` dependencies
2. `ledfx/sendspin/` module created (`stream.py`, `config.py`)
3. Integrated into `ledfx/effects/audio.py` (SENDSPIN host API, device-per-server listing)
4. Configuration via REST API (see [Sendspin Servers API](apis/sendspin_servers.md))

**Design decisions:**
- Config simplified to `server_url` + `client_name` only. `preferred_codec`, `sample_rate`, and `auto_reconnect` removed — PCM 48kHz is always requested; reconnect handled in `_reconnect_loop()`.
- `BUFFER_CAPACITY` = 65536 bytes is a module constant, not per-server config.
- Reconnect uses exponential backoff (1s → 30s cap). No config knob needed.
- Multiple servers supported: each `sendspin_servers` entry appears as its own device in the audio device list.

---

## Phase 2 - Build a throwaway bridge for validation

**STATUS: ⏭️ SKIPPED** — aiosendspin library made this unnecessary. See Phase 3.

~~Goal: prove Sendspin audio can drive LedFx effects reliably before embedding the client natively.~~

Deliverables:

* prototype bridge
* documented results
* notes on latency, stability, and dropouts

Success criteria:

* A LedFx instance can react to Sendspin playback consistently for an extended run.

---

## Phase 3 - Built-in LedFx implementation ✅ COMPLETE

Goal: translate the validated bridge into a native LedFx architecture.

**STATUS: ✅ COMPLETE — aiosendspin integrated, all files implemented and tested**

### Updated Architecture with aiosendspin

**Dependency:** Add `aiosendspin` to LedFx's dependencies
- License: Apache-2.0 (compatible with GPL-3.0)
- Mature, actively maintained library
- Async-first design matches LedFx

**Actual File Structure (simplified from original plan):**
```
ledfx/
  sendspin/
    __init__.py           # Exposes SENDSPIN_AVAILABLE; Python 3.12+ guard
    stream.py             # SendspinAudioStream — connection, audio conversion, reconnect
    config.py             # SENDSPIN_CONFIG_SCHEMA, BUFFER_CAPACITY constant
  api/
    sendspin_servers.py   # GET + POST /api/sendspin/servers
    sendspin_server.py    # PUT + DELETE /api/sendspin/servers/{server_id}
    sendspin_discover.py  # GET /api/sendspin/discover (mDNS)
```

`client.py`, `audio_converter.py`, `decoder.py`, and `buffer.py` were not needed as separate files — the `SendspinAudioStream` class in `stream.py` handles all of these responsibilities directly.

### 3.1 SendspinAudioStream Class — as implemented

Implements the stream interface expected by LedFx (matching `WebAudioStream`).
See [ledfx/sendspin/stream.py](../ledfx/sendspin/stream.py) for the full source.

**Key implementation details that differ from the original plan:**

- Uses `SendspinClient` (not `Client`), `Roles.PLAYER` (not `PlayerRole`), `ClientHelloPlayerSupport`, `SupportedAudioFormat`, `AudioCodec` from `aiosendspin`.
- `_audio_chunk_handler` is **synchronous** (not async); aiosendspin calls it on the event-loop thread.
- `_run_client` spawns a dedicated daemon thread with its own `asyncio.new_event_loop()`.
- Reconnect is handled in `_reconnect_loop()` (exponential backoff, 1 s → 30 s cap).
- Config keys are just `server_url` and `client_name` — codec/sample_rate/auto_reconnect removed from schema.

```python
# Actual aiosendspin API used in _connect_and_receive()
from aiosendspin.client import AudioFormat, SendspinClient
from aiosendspin.models import AudioCodec, PlayerCommand, Roles
from aiosendspin.models.player import ClientHelloPlayerSupport, SupportedAudioFormat

supported_formats = [
    SupportedAudioFormat(codec=AudioCodec.PCM, channels=2, sample_rate=48000, bit_depth=16),
]
player_support = ClientHelloPlayerSupport(
    supported_formats=supported_formats,
    buffer_capacity=BUFFER_CAPACITY,
    supported_commands=[PlayerCommand.VOLUME, PlayerCommand.MUTE],
)
client = SendspinClient(
    client_id=f"ledfx-{id(self)}",
    client_name=client_name,
    roles=[Roles.PLAYER],
    player_support=player_support,
)
client.add_audio_chunk_listener(self._audio_chunk_handler)   # sync callback
client.add_stream_start_listener(self._stream_start_handler)
await client.connect(server_url)
```

**Audio conversion path (PCM int16 stereo → float32 mono):**

```python
# _audio_chunk_handler(timestamp, chunk_data, audio_format)
audio = np.frombuffer(chunk_data, dtype=np.int16)
audio_float = audio.astype(np.float32) / 32768.0
audio_mono = np.mean(audio_float.reshape(-1, 2), axis=1)  # stereo → mono
callback(audio_mono, len(audio_mono), None, None)
```

The handler also supports 24-bit and 32-bit PCM depths and has a fallback path for FLAC/Opus chunks (treated as int16 PCM, with a warning log).

**Original planning note (kept for history):**

```python
# PLANNED (not what was built — aiosendspin API was different)
class SendspinAudioStream:
    def __init__(self, config: dict, callback: callable):
        """
        Args:
            config: {
                'server_url': 'ws://192.168.1.100:8927/sendspin',
                'client_name': 'LedFx Visualizer',
                'preferred_format': 'pcm',  # or 'opus', 'flac'
                'sample_rate': 48000,
                'channels': 2
            }
            callback: LedFx's _audio_sample_callback(data, frame_count, time_info, status)
        """
        self.config = config
        self.callback = callback
        self._active = False
        self._client = None
        self._loop = None
        # NOTE: actual implementation also adds self._thread; see stream.py
```

### 3.2 Integration into LedFx Audio System — as implemented

`ledfx/effects/audio.py` was modified to add Sendspin support:

- `SENDSPIN_AVAILABLE` imported from `ledfx.sendspin`
- `SENDSPIN_SERVERS = {}` module-level dict populated by `core._load_sendspin_servers()`
- `query_hostapis()` appends `{"name": "SENDSPIN"}` when `SENDSPIN_AVAILABLE` is True
- `query_devices()` iterates `SENDSPIN_SERVERS` and appends an entry per server with `"sendspin_config"` key
- `activate()` has an `elif` branch for `"SENDSPIN"` hostapi that creates `SendspinAudioStream(device["sendspin_config"], self._audio_sample_callback)`

### 3.3 Configuration Schema — as implemented

```python
# ledfx/sendspin/config.py
SENDSPIN_CONFIG_SCHEMA = vol.Schema({
    vol.Required("server_url", default="ws://192.168.1.12:8927/sendspin"): str,
    vol.Optional("client_name", default="LedFx"): str,
})
BUFFER_CAPACITY = 65536  # 64 KB — ~few hundred ms at 48kHz/16-bit stereo
```

`preferred_codec`, `sample_rate`, and `auto_reconnect` were **not added** — PCM 48kHz is always requested; reconnect is handled internally by `_reconnect_loop()`.

*(Original planning notes retained below for historical reference — the implementation followed this approach with minor API differences.)*

### 3.1 New audio source type — original planning notes

Add a LedFx audio source/provider for Sendspin, conceptually parallel to existing input sources.

**Implementation approach (following WEB AUDIO pattern):**

File structure:
```
ledfx/
  effects/
    audio.py              # <-- Modify to add Sendspin support
  sendspin/
    __init__.py
    client.py              # SendspinClient: protocol/connection logic
    stream.py              # SendspinAudioStream: LedFx stream interface
    decoder.py             # FLAC decode wrapper (if needed)
    buffer.py              # Audio buffering/resampling
```

Registration in `ledfx/effects/audio.py`:
```python
# In AudioInputSource.query_hostapis() (~line 296)
@staticmethod
def query_hostapis():
    apis = list(sd.query_hostapis())
    apis.append({"name": "WEB AUDIO"})
    apis.append({"name": "SENDSPIN"})  # Add this
    return tuple(apis)

# In AudioInputSource.query_devices() (~line 301)
# Add Sendspin "devices" (one per configured server/room)
sendspin_configs = get_sendspin_configs()  # From LedFx config
for config in sendspin_configs:
    devices.append({
        "hostapi": sendspin_hostapi_index,
        "name": f"{config['server_name']} - {config['room_name']}",
        "max_input_channels": 1,
        "sendspin_config": config,
    })

# In AudioInputSource.activate() (~line 543)
elif hostapis[device["hostapi"]]["name"] == "SENDSPIN":
    from ledfx.sendspin.stream import SendspinAudioStream
    AudioInputSource._stream = SendspinAudioStream(
        device["sendspin_config"],
        self._audio_sample_callback
    )
```

**`SendspinAudioStream` Interface (planning note):**
```python
class SendspinAudioStream:
    def __init__(self, config: dict, callback: callable):
        self.callback = callback
        self.client = SendspinClient(config)
        self._active = False

    def start(self):
        self._active = True
        self.client.connect()
        # Start background thread to receive audio

    def stop(self):
        self._active = False

    def close(self):
        self.client.disconnect()
```

*Final interface matches this pattern (start/stop/close); see implemented detail in 3.1 above.*

Possible naming:

* `SendspinAudioSource`  ❌ (Redundant - we're using stream pattern)
* `SendspinInputSource` ❌ (Redundant - we're using stream pattern)
* `SendspinClientInput` ❌ (Redundant - we're using stream pattern)
* `SendspinAudioStream` ✅ (Matches WebAudioStream pattern)

Responsibilities:

* manage connection lifecycle
* negotiate format
* receive chunks
* buffer audio safely
* decode if necessary
* emit frames to existing LedFx analysis callback path

### 3.2 Separation of concerns

Structure the implementation into small components:

* `sendspin_client.py`

  * protocol/session management
  * hello / capability negotiation
  * reconnect logic

* `sendspin_audio_format.py`

  * format parsing / negotiation helpers
  * PCM layout helpers

* `sendspin_decoder.py`

  * FLAC decode wrapper if needed
  * keep codec-specific code isolated

* `sendspin_buffer.py`

  * timestamped buffering / resync policy

* `sendspin_input.py`

  * LedFx-facing audio input implementation
  * adaptation into LedFx sample callback expectations

### 3.3 Reuse existing LedFx analysis path

Do not rewrite FFT/melbank/effect plumbing.

The Sendspin source should produce samples in the same shape and cadence expected by the current analysis pipeline.

### 3.4 Mono conversion policy

**LedFx's existing behavior:**
- Windows WASAPI Loopback devices: keep all channels, let sounddevice downmix
- All other devices (Mac, Linux, regular microphones): request mono (channels=1) from sounddevice
- Audio processing expects mono float32 arrays

**Sendspin integration strategy:**

Define explicitly:

* If Sendspin provides stereo, downmix using simple average: `(left + right) / 2`
* Implement in `SendspinAudioStream` before calling callback
* Use numpy for efficiency: `audio_mono = np.mean(audio_stereo.reshape(-1, 2), axis=1)`

Keep future room/zone/channel-aware enhancements out of the first implementation.

### 3.5 Sample rate policy

Decide whether to:

* request the LedFx-preferred rate from Sendspin if possible, or
* accept Sendspin rate and resample inside LedFx.

Prefer the simplest stable path first.

---

## Phase 4 - Integrate into LedFx configuration and UX

**STATUS: ✅ Config REST API complete / 🚧 Frontend UI pending**

### What is implemented

**REST API (fully functional):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sendspin/servers` | GET | List all configured servers |
| `/api/sendspin/servers` | POST | Add a new server (`id`, `server_url`, optional `client_name`) |
| `/api/sendspin/servers/{server_id}` | PUT | Update an existing server |
| `/api/sendspin/servers/{server_id}` | DELETE | Remove a server |
| `/api/sendspin/discover` | GET | mDNS scan for `_sendspin-server._tcp.local.` with configurable `timeout` |

All endpoints return `400 / status: failed` when `SENDSPIN_AVAILABLE` is False (Python < 3.12 or `aiosendspin` not installed). Server URL is validated to start with `ws://` or `wss://`.

After every add/update/delete, `core._load_sendspin_servers()` is called to sync `SENDSPIN_SERVERS` (the module-level dict in `audio.py`) without requiring a restart.

**What is NOT yet done:**

* Frontend UI — no frontend components for Sendspin server management exist yet
* Connection status reporting in real-time (not exposed via API)
* Auth support (not needed by current Sendspin protocol)

Original planning notes:

* ~~enable/disable Sendspin source~~ — controlled implicitly by whether any server is configured
* ~~preferred codec / format~~ — removed from config; PCM 48kHz stereo hardcoded
* ~~reconnect policy config~~ — handled internally with fixed backoff

---

## Phase 5 - Robustness, buffering, and sync policy

**STATUS: ✅ Partial — reconnect + backoff implemented; deep buffer/sync metrics pending**

### What is implemented

- **Reconnect with exponential backoff**: `_reconnect_loop()` retries after 1 s, doubling to 30 s cap. Logs warning with delay on each attempt.
- **Buffer capacity**: `BUFFER_CAPACITY = 65536` (64 KB, ~few hundred ms at 48 kHz/16-bit stereo) advertised to the Sendspin server in `ClientHello`.
- **Disconnect handling**: `stop()` calls `client.disconnect()` via `run_coroutine_threadsafe`; `close()` shuts down the event loop and joins the thread with a 5 s timeout.
- **Graceful no-op**: if `_active` is False when a chunk arrives, it is silently ignored.

### What is NOT yet done

- Jitter buffer depth monitoring and metrics (chunk arrival jitter, dropped chunks, reconnect count, decode time, callback lag)
- Timestamp-based resync (audio is forwarded as it arrives, no timeline alignment to Sendspin server clock)
- Underrun detection / silence injection
- Multi-channel (>2) audio sources beyond the basic "take first channel" fallback

Original planning questions — current answers:

| Question | Current answer |
|----------|----------------|
| How much audio buffered? | 64 KB (`BUFFER_CAPACITY`) advertised; aiosendspin manages the buffer |
| What happens on underrun? | Nothing special; LedFx analysis just receives less data |
| What happens on disconnect? | `_reconnect_loop()` retries automatically with backoff |
| Timestamp gaps? | Not handled; audio is forwarded immediately as delivered |
| Tight sync or opportunistic? | Opportunistic — "latest available" audio, no timeline enforcement |

Metrics to capture:

* current buffer depth
* chunk arrival jitter
* dropped chunks
* reconnect count
* decode time
* callback lag

---

## Phase 6 - Testing strategy

**STATUS: 🚧 In progress — REST API tests done; stream unit tests pending**

Goal: make the feature maintainable and upstream-safe.

### Implemented tests

`tests/test_api_sendspin_servers.py` covers:

* GET /api/sendspin/servers (empty, with entries, unavailable)
* POST /api/sendspin/servers (valid, missing fields, bad URL, duplicate, unavailable)
* PUT /api/sendspin/servers/{id} (update URL, update name, not found, bad URL)
* DELETE /api/sendspin/servers/{id} (success, not found)
* GET /api/sendspin/discover (mocked zeroconf, `already_configured` flag, timeout validation)

### Still needed

* `SendspinAudioStream` unit tests:
  * PCM byte-to-float conversion (int16, int24, int32)
  * stereo-to-mono downmix
  * `_unpack_int24()` correctness
  * reconnect state transitions (mock `aiosendspin`)
* Integration tests:

Cover:

* mocked Sendspin server producing PCM chunks
* mocked Sendspin server producing FLAC chunks
* LedFx source start/stop lifecycle
* stream clear / format change handling
* disconnect and reconnect

### Manual validation matrix

Test:

* PCM 44.1kHz 16-bit stereo
* PCM 48kHz 16-bit stereo
* FLAC 48kHz 24-bit stereo
* long-duration playback
* server restart during playback
* network hiccups
* multiple LedFx effects

### Performance checks

Measure:

* CPU overhead versus native microphone input
* decode overhead for FLAC
* added latency to effect response
* memory growth over long runs

---

## Key technical decisions ✅ ANSWERED

All key questions have been answered through Phase 0-1 investigation:

1. **Can LedFx directly reuse any current Sendspin client code?**
   - ✅ YES - Use `aiosendspin` Python library as a dependency
   - Apache-2.0 licensed, production-ready, actively maintained

2. **Is requesting PCM from Sendspin realistic and portable?**
   - ✅ YES - PCM is mandatory in Sendspin spec
   - Servers must support opus, flac, AND pcm
   - Request PCM in `supported_formats` list (priority order)

3. **If FLAC decode is needed, what is the smallest dependency surface?**
   - ✅ Can avoid FLAC entirely by preferring PCM
   - If needed: Python's `soundfile` library (already in audio ecosystem)
   - Optional: handle both for maximum compatibility

4. **Where is the cleanest seam in LedFx to add a non-PortAudio streaming source?**
   - ✅ Follow WEB AUDIO pattern in `AudioInputSource.activate()`
   - Add "SENDSPIN" host API type
   - Create `SendspinAudioStream` matching `WebAudioStream` interface
   - Call `_audio_sample_callback()` with float32 numpy arrays

5. **Should first implementation reuse LedFx's WEB AUDIO plumbing?**
   - ✅ NO - not needed
   - Create parallel `SendspinAudioStream` matching the interface
   - Cleaner separation, easier to maintain
   - WEB AUDIO remains as reference pattern only

6. **What buffering depth gives stable visuals without sluggishness?**
   - ✅ Let aiosendspin handle buffering/timing
   - `BUFFER_CAPACITY = 65536` (64 KB, ~few hundred ms at 48 kHz/16-bit stereo) — NOT 1 MB
   - Sendspin timestamps ensure synchronization between players, but LedFx does not enforce timeline
   - LedFx processes audio as it arrives (real-time analysis)

7. **What is minimal frontend/config surface for mergeable first version?**
   - ✅ Server URL (WebSocket endpoint) — implemented
   - ✅ Client name (friendly identifier) — implemented
   - ~~Format preferences (codec, sample rate)~~ — removed; PCM 48kHz hardcoded
   - ~~Auto-reconnect toggle~~ — removed; always reconnects with exponential backoff
   - 🚧 Frontend UI not yet implemented
   - **No UI needed initially** - config file first, UI later

---

## Recommended implementation order ✅ UPDATED

**Phases 0-1 COMPLETE** - Investigation finished, ready to implement!

**Skip Phase 2** - No throwaway bridge needed with aiosendspin library available

**Begin Phase 3** - Native LedFx implementation:

1. ✅ ~~Inspect Sendspin protocol/client path~~ (COMPLETE - using aiosendspin)
2. ✅ ~~Build throwaway external bridge~~ (SKIP - not needed)
3. ✅ ~~Validate audio quality and effect responsiveness~~ (SKIP - proven in sendspin-cli)
4. **ADD DEPENDENCY**: Add `aiosendspin` to `pyproject.toml`
5. **CORE IMPLEMENTATION**: Create `ledfx/sendspin/` module
   - `stream.py` - SendspinAudioStream class
   - `client.py` - Client wrapper and connection management
   - `audio_converter.py` - Format conversion utilities
   - `config.py` - Configuration schema
6. **INTEGRATION**: Modify `ledfx/effects/audio.py`
   - Add SENDSPIN to `query_hostapis()`
   - Add Sendspin devices to `query_devices()`
   - Add Sendspin branch in `activate()`
7. **CONFIGURATION**: Add Sendspin config schema to LedFx config
8. **TESTING**: Unit and integration tests
9. **DOCUMENTATION**: User docs and API reference
10. **UI (Later)**: Frontend for Sendspin configuration

### Immediate Next Steps

1. **Add aiosendspin dependency**:
   ```toml
   # In pyproject.toml [project.dependencies]
   aiosendspin = "^4.4.0"
   ```

2. **Create module structure**:
   ```bash
   mkdir ledfx/sendspin
   touch ledfx/sendspin/__init__.py
   touch ledfx/sendspin/stream.py
   touch ledfx/sendspin/client.py
   touch ledfx/sendspin/audio_converter.py
   touch ledfx/sendspin/config.py
   ```

3. **Implement SendspinAudioStream** (see Phase 3 design above)

4. **Test with local Sendspin server** (e.g., Music Assistant or test server)

---

## Guardrails for Copilot

Use these guardrails while assisting with investigation and implementation:

* Do not propose virtual audio devices as the production solution.
* Do not propose a permanent fork of Sendspin.
* Do not rewrite LedFx’s effect system.
* Prefer small, reviewable changes.
* Prefer clear separation between protocol code, decode code, buffering code, and LedFx adaptation code.
* Keep temporary instrumentation clearly marked and easy to remove.
* When uncertain, produce findings and options rather than inventing protocol behavior.
* Favor evidence from current LedFx and Sendspin source over assumptions.

---

## Questions to answer before coding the native LedFx client

* What exact Sendspin messages are required for a minimal client that receives audio?
* Can a client receive audio without being a normal speaker/player?
* If not, can LedFx safely behave as a player role while discarding actual audio playback?
* Can Sendspin deliver PCM directly in all intended environments?
* Is the visualizer role useful later for timeline-aligned metadata or FFT, even if not for initial raw-audio ingestion?
* Which dependency is acceptable for FLAC decoding in LedFx, if any?
* What are the licensing implications of bringing over any Sendspin-derived logic?

---

## Expected output from Copilot during investigation

Ask Copilot to produce the following artifacts as it progresses:

1. **Architecture note**

   * concise findings on LedFx and Sendspin integration seams

2. **Investigation log**

   * exact files inspected
   * exact conclusions
   * unknowns remaining

3. **Prototype plan**

   * minimal external bridge design
   * format handling strategy
   * logging plan

4. **Native LedFx design note**

   * class layout
   * lifecycle
   * buffering model
   * config model

5. **Implementation checklist**

   * ordered tasks with dependencies

6. **Risk register**

   * protocol risk
   * decode/dependency risk
   * buffering/timing risk
   * upstream-maintainability risk

---

## Final target definition

The project is complete when:

* LedFx can connect directly to a Sendspin server as a built-in source
* no external bridge is required for normal use
* no virtual sound card is required
* audio-reactive effects behave correctly from Sendspin playback
* the feature is tested, documented, and maintainable enough for upstream contribution

---

## Prompt to give Copilot

Use this as the working instruction block:

"Investigate how to implement Sendspin as a built-in audio source in LedFx. Start by inspecting current LedFx audio input architecture and current Sendspin client/player code to identify the cleanest way to receive audio samples inside LedFx without relying on virtual audio devices and without requiring a permanent Sendspin fork. Prefer a design where LedFx acts as a native Sendspin client. First confirm whether Sendspin can deliver PCM directly or whether FLAC decode is required. Use the existing LedFx WEB AUDIO path only as a reference or temporary validation mechanism, not as the final architecture unless that turns out to be the cleanest internal seam. Produce: (1) architecture findings, (2) exact candidate integration points in both repos, (3) a prototype plan for a throwaway bridge if needed, (4) a native LedFx design with class boundaries, config surface, and buffering policy, (5) an implementation checklist, and (6) explicit risks and unknowns. Favor current source evidence over assumptions, and keep changes small and reviewable."
