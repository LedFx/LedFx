"""
Security utilities for LedFx.

This module provides security-related functions for path validation,
SSRF protection, and file type validation. These functions are used
across assets.py, utils.py, and API endpoints to ensure consistent
security controls.
"""

import http.client
import ipaddress
import logging
import mimetypes
import os
import socket
import urllib.parse
import urllib.request
from functools import partial

from PIL import Image

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
# Networks always blocked regardless of context
ALWAYS_BLOCKED_IP_NETWORKS = [
    # IPv4 Loopback
    ipaddress.ip_network("127.0.0.0/8"),
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
    # IPv6 Link-local
    ipaddress.ip_network("fe80::/10"),
    # IPv6 Multicast
    ipaddress.ip_network("ff00::/8"),
    # Obsolete IPv6 transition mechanisms that embed an IPv4 destination
    # (GHSA-pc6c-8c73-p6p2); embedded addresses are also checked below.
    ipaddress.ip_network("2002::/16"),  # 6to4 (RFC 3056)
    ipaddress.ip_network("2001::/32"),  # Teredo (RFC 4380)
    ipaddress.ip_network("::/96"),  # IPv4-compatible (RFC 4291, deprecated)
    # NAT64 local-use (RFC 8215): operator-chosen prefix length, so the IPv4
    # position is not fixed; block the range rather than guess.
    ipaddress.ip_network("64:ff9b:1::/48"),
]

# Private networks blocked by default but allowed with allow_private=True
PRIVATE_IP_NETWORKS = [
    # IPv4 Private networks
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Carrier-grade NAT / shared address space (RFC 6598), e.g. Tailscale
    ipaddress.ip_network("100.64.0.0/10"),
    # IPv6 Private/ULA
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fd00::/8"),
]

BLOCKED_IP_NETWORKS = ALWAYS_BLOCKED_IP_NETWORKS + PRIVATE_IP_NETWORKS

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
                        "Created %s subdirectory: %s",
                        directory_name,
                        parent_dir,
                    )
                except OSError as e:
                    return (
                        False,
                        None,
                        f"Failed to create parent directories: {e}",
                    )

        return True, resolved_path, None

    except (ValueError, OSError) as e:
        _LOGGER.warning("Path resolution failed for '%s': %s", relative_path, e)
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
        _LOGGER.warning("No allowed directories configured for path validation")
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
            "Path traversal attempt blocked: %s is outside allowed directories",
            file_path,
        )
        return False, None

    except (ValueError, OSError) as e:
        _LOGGER.warning("Invalid path rejected: %s : %s", file_path, e)
        return False, None


# =============================================================================
# SSRF Protection Functions
# =============================================================================


# NAT64 well-known prefix (RFC 6052): the last 32 bits are the IPv4
# destination. Checked via the embedded address rather than blocked outright,
# so DNS64 networks can still reach public hosts.
_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")


