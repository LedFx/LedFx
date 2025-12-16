"""
Secure asset storage system for LedFx.

This module provides helper functions for storing, listing, and managing
image assets within the LedFx configuration directory. All assets are stored
under `.ledfx/assets/` with strict security controls:

- Path traversal protection (no ../, symlinks, or absolute paths)
- File type validation (extension, MIME type, and PIL format checks)
- Size limits enforcement (default 10MB max)
- Atomic write operations via temporary files
- Safe path normalization and resolution

Supported image formats: png, jpg, jpeg, webp, gif, bmp, tiff, tif, ico
"""

import io
import logging
import mimetypes
import os
import tempfile
from datetime import datetime, timezone

import PIL.Image as Image

from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.utilities.image_utils import get_image_metadata
from ledfx.utilities.security_utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    resolve_safe_path_in_directory,
    validate_pil_image,
)
from ledfx.utils import get_image_cache

_LOGGER = logging.getLogger(__name__)

# Asset storage configuration
ASSETS_DIRECTORY = "assets"  # Directory name under .ledfx/

# Maximum file size for uploaded assets (10MB default)
# Accounts for animated GIFs and WebP which can be larger
DEFAULT_MAX_ASSET_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Files to ignore when listing assets
IGNORED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def get_assets_directory(config_dir: str) -> str:
    """
    Get the absolute path to the assets directory.

    Args:
        config_dir: LedFx configuration directory path

    Returns:
        Absolute path to the assets directory
    """
    return os.path.join(os.path.abspath(config_dir), ASSETS_DIRECTORY)


def ensure_assets_directory(config_dir: str) -> None:
    """
    Ensure the assets directory exists, creating it if necessary.

    Args:
        config_dir: LedFx configuration directory path

    Raises:
        OSError: If unable to create the assets directory
    """
    assets_dir = get_assets_directory(config_dir)

    if not os.path.exists(assets_dir):
        try:
            os.makedirs(assets_dir, exist_ok=True)
            _LOGGER.info(f"Created assets directory: {assets_dir}")
        except OSError as e:
            _LOGGER.error(f"Failed to create assets directory: {e}")
            raise


def resolve_safe_asset_path(
    config_dir: str, relative_path: str, create_dirs: bool = False
) -> tuple[bool, str | None, str | None]:
    """
    Resolve and validate an asset path, ensuring it stays within the assets directory.

    This function provides critical security protection against:
    - Path traversal attacks (../, ..\\ etc.)
    - Absolute path usage
    - Symlink escape
    - Paths resolving outside the assets directory

    Args:
        config_dir: LedFx configuration directory path
        relative_path: User-provided relative path to the asset
        create_dirs: If True, create parent directories if they don't exist

    Returns:
        tuple: (is_valid, absolute_path, error_message)
            - is_valid: True if path is safe and valid
            - absolute_path: Resolved absolute path within assets directory (None if invalid)
            - error_message: Description of validation failure (None if valid)
    """
    assets_root = get_assets_directory(config_dir)
    return resolve_safe_path_in_directory(
        assets_root, relative_path, create_dirs, "assets"
    )


def validate_asset_extension(file_path: str) -> tuple[bool, str | None]:
    """
    Validate that the file has an allowed image extension for asset storage.

    Args:
        file_path: Path to validate (can be relative or absolute)

    Returns:
        tuple: (is_valid, error_message)
            - is_valid: True if extension is allowed
            - error_message: Description of validation failure (None if valid)
    """
    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()

    if ext_lower not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        return (
            False,
            f"File extension '{ext}' not allowed. Allowed: {allowed}",
        )

    return True, None


