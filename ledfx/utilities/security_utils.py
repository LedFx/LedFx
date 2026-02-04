"""
Security utilities for LedFx.

This module provides security-related functions for path validation,
SSRF protection, and file type validation. These functions are used
across assets.py, utils.py, and API endpoints to ensure consistent
security controls.
"""

import ipaddress
import logging
import mimetypes
import os
import socket
import urllib.parse
import urllib.request

import PIL.Image as Image

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# Image File Type Constants
# =============================================================================

ALLOWED_IMAGE_EXTENSIONS = {
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".ico",
}

ALLOWED_MIME_TYPES = {
    "image/gif",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/x-icon",
}

ALLOWED_PIL_FORMATS = {
    "GIF",
    "PNG",
    "JPEG",
    "WEBP",
    "BMP",
    "TIFF",
    "ICO",
    "PPM",
    "PGM",
    "PBM",
}

# =============================================================================
# Image Size Limits
# =============================================================================

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 4096 * 4096  # Prevent decompression bombs
DOWNLOAD_TIMEOUT = 30  # seconds

# =============================================================================
# SSRF Protection
# =============================================================================

# Blocked IP ranges for SSRF protection
BLOCKED_IP_NETWORKS = [
    # IPv4 Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    # IPv4 Private networks
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # IPv4 Link-local
    ipaddress.ip_network("169.254.0.0/16"),
    # IPv4 Reserved ranges
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("240.0.0.0/4"),
    # IPv4 Multicast
    ipaddress.ip_network("224.0.0.0/4"),
    # IPv6 Loopback
    ipaddress.ip_network("::1/128"),
    # IPv6 Unspecified
    ipaddress.ip_network("::/128"),
    # IPv6 Private/ULA
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fd00::/8"),
    # IPv6 Link-local
    ipaddress.ip_network("fe80::/10"),
    # IPv6 Multicast
    ipaddress.ip_network("ff00::/8"),
]

# Cloud metadata endpoints (commonly targeted in SSRF attacks)
BLOCKED_HOSTNAMES = [
    "169.254.169.254",  # AWS, Azure, GCP metadata
    "metadata.google.internal",  # GCP
    "169.254.170.2",  # AWS ECS metadata
]


# =============================================================================
# Path Security Functions
# =============================================================================


def resolve_safe_path_in_directory(
    root_dir: str,
    relative_path: str,
    create_dirs: bool = False,
    directory_name: str = "directory",
) -> tuple[bool, str | None, str | None]:
    """
    Resolve and validate a path within a root directory.

    Provides security protection against path traversal, absolute paths, and symlink escapes.

    Args:
        root_dir: Root directory to constrain paths within
        relative_path: User-provided relative path
        create_dirs: If True, create parent directories if they don't exist
        directory_name: Name of directory type for error messages

    Returns:
        tuple: (is_valid, absolute_path, error_message)
    """
    if not relative_path:
        return False, None, "Empty path provided"

    # Normalize path separators and strip whitespace
    relative_path = relative_path.strip().replace("\\", "/")

    # Reject absolute paths (including leading slashes and protocol schemes)
    if (
        os.path.isabs(relative_path)
        or relative_path.startswith("/")
        or "://" in relative_path
    ):
        return False, None, "Absolute paths are not allowed"

    try:
        # Join with root directory and resolve to absolute path
        # This handles normalization and resolves any ../ components
        candidate_path = os.path.join(root_dir, relative_path)
        resolved_path = os.path.abspath(os.path.realpath(candidate_path))
        normalized_root = os.path.abspath(os.path.realpath(root_dir))

        # Ensure the resolved path is still within the root directory
        # Use commonpath to verify containment (works across platforms)
        try:
            common = os.path.commonpath([resolved_path, normalized_root])
            if common != normalized_root:
                return (
                    False,
                    None,
                    f"Path escapes {directory_name} directory (path traversal blocked)",
                )
        except ValueError:
            # Different drives on Windows or other path incompatibility
            return (
                False,
                None,
                f"Path is outside {directory_name} directory (different drive/root)",
            )

        # Create parent directories if requested
        if create_dirs:
            parent_dir = os.path.dirname(resolved_path)
            if not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    _LOGGER.debug(
                        f"Created {directory_name} subdirectory: {parent_dir}"
                    )
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


def validate_local_path(
    file_path: str, allowed_directories: list[str]
) -> tuple[bool, str | None]:
    """
    Validate that local file path is within allowed directories (path traversal protection).

    Args:
        file_path: Local file path to validate
        allowed_directories: List of absolute paths to allowed directories

    Returns:
        tuple: (is_valid, validated_path) where validated_path is the absolute normalized path
               or None if validation failed
    """
    if not allowed_directories:
        _LOGGER.warning(
            "No allowed directories configured for path validation"
        )
        return False, None

    try:
        # Resolve to absolute path and normalize
        abs_path = os.path.abspath(os.path.realpath(file_path))

        # Check if file is within any allowed directory
        for allowed_dir in allowed_directories:
            abs_allowed = os.path.abspath(os.path.realpath(allowed_dir))

            try:
                common = os.path.commonpath([abs_path, abs_allowed])
                if common == abs_allowed:
                    return True, abs_path
            except ValueError:
                # Different drives on Windows, continue checking other directories
                continue

        _LOGGER.warning(
            f"Path traversal attempt blocked: {file_path} is outside allowed directories"
        )
        return False, None

    except (ValueError, OSError) as e:
        _LOGGER.warning(f"Invalid path rejected: {file_path} : {e}")
        return False, None


