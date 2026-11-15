"""An effect's audio update never waits for its render thread.

The render thread holds the effect lock for a whole frame. The thread that
delivers audio results (the audio callback, or the audio process reader)
updates every active effect in turn, so waiting on one effect's lock held up
all the others behind it. Now a busy lock defers the update to the start of
that effect's next frame, with the newest results and every missed event.
"""

import threading
import time

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect


class FakeAudio:
    def __init__(self):
        self.flags = {"onset": False, "bpm_beat_now": False, "volume_beat_now": False}
        self.pitch_value = 0.0

    def onset(self):
        return self.flags["onset"]

    def bpm_beat_now(self):
        return self.flags["bpm_beat_now"]

    def volume_beat_now(self):
        return self.flags["volume_beat_now"]

    def pitch(self):
        return self.pitch_value


class FakeMelbank:
    def cache_clear(self):
        pass


class FakeLogSec:
    def log_sec(self, now):
        pass

    def try_log(self):
        return False


@Effect.no_registration
class Recorder(AudioReactiveEffect):
    def audio_data_updated(self, data):
        self.updates.append(
            (data.pitch(), data.onset(), data.bpm_beat_now(), data.volume_beat_now())
        )

    def render(self):
        self.frames += 1

    def __del__(self):
        pass  # built without activate(), so there is nothing to deactivate


def make_effect():
    effect = Recorder.__new__(Recorder)
    effect.lock = threading.Lock()
    effect.audio = FakeAudio()
    effect.melbank = FakeMelbank()
    effect.logsec = FakeLogSec()
    effect._last_frame_time = time.perf_counter()
    effect._active = True
    effect._audio_pending = False
    effect._missed_events = set()
    effect._pending_lock = threading.Lock()
    effect.updates = []
    effect.frames = 0
    return effect


def deliver(effect, pitch, **flags):
    effect.audio.pitch_value = pitch
    effect.audio.flags = {
        "onset": False,
        "bpm_beat_now": False,
        "volume_beat_now": False,
        **flags,
    }
    effect._audio_data_updated()


def test_free_lock_updates_at_once_as_before():
    effect = make_effect()
    deliver(effect, 1.0, onset=True)
    assert effect.updates == [(1.0, True, False, False)]
    assert not effect._audio_pending


def test_busy_lock_returns_at_once_and_render_applies_newest_with_missed_events():
    effect = make_effect()
    effect.lock.acquire()  # the render thread is mid-frame
    try:
        started = time.perf_counter()
        deliver(effect, 1.0, onset=True)
        deliver(effect, 2.0, bpm_beat_now=True)
        deliver(effect, 3.0)
        assert time.perf_counter() - started < 0.1
        assert effect.updates == []
        assert effect._audio_pending
    finally:
        effect.lock.release()

    effect._render()
    # Newest values, and both events from the blocks it missed.
    assert effect.updates == [(3.0, True, True, False)]
    assert effect.frames == 1
    assert not effect._audio_pending

    # The missed events are reported once, not again on the next update.
    deliver(effect, 4.0)
    assert effect.updates[-1] == (4.0, False, False, False)


def test_missed_events_carry_into_an_update_the_reader_makes_itself():
    """Render had no frame in between: the next free update merges them."""
    effect = make_effect()
    effect.lock.acquire()
    deliver(effect, 1.0, volume_beat_now=True)
    effect.lock.release()
    deliver(effect, 2.0)
    assert effect.updates == [(2.0, False, False, True)]
    assert not effect._audio_pending


def test_render_without_pending_audio_does_not_update():
    effect = make_effect()
    effect._render()
    assert effect.updates == []
    assert effect.frames == 1