def validate_asset_content(
    data: bytes, file_path: str
) -> tuple[bool, str | None, Image.Image | None]:
    """
    Validate that the file content is a real image using Pillow.

    This prevents attacks where non-image files are renamed with image extensions.
    Validates:
    - File can be opened by Pillow
    - File format matches allowed formats
    - MIME type matches allowed types
    - Image dimensions are within safe limits
    - Extension matches PIL format

    Args:
        data: Binary image data to validate
        file_path: File path (for extension cross-check and logging)

    Returns:
        tuple: (is_valid, error_message, image)
            - is_valid: True if content is a valid image
            - error_message: Description of validation failure (None if valid)
            - image: Opened PIL Image object (None if invalid)
    """
    try:
        # Try to open with Pillow
        image = Image.open(io.BytesIO(data))

        # Validate using existing utility function
        # This checks format, dimensions, and other PIL-level validations
        if not validate_pil_image(image):
            return (
                False,
                "Image validation failed (invalid format or dimensions)",
                None,
            )

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type not in ALLOWED_MIME_TYPES:
            return (
                False,
                f"Invalid MIME type: {mime_type} (not in allowed list)",
                None,
            )

        # Cross-check extension matches PIL format
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower().lstrip(".")

        pil_format = image.format
        if pil_format:
            # Normalize format names for comparison
            format_extensions = {
                "JPEG": {"jpg", "jpeg"},
                "PNG": {"png"},
                "WEBP": {"webp"},
                "GIF": {"gif"},
            }

            # Find matching format
            expected_exts = format_extensions.get(pil_format.upper(), set())
            if expected_exts and ext_lower not in expected_exts:
                return (
                    False,
                    f"Extension mismatch: file has .{ext_lower} but contains {pil_format} data",
                    None,
                )

        return True, None, image

    except Exception as e:
        _LOGGER.warning(f"Image validation failed for {file_path}: {e}")
        return False, f"Not a valid image file: {e}", None


def validate_asset_size(
    data: bytes, max_size: int = DEFAULT_MAX_ASSET_SIZE_BYTES
) -> tuple[bool, str | None]:
    """
    Validate that the asset size is within the allowed limit.

    Args:
        data: Binary data to check
        max_size: Maximum allowed size in bytes

    Returns:
        tuple: (is_valid, error_message)
            - is_valid: True if size is acceptable
            - error_message: Description of validation failure (None if valid)
    """
    size = len(data)

    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        return (
            False,
            f"File too large: {actual_mb:.2f}MB (max {max_mb:.2f}MB)",
        )

    return True, None


def save_asset(
    config_dir: str,
    relative_path: str,
    data: bytes,
    max_size: int = DEFAULT_MAX_ASSET_SIZE_BYTES,
    allow_overwrite: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Securely save an asset file with full validation and atomic write.

    This function performs comprehensive security checks:
    1. Path validation (no traversal, stays in assets directory)
    2. Extension validation (only allowed image types)
    3. Size validation (enforces max size limit)
    4. Content validation (MIME type, PIL format, real image data)
    5. Overwrite protection (optional)
    6. Atomic write (temp file + rename)
    7. Thumbnail cache invalidation (clears stale cached thumbnails)

    Args:
        config_dir: LedFx configuration directory path
        relative_path: Relative path within assets directory for the file
        data: Binary file data to save
        max_size: Maximum allowed file size in bytes
        allow_overwrite: If False, reject if file already exists (default)

    Returns:
        tuple: (success, absolute_path, error_message)
            - success: True if file was saved successfully
            - absolute_path: Full path to saved file (None if failed)
            - error_message: Description of failure (None if successful)

    Note:
        When an asset is saved (either new or overwriting existing), any cached
        thumbnails for that asset path are automatically cleared to prevent serving
        stale thumbnails on subsequent requests. Cache clearing failures do not
        affect the save operation.
    """
    # Ensure assets directory exists
    try:
        ensure_assets_directory(config_dir)
    except OSError as e:
        return False, None, f"Assets directory error: {e}"

    # 1. Validate and resolve safe path
    is_valid, absolute_path, error = resolve_safe_asset_path(
        config_dir, relative_path, create_dirs=True
    )
    if not is_valid:
        _LOGGER.warning(f"Path validation failed: {error}")
        return False, None, error

    # 2. Validate file extension
    is_valid, error = validate_asset_extension(absolute_path)
    if not is_valid:
        _LOGGER.warning(f"Extension validation failed: {error}")
        return False, None, error

    # 3. Check for overwrite if not allowed
    if not allow_overwrite and os.path.exists(absolute_path):
        return (
            False,
            None,
            f"File already exists: {relative_path} (overwrite not allowed)",
        )

    # 4. Validate file size
    is_valid, error = validate_asset_size(data, max_size)
    if not is_valid:
        _LOGGER.warning(f"Size validation failed: {error}")
        return False, None, error

    # 5. Validate content is a real image
    is_valid, error, image = validate_asset_content(data, absolute_path)
    if not is_valid:
        _LOGGER.warning(f"Content validation failed: {error}")
        return False, None, error

    # Image validated, can close it now
    if image:
        image.close()

    # 6. Perform atomic write via temporary file
    parent_dir = os.path.dirname(absolute_path)
    temp_fd = None
    temp_path = None

    try:
        # Create temporary file in same directory (ensures same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".tmp", dir=parent_dir, prefix=".asset_"
        )

        # Write data to temp file
        os.write(temp_fd, data)
        os.close(temp_fd)
        temp_fd = None  # Mark as closed

        # Atomically replace target file with temp file
        # On Windows, need to remove target first if it exists
        if os.name == "nt" and os.path.exists(absolute_path):
            os.remove(absolute_path)

        os.rename(temp_path, absolute_path)
        temp_path = None  # Mark as moved

        _LOGGER.info(f"Saved asset: {relative_path} ({len(data)} bytes)")

        # Clear any cached thumbnails for this asset to prevent stale thumbnails
        try:
            cache = get_image_cache()
            if cache:
                cache_url = f"asset://{relative_path}"
                deleted_count = cache.delete_all_for_url(cache_url)
                if deleted_count > 0:
                    _LOGGER.info(
                        f"Cleared {deleted_count} cached thumbnail(s) for {relative_path}"
                    )
        except Exception as e:
            # Log but don't fail the save operation if cache clearing fails
            _LOGGER.warning(
                f"Failed to clear cached thumbnails for {relative_path}: {e}"
            )

        return True, absolute_path, None

    except Exception as e:
        _LOGGER.error(f"Failed to save asset {relative_path}: {e}")
        return False, None, f"Write failed: {e}"

    finally:
        # Clean up on any failure
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except Exception:
                pass

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to clean up temp file {temp_path}: {e}"
                )


def delete_asset(
    config_dir: str, relative_path: str
) -> tuple[bool, str | None]:
    """
    Securely delete an asset file.

    Validates that the path is within the assets directory before deletion.

    Args:
        config_dir: LedFx configuration directory path
        relative_path: Relative path within assets directory to delete

    Returns:
        tuple: (success, error_message)
            - success: True if file was deleted successfully
            - error_message: Description of failure (None if successful)
    """
    # Validate and resolve safe path (don't create dirs)
    is_valid, absolute_path, error = resolve_safe_asset_path(
        config_dir, relative_path, create_dirs=False
    )
    if not is_valid:
        _LOGGER.warning(f"Path validation failed for delete: {error}")
        return False, error

    # Check if file exists
    if not os.path.exists(absolute_path):
        return False, f"Asset not found: {relative_path}"

    # Ensure it's a file, not a directory
    if not os.path.isfile(absolute_path):
        return False, f"Not a file: {relative_path}"

    # Delete the file
    try:
        os.remove(absolute_path)
        _LOGGER.info(f"Deleted asset: {relative_path}")

        # Optionally clean up empty parent directories (but not assets root)
        _cleanup_empty_directories(config_dir, os.path.dirname(absolute_path))

        return True, None

    except Exception as e:
        _LOGGER.error(f"Failed to delete asset {relative_path}: {e}")
        return False, f"Delete failed: {e}"


def _cleanup_empty_directories(config_dir: str, dir_path: str) -> None:
    """
    Remove empty directories up to (but not including) the assets root.

    This is a helper to keep the asset tree clean after deletions.

    Args:
        config_dir: LedFx configuration directory path
        dir_path: Directory to start cleanup from
    """
    assets_root = get_assets_directory(config_dir)

    current = dir_path
    while current and current != assets_root:
        try:
            # Only remove if directory is empty
            if os.path.isdir(current) and not os.listdir(current):
                os.rmdir(current)
                _LOGGER.debug(f"Removed empty directory: {current}")
                current = os.path.dirname(current)
            else:
                # Not empty or not a directory, stop
                break
        except Exception as e:
            _LOGGER.debug(f"Could not remove directory {current}: {e}")
            break


def _list_assets_from_directory(
    root_dir: str, log_prefix: str = "assets"
) -> list[dict]:
    """
    List all image assets in a directory recursively with metadata.

    Internal helper function that walks a directory tree and extracts metadata
    for all image files.

    Args:
        root_dir: Root directory to scan for assets
        log_prefix: Prefix for log messages (e.g., "assets", "built-in assets")

    Returns:
        List of asset metadata dicts, each containing:
            - path: Relative path from root_dir
            - size: File size in bytes
            - modified: ISO 8601 timestamp of last modification
            - width: Image width in pixels
            - height: Image height in pixels
            - format: Image format (e.g., "PNG", "JPEG", "GIF", "WEBP")
            - n_frames: Number of frames (1 for static images, >1 for animations)
            - is_animated: Boolean indicating if image is animated
    """
    if not os.path.exists(root_dir):
        _LOGGER.debug(
            f"{log_prefix.capitalize()} directory does not exist: {root_dir}"
        )
        return []

    assets = []

    try:
        # Walk the directory recursively
        for root, _dirs, files in os.walk(root_dir):
            for filename in files:
                # Skip ignored system files
                if filename in IGNORED_FILES:
                    continue

                # Skip temporary files
                if filename.endswith(".tmp") or filename.startswith(".asset_"):
                    continue

                # Get absolute path
                abs_path = os.path.join(root, filename)

                # Get relative path from root directory
                rel_path = os.path.relpath(abs_path, root_dir)

                # Normalize to forward slashes for consistency
                rel_path = rel_path.replace("\\", "/")

                # Only include files with allowed image extensions
                _, ext = os.path.splitext(filename)
                if ext.lower() not in ALLOWED_IMAGE_EXTENSIONS:
                    _LOGGER.debug(
                        f"Skipping non-image file in {log_prefix}: {rel_path}"
                    )
                    continue

                # Get file metadata
                try:
                    stat_info = os.stat(abs_path)
                    file_size = stat_info.st_size
                    modified_time = datetime.fromtimestamp(
                        stat_info.st_mtime, tz=timezone.utc
                    ).isoformat()

                    # Get image dimensions and animation metadata
                    width, height, img_format, n_frames, is_animated = (
                        get_image_metadata(abs_path)
                    )

                    assets.append(
                        {
                            "path": rel_path,
                            "size": file_size,
                            "modified": modified_time,
                            "width": width,
                            "height": height,
                            "format": img_format,
                            "n_frames": n_frames,
                            "is_animated": is_animated,
                        }
                    )

                except Exception as e:
                    _LOGGER.warning(
                        f"Could not get metadata for {log_prefix} {rel_path}: {e}"
                    )
                    # Skip this file if we can't get its metadata
                    continue

        # Sort by path for consistent ordering
        assets.sort(key=lambda x: x["path"])

        _LOGGER.debug(f"Listed {len(assets)} {log_prefix} with metadata")

    except Exception as e:
        _LOGGER.error(f"Error listing {log_prefix}: {e}")

    return assets


def list_assets(config_dir: str) -> list[dict]:
    """
    List all assets in the assets directory recursively with metadata.

    Returns asset information including path, size, modification time, and dimensions.
    Filters out:
    - Temporary files (.tmp extension)
    - System files (.DS_Store, Thumbs.db, etc.)
    - Non-image files (optionally, based on extension)

    Args:
        config_dir: LedFx configuration directory path

    Returns:
        List of asset metadata dicts, each containing:
            - path: Relative path (e.g., "icon.png", "buttons/play.png")
            - size: File size in bytes
            - modified: ISO 8601 timestamp of last modification
            - width: Image width in pixels
            - height: Image height in pixels
            - format: Image format (e.g., "PNG", "JPEG", "GIF", "WEBP")
            - n_frames: Number of frames (1 for static images, >1 for animations)
            - is_animated: Boolean indicating if image is animated
    """
    assets_root = get_assets_directory(config_dir)
    return _list_assets_from_directory(assets_root, "assets")


def get_asset_path(
    config_dir: str, relative_path: str
) -> tuple[bool, str | None, str | None]:
    """
    Get the absolute path to an existing asset file.

    This is a convenience function for retrieving assets with validation.

    Args:
        config_dir: LedFx configuration directory path
        relative_path: Relative path within assets directory

    Returns:
        tuple: (exists, absolute_path, error_message)
            - exists: True if asset exists and is accessible
            - absolute_path: Full path to asset file (None if not found)
            - error_message: Description of issue (None if successful)
    """
    # Validate and resolve safe path
    is_valid, absolute_path, error = resolve_safe_asset_path(
        config_dir, relative_path, create_dirs=False
    )
    if not is_valid:
        return False, None, error

    # Check if file exists
    if not os.path.exists(absolute_path):
        return False, None, f"Asset not found: {relative_path}"

    # Ensure it's a file
    if not os.path.isfile(absolute_path):
        return False, None, f"Not a file: {relative_path}"

    return True, absolute_path, None


def get_asset_or_builtin_path(
    config_dir: str, relative_path: str
) -> tuple[bool, str | None, str | None]:
    """
    Get the absolute path to an asset file from either user assets or built-in assets.

    Uses explicit prefix to differentiate sources:
    - "builtin://path" -> Built-in assets from LEDFX_ASSETS_PATH/gifs/
    - "path" (no prefix) -> User assets from config_dir/assets/

    Args:
        config_dir: LedFx configuration directory path
        relative_path: Relative path to the asset, optionally with "builtin://" prefix

    Returns:
        tuple: (exists, absolute_path, error_message)
            - exists: True if asset exists and is accessible
            - absolute_path: Full path to asset file (None if not found)
            - error_message: Description of issue (None if successful)

    Examples:
        "backgrounds/galaxy.jpg" -> User asset at {config_dir}/assets/backgrounds/galaxy.jpg
        "builtin://skull.gif" -> Built-in asset at {ledfx_assets}/gifs/skull.gif
        "builtin://pixelart/dj_bird.gif" -> Built-in at {ledfx_assets}/gifs/pixelart/dj_bird.gif
    """
    # Check for builtin:// prefix
    if relative_path.startswith("builtin://"):
        # Built-in asset requested explicitly
        actual_path = relative_path[10:]  # Remove "builtin://" prefix
        gifs_root = os.path.join(LEDFX_ASSETS_PATH, "gifs")

        # Use the same path validation as user assets
        is_valid, resolved_path, error = resolve_safe_path_in_directory(
            gifs_root,
            actual_path,
            create_dirs=False,
            directory_name="built-in assets",
        )

        if not is_valid:
            return False, None, error

        # Check if file exists
        if not os.path.exists(resolved_path):
            return False, None, f"Built-in asset not found: {actual_path}"

        # Ensure it's a file
        if not os.path.isfile(resolved_path):
            return False, None, f"Not a file: {actual_path}"

        return True, resolved_path, None

    # No prefix - user asset
    return get_asset_path(config_dir, relative_path)
