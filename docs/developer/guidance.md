
# Guidance: Extract LedFx audio device change monitor into a tiny PyPI lib (uv workflow)

This document describes how to extract the audio device change detection introduced in LedFx PR #1725 into a **platform-agnostic PyPI dependency**. The new library should do **one thing**: detect “audio device topology changed” on Windows/macOS/Linux and invoke a user callback (debounced/coalesced). LedFx will keep responsibility for **PortAudio refresh** and any **LedFx event/websocket** behavior.

---

## Goals

- Create a new PyPI package (working name): **audio-hotplug**
  - Import name: **audio_hotplug**
- Provide a minimal, stable API:
  - A factory to create the correct platform monitor
  - A monitor object with `start()` and `stop()`
  - Callback is invoked on the provided asyncio loop thread (or safely in sync mode)
  - Debounce/coalesce by default (avoid burst storms)
- Use **uv** for environment + dependency management
- Add isolated unit tests (do NOT rely on OS audio events)
- Publish to TestPyPI then PyPI
- Modify LedFx to depend on and use the new library (without moving PortAudio refresh into the library)

---

## Recommended minimal API surface (v0.1)

### Public API (ONLY these two exports)

```python
# audio_hotplug/__init__.py
from .monitor import create_monitor
from ._base import AudioDeviceMonitor

__all__ = ["create_monitor", "AudioDeviceMonitor"]
```

### Factory

```python
def create_monitor(
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    debounce_ms: int = 200,
    logger: logging.Logger | None = None,
) -> AudioDeviceMonitor | None:
    """
    Create a platform-appropriate audio device change monitor.
    Returns None if platform unsupported.
    """
```

### Monitor interface

```python
Callback = Callable[[], None] | Callable[[], Awaitable[None]]

class AudioDeviceMonitor(ABC):
    def start(self, on_change: Callback) -> None:
        """Start monitoring. on_change will be invoked (debounced) when change detected."""

    def stop(self) -> None:
        """Stop monitoring. Safe to call multiple times."""
```

### Behavior contract

- The monitor detects **device list changes** (hot-plug, default device changes, etc.).
- The monitor calls `on_change` after coalescing bursts using `debounce_ms` (default 200ms).
- If an asyncio `loop` is provided, callback is scheduled onto that loop thread safely:
  - sync callback → `loop.call_soon_threadsafe(cb)`
  - async callback → `asyncio.run_coroutine_threadsafe(cb(), loop)`
- If no loop is provided:
  - if there is a running loop at `start()`, use it
  - otherwise: allow sync callbacks to run directly; reject async callbacks with a clear error
- The library never enumerates audio devices and never refreshes PortAudio/sounddevice.

---

## New package: repository layout (src layout)

```
audio-hotplug/
  pyproject.toml
  README.md
  LICENSE
  src/
    audio_hotplug/
      __init__.py
      monitor.py
      _base.py
      _debounce.py
      _platform/
        __init__.py
        windows.py
        macos.py
        linux.py
  tests/
    test_debounce.py
    test_callback_scheduling.py
    test_factory.py
  examples/
    monitor_print.py
  .github/workflows/
    ci.yml
```

---

## uv-based workflow

### Create venv + sync deps

```bash
uv venv
uv sync --extra test
```

### Run tests

```bash
uv run pytest -q
```

### Run example

```bash
uv run python examples/monitor_print.py
```

### Build package

```bash
uv add --dev build
uv run python -m build
```

### Twine check + publish

```bash
uv add --dev twine
uv run twine check dist/*
# TestPyPI first:
uv run twine upload --repository testpypi dist/*
# Then PyPI:
uv run twine upload dist/*
```

---

## Dependency strategy (recommended)

Use platform markers in the library so downstream apps (LedFx) only need:

```
audio-hotplug>=0.1.0
```

In `pyproject.toml` for the new lib, add dependencies like:

- Windows: `pycaw; platform_system=='Windows'`
- macOS: `pyobjc-framework-CoreAudio; platform_system=='Darwin'`
- Linux: `pyudev; platform_system=='Linux'`

Keep platform-specific imports contained within platform modules and/or lazily imported.

---

## Extraction checklist (from LedFx PR #1725)

Source file in LedFx: `ledfx/audio_device_monitor.py`

### Step A — Remove LedFx coupling

- Remove all imports of LedFx events / LedFx core
- Remove any use of `ledfx_instance.events.fire_event(...)`
- Replace “fire LedFx event” with “trigger debounce → callback”

