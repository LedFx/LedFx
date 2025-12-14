"""API endpoint for generating asset thumbnails."""

import io
import logging

from aiohttp import web
from PIL import Image

from ledfx import assets
from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache

_LOGGER = logging.getLogger(__name__)

# Default and limits for thumbnail size
DEFAULT_THUMBNAIL_SIZE = 128
MIN_THUMBNAIL_SIZE = 16
MAX_THUMBNAIL_SIZE = 512


def _calculate_thumbnail_dimensions(width, height, size, dimension):
    """
    Calculate thumbnail dimensions based on the requested size and dimension mode.

    Args:
        width: Original image width in pixels
        height: Original image height in pixels
        size: Target size in pixels
        dimension: Dimension mode - "max", "width", or "height"

    Returns:
        tuple: (new_width, new_height) for the thumbnail

    Raises:
        ValueError: If width or height are not positive non-zero integers
    """
    if width <= 0 or height <= 0:
        raise ValueError(
            f"Width and height must be positive non-zero integers, got width={width}, height={height}"
        )

    if dimension == "width":
        new_width = size
        new_height = max(1, int(height * (size / width)))
    elif dimension == "height":
        new_height = size
        new_width = max(1, int(width * (size / height)))
    else:  # dimension == "max"
        # Apply size to longest axis, maintaining aspect ratio
        if width > height:
            new_width = size
            new_height = max(1, int(height * (size / width)))
        else:
            new_height = size
            new_width = max(1, int(width * (size / height)))

    return new_width, new_height


