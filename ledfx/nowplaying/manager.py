"""
Now-playing manager: lifecycle, dedupe, art resolution, palette generation, event emission.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import time
from collections import OrderedDict

import PIL.Image as Image

from ledfx.events import (
    Event,
    NowPlayingArtUpdatedEvent,
    NowPlayingPaletteUpdatedEvent,
    NowPlayingUpdatedEvent,
)
from ledfx.nowplaying.models import NowPlayingState, NowPlayingTrack

_LOGGER = logging.getLogger(__name__)


class NowPlayingManager:
    """Manages now-playing metadata, art caching, palette derivation, and event emission."""

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self.state = NowPlayingState()
        self._provider = None
        self._art_cache: OrderedDict[str, bytes] = OrderedDict()
        self._shutdown_unsub = None

    async def start(self) -> None:
        config = self._ledfx.config.get("now_playing", {})
        if not config.get("enabled", False):
            self.state.status = "disabled"
            _LOGGER.info("Now-playing subsystem disabled by config")
            return

        self.state.enabled = True
        self.state.status = "starting"

        # Register shutdown listener for clean stop
        self._shutdown_unsub = self._ledfx.events.add_listener(
            lambda _: asyncio.ensure_future(self.stop()),
            Event.LEDFX_SHUTDOWN,
        )

        provider_name = config.get("provider", "platform_media")
        self.state.provider_name = provider_name

        try:
            provider = self._create_provider(provider_name, config)
            if provider is None:
                self.state.status = "error"
                return
            self._provider = provider
            await self._provider.start(self._on_track_update)
            self.state.status = "running"
            _LOGGER.info(
                "Now-playing subsystem started with provider: %s",
                provider_name,
            )
        except Exception as e:
            self.state.status = "error"
            self.state.last_error = str(e)
            _LOGGER.error("Failed to start now-playing provider: %s", e)

    async def stop(self) -> None:
        if self._provider:
            try:
                await self._provider.stop()
            except Exception as e:
                _LOGGER.warning("Error stopping now-playing provider: %s", e)
            self._provider = None

        if self._shutdown_unsub:
            self._shutdown_unsub()
            self._shutdown_unsub = None

        self.state.status = "disabled" if not self.state.enabled else "idle"
        _LOGGER.info("Now-playing subsystem stopped")

    def _create_provider(self, provider_name: str, config: dict):
        """Create the appropriate provider instance."""
        if provider_name == "platform_media":
            from ledfx.nowplaying.providers.platform_media_provider import (
                PlatformMediaProvider,
                is_available,
                unavailable_reason,
            )

            if not is_available():
                reason = unavailable_reason()
                self.state.last_error = reason
                _LOGGER.warning(
                    "Platform media provider unavailable: %s", reason
                )
                return None

            poll_interval = config.get("poll_interval_s", 2.0)
            return PlatformMediaProvider(poll_interval=poll_interval)
        else:
            self.state.last_error = f"Unknown provider: {provider_name}"
            _LOGGER.warning("Unknown now-playing provider: %s", provider_name)
            return None

    async def _on_track_update(self, track: NowPlayingTrack) -> None:
        """Callback from provider with new track data."""
        try:
            config = self._ledfx.config.get("now_playing", {})
            now = time.time()

            sig = track.signature()
            art_sig = track.art_signature()

            # Check for meaningful change
            track_changed = sig != self.state.last_track_signature
            art_changed = art_sig != self.state.last_art_signature
            playing_changed = (
                self.state.active_track is not None
                and self.state.active_track.is_playing != track.is_playing
            )

            if not track_changed and not art_changed and not playing_changed:
                return

            # Update state
            self.state.active_track = track
            self.state.last_update_ts = now

            if track_changed:
                self.state.last_track_signature = sig
                self.state.last_art_signature = art_sig
                self.state.palette_applied = False
                self.state.active_gradient = None
                self.state.active_art_cache_key = None
                self.state.active_art_url = track.art_url

                # Emit track update event
                self._ledfx.events.fire_event(
                    NowPlayingUpdatedEvent(
                        provider=track.provider,
                        title=track.title,
                        artist=track.artist,
                        album=track.album,
                        art_url=track.art_url,
                        is_playing=track.is_playing,
                        duration=track.duration,
                        position=track.position,
                        player_name=track.player_name,
                        track_signature=sig,
                        timestamp=now,
                    )
                )
                _LOGGER.info(
                    "Now playing: %s - %s (%s)",
                    track.artist or "Unknown",
                    track.title or "Unknown",
                    track.album or "",
                )

                # Handle art and palette for new track
                await self._handle_art_and_palette(track, sig, config, now)

            elif art_changed:
                self.state.last_art_signature = art_sig
                self.state.active_art_url = track.art_url
                await self._handle_art_and_palette(track, sig, config, now)

        except Exception:
            _LOGGER.warning("Error processing track update", exc_info=True)

    async def _handle_art_and_palette(
        self,
        track: NowPlayingTrack,
        sig: str,
        config: dict,
        now: float,
    ) -> None:
        """Resolve art, extract palette, apply to effects."""
        art_bytes = await self._resolve_art(track, config)
        if art_bytes is None:
            return

        cache_key = hashlib.md5(art_bytes[:4096]).hexdigest()
        self.state.active_art_cache_key = cache_key

        # Emit art event
        self._ledfx.events.fire_event(
            NowPlayingArtUpdatedEvent(
                provider=track.provider,
                track_signature=sig,
                art_url=track.art_url,
                art_cache_key=cache_key,
                timestamp=now,
            )
        )

        # Generate palette if enabled
        if config.get("generate_palette_from_album_art", False):
            await self._generate_and_apply_palette(
                art_bytes, track, sig, config, now
            )

    async def _resolve_art(
        self, track: NowPlayingTrack, config: dict
    ) -> bytes | None:
        """Resolve album art to bytes. Uses cache when possible."""
        art_sig = track.art_signature()
        max_cache = config.get("art_cache_max_items", 64)

        # Check cache
        if config.get("art_cache", True) and art_sig in self._art_cache:
            self._art_cache.move_to_end(art_sig)
            _LOGGER.debug("Art cache hit for %s", art_sig[:8])
            return self._art_cache[art_sig]

        art_bytes = None

        # Try provider-specific thumbnail
        if self._provider and hasattr(self._provider, "get_thumbnail_bytes"):
            try:
                art_bytes = await asyncio.wait_for(
                    self._provider.get_thumbnail_bytes(),
                    timeout=config.get("art_fetch_timeout_ms", 5000) / 1000,
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Thumbnail fetch timed out")
            except Exception:
                _LOGGER.debug("Failed to get thumbnail bytes", exc_info=True)

        # Fallback: try HTTP fetch if art_url looks like HTTP
        if (
            art_bytes is None
            and track.art_url
            and track.art_url.startswith(("http://", "https://"))
        ):
            art_bytes = await self._fetch_art_http(
                track.art_url, config.get("art_fetch_timeout_ms", 5000) / 1000
            )

        if art_bytes is None:
            _LOGGER.debug("No album art available for current track")
            return None

        # Cache
        if config.get("art_cache", True):
            self._art_cache[art_sig] = art_bytes
            while len(self._art_cache) > max_cache:
                self._art_cache.popitem(last=False)

        return art_bytes

    async def _fetch_art_http(self, url: str, timeout: float) -> bytes | None:
        """Fetch album art from an HTTP URL."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 10 * 1024 * 1024:
                            _LOGGER.warning("Art image too large, skipping")
                            return None
                        return data
        except Exception:
            _LOGGER.debug("HTTP art fetch failed for %s", url, exc_info=True)
        return None

    async def _generate_and_apply_palette(
        self,
        art_bytes: bytes,
        track: NowPlayingTrack,
        sig: str,
        config: dict,
        now: float,
    ) -> None:
        """Extract palette from art and optionally apply to running effects."""
        try:
            pil_image = Image.open(io.BytesIO(art_bytes))
        except Exception:
            _LOGGER.warning("Failed to open art image for palette extraction")
            return

        try:
            from ledfx.utilities.gradient_extraction import (
                extract_gradient_metadata,
            )

            metadata = extract_gradient_metadata(pil_image)
        except Exception:
            _LOGGER.warning("Palette extraction failed", exc_info=True)
            return

        # Use led_punchy variant by default for LED-optimized colors
        variant = config.get("gradient_variant", "led_punchy")
        gradient_data = metadata.get(variant, metadata.get("led_punchy", {}))
        gradient = gradient_data.get("gradient")

        if not gradient:
            _LOGGER.debug("No gradient extracted from album art")
            return

        # Skip if palette is identical to what's already active
        if gradient == self.state.active_gradient:
            _LOGGER.debug("Palette unchanged, skipping application")
            return

        self.state.active_gradient = gradient
        self.state.active_palette_id = f"nowplaying_{sig[:8]}"

        affected = []
        skipped = []

        # Apply to running effects if enabled
        if config.get("apply_palette_to_running_effects", False):
            affected, skipped = self._apply_gradient_to_effects(gradient)
            self.state.palette_applied = len(affected) > 0

        # Emit palette event
        self._ledfx.events.fire_event(
            NowPlayingPaletteUpdatedEvent(
                provider=track.provider,
                track_signature=sig,
                gradient=gradient,
                palette_applied=self.state.palette_applied,
                affected_effects=affected,
                skipped_effects=skipped,
                timestamp=now,
            )
        )

        if affected:
            _LOGGER.info(
                "Applied now-playing palette to %d effect(s)", len(affected)
            )
        if skipped:
            _LOGGER.debug(
                "Skipped %d effect(s) without gradient support", len(skipped)
            )

    def _apply_gradient_to_effects(
        self, gradient: str
    ) -> tuple[list[str], list[str]]:
        """Apply gradient to all running effects that support it."""
        from ledfx.effects import DummyEffect
        from ledfx.effects.gradient import GradientEffect

        affected = []
        skipped = []

        for virtual in self._ledfx.virtuals.values():
            effect = virtual.active_effect
            if effect is None or isinstance(effect, DummyEffect):
                continue

            effect_id = f"{virtual.id}:{getattr(effect, 'type', 'unknown')}"

            # Check if effect supports gradient config
            has_gradient = isinstance(effect, GradientEffect) or (
                hasattr(effect, "_config") and "gradient" in effect._config
            )

            if not has_gradient:
                skipped.append(effect_id)
                continue

            # Skip if effect already has this exact gradient
            current = getattr(effect, "_config", {}).get("gradient")
            if current == gradient:
                _LOGGER.debug("Gradient already applied to %s", effect_id)
                continue

            try:
                effect.update_config({"gradient": gradient})
                affected.append(effect_id)
            except Exception as e:
                _LOGGER.warning(
                    "Failed to update gradient for %s: %s",
                    effect_id,
                    e,
                )
                skipped.append(effect_id)

        return affected, skipped