### Step B — Split into modules

1) **_base.py**

- Abstract base class and callback scheduling helper (`_notify()`)
- Stores loop, callback, running state
- Contains no platform imports and no LedFx imports

2) **_debounce.py**

- Thread-safe debouncer that schedules one callback after `debounce_ms`
- Coalesces bursts

3) **_platform/windows.py**

- Windows watcher (pycaw / CoreAudio notifications)
- OS callbacks only call `self._debouncer.trigger()`

4) **_platform/macos.py**

- CoreAudio property listeners via pyobjc
- Listener only calls `self._debouncer.trigger()`

5) **_platform/linux.py**

- pyudev monitor thread on `SUBSYSTEM=sound`
- udev callback only calls `self._debouncer.trigger()`

6) **monitor.py**

- `create_monitor(...)` factory, uses lazy imports per platform
- returns correct monitor instance or None

### Step C — Ensure lazy import correctness

- Importing `audio_hotplug` must not require any platform deps
- Platform deps are imported only when that platform monitor is instantiated

---

## Testing strategy (unit tests, no hardware reliance)

We do NOT attempt to validate real OS audio events in CI.

### Required tests

1) `test_debounce.py`

- Trigger multiple times quickly → callback called once
- Trigger from background thread → still called once on loop

2) `test_callback_scheduling.py`

- Sync callback invoked on loop thread when triggered from other thread
- Async callback scheduled and completes successfully

3) `test_factory.py`

- Monkeypatch `sys.platform` to simulate win/darwin/linux/unsupported
- Unsupported → create_monitor returns None
- Validate lazy import behavior using `sys.modules`

---

## Example harness (manual verification)

Create `examples/monitor_print.py`.

Behavior:

- Starts monitor using asyncio loop
- Prints a line when callback fires
- Run it, then:
  - plug/unplug headset
  - change default audio device
  - add/remove USB audio device

This acts as the primary manual smoke test.

---

## Publishing process

1) Publish to **TestPyPI** first  
2) Install from TestPyPI into a clean environment and run the example harness  
3) Publish to PyPI  
4) Tag release in GitHub

Versioning:

```
0.1.0  initial release
0.1.x  bug fixes
0.2.0  additive API improvements
```

---

## Migrating LedFx to use the new library

### Phase 1 — Add dependency (no behavior change)

Add to LedFx `pyproject.toml`:

```
audio-hotplug>=0.1.0
```

Keep existing LedFx monitor code temporarily.

---

### Phase 2 — Replace LedFx monitor initialization

Replace the existing LedFx monitor creation with:

```python
from audio_hotplug import create_monitor

self._audio_monitor = create_monitor(loop=self.loop, debounce_ms=200)

if self._audio_monitor:
    self._audio_monitor.start(self._on_audio_devices_changed)
```

---

### Phase 3 — Keep LedFx policy in LedFx

Implement the callback in LedFx:

```python
def _on_audio_devices_changed(self):
    AudioInputSource.refresh_device_list()
    # then fire websocket/event updates for frontend
```

The external library **does not refresh device lists**.

---

### Phase 4 — Remove old LedFx module

After successful testing:

- Delete `ledfx/audio_device_monitor.py`
- Remove any now-unused event classes
- Update documentation

---

## Validation checklist

- LedFx launches cleanly on Windows, macOS, Linux
- Device hot-plug triggers exactly one refresh per burst
- No runaway callback loops
- Monitor stops cleanly on application shutdown
- Importing LedFx does not require platform dependencies for other OSes

---

## Recommendations & Considerations

### 1. Async Callback Handling

The new API improves callback handling by supporting both sync and async callbacks. Provide examples showing both patterns:

```python
# Sync callback
def on_change():
    audio_lib.refresh_devices()

# Async callback  
async def on_change():
    await notify_websocket_clients()
    audio_lib.refresh_devices()
```

### 2. Thread Safety Documentation

The library must clearly document threading behavior:

- Debouncer must be thread-safe (uses locks internally)
- Platform monitors run in background threads
- Callbacks are marshalled to the main loop thread safely
- Windows uses COM threading (`CoInitialize`) - documented in platform module

### 3. Logging Strategy

Add a logging parameter to `create_monitor()`:

```python
create_monitor(
    loop=self.loop,
    debounce_ms=200,
    logger=_LOGGER  # Allow library users to control logging
)
```

