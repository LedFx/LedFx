# Security Review: Input Validation & Path Traversal

**Date**: 2025-11-13  
**Reviewer**: Security Review  
**Scope**: Python codebase input validation and file handling

## Executive Summary

Security review identified **Path Traversal vulnerabilities** in image/file handling endpoints. These vulnerabilities allow attackers to read arbitrary files from the server filesystem by manipulating file paths in API requests.

## Vulnerabilities Identified

### 1. Path Traversal in `open_image` Function

**Severity**: HIGH  
**File**: `ledfx/utils.py:1518`  
**Endpoint**: `/api/get_image` (`ledfx/api/get_image.py`)

#### Vulnerability Details
The `open_image` function accepts a user-provided `image_path` parameter and directly opens files without validating the path. This allows path traversal attacks.

**Vulnerable Code:**
```python
def open_image(image_path):
    try:
        image_path = image_path.strip()
        _LOGGER.info(f"Attempting to open image: {image_path}")
        if image_path.startswith(("http://", "https://")):
            # ... URL handling ...
        else:
            image = Image.open(image_path)  # ❌ No path validation!
            return image
```

**Attack Scenario:**
```json
POST /api/get_image
{
  "path_url": "../../../../../../etc/passwd"
}
```

An attacker could read any file accessible to the LedFx process, including:
- Configuration files with credentials
- System files
- Other users' data
- Private keys

#### Impact
- **Confidentiality**: HIGH - Arbitrary file read
- **Integrity**: NONE
- **Availability**: NONE

### 2. Path Traversal in `open_gif` Function

**Severity**: HIGH  
**File**: `ledfx/utils.py:1484`  
**Endpoint**: `/api/get_gif_frames` (`ledfx/api/get_gif_frames.py`)

#### Vulnerability Details
Similar to `open_image`, the `open_gif` function accepts user-provided paths without validation.

**Vulnerable Code:**
```python
def open_gif(gif_path):
    try:
        gif_path = gif_path.strip()
        if gif_path.startswith(("http://", "https://")):
            # ... URL handling ...
        else:
            gif = Image.open(gif_path)  # ❌ No path validation!
            return gif
```

**Attack Scenario:**
```json
POST /api/get_gif_frames
{
  "path_url": "../../../config.json"
}
```

#### Impact
Same as vulnerability #1 - arbitrary file read.

## Additional Security Concerns

### URL Handling
Both functions accept HTTP/HTTPS URLs which could be exploited for:
- **SSRF (Server-Side Request Forgery)**: Access internal network resources
- **Information Disclosure**: Probe internal services
- **Denial of Service**: Request large files or slow endpoints

### No File Type Validation
While PIL handles malformed images safely, there's no explicit validation of file types before processing, which could lead to resource exhaustion with large files.

## Recommendations

### Immediate Actions (Critical)

1. **Implement Path Validation**
   - Validate and sanitize all file paths
   - Use allowlist approach for permitted directories
   - Reject paths with directory traversal patterns (`..`, absolute paths)
   - Use `os.path.realpath()` and verify resolved path is within allowed directory

2. **Restrict File Access**
   - Define a safe directory for user-provided image/gif files
   - Only allow access to files within that directory
   - Consider using a content-addressable storage system

3. **URL Validation for SSRF Prevention**
   - Validate URL schemes (only allow http/https)
   - Block private IP ranges (127.0.0.1, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
   - Block metadata endpoints (169.254.169.254)
   - Implement URL allowlist if possible

4. **Add File Size Limits**
   - Limit maximum file size for image/gif processing
   - Implement timeout for network requests
   - Add rate limiting to endpoints

### Medium Priority

5. **Add File Type Validation**
   - Verify file magic numbers (not just extensions)
   - Reject files that aren't valid images

6. **Implement Audit Logging**
   - Log all file access attempts
   - Alert on suspicious patterns (repeated failures, traversal attempts)

7. **Add API Authentication/Authorization**
   - Verify endpoints require authentication
   - Implement rate limiting per user

### Long-term Actions

8. **Security Testing**
   - Add security tests for path traversal
   - Implement fuzzing for API endpoints
   - Regular penetration testing

9. **Security Headers**
   - Implement CSP (Content Security Policy)
   - Add security headers to all responses

10. **Dependency Scanning**
    - Automated scanning for vulnerable dependencies
    - Regular updates of critical dependencies

## Proposed Fix

### Path Sanitization Function
```python
import os
from pathlib import Path

ALLOWED_IMAGE_DIRS = [
    Path(get_default_config_directory()) / "images",
    Path(LEDFX_ASSETS_PATH) / "images",
]

def validate_file_path(file_path: str, allowed_dirs: list) -> Path:
    """
    Validate and sanitize a file path to prevent directory traversal.
    
    Args:
        file_path: User-provided file path
        allowed_dirs: List of allowed base directories
        
    Returns:
        Resolved Path object if valid
        
    Raises:
        ValueError: If path is invalid or outside allowed directories
    """
    try:
        # Convert to Path and resolve to absolute path
        path = Path(file_path).resolve()
        
        # Check if path is within any allowed directory
        for allowed_dir in allowed_dirs:
            allowed_dir = allowed_dir.resolve()
            try:
                # Check if path is relative to allowed_dir
                path.relative_to(allowed_dir)
                # If we get here, path is within allowed_dir
                if path.is_file():
                    return path
            except ValueError:
                # Path is not relative to this allowed_dir, try next
                continue
        
        # Path is not in any allowed directory
        raise ValueError(f"Path {file_path} is not in allowed directories")
        
    except Exception as e:
        raise ValueError(f"Invalid file path: {e}")
```

### URL Validation Function
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (metadata)
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
]

def validate_url(url: str) -> str:
    """
    Validate URL to prevent SSRF attacks.
    
    Args:
        url: User-provided URL
        
    Returns:
        Validated URL string
        
    Raises:
        ValueError: If URL is invalid or points to blocked resource
    """
    parsed = urlparse(url)
    
    # Only allow http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    
    # Resolve hostname to IP
    try:
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must have a hostname")
            
        # Get IP address
        import socket
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        # Check against blocked ranges
        for blocked_range in BLOCKED_IP_RANGES:
            if ip_obj in blocked_range:
                raise ValueError(f"Access to {ip} is blocked (SSRF prevention)")
                
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")
    
    return url
```

## Testing Requirements

1. **Path Traversal Tests**
   - Attempt to access `/etc/passwd` via `../../` patterns
   - Test absolute paths (`/etc/passwd`)
   - Test Windows paths (`C:\Windows\System32\config\sam`)
   - Test URL encoded traversal (`..%2F..%2F`)

2. **SSRF Tests**
   - Attempt to access `http://127.0.0.1`
   - Attempt to access `http://169.254.169.254` (AWS metadata)
   - Attempt to access internal IP ranges

3. **Positive Tests**
   - Verify legitimate files can still be accessed
   - Verify legitimate URLs still work

## Timeline

- **Week 1**: Implement path validation and URL validation functions
- **Week 1**: Update `open_image` and `open_gif` to use validation
- **Week 1**: Add security tests
- **Week 2**: Code review and security testing
- **Week 2**: Deploy fixes

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [OWASP SSRF](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery)
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-918: SSRF](https://cwe.mitre.org/data/definitions/918.html)

---

**Review Status**: In Progress  
**Fixes Required**: YES - CRITICAL  
**Next Steps**: Implement fixes and security tests