def _ip_and_embedded_ipv4(
    ip_str: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Parse an IP and add any IPv4 destination embedded in an IPv6 address.

    ipaddress never compares across families, so without this e.g.
    ::ffff:127.0.0.1 or 64:ff9b::a9fe:a9fe slips past the IPv4 blocks.
    """
    ip = ipaddress.ip_address(ip_str)
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            candidates.append(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            candidates.append(ip.sixtofour)
        if ip.teredo is not None:
            candidates.extend(ip.teredo)
        if ip in _NAT64_WELL_KNOWN or ip in ipaddress.ip_network("::/96"):
            candidates.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return candidates


def _is_in_networks(
    ip_str: str,
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    return any(
        ip in network for ip in _ip_and_embedded_ipv4(ip_str) for network in networks
    )


def is_blocked_ip(ip_str: str) -> bool:
    """
    Check if an IP address is in the blocklist.

    Args:
        ip_str: IP address string to check

    Returns:
        bool: True if IP is blocked
    """
    try:
        return _is_in_networks(ip_str, BLOCKED_IP_NETWORKS)
    except ValueError:
        # Invalid IP address
        return True


def validate_url_safety(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """
    Validate URL for SSRF protection by checking scheme, hostname, and resolved IP.

    Args:
        url: URL to validate
        allow_private: If True, allow private/LAN IP addresses (e.g. for
            fetching artwork from local media servers like Music Assistant).
            Loopback, link-local, and other dangerous ranges remain blocked.

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

        # Select which networks to block based on context
        blocked_networks = (
            ALWAYS_BLOCKED_IP_NETWORKS if allow_private else BLOCKED_IP_NETWORKS
        )

        # Check all resolved IPs
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = str(sockaddr[0])
            try:
                if _is_in_networks(ip_str, blocked_networks):
                    return (
                        False,
                        f"URL resolves to blocked IP address: {ip_str}",
                    )
            except ValueError:
                return False, f"Invalid IP address resolved: {ip_str}"

        return True, ""

    except Exception as e:  # noqa: BLE001
        return False, f"URL validation error: {e}"


def _create_validated_connection(
    address: tuple[str, int],
    timeout: float | None = None,
    source_address: tuple[str, int] | None = None,
    *,
    allow_private: bool = False,
) -> socket.socket:
    """socket.create_connection that connects only to addresses it validated.

    Resolving once and connecting to the checked sockaddr closes the DNS
    rebinding window between validate_url_safety() and the fetch, and also
    covers redirects, which never pass through validate_url_safety().
    """
    host, port = address
    if host.lower() in BLOCKED_HOSTNAMES:
        raise OSError(f"Hostname '{host}' is blocked")
    blocked_networks = (
        ALWAYS_BLOCKED_IP_NETWORKS if allow_private else BLOCKED_IP_NETWORKS
    )
    addr_info = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    for *_, sockaddr in addr_info:
        if _is_in_networks(str(sockaddr[0]), blocked_networks):
            raise OSError(f"'{host}' resolves to blocked IP address: {sockaddr[0]}")

    error: OSError | None = None
    for family, socktype, proto, _, sockaddr in addr_info:
        sock = socket.socket(family, socktype, proto)
        try:
            if timeout is not None:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            error = exc
            sock.close()
    raise error or OSError(f"Could not connect to '{host}'")


class _ValidatedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, allow_private: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = partial(
            _create_validated_connection, allow_private=allow_private
        )


class _ValidatedHTTPSConnection(http.client.HTTPSConnection):
    # TLS SNI and certificate checks still use the hostname (self.host).
    def __init__(self, *args, allow_private: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = partial(
            _create_validated_connection, allow_private=allow_private
        )


class _ValidatedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, allow_private: bool) -> None:
        super().__init__()
        self._allow_private = allow_private

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(
            partial(_ValidatedHTTPConnection, allow_private=self._allow_private), req
        )


class _ValidatedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, allow_private: bool) -> None:
        super().__init__()
        self._allow_private = allow_private

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(
            partial(_ValidatedHTTPSConnection, allow_private=self._allow_private),
            req,
            context=self._context,
        )


def safe_urlopen(
    request: urllib.request.Request | str,
    timeout: float,
    allow_private: bool = False,
) -> http.client.HTTPResponse:
    """urlopen that re-validates every connection, including redirects.

    Call validate_url_safety() first for a readable rejection reason; this
    enforces the same policy on the address actually connected to. Proxies
    are disabled (a proxy would resolve the target itself), and only
    http/https are handled, so redirects to ftp:// or file:// fail.
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler({}),
        urllib.request.UnknownHandler(),
        _ValidatedHTTPHandler(allow_private),
        _ValidatedHTTPSHandler(allow_private),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener.open(request, timeout=timeout)


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

    # For remote URLs, allow no extension (e.g., CDN URLs like https://cdn.example.com/image/abc123)
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
        return not (mime_type and mime_type not in ALLOWED_MIME_TYPES)
    except Exception:  # noqa: BLE001
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
        _LOGGER.warning("Rejected unsupported image format: %s", image.format)
        return False

    # Check pixel dimensions (prevent decompression bombs)
    if image.width * image.height > MAX_IMAGE_PIXELS:
        _LOGGER.warning(
            "Image too large: %sx%s pixels (max %s)",
            image.width,
            image.height,
            MAX_IMAGE_PIXELS,
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
        f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else ""
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