### 4. Error Handling During Callback

Document error handling behavior:

- If user callback raises an exception, log it but don't crash the monitor
- Continue monitoring after callback errors
- Consider optional error callback parameter
- Use `try/except` around user callback invocation

### 5. Package Naming

Verify PyPI namespace availability for `audio-hotplug`:

- **`audio-hotplug`** - Shorter, clearly describes behavior ✅
- Previously considered: `audio-device-watch` (more verbose)
- Check both PyPI and TestPyPI before committing

### 6. Debouncing Implementation Notes

The current LedFx implementation has **no debouncing** - it fires events immediately for every OS notification. The proposed 200ms debounce with coalescing is a **significant improvement** that prevents callback storms when multiple devices change rapidly (e.g., USB hub disconnect).

---

## Execution Phases

### Phase 0: Repository Setup (Week 1)

**Goal:** Create infrastructure for independent development

- [ ] Create `audio-hotplug` repo under `https://github.com/LedFx`
- [ ] Set up uv project with `pyproject.toml`
- [ ] Python version support: 3.10-3.13 (match LedFx)
- [ ] Add CI/CD workflow (GitHub Actions for win/mac/linux)
- [ ] Configure pre-commit hooks (black, ruff, isort, mypy)
- [ ] Create README.md with project goals
- [ ] Add LICENSE (MIT or same as LedFx)

**Deliverable:** Empty repo with CI infrastructure passing

### Phase 1: Core Extraction (Week 1-2)

**Goal:** Implement platform-agnostic core with tests

- [ ] Create `src/audio_hotplug/` (src layout)
- [ ] Implement `_base.py` with `AudioDeviceMonitor` abstract class
- [ ] Implement `_debounce.py` with thread-safe debouncer
- [ ] Implement `monitor.py` factory with lazy platform imports
- [ ] Create `tests/test_debounce.py` - trigger multiple times, verify coalescing
- [ ] Create `tests/test_callback_scheduling.py` - sync/async callback tests
- [ ] Create `tests/test_factory.py` - mock `sys.platform`, test returns
- [ ] Verify lazy import behavior (platform deps not loaded until used)
- [ ] Run tests: `uv run pytest -v`

**Deliverable:** Core abstractions + tests passing on all platforms

### Phase 2: Platform Implementations (Week 2)

**Goal:** Port all platform-specific monitors

#### Windows Monitor
- [ ] Port `_platform/windows.py` from LedFx
- [ ] Remove LedFx event firing, replace with `_debouncer.trigger()`
- [ ] Test on Windows: plug/unplug USB audio, change default device
- [ ] Verify COM threading works correctly with asyncio

#### macOS Monitor
- [ ] Port `_platform/macos.py` from LedFx
- [ ] Remove LedFx event firing, replace with `_debouncer.trigger()`
- [ ] Test on macOS: plug/unplug USB audio, change default device
- [ ] Verify CoreAudio property listeners work

#### Linux Monitor
- [ ] Port `_platform/linux.py` from LedFx
- [ ] Remove LedFx event firing, replace with `_debouncer.trigger()`
- [ ] Test on Linux: plug/unplug USB audio
- [ ] Verify pyudev monitoring works

#### Integration
- [ ] Create `examples/monitor_print.py` for manual testing
- [ ] Test all platforms manually
- [ ] Verify debouncing works (rapid changes → single callback)

**Deliverable:** Working monitors on all 3 platforms

### Phase 3: Publishing (Week 3)

**Goal:** Make library available publicly

- [ ] Finalize README.md with usage examples
- [ ] Add CHANGELOG.md
- [ ] Set version to `0.1.0` in `pyproject.toml`
- [ ] Build: `uv run python -m build`
- [ ] Check: `uv run twine check dist/*`
- [ ] Publish to TestPyPI: `uv run twine upload --repository testpypi dist/*`
- [ ] Install from TestPyPI in clean environment
- [ ] Run manual tests with TestPyPI install
- [ ] Verify dependency resolution works
- [ ] Publish to PyPI: `uv run twine upload dist/*`
- [ ] Tag release: `git tag v0.1.0 && git push --tags`
- [ ] Create GitHub release with notes

**Deliverable:** `audio-hotplug>=0.1.0` available on PyPI

### Phase 4: LedFx Integration (Week 3-4)

**Goal:** Replace LedFx internal implementation with library