class AssetsThumbnailEndpoint(RestEndpoint):
    """
    REST API endpoint for generating asset thumbnails on-demand.

    Generates thumbnails with configurable size, maintaining aspect ratio.
    - Static images: PNG format
    - Animated images: WebP format (preserves animation)

    Supports user-uploaded assets, built-in assets, and remote URLs:
    - User assets: "icons/led.png" (no prefix)
    - Built-in assets: "builtin://skull.gif" (builtin:// prefix)
    - Remote URLs: "https://example.com/image.gif" (automatically fetched and cached)

    Remote URLs are validated (SSRF protection, size limits, content validation),
    fetched if not cached, and cached for future requests.
    """

    ENDPOINT_PATH = "/api/assets/thumbnail"

    async def post(self, request: web.Request) -> web.Response:
        """
        Generate and return a thumbnail of an asset.

        Request Body (JSON):
            path (required): Asset identifier
                - User assets: "icons/led.png" (no prefix)
                - Built-in assets: "builtin://skull.gif" (builtin:// prefix)
                - Cached URLs: "https://example.com/image.gif" (http:// or https://)
            size (optional): Dimension size in pixels (default 128, range 16-512)
            dimension (optional): Which dimension to apply size to (default "max")
                - "max": Apply to longest axis (default)
                - "width": Apply to width, scale height proportionally
                - "height": Apply to height, scale width proportionally
            animated (optional): For multi-frame images, preserve animation (default true)
                - true: Return animated WebP for animated images
                - false: Return static PNG of first frame
            force_refresh (optional): Force regeneration bypassing cache (default false)
                - true: Clear cache and regenerate thumbnail
                - false: Use cached thumbnail if available

        Returns:
            PNG or WebP image data with appropriate Content-Type header.
            - Static images: image/png
            - Animated images (when animated=true): image/webp
            - Animated images (when animated=false): image/png (first frame only)
        """
        try:
            data = await request.json()
        except Exception:
            return await self.json_decode_error()

        asset_path = data.get("path")
        if not asset_path:
            return await self.invalid_request(
                message='Required attribute "path" was not provided',
                type="error",
            )

        # Get and validate size parameter
        size = data.get("size", DEFAULT_THUMBNAIL_SIZE)
        try:
            size = int(size)
            if size < MIN_THUMBNAIL_SIZE or size > MAX_THUMBNAIL_SIZE:
                return await self.invalid_request(
                    message=f"Size must be between {MIN_THUMBNAIL_SIZE} and {MAX_THUMBNAIL_SIZE} pixels",
                    type="error",
                )
        except (ValueError, TypeError):
            return await self.invalid_request(
                message="Size must be an integer",
                type="error",
            )

        # Get and validate dimension parameter
        dimension = data.get("dimension", "max")
        if dimension not in ("max", "width", "height"):
            return await self.invalid_request(
                message='Dimension must be "max", "width", or "height"',
                type="error",
            )

        # Get and validate animated parameter
        animated = data.get("animated", True)
        if not isinstance(animated, bool):
            return await self.invalid_request(
                message=f"Invalid animated value type: {type(animated).__name__}. Must be boolean (true/false)",
                type="error",
            )

        # Get and validate force_refresh parameter
        force_refresh = data.get("force_refresh", False)
        if not isinstance(force_refresh, bool):
            return await self.invalid_request(
                message=f"Invalid force_refresh value type: {type(force_refresh).__name__}. Must be boolean (true/false)",
                type="error",
            )

        # Check if path is a cached remote URL
        is_cached_url = asset_path.startswith(("http://", "https://"))

        # Create cache key with parameters
        # Use "asset://" prefix for local assets to distinguish from URL-based cache
        # For cached URLs, use the URL directly as the cache key
        if is_cached_url:
            cache_url = asset_path
        else:
            cache_url = f"asset://{asset_path}"

        cache_params = {
            "size": size,
            "dimension": dimension,
            "animated": animated,
        }

        # Check cache first (unless force_refresh is requested)
        cache = get_image_cache()
        if cache and not force_refresh:
            cached_path = cache.get(cache_url, cache_params)
            if cached_path:
                try:
                    # Return cached thumbnail
                    with open(cached_path, "rb") as f:
                        cached_data = f.read()

                    # Determine content type from extension
                    content_type = (
                        "image/webp"
                        if cached_path.endswith(".webp")
                        else "image/png"
                    )

                    _LOGGER.debug(
                        f"Returning cached thumbnail for {asset_path} (size={size}, dimension={dimension}, animated={animated})"
                    )

                    return web.Response(
                        body=cached_data,
                        headers={"Content-Type": content_type},
                    )
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to read cached thumbnail, regenerating: {e}"
                    )
                    # Delete corrupt cache entry and fall through to regenerate
                    cache.delete(cache_url, cache_params)

        try:
            # For URLs, fetch and cache if needed (with validation)
            if is_cached_url:
                from ledfx.utils import open_image

                # open_image handles URL validation, download, and caching
                try:
                    image = open_image(
                        asset_path, config_dir=self._ledfx.config_dir
                    )
                    if not image:
                        return await self.invalid_request(
                            message=f"Failed to download or validate URL: {asset_path}",
                            type="error",
                        )

                    # Get cached path after successful download
                    if not cache:
                        return await self.invalid_request(
                            message="Image cache not initialized",
                            type="error",
                        )

                    abs_path = cache.get(asset_path)
                    if not abs_path:
                        return await self.invalid_request(
                            message=f"Failed to cache URL: {asset_path}",
                            type="error",
                        )
                except Exception as e:
                    _LOGGER.warning(f"Failed to fetch URL {asset_path}: {e}")
                    return await self.invalid_request(
                        message=f"Failed to fetch URL: {e}",
                        type="error",
                    )
            else:
                # Get the asset path (checks both user assets and built-in assets)
                exists, abs_path, error = assets.get_asset_or_builtin_path(
                    self._ledfx.config_dir, asset_path
                )

                if not exists:
                    return await self.invalid_request(
                        message=error or f"Asset not found: {asset_path}",
                        type="error",
                    )

            # Open and generate thumbnail
            try:
                with Image.open(abs_path) as img:
                    # Check if image is animated
                    is_animated_image = getattr(img, "is_animated", False)
                    n_frames = getattr(img, "n_frames", 1)

                    if animated and is_animated_image and n_frames > 1:
                        # Process animated image - create WebP thumbnail
                        frames = []
                        durations = []

                        for frame_idx in range(n_frames):
                            img.seek(frame_idx)
                            frame = img.copy()

                            # Convert frame to RGBA for consistency
                            # This ensures palette/grayscale frames are handled properly
                            if frame.mode != "RGBA":
                                frame = frame.convert("RGBA")

                            # Calculate dimensions
                            width, height = frame.size
                            new_width, new_height = (
                                _calculate_thumbnail_dimensions(
                                    width, height, size, dimension
                                )
                            )

                            # Resize frame
                            resized_frame = frame.resize(
                                (new_width, new_height),
                                Image.Resampling.LANCZOS,
                            )
                            frames.append(resized_frame)

                            # Get frame duration (default 100ms if not available)
                            duration = img.info.get("duration", 100)
                            durations.append(duration)

                        # Save as animated WebP
                        buffer = io.BytesIO()
                        frames[0].save(
                            buffer,
                            format="WEBP",
                            save_all=True,
                            append_images=frames[1:],
                            duration=durations,
                            loop=0,
                            optimize=True,
                        )
                        buffer.seek(0)

                        thumbnail_data = buffer.read()

                        # Clear existing cache entry if force_refresh was requested
                        if cache and force_refresh:
                            cache.delete(cache_url, cache_params)

                        # Cache the generated thumbnail
                        if cache:
                            try:
                                cache.put(
                                    cache_url,
                                    thumbnail_data,
                                    "image/webp",
                                    params=cache_params,
                                )
                                _LOGGER.debug(
                                    f"Cached animated thumbnail for {asset_path}"
                                )
                            except Exception as e:
                                _LOGGER.warning(
                                    f"Failed to cache thumbnail: {e}"
                                )

                        return web.Response(
                            body=thumbnail_data,
                            headers={"Content-Type": "image/webp"},
                        )
                    else:
                        # Process static image - create PNG thumbnail
                        # For animated images with animated=false, use first frame
                        if is_animated_image and n_frames > 1:
                            img.seek(0)  # Get first frame

                        # Convert to RGB if necessary (handles RGBA, P, etc.)
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")

                        # Calculate thumbnail dimensions based on dimension parameter
                        width, height = img.size
                        new_width, new_height = (
                            _calculate_thumbnail_dimensions(
                                width, height, size, dimension
                            )
                        )

                        # Resize image
                        img = img.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                        # Save to bytes buffer as PNG
                        buffer = io.BytesIO()
                        img.save(buffer, format="PNG", optimize=True)
                        buffer.seek(0)

                        thumbnail_data = buffer.read()

                        # Clear existing cache entry if force_refresh was requested
                        if cache and force_refresh:
                            cache.delete(cache_url, cache_params)

                        # Cache the generated thumbnail
                        if cache:
                            try:
                                cache.put(
                                    cache_url,
                                    thumbnail_data,
                                    "image/png",
                                    params=cache_params,
                                )
                                _LOGGER.debug(
                                    f"Cached static thumbnail for {asset_path}"
                                )
                            except Exception as e:
                                _LOGGER.warning(
                                    f"Failed to cache thumbnail: {e}"
                                )

                        return web.Response(
                            body=thumbnail_data,
                            headers={"Content-Type": "image/png"},
                        )

            except Exception as e:
                _LOGGER.warning(
                    f"Failed to generate thumbnail for {asset_path}: {e}"
                )
                return await self.internal_error(
                    message=f"Failed to generate thumbnail: {e}"
                )

        except Exception as e:
            _LOGGER.warning(f"Failed to process thumbnail request: {e}")
            return await self.internal_error(
                message=f"Failed to process request: {e}"
            )