# =============================================================================
# SSRF Protection Functions
# =============================================================================


def is_blocked_ip(ip_str: str) -> bool:
    """
    Check if an IP address is in the blocklist.

    Args:
        ip_str: IP address string to check

    Returns:
        bool: True if IP is blocked
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_IP_NETWORKS:
            if ip in network:
                return True
        return False
    except ValueError:
        # Invalid IP address
        return True


def validate_url_safety(url: str) -> tuple[bool, str]:
    """
    Validate URL for SSRF protection by checking scheme, hostname, and resolved IP.

    Args:
        url: URL to validate

    Returns:
        tuple: (is_safe, error_message)
    """
    try:
        parsed = urllib.parse.urlparse(url)

        # Only allow HTTP/HTTPS
        if parsed.scheme not in ("http", "https"):
            return False, f"Protocol '{parsed.scheme}' not allowed"

        hostname = parsed.hostname
        if not hostname:
            return False, "No hostname found in URL"

        # Check against blocked hostname list
        if hostname.lower() in BLOCKED_HOSTNAMES:
            return False, f"Hostname '{hostname}' is blocked"

        # Resolve hostname to IP addresses
        try:
            addr_info = socket.getaddrinfo(
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            )
        except socket.gaierror as e:
            return False, f"Failed to resolve hostname '{hostname}': {e}"

        # Check all resolved IPs
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]

            # Check if IP is blocked
            if is_blocked_ip(ip_str):
                return False, f"URL resolves to blocked IP address: {ip_str}"

        return True, ""

    except Exception as e:
        return False, f"URL validation error: {e}"


# =============================================================================
# File Type Validation Functions
# =============================================================================


def is_allowed_image_extension(path: str) -> bool:
    """
    Check if file extension is in allowlist.

    For remote URLs (http/https), allows URLs without extensions since content
    will be validated after download via Content-Type header and PIL validation.
    For local files, extension must be in the allowlist.

    Args:
        path: File path or URL to check

    Returns:
        bool: True if extension is allowed or if remote URL without extension
    """
    # Parse URL to remove query strings and fragments
    parsed = urllib.parse.urlparse(path)

    # Use parsed path component for URLs (http/https or if netloc is present)
    if parsed.scheme in ("http", "https") or parsed.netloc:
        path_to_check = parsed.path
    else:
        # Keep original path for local files
        path_to_check = path

    ext = os.path.splitext(path_to_check.lower())[1]
    
    # For remote URLs, allow no extension (e.g., Spotify CDN URLs like https://i.scdn.co/image/)
    # Content will be validated after download via Content-Type header and PIL validation
    if parsed.scheme in ("http", "https"):
        return ext in ALLOWED_IMAGE_EXTENSIONS or not ext
    
    # For local files, extension must be in allowlist
    return ext in ALLOWED_IMAGE_EXTENSIONS


def validate_image_mime_type(file_path: str) -> bool:
    """
    Validate file MIME type using multiple methods.

    Args:
        file_path: Path to file to validate (must be pre-validated by validate_local_path)

    Returns:
        bool: True if MIME type is allowed
    """
    try:
        # Try to open with PIL to detect format from content
        # lgtm[py/path-injection] - file_path is validated by validate_local_path before calling this function
        with Image.open(file_path) as img:
            # PIL format detection (more reliable than imghdr)
            if img.format is None:
                return False

            # Check if PIL format is in allowed list
            if img.format.upper() not in ALLOWED_PIL_FORMATS:
                return False

        # Additional MIME check using file extension
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type not in ALLOWED_MIME_TYPES:
            return False

        return True
    except Exception:
        return False


def validate_pil_image(image: Image.Image) -> bool:
    """
    Validate PIL image format and dimensions.

    Args:
        image: PIL Image object

    Returns:
        bool: True if image format and size are allowed
    """
    # Check format
    if image.format not in ALLOWED_PIL_FORMATS:
        _LOGGER.warning(f"Rejected unsupported image format: {image.format}")
        return False

    # Check pixel dimensions (prevent decompression bombs)
    if image.width * image.height > MAX_IMAGE_PIXELS:
        _LOGGER.warning(
            f"Image too large: {image.width}x{image.height} pixels "
            f"(max {MAX_IMAGE_PIXELS})"
        )
        return False

    return True


def build_browser_request(url: str) -> urllib.request.Request:
    """
    Build a URL request with browser-like headers to avoid hotlink blocking.

    Args:
        url: URL to create request for

    Returns:
        urllib.request.Request with User-Agent and Referer headers
    """
    parsed = urllib.parse.urlsplit(url)
    origin = (
        f"{parsed.scheme}://{parsed.netloc}/"
        if parsed.scheme and parsed.netloc
        else ""
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Safari/537.36"
        ),
        "Referer": origin,  # helps with sites that block direct hotlinks (e.g., JSTOR)
    }
    return urllib.request.Request(url, headers=headers)
