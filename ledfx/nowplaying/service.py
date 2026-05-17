"""Now Playing Service implementation.

Centralized service managing current media playback state.
Receives normalized metadata from providers and exposes a single
source of truth for the rest of LedFx.
"""

import hashlib
import io
import logging
import time
import urllib.request

import voluptuous as vol
from PIL import Image

from ledfx.assets import (
    save_asset,
)
from ledfx.color import (
    build_gradient_config,
)
from ledfx.config import save_config
from ledfx.events import (
    NowPlayingArtworkChangedEvent,
    NowPlayingClearedEvent,
    NowPlayingGradientChangedEvent,
    NowPlayingMetadataChangedEvent,
    NowPlayingTrackChangedEvent,
)
from ledfx.nowplaying.models import (
    ArtworkReference,
    NowPlayingState,
    TrackMetadata,
)
from ledfx.utilities.gradient_extraction import extract_gradient_metadata
from ledfx.utilities.security_utils import (
    DOWNLOAD_TIMEOUT,
    MAX_IMAGE_SIZE_BYTES,
    build_browser_request,
    is_allowed_image_extension,
    validate_pil_image,
    validate_url_safety,
)
from ledfx.virtuals import apply_config_to_active_effects

_LOGGER = logging.getLogger(__name__)

# Valid gradient variant names
GRADIENT_VARIANTS = ("led_safe", "led_punchy", "led_max")

# Valid track-text / album-art display modes
DISPLAY_MODES = ("off", "temporary", "continuous")

NOW_PLAYING_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("gradient", default={}): vol.Schema(
            {
                vol.Optional("enabled", default=True): bool,
                vol.Optional("variant", default="led_punchy"): vol.In(
                    GRADIENT_VARIANTS
                ),
                vol.Optional("virtual_ids", default=[]): [str],
            }
        ),
        vol.Optional("track_text", default={}): vol.Schema(
            {
                vol.Optional("mode", default="off"): vol.In(DISPLAY_MODES),
                vol.Optional("duration", default=8): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=60)
                ),
                vol.Optional("virtual_ids", default=[]): [str],
                vol.Optional("fallback_effect", default="text"): str,
            }
        ),
        vol.Optional("album_art", default={}): vol.Schema(
            {
                vol.Optional("mode", default="off"): vol.In(DISPLAY_MODES),
                vol.Optional("duration", default=10): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=60)
                ),
                vol.Optional("virtual_ids", default=[]): [str],
                vol.Optional("fallback_effect", default="image"): str,
            }
        ),
    }
)

# Content-type to file extension mapping
_EXTENSION_MAP = {
    "image/gif": ".gif",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}

# Subdirectory within assets for now-playing artwork
_NOW_PLAYING_ASSET_DIR = "now_playing"
# Fixed base filename for the single artwork file
_ARTWORK_FILENAME = "now_playing"


