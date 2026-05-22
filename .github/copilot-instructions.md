# Copilot Instructions for LedFx

LedFx is a real-time LED visualization system syncing audio input to networked LED devices (WLED, ESP8266/ESP32, E1.31, etc.).

## Commands

**CRITICAL**: Always use `uv run`. Never use bare `python`, `pip`, or `pytest`.

- Tests: `uv run pytest ...`
- Scripts: `uv run python ...`
- Linting: `uv run black ...`, `uv run flake8 ...`
- Packages: `uv sync`, `uv add` (not `pip install`)

## Key Structure

```
ledfx/
├── api/          # REST endpoints (one RestEndpoint class per file)
├── devices/      # Device drivers (WLED, E1.31, DDP, ArtNet, Serial, OpenRGB)
├── effects/      # 50+ effect implementations
├── integrations/ # External service integrations
├── color.py      # Color utilities
├── core.py       # App orchestrator
├── utils.py      # BaseRegistry (base for all effects/devices)
└── virtuals.py   # Virtual LED strip management
```

## Effect Pattern

All effects inherit from `Effect` (extends `BaseRegistry`). Modify `self.pixels` in `render()`.

```python
class MyEffect(Effect):
    NAME = "My Effect"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("speed", default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
    })
    def render(self):
        pass  # modify self.pixels
```

## Device Pattern

All devices inherit from `BaseRegistry`. Implement `flush()` for data transmission. Base classes: `Device`, `NetworkedDevice`, `UDPDevice`, `SerialDevice`.

## REST API Standards

**CRITICAL**: Each file in `ledfx/api/` must have exactly ONE `RestEndpoint` class (RegistryLoader auto-discovery). For multiple related endpoints, create separate files (e.g., `cache_images.py` + `cache_images_refresh.py`).

**Never use `web.json_response()` directly.** Use helper methods:
- `await self.request_success(type, message, data=None)` — with snackbar feedback
- `await self.bare_request_success(data)` — no snackbar
- `await self.invalid_request(message, type="error")` — returns HTTP 200 with `status:"failed"`
- `await self.json_decode_error()` — in `except JSONDecodeError`

## Code Standards

- **Imports**: Always at top of file; no inline/local imports except for circular dependency avoidance.
- **Paths**: Use `os.path` only — `os.path.join()`, `os.path.exists()`, `os.makedirs()`, `os.remove()`. **Never use `pathlib`.**
- **Logging**: `_LOGGER.warning()` for client errors; `_LOGGER.error()` for system errors only (avoid Sentry noise).
- **NumPy**: Vectorized operations for pixel manipulation; protect shared state with `self.lock`.
- **Formatting**: black + flake8 (E501 relaxed) + isort.

## Security Testing

For input validation tests (paths, URLs), cover: path traversal (`../`, encoded variants, null bytes), URL injection, reserved filenames (CON, PRN, NUL), SSRF (loopback, private networks).

## Debugging Libraries

**CRITICAL**: Never assume a library is broken. Before concluding a bug exists:
1. `uv pip show <package>` — check metadata and docs URL
2. Read README in `.venv/Lib/site-packages/<package>*.dist-info/`
3. Test the exact documented example first
4. Compare your data types/shapes to documented API (e.g., float32 vs float64, array axis order)

Only after exhausting the above: create a minimal repro and file an issue.