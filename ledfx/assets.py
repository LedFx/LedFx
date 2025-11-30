"""
Secure asset storage system for LedFx.

This module provides helper functions for storing, listing, and managing
image assets within the LedFx configuration directory. All assets are stored
under `.ledfx/assets/` with strict security controls:

- Path traversal protection (no ../, symlinks, or absolute paths)
- File type validation (extension, MIME type, and PIL format checks)
- Size limits enforcement (default 2MB max)
- Atomic write operations via temporary files
- Safe path normalization and resolution

Supported image formats: png, jpg, jpeg, webp, gif, bmp, tiff, tif, ico
"""

import io
import logging
import os
import tempfile

import PIL.Image as Image

from ledfx.utils import validate_pil_image

_LOGGER = logging.getLogger(__name__)

# Asset storage configuration
ASSETS_DIRECTORY = "assets"  # Directory name under .ledfx/

# Allowed image extensions for asset storage (matches ALLOWED_IMAGE_EXTENSIONS in utils.py)
ALLOWED_ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".ico",
}

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
    if not relative_path:
        return False, None, "Empty path provided"

    # Normalize path separators and strip whitespace
    relative_path = relative_path.strip().replace("\\", "/")

    # Reject absolute paths (including leading slashes and protocol schemes)
    if os.path.isabs(relative_path) or relative_path.startswith("/") or "://" in relative_path:
        return False, None, "Absolute paths are not allowed"

    # Get the assets root directory
    assets_root = get_assets_directory(config_dir)

    try:
        # Join with assets directory and resolve to absolute path
        # This handles normalization and resolves any ../ components
        candidate_path = os.path.join(assets_root, relative_path)
        resolved_path = os.path.abspath(os.path.realpath(candidate_path))

        # Ensure the resolved path is still within the assets directory
        # Use commonpath to verify containment (works across platforms)
        try:
            common = os.path.commonpath([resolved_path, assets_root])
            if common != assets_root:
                return (
                    False,
                    None,
                    "Path escapes assets directory (path traversal blocked)",
                )
        except ValueError:
            # Different drives on Windows or other path incompatibility
            return (
                False,
                None,
                "Path is outside assets directory (different drive/root)",
            )

        # Create parent directories if requested
        if create_dirs:
            parent_dir = os.path.dirname(resolved_path)
            if not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    _LOGGER.debug(f"Created asset subdirectory: {parent_dir}")
                except OSError as e:
                    return (
                        False,
                        None,
                        f"Failed to create parent directories: {e}",
                    )

        return True, resolved_path, None

    except (ValueError, OSError) as e:
        _LOGGER.warning(f"Path resolution failed for '{relative_path}': {e}")
        return False, None, f"Invalid path: {e}"


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

    if ext_lower not in ALLOWED_ASSET_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_ASSET_EXTENSIONS))
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
    - Image dimensions are within safe limits

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
    4. Content validation (real image using Pillow)
    5. Overwrite protection (optional)
    6. Atomic write (temp file + rename)

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


def list_assets(config_dir: str) -> list[str]:
    """
    List all assets in the assets directory recursively.

    Returns normalized relative paths (forward slashes) suitable for API responses.
    Filters out:
    - Temporary files (.tmp extension)
    - System files (.DS_Store, Thumbs.db, etc.)
    - Non-image files (optionally, based on extension)

    Args:
        config_dir: LedFx configuration directory path

    Returns:
        List of relative asset paths (e.g., ["icon.png", "buttons/play.png"])
    """
    assets_root = get_assets_directory(config_dir)

    # Ensure assets directory exists
    if not os.path.exists(assets_root):
        _LOGGER.debug("Assets directory does not exist, returning empty list")
        return []

    assets = []

    try:
        # Walk the assets directory recursively
        for root, _dirs, files in os.walk(assets_root):
            for filename in files:
                # Skip ignored system files
                if filename in IGNORED_FILES:
                    continue

                # Skip temporary files
                if filename.endswith(".tmp") or filename.startswith(".asset_"):
                    continue

                # Get absolute path
                abs_path = os.path.join(root, filename)

                # Get relative path from assets root
                rel_path = os.path.relpath(abs_path, assets_root)

                # Normalize to forward slashes for consistency
                rel_path = rel_path.replace("\\", "/")

                # Optional: Only include files with allowed image extensions
                # This makes the listing cleaner for API consumers
                _, ext = os.path.splitext(filename)
                if ext.lower() not in ALLOWED_ASSET_EXTENSIONS:
                    _LOGGER.debug(
                        f"Skipping non-image file in assets: {rel_path}"
                    )
                    continue

                assets.append(rel_path)

        # Sort for consistent ordering
        assets.sort()

        _LOGGER.debug(f"Listed {len(assets)} assets")
        return assets

    except Exception as e:
        _LOGGER.error(f"Failed to list assets: {e}")
        return []


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
