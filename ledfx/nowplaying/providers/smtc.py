"""SMTC (System Media Transport Controls) Now Playing provider.

Windows-only. Uses WinRT events to react to media session changes.
Track metadata (title, artist, album) is forwarded to NowPlayingService.
Artwork is NOT fetched here; that is handled by the album-art resolver.
"""

import asyncio
import logging
import sys

from ledfx.nowplaying.models import TrackMetadata

_LOGGER = logging.getLogger(__name__)

SOURCE_ID = "smtc"

# Bounds for WinRT calls that can stall in ways asyncio alone cannot interrupt.
# Generous rather than tight: blowing one of these costs a bonus (artwork,
# timing) or one selection attempt, never the track metadata itself, so the
# cost of being too patient is far lower than the cost of giving up early on a
# slower machine than the one this was written on.
_PROPS_READ_TIMEOUT = 2.0
_TIMING_READ_TIMEOUT = 3.0
_ARTWORK_READ_TIMEOUT = 6.0

# Retry schedule, in seconds, for finding a music session after startup.
# Media apps register their session asynchronously and Windows only notifies us
# when the *current* app changes - a player already running before LedFx
# started therefore never wakes us. Backing off is recovery, not polling: it
# gives up after the last entry rather than looping forever.
_RESELECT_DELAYS = (2, 3, 5, 10, 15)