class NowPlayingService:
    """Provider-neutral Now Playing state manager.

    Attributes:
        ledfx: Reference to the LedFxCore instance.
        state: Current NowPlayingState.
    """

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._state = NowPlayingState()

        # Load persisted configuration
        raw_config = getattr(ledfx, "config", {}).get("now_playing", {})
        self._config = NOW_PLAYING_CONFIG_SCHEMA(raw_config)

        # Apply gradient settings from config
        grad_cfg = self._config["gradient"]
        self._gradient_enabled = grad_cfg["enabled"]
        self._gradient_virtual_ids: list[str] = list(grad_cfg["virtual_ids"])
        self._state.selected_gradient_variant = grad_cfg["variant"]

        _LOGGER.info("Now Playing Service initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_metadata(self, source_id: str, metadata: TrackMetadata) -> bool:
        """Update current track metadata from a provider.

        Args:
            source_id: Provider identifier (e.g. "sendspin").
            metadata: Normalized track metadata.

        Returns:
            True if a track change was detected, False otherwise.
        """
        now = time.time()
        metadata.updated_at = now

        # Determine if this is a new track
        track_changed = self._detect_track_change(metadata)

        # Activate source on first metadata or if already active
        if self._state.active_source_id is None:
            self._state.active_source_id = source_id
            _LOGGER.info("Now Playing active source set to: %s", source_id)

        # Only update state if this provider is the active source
        if source_id != self._state.active_source_id:
            _LOGGER.debug(
                "Ignoring metadata from inactive source: %s (active: %s)",
                source_id,
                self._state.active_source_id,
            )
            return False

        self._state.metadata = metadata
        self._state.updated_at = now

        # Fire events
        self._fire_event(
            NowPlayingMetadataChangedEvent(source_id, metadata.to_dict())
        )

        if track_changed:
            _LOGGER.info(
                "Track changed: %s - %s - %s",
                metadata.artist or "Unknown artist",
                metadata.title or "Unknown title",
                metadata.album or "Unknown album",
            )
            self._fire_event(
                NowPlayingTrackChangedEvent(
                    source_id, metadata.title, metadata.artist, metadata.album
                )
            )

        return track_changed

    def set_artwork_url(
        self,
        source_id: str,
        url: str,
        content_type: str = None,
        artwork_hash: str = None,
    ) -> bool:
        """Set artwork from a URL, download it, and extract gradients.

        Downloads the image, saves it as a single ``now_playing.{ext}``
        file (overwriting any previous artwork), and runs gradient
        extraction via the existing pipeline.

        Args:
            source_id: Provider identifier.
            url: URL to the artwork image.
            content_type: MIME type of the image.
            artwork_hash: Hash for change detection.

        Returns:
            True if artwork changed, False otherwise.
        """
        if source_id != self._state.active_source_id:
            return False

        # Detect artwork change
        current = self._state.artwork
        if current and current.url == url and current.hash == artwork_hash:
            return False

        # Download the image
        data, detected_content_type = self._download_image(url)
        if data is None:
            _LOGGER.warning("Failed to download artwork from %s", url)
            return False

        if content_type is None:
            content_type = detected_content_type

        # Compute hash from downloaded bytes if not provided
        if artwork_hash is None:
            artwork_hash = hashlib.sha256(data).hexdigest()[:16]

        # Save to disk and extract gradients
        artwork_path, gradients, width, height = self._store_artwork(
            data, content_type
        )

        self._state.artwork = ArtworkReference(
            source_id=source_id,
            url=url,
            cache_key=artwork_path,
            content_type=content_type,
            hash=artwork_hash,
            width=width,
            height=height,
            gradients=gradients,
        )
        self._state.updated_at = time.time()
        self._update_current_gradient()

        _LOGGER.info("Artwork URL updated from %s", source_id)
        self._fire_event(
            NowPlayingArtworkChangedEvent(
                source_id, self._state.artwork.to_dict()
            )
        )
        return True

    def set_artwork_bytes(
        self,
        source_id: str,
        data: bytes,
        content_type: str,
        artwork_hash: str = None,
    ) -> bool:
        """Set artwork from raw image bytes.

        Saves the bytes as a single ``now_playing.{ext}`` file
        (overwriting any previous artwork) and runs gradient extraction.

        Args:
            source_id: Provider identifier.
            data: Raw image bytes.
            content_type: MIME type of the image.
            artwork_hash: Hash for change detection. If None, computed from data.

        Returns:
            True if artwork changed, False otherwise.
        """
        if source_id != self._state.active_source_id:
            return False

        if artwork_hash is None:
            artwork_hash = hashlib.sha256(data).hexdigest()[:16]

        # Detect artwork change
        current = self._state.artwork
        if current and current.hash == artwork_hash:
            return False

        # Save to disk and extract gradients
        artwork_path, gradients, width, height = self._store_artwork(
            data, content_type
        )

        self._state.artwork = ArtworkReference(
            source_id=source_id,
            url=None,
            cache_key=artwork_path,
            content_type=content_type,
            hash=artwork_hash,
            width=width,
            height=height,
            gradients=gradients,
        )
        self._state.updated_at = time.time()
        self._update_current_gradient()

        _LOGGER.info(
            "Artwork bytes updated from %s (hash: %s)", source_id, artwork_hash
        )
        self._fire_event(
            NowPlayingArtworkChangedEvent(
                source_id, self._state.artwork.to_dict()
            )
        )
        return True

    def clear(self, source_id: str) -> None:
        """Clear state for a provider.

        If the cleared provider is the active source, resets all state.

        Args:
            source_id: Provider identifier to clear.
        """
        if self._state.active_source_id == source_id:
            _LOGGER.info(
                "Clearing Now Playing state for active source: %s", source_id
            )
            self._state = NowPlayingState()
            self._fire_event(NowPlayingClearedEvent(source_id))
        else:
            _LOGGER.debug(
                "Clear requested for inactive source: %s (active: %s)",
                source_id,
                self._state.active_source_id,
            )

    def get_current(self) -> NowPlayingState:
        """Return the current Now Playing state.

        Returns:
            The current NowPlayingState instance.
        """
        return self._state

    @property
    def gradient_enabled(self) -> bool:
        """Whether gradient application to virtuals is enabled."""
        return self._gradient_enabled

    @gradient_enabled.setter
    def gradient_enabled(self, value: bool) -> None:
        self._gradient_enabled = bool(value)

    @property
    def gradient_virtual_ids(self) -> list[str]:
        """Virtual IDs to target. Empty list means all virtuals."""
        return list(self._gradient_virtual_ids)

    @gradient_virtual_ids.setter
    def gradient_virtual_ids(self, value: list[str]) -> None:
        self._gradient_virtual_ids = list(value)

    @property
    def config(self) -> dict:
        """Return the current validated configuration dict."""
        return dict(self._config)

    def update_config(self, new_config: dict) -> dict:
        """Validate, apply and persist a new configuration.

        Merges *new_config* with the current configuration, validates
        the result against :data:`NOW_PLAYING_CONFIG_SCHEMA`, applies
        the settings to the service, and saves to disk.

        Args:
            new_config: Partial or full configuration dict.

        Returns:
            The validated, complete configuration dict.

        Raises:
            vol.Invalid: If validation fails.
        """
        # Merge: new values override current, then validate
        merged = {**self._config}
        for section in ("gradient", "track_text", "album_art"):
            if section in new_config:
                merged[section] = {
                    **merged.get(section, {}),
                    **new_config[section],
                }

        validated = NOW_PLAYING_CONFIG_SCHEMA(merged)
        self._config = validated

        # Apply gradient settings
        grad_cfg = validated["gradient"]
        self._gradient_enabled = grad_cfg["enabled"]
        self._gradient_virtual_ids = list(grad_cfg["virtual_ids"])

        old_variant = self._state.selected_gradient_variant
        self._state.selected_gradient_variant = grad_cfg["variant"]

        # Re-resolve gradient if variant changed
        if grad_cfg["variant"] != old_variant:
            self._update_current_gradient()

        # Persist to core config
        self._save_config()

        return dict(validated)

    def _save_config(self) -> None:
        """Persist the now_playing config section to disk."""
        config = getattr(self._ledfx, "config", None)
        config_dir = getattr(self._ledfx, "config_dir", None)
        if config is not None and config_dir:
            config["now_playing"] = dict(self._config)
            try:
                save_config(config=config, config_dir=config_dir)
            except Exception as exc:
                _LOGGER.warning(
                    "Failed to save now_playing config: %s", exc
                )

    def apply_gradient_to_virtuals(self) -> int:
        """Apply the current gradient + color group updates to target virtuals.

        Uses :func:`~ledfx.color.build_gradient_config` for gradient
        resolution / color-group sampling and
        :func:`~ledfx.virtuals.apply_config_to_active_effects` for the
        per-effect update loop.

        Returns:
            The number of effects successfully updated.
        """
        gradient_str = self._state.current_gradient
        if not gradient_str:
            return 0

        virtuals = getattr(self._ledfx, "virtuals", None)
        if virtuals is None:
            return 0

        gradients_collection = getattr(self._ledfx, "gradients", None)
        if gradients_collection is None:
            return 0

        # Resolve the gradient and sample color groups
        try:
            config_updates = build_gradient_config(
                gradient_str, gradients_collection
            )
        except Exception as exc:
            _LOGGER.warning("Failed to resolve gradient: %s", exc)
            return 0

        # Determine target virtuals
        target_ids = (
            set(self._gradient_virtual_ids)
            if self._gradient_virtual_ids
            else None
        )

        updated, _skipped = apply_config_to_active_effects(
            virtuals.values(),
            config_updates,
            target_ids=target_ids,
        )

        # Persist configuration changes
        if updated > 0:
            config_dir = getattr(self._ledfx, "config_dir", None)
            config = getattr(self._ledfx, "config", None)
            if config is not None and config_dir:
                try:
                    save_config(config=config, config_dir=config_dir)
                except Exception as exc:
                    _LOGGER.warning(
                        "Failed to save config after gradient apply: %s", exc
                    )

        _LOGGER.info("Applied Now Playing gradient to %d effect(s)", updated)
        return updated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_track_change(self, new_metadata: TrackMetadata) -> bool:
        """Compare new metadata against current to detect track changes.

        A track change is detected when the track identity tuple differs.
        Position-only updates are not considered track changes.

        Args:
            new_metadata: Incoming metadata to compare.

        Returns:
            True if the track identity changed.
        """
        current = self._state.metadata
        if current is None:
            return True

        return current.track_identity() != new_metadata.track_identity()

    def _fire_event(self, event) -> None:
        """Fire an event if the events system is available.

        Gracefully no-ops if events is not yet initialized (e.g. during testing).
        """
        if hasattr(self._ledfx, "events"):
            self._ledfx.events.fire_event(event)

    # ------------------------------------------------------------------
    # Artwork storage helpers
    # ------------------------------------------------------------------

    def _get_artwork_relative_path(self, content_type: str) -> str:
        """Return the relative asset path for the now-playing artwork file."""
        extension = _EXTENSION_MAP.get(content_type, ".jpg")
        return f"{_NOW_PLAYING_ASSET_DIR}/{_ARTWORK_FILENAME}{extension}"

    def _store_artwork(self, data: bytes, content_type: str) -> tuple:
        """Save artwork bytes via the asset management system.

        Uses save_asset() with allow_overwrite=True for secure, validated,
        atomic writes. Extracts gradients directly from the saved file.

        Args:
            data: Raw image bytes.
            content_type: MIME type of the image.

        Returns:
            Tuple of (artwork_path, gradients_dict, width, height).
            artwork_path is ``None`` when config_dir is unavailable.
        """
        config_dir = getattr(self._ledfx, "config_dir", None)
        if not config_dir:
            return None, None, None, None

        relative_path = self._get_artwork_relative_path(content_type)

        # Use the asset system for validated, atomic write (overwrites in place)
        success, absolute_path, error = save_asset(
            config_dir, relative_path, data, allow_overwrite=True
        )
        if not success:
            _LOGGER.error("Failed to save artwork via asset system: %s", error)
            return None, None, None, None

        # Extract image dimensions
        width, height = None, None
        try:
            with Image.open(io.BytesIO(data)) as img:
                width, height = img.size
        except Exception as exc:
            _LOGGER.warning("Could not read image dimensions: %s", exc)

        # Extract gradients directly from the saved file
        gradients = None
        try:
            gradients = extract_gradient_metadata(absolute_path)
        except Exception as exc:
            _LOGGER.warning("Gradient extraction failed: %s", exc)

        return absolute_path, gradients, width, height

    def _download_image(self, url: str) -> tuple:
        """Download an image from *url* with security validation.

        Returns:
            Tuple of (data_bytes, content_type) or (None, None) on failure.
        """
        if not is_allowed_image_extension(url):
            _LOGGER.warning("URL has invalid image extension: %s", url)
            return None, None

        is_safe, error_msg = validate_url_safety(url, allow_private=True)
        if not is_safe:
            _LOGGER.warning(
                "URL blocked for security: %s - %s", url, error_msg
            )
            return None, None

        try:
            req = build_browser_request(url)
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                content_length = resp.headers.get("Content-Length")
                if (
                    content_length
                    and int(content_length) > MAX_IMAGE_SIZE_BYTES
                ):
                    _LOGGER.warning(
                        "Artwork too large: %s bytes", content_length
                    )
                    return None, None

                data = resp.read(MAX_IMAGE_SIZE_BYTES + 1)
                if len(data) > MAX_IMAGE_SIZE_BYTES:
                    _LOGGER.warning(
                        "Artwork exceeded size limit during download"
                    )
                    return None, None

                content_type = resp.headers.get("Content-Type", "image/jpeg")
                content_type = content_type.split(";")[0].strip().lower()

                # Validate the downloaded image
                try:
                    img = Image.open(io.BytesIO(data))
                    if not validate_pil_image(img):
                        _LOGGER.warning(
                            "Downloaded image failed validation: %s", url
                        )
                        return None, None
                except Exception:
                    _LOGGER.warning(
                        "Downloaded data is not a valid image: %s", url
                    )
                    return None, None

                return data, content_type
        except Exception as exc:
            _LOGGER.warning("Failed to download artwork from %s: %s", url, exc)
            return None, None

    def _update_current_gradient(self) -> None:
        """Resolve ``current_gradient`` from artwork gradients and the
        selected variant. Fires NowPlayingGradientChangedEvent on change."""
        artwork = self._state.artwork
        old_gradient = self._state.current_gradient

        if not artwork or not artwork.gradients:
            self._state.current_gradient = None
        else:
            variant = self._state.selected_gradient_variant
            variant_data = artwork.gradients.get(variant)
            if variant_data and "gradient" in variant_data:
                self._state.current_gradient = variant_data["gradient"]
            else:
                self._state.current_gradient = None

        if self._state.current_gradient != old_gradient:
            source_id = self._state.active_source_id or "unknown"
            self._fire_event(
                NowPlayingGradientChangedEvent(
                    source_id,
                    self._state.current_gradient,
                    self._state.selected_gradient_variant,
                )
            )

            # Apply gradient to target virtuals if enabled
            if self._gradient_enabled and self._state.current_gradient:
                self.apply_gradient_to_virtuals()