#### Step A: Add Dependency (No Behavior Change)
- [ ] Add `audio-hotplug>=0.1.0` to LedFx `pyproject.toml`
- [ ] Run `uv sync` to install
- [ ] Keep existing `ledfx/audio_device_monitor.py` temporarily
- [ ] Verify LedFx still works

#### Step B: Replace Monitor Creation
- [ ] Modify `ledfx/core.py` imports:
  ```python
  from audio_hotplug import create_monitor
  ```
- [ ] Replace monitor creation in `_start_audio_device_monitor()`:
  ```python
  self._audio_monitor = create_monitor(loop=self.loop, debounce_ms=200)
  if self._audio_monitor:
      self._audio_monitor.start(self._on_audio_devices_changed)
  ```
- [ ] Implement callback in LedFx (keep PortAudio refresh):
  ```python
  def _on_audio_devices_changed(self):
      from ledfx.effects.audio import AudioInputSource
      AudioInputSource.refresh_device_list()
      _LOGGER.info("Audio device list updated")
  ```

#### Step C: Testing
- [ ] Run LedFx test suite
- [ ] Manual test: plug/unplug headset
- [ ] Manual test: change default audio device
- [ ] Manual test: USB audio device add/remove
- [ ] Verify debouncing prevents callback storms
- [ ] Verify websocket notifications still work (if applicable)
- [ ] Test on Windows, macOS, Linux

#### Step D: Cleanup
- [ ] Delete `ledfx/audio_device_monitor.py`
- [ ] Remove `AudioDeviceListChangedEvent` from `ledfx/events.py` (if unused)
- [ ] Remove event listener registration code
- [ ] Update LedFx documentation
- [ ] Update `docs/developer/audio_device_monitoring.md`

**Deliverable:** LedFx uses external library, old code removed

---

## Success Criteria

Before considering extraction complete, verify:

### Functional Requirements

1. ✅ **Cross-platform**: Library works on Windows, macOS, Linux
2. ✅ **Debouncing**: Multiple rapid changes trigger single callback
3. ✅ **Thread-safe**: Callbacks marshalled correctly to asyncio loop
4. ✅ **Graceful degradation**: Returns None on unsupported platforms
5. ✅ **Clean lifecycle**: `start()` and `stop()` work reliably
6. ✅ **No dependencies leak**: Installing on Linux doesn't install pycaw
7. ✅ **Lazy imports**: Importing library doesn't require platform deps

### Integration Requirements

8. ✅ **LedFx unchanged behavior**: Device refresh works as before
9. ✅ **No regressions**: All LedFx tests pass
10. ✅ **Performance**: No CPU usage increase, no memory leaks
11. ✅ **Shutdown clean**: Monitor stops without hanging
12. ✅ **Error handling**: Invalid callbacks don't crash monitor

### Code Quality

13. ✅ **Test coverage**: >80% coverage on core logic
14. ✅ **CI passing**: Tests pass on all platforms
15. ✅ **Documentation**: README, API docs, examples complete
16. ✅ **Type hints**: All public APIs have type annotations
17. ✅ **Linting**: Passes black, ruff, mypy checks

### Publishing

18. ✅ **PyPI published**: Package installable via `uv pip install audio-hotplug`
19. ✅ **Versioning**: Follows semver (0.1.0 for initial)
20. ✅ **License**: Proper license file and metadata
21. ✅ **Metadata**: Homepage, repository, changelog URLs correct

### Reusability

22. ✅ **Other projects**: Example works standalone (not LedFx-specific)
23. ✅ **API stability**: No breaking changes planned for 0.1.x
24. ✅ **Documentation**: Usage clear for non-LedFx developers

---

## Copilot Staged Workflow (Recommended)

Use small, validated stages with clear verification:

1. **Create repo skeleton + uv workflow** → Verify CI passes
2. **Implement `_debounce` + `_base` + unit tests** → Verify tests pass
3. **Port Linux monitor** → Manual test on Linux
4. **Port Windows monitor** → Manual test on Windows
5. **Port macOS monitor** → Manual test on macOS
6. **Add example harness** → Verify works on all platforms
7. **Publish to TestPyPI** → Install and test from TestPyPI
8. **Publish to PyPI** → Verify package metadata
9. **Modify LedFx to use dependency** → Run LedFx test suite
10. **Remove LedFx internal monitor implementation** → Final verification

**Note:** Each stage should be fully validated before proceeding to the next.

---