class SMTCNowPlayingProvider:
    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._loop = None
        self._manager = None
        self._manager_token = None
        self._session = None
        self._session_tokens = []
        self._init_task = None
        self._reselect_task = None
        self._last_title = None
        self._last_artist = None
        self._last_album = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if sys.platform != "win32":
            return
        if self._init_task is not None:
            _LOGGER.debug("SMTC: start() called again, already initialising")
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            _LOGGER.error("SMTC: start() called without a running loop")
            return
        _LOGGER.debug("SMTC: starting Now Playing provider")
        self._init_task = asyncio.ensure_future(self._initialize())
        # ensure_future swallows exceptions unless someone looks at the task.
        self._init_task.add_done_callback(self._log_init_result)

    @staticmethod
    def _log_init_result(task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            _LOGGER.error("SMTC: initialisation failed", exc_info=exc)

    def stop(self):
        if self._reselect_task is not None:
            self._reselect_task.cancel()
            self._reselect_task = None
        if self._init_task is not None:
            self._init_task.cancel()
            self._init_task = None
        if self._manager is not None and self._manager_token is not None:
            try:
                self._manager.remove_current_session_changed(
                    self._manager_token
                )
            except Exception:
                pass
        self._manager_token = None
        self._manager = None
        self._detach_session_events()
        self._last_title = None
        self._last_artist = None
        self._last_album = None

    def clear(self):
        """Explicitly reset this provider's state and notify the service."""
        self._last_title = None
        self._last_artist = None
        self._last_album = None
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def _initialize(self):
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
        except ImportError:
            _LOGGER.warning(
                "SMTC: winrt media control projection missing, "
                "Now Playing disabled on this install"
            )
            return

        try:
            manager = await MediaManager.request_async()
        except Exception:
            _LOGGER.exception("SMTC: failed to acquire MediaManager")
            return

        _LOGGER.debug("SMTC: MediaManager acquired")

        self._manager = manager
        self._manager_token = manager.add_current_session_changed(
            self._on_session_changed
        )
        await self._select_and_attach()

    # ------------------------------------------------------------------
    # Session selection
    # ------------------------------------------------------------------

    async def _select_and_attach(self):
        """Choose the most music-like session and attach to it."""
        session = await self._select_best_session()

        # Windows hands "current" to whatever last touched the media controls,
        # so merely opening a launcher can take it away from a player that is
        # still going. Dropping the track we already have would blank
        # now-playing while the music keeps playing, so keep the existing
        # session as long as it still qualifies. If it has gone away - the app
        # closed - it fails the same test and we fall through and clear.
        if session is None and self._session is not None:
            if await self._looks_like_music(self._session, "<attached>"):
                _LOGGER.debug(
                    "SMTC: current session is not music, staying attached"
                )
                return

        await self._attach_to_session(session)
        if session is None:
            self._schedule_reselect()

    def _schedule_reselect(self):
        """Retry briefly when nothing musical was available yet.

        Media apps register their session asynchronously, so at startup the
        only one present can be a launcher. Windows fires
        current_session_changed only when the *current* app changes - a player
        that was already current before LedFx started therefore never wakes us
        up, and we would sit attached to nothing indefinitely.

        Bounded retries, only while idle: this is recovery, not polling.
        """
        if self._reselect_task is not None and not self._reselect_task.done():
            return
        self._reselect_task = asyncio.ensure_future(self._reselect_loop())

    async def _reselect_loop(self):
        for delay in _RESELECT_DELAYS:
            await asyncio.sleep(delay)
            try:
                session = await self._select_best_session()
            except Exception:
                _LOGGER.debug("SMTC: reselect failed", exc_info=True)
                continue
            if session is not None:
                _LOGGER.debug("SMTC: music session appeared, attaching")
                await self._attach_to_session(session)
                return

    async def _select_best_session(self):
        """Take the session Windows reports as current, unless it is not music.

        Windows gives "current" to whichever app most recently touched the
        media controls, so a game launcher or an idle browser tab can win it -
        and then now-playing reports that launcher's title while the album-art
        lookup invents a cover for it.

        Judged on what the session reports rather than on which app it is: a
        name-based denylist only ever covers the offenders one developer
        happened to have installed. Returning None is fine - reporting nothing
        beats reporting a launcher, and the retry ladder tries again.
        """
        manager = self._manager
        if manager is None:
            return None

        # Deliberately NOT enumerating with get_sessions(): it stalls silently
        # on LedFx's running loop - not even an asyncio timeout fires - leaving
        # now-playing empty forever. The current session is safe to ask for.
        try:
            current = manager.get_current_session()
        except Exception:
            _LOGGER.debug("SMTC: no current session", exc_info=True)
            return None

        if current is None:
            return None

        try:
            app_id = current.source_app_user_model_id or "<unknown>"
        except Exception:
            app_id = "<unknown>"

        if not await self._looks_like_music(current, app_id):
            return None

        _LOGGER.info("SMTC: using media session %s", app_id)
        return current

    async def _looks_like_music(self, session, app_id):
        """Whether a session carries enough to be a track worth reporting.

        Deliberately generous: a session qualifies on an artist *or* a real
        duration. Requiring both would drop live streams (no duration) and
        untagged local media (no artist), and requiring "currently playing"
        would drop a paused track we still want on screen. What this rejects is
        the session carrying neither - launchers and notification-only apps,
        which is the whole class of false positives.
        """
        try:
            props = await asyncio.wait_for(
                session.try_get_media_properties_async(),
                timeout=_PROPS_READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("SMTC: timed out reading properties of %s", app_id)
            return False
        except Exception:
            _LOGGER.debug(
                "SMTC: could not read properties of %s", app_id, exc_info=True
            )
            return False

        if props is None:
            return False

        has_artist = bool((getattr(props, "artist", None) or "").strip())

        # Threaded: these are synchronous WinRT calls on a session we have not
        # attached to yet, and selection must not be what stalls the loop.
        _, duration, _ = await self._read_timing(session)

        if has_artist or duration:
            return True

        _LOGGER.debug(
            "SMTC: session %s reports neither artist nor duration, "
            "not treating it as music",
            app_id,
        )
        return False

    # ------------------------------------------------------------------
    # WinRT event callbacks (called from WinRT thread pool)
    # ------------------------------------------------------------------

    def _on_session_changed(self, manager, args):
        """Fires when the active media session changes."""
        if self._loop is None:
            return
        # Re-run selection rather than taking the new "current" session:
        # whatever just grabbed the controls is not necessarily the music.
        asyncio.run_coroutine_threadsafe(self._select_and_attach(), self._loop)

    def _on_timeline_changed(self, session, args):
        """Fires as position advances and on seek."""
        self._schedule_timing_push()

    def _on_playback_info_changed(self, session, args):
        """Fires on play / pause / stop."""
        self._schedule_timing_push()

    def _schedule_timing_push(self):
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._push_timing(), self._loop)

    def _on_media_properties_changed(self, session, args):
        """Fires when track title/artist/album changes."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._fetch_and_push_metadata(), self._loop
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _attach_to_session(self, session):
        self._detach_session_events()
        if session is None:
            self._maybe_clear()
            return
        self._session = session

        tokens = []
        tok = session.add_media_properties_changed(
            self._on_media_properties_changed
        )
        tokens.append((session.remove_media_properties_changed, tok))

        # Timeline and playback-state events are what keep position honest
        # across seeks and pauses - the two moments a client extrapolating
        # from an old anchor is guaranteed to be wrong. Event-driven, so no
        # polling. Optional: an older projection may not expose them.
        for add_name, remove_name, handler in (
            (
                "add_timeline_properties_changed",
                "remove_timeline_properties_changed",
                self._on_timeline_changed,
            ),
            (
                "add_playback_info_changed",
                "remove_playback_info_changed",
                self._on_playback_info_changed,
            ),
        ):
            try:
                add = getattr(session, add_name)
                remove = getattr(session, remove_name)
                tokens.append((remove, add(handler)))
            except Exception:
                _LOGGER.debug("SMTC: %s unavailable", add_name, exc_info=True)

        self._session_tokens = tokens
        await self._fetch_and_push_metadata()

    def _detach_session_events(self):
        for remove_fn, token in self._session_tokens:
            try:
                remove_fn(token)
            except Exception:
                pass
        self._session_tokens = []
        self._session = None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def _fetch_and_push_metadata(self):
        if self._session is None:
            return
        try:
            props = await self._session.try_get_media_properties_async()
        except Exception:
            _LOGGER.warning("SMTC: failed to fetch media properties")
            return

        if props is None:
            self._maybe_clear()
            return

        title = props.title or None
        artist = props.artist or None
        album = props.album_title or None

        self._last_title = title
        self._last_artist = artist
        self._last_album = album

        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is None:
            return

        position, duration, playing = await self._read_timing()

        # Read the player's own embedded art first. It has to happen before
        # set_metadata so the service knows whether to fall back to a
        # MusicBrainz lookup for this track.
        # Metadata goes out FIRST and unconditionally. Reading the embedded
        # artwork stream can stall in a way asyncio cannot interrupt, and
        # awaiting it here previously took the whole track push down with it.
        # has_own_artwork=True suppresses the MusicBrainz lookup: SMTC players
        # carry real cover art, and a wrong guess is worse than a late image.
        now_playing.set_metadata(
            SOURCE_ID,
            TrackMetadata(
                source_id=SOURCE_ID,
                title=title,
                artist=artist,
                album=album,
                position=position,
                duration=duration,
                playing=playing,
            ),
            has_own_artwork=True,
        )
        _LOGGER.debug("SMTC: metadata pushed for %s", title)

        # Fire-and-forget: artwork arrives when it arrives.
        asyncio.ensure_future(self._push_artwork(props))

    async def _push_artwork(self, props):
        """Read and publish embedded artwork without blocking the track push."""
        art_bytes, art_content_type = await self._read_thumbnail(props)
        if not art_bytes:
            return
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is None:
            return
        now_playing.set_artwork_bytes(SOURCE_ID, art_bytes, art_content_type)
        _LOGGER.debug(
            "SMTC: embedded artwork applied (%d bytes)", len(art_bytes)
        )

    async def _read_thumbnail(self, props):
        """Read embedded album art, bounded so it can never strand metadata.

        The WinRT stream calls are awaited on LedFx's loop from a WinRT
        callback thread, and a stall there would block the whole metadata push
        - which is exactly how this provider went silent once already. Cap it:
        artwork is a bonus, track info is not.
        """
        try:
            # Run in a worker thread with its own event loop. Awaiting the
            # WinRT stream calls directly on LedFx's running loop stalls
            # indefinitely - not even asyncio.wait_for can interrupt it - while
            # the identical code completes instantly under a fresh asyncio.run.
            return await asyncio.wait_for(
                asyncio.to_thread(self._read_thumbnail_blocking, props),
                timeout=_ARTWORK_READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "SMTC: timed out reading embedded artwork; "
                "falling back to album-art lookup"
            )
            return None, None
        except Exception:
            _LOGGER.warning(
                "SMTC: embedded artwork unavailable; "
                "falling back to album-art lookup",
                exc_info=True,
            )
            return None, None

    def _read_thumbnail_blocking(self, props):
        """Bridge into a private event loop on a worker thread."""
        return asyncio.run(self._read_thumbnail_inner(props))

    async def _read_thumbnail_inner(self, props):
        """Actual embedded-artwork read. See :meth:`_read_thumbnail`."""
        stream = None
        reader = None
        try:
            # Import first, and keep the .thumbnail access inside this try:
            # reading that property makes winrt lazily import the projection
            # package for its stream-reference type, and if
            # winrt-Windows.Storage.Streams is not installed that raises
            # ModuleNotFoundError - which getattr's default does NOT swallow.
            # Outside the try it takes the whole metadata push down with it.
            from winrt.windows.storage.streams import DataReader

            ref = getattr(props, "thumbnail", None)
            if ref is None:
                return None, None

            stream = await ref.open_read_async()
            size = getattr(stream, "size", 0) if stream is not None else 0
            if not size:
                return None, None

            content_type = (
                getattr(stream, "content_type", None) or "image/jpeg"
            )
            reader = DataReader(stream)
            await reader.load_async(size)
            data = bytes(bytearray(reader.read_buffer(size)))
            return (data, content_type) if data else (None, None)
        finally:
            for closeable in (reader, stream):
                try:
                    if closeable is not None:
                        closeable.close()
                except Exception:
                    pass

    async def _push_timing(self):
        """Re-publish the current track with a fresh timing anchor.

        Same track identity, so the service treats it as a timing refresh: no
        artwork re-read, no album-art lookup. It decides whether this is worth
        forwarding by checking whether a client extrapolating from the last
        anchor would now be wrong.
        """
        if self._session is None or self._last_title is None:
            return

        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is None:
            return

        position, duration, playing = await self._read_timing()
        if position is None and playing is None:
            return

        now_playing.set_metadata(
            SOURCE_ID,
            TrackMetadata(
                source_id=SOURCE_ID,
                title=self._last_title,
                artist=self._last_artist,
                album=self._last_album,
                position=position,
                duration=duration,
                playing=playing,
            ),
            has_own_artwork=True,
        )

    async def _read_timing(self, session=None):
        """Playback timing, read off the loop.

        The WinRT calls are synchronous; running them on LedFx's event loop
        would risk stalling the loop itself, which is strictly worse than the
        artwork stall we already hit. Bounded and threaded for that reason.

        ``session`` defaults to the attached one; selection passes a candidate
        it has not attached to yet.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._read_timing_blocking, session),
                timeout=_TIMING_READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("SMTC: timed out reading playback timing")
            return None, None, None
        except Exception:
            _LOGGER.debug("SMTC: timing unavailable", exc_info=True)
            return None, None, None

    def _read_timing_blocking(self, session=None):
        """Best-effort playback timing from the session we already hold.

        Deliberately opportunistic: read once, here, off the session object this
        handler already has. Nothing polls, so these are a snapshot taken when
        the metadata event fired - good enough for a client that extrapolates
        from a timestamp, and stale after a seek or pause until the next event.

        Any failure yields None rather than raising: timing is a bonus, and it
        must never cost us the track metadata itself.
        """
        position = duration = playing = None
        session = session if session is not None else self._session
        if session is None:
            return position, duration, playing

        try:
            timeline = session.get_timeline_properties()
            if timeline is not None:
                if timeline.position is not None:
                    position = timeline.position.total_seconds()
                if timeline.end_time is not None:
                    end = timeline.end_time.total_seconds()
                    # Sessions with no real media report a zero-length timeline.
                    if end > 0:
                        duration = end
        except Exception:
            _LOGGER.debug(
                "SMTC: timeline properties unavailable", exc_info=True
            )

        try:
            info = session.get_playback_info()
            if info is not None and info.playback_status is not None:
                # Compare by name so this does not depend on the enum's
                # numeric layout in whichever winsdk build is installed.
                status = getattr(
                    info.playback_status, "name", str(info.playback_status)
                )
                playing = str(status).upper().endswith("PLAYING")
        except Exception:
            _LOGGER.debug("SMTC: playback info unavailable", exc_info=True)

        return position, duration, playing

    def _maybe_clear(self):
        if (
            self._last_title is None
            and self._last_artist is None
            and self._last_album is None
        ):
            return
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)
        self._last_title = None
        self._last_artist = None
        self._last_album = None
