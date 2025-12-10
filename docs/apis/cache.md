# Images and Cache APIs

## Overview

LedFx provides API endpoints for retrieving and managing images. Remote images are automatically cached with a "cache and keep" policy, providing performance benefits while giving you explicit control over cache management.

## Cache Policy

- **No automatic expiration**: Images cached indefinitely
- **No TTL**: No time-based refresh
- **LRU eviction**: Least Recently Used items evicted when cache limits exceeded
- **Explicit control**: Refresh/clear only via API calls
- **Access tracking**: Updates `last_accessed` and `access_count` on every cache hit

## Cache Limits

- **Default max size**: 500MB (configurable in `config.json`)
- **Default max items**: 500 images (configurable in `config.json`)
- **Eviction strategy**: LRU (Least Recently Used)

## Configuration

Add to `config.json`:

```json
{
  "image_cache": {
    "max_size_mb": 500,
    "max_items": 500
  }
}
```

## API Endpoints

### Get Cache Statistics

Get current cache statistics including all cached entries.

**Endpoint:** `GET /api/cache/images`

**Success Response (bare response - no status wrapper):**
```json
{
  "total_size": 52428800,
  "total_count": 45,
  "max_size": 524288000,
  "max_count": 500,
  "cache_policy": {
    "expiration": "none",
    "refresh": "explicit only",
    "eviction": "LRU when limits exceeded"
  },
  "entries": [
    {
      "url": "https://example.com/image.gif",
      "cached_at": "2024-01-15T10:30:00Z",
      "last_accessed": "2024-01-20T14:20:00Z",
      "access_count": 42,
      "file_size": 524288,
      "content_type": "image/gif"
    }
  ]
}
```

**Error Response (cache not initialized):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Image cache not initialized"
  }
}
```

**Entries sorted by:** `access_count` (descending) - most frequently used first

---

### Clear Cache

Clear specific URL from cache or clear entire cache.

**Endpoint:** `DELETE /api/cache/images`

**Query Parameters:**
- `url` (optional): Specific URL to clear
- `all_variants` (optional, default: false): If "true" and url provided, clears all cache entries for that URL (including thumbnails with different params)

**Examples:**

Clear specific URL:
```
DELETE /api/cache/images?url=https://example.com/image.gif
```

Clear all thumbnail variants for an asset:
```
DELETE /api/cache/images?url=asset://backgrounds/galaxy.jpg&all_variants=true
```

Clear entire cache:
```
DELETE /api/cache/images
```

**Success Response (specific URL):**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Cleared cache for URL: https://example.com/image.gif"
  },
  "data": {
    "cleared_count": 1
  }
}
```

**Success Response (entire cache):**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Entire cache cleared"
  },
  "data": {
    "cleared_count": 45,
    "freed_bytes": 52428800
  }
}
```

**Error Response (URL not found):**
```json
{
  "status": "failed",
  "payload": {
    "type": "warning",
    "reason": "URL not found in cache: https://example.com/notfound.gif"
  }
}
```

---

### Refresh Image

Clear a cached image to force re-download on next access.

This endpoint removes the specified URL from the cache. The next time the image is requested via `/api/get_image` or `/api/get_gif_frames`, it will be re-downloaded from the origin server and cached again.

**Endpoint:** `POST /api/cache/images/refresh`

**Request Body:**
```json
{
  "url": "https://example.com/image.gif",
  "all_variants": false
}
```

**Parameters:**
- `url` (required): The URL to clear from cache
- `all_variants` (optional, default: false): If true, clears all cached entries for this URL (useful for clearing all thumbnail size/dimension variations of an asset)

**Success Response (entry was in cache):**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Cache entry cleared. Image will be re-downloaded on next access."
  },
  "data": {
    "url": "https://example.com/image.gif"
  }
}
```

**Success Response (entry was not in cache):**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "URL was not in cache (no action needed)."
  },
  "data": {
    "url": "https://example.com/image.gif"
  }
}
```

**Success Response (all_variants=true, multiple cleared):**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Cleared 3 cache entries. Images will be regenerated on next access."
  },
  "data": {
    "url": "asset://backgrounds/galaxy.jpg",
    "cleared_count": 3
  }
}
```

**Error Response (invalid request):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Missing 'url' in request body"
  }
}
```

---

## Image Request Endpoints

### /api/get_image

A RESTful endpoint designed for retrieving an image. Clients can request
a file by providing either the URL or the local file path of the image
resource. The image is returned in JPEG format for efficient data
transmission.

**Security Features:**
- ✅ File type validation (triple-layer: extension + MIME + PIL format)
- ✅ Size limits (10MB max file size, 4096×4096 pixels max)
- ✅ Path traversal protection (local files restricted to config dir and assets dir)
- ✅ SSRF protection (blocks private networks, loopback, link-local, cloud metadata endpoints)
- ✅ URL scheme validation (only http/https for remote, no schemes for local files)
- ✅ Download timeout (30 seconds)
- ✅ Automatic caching with corruption recovery

#### Endpoint Details

-   **Endpoint Path**: `/api/get_image`

#### Request

-   **Method**: POST
-   **Request Body** (JSON):
    -   `path_url` (String, required): The URL or local file path of the image to be opened.
        - **Remote URLs**: Only `http://` or `https://` URLs are allowed. Downloaded and cached automatically.
        - **Local files**: Plain file paths only (no URL schemes). Must be within config directory or LEDFX_ASSETS_PATH.

#### Response

All responses return **Status Code 200** with JSON body (for frontend snackbar compatibility).

-   **Success**:
    -   Body:
        -   `status` (String): `"success"`
        -   `image` (String): Base64-encoded JPEG image data

-   **Failure**:
    -   Body:
        -   `status` (String): `"error"` or `"failed"`
        -   `reason` (String): Error description (e.g., "Failed to open image from: <path_url>")

#### Error Handling

The endpoint returns status code 200 for all responses (success and error) to support frontend snackbar notifications. Check the `status` field in the JSON response to determine success/failure.

**Common error reasons:**
- `"Required attribute "path_url" was not provided"` - Missing required parameter
- `"Failed to open image from: <path>"` - Image validation failed, file not found, or path traversal blocked
- Invalid JSON body

Error response structure:

``` json
{
  "status": "failed",
  "reason": "<error description>"
}
```

#### Usage Example

##### Requesting Remote Image

To request an image from a URL, send a POST request with JSON body:

``` json
{
  "path_url": "https://example.com/image.gif"
}
```

**Note:** Remote images are automatically cached. Subsequent requests for the same URL will use the cached version unless explicitly refreshed via the cache API.

##### Requesting Local File

For a local file (must be within config directory or assets directory):

``` json
{
  "path_url": "/path/to/local/image.gif"
}
```

Windows example:

``` json
{
  "path_url": "C:\\Users\\username\\.ledfx\\images\\custom.gif"
}
```

**Security Note:**

Local file paths are restricted to:
- Config directory (e.g., `~/.ledfx/` or `C:\Users\username\.ledfx\`)
- LEDFX_ASSETS_PATH (built-in preset assets)

Remote URLs are protected against SSRF attacks by blocking:
- Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
- Loopback addresses (127.0.0.0/8, ::1/128)
- Link-local addresses (169.254.0.0/16, fe80::/10)
- Cloud metadata endpoints (169.254.169.254, metadata.google.internal)

URL schemes other than http/https are rejected (file://, ftp://, javascript:, etc.).

Attempts to access blocked resources (e.g., `/etc/passwd`, `C:\Windows\System32\*`, `http://127.0.0.1/`, `file:///etc/passwd`) will be blocked with error response.

##### Sample Success Response

``` json
{
  "status": "success",
  "image": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a..."
}
```

##### Sample Error Response

``` json
{
  "status": "failed",
  "reason": "Failed to open image from: /invalid/path.gif"
}
```

---

### /api/get_gif_frames

A RESTful endpoint designed for extracting and returning individual
frames from a GIF or animated image. Clients can request frames by providing either
the URL or the local file path of the image resource. The frames are
returned in JPEG format for efficient data transmission.

**Security Features:**
- ✅ File type validation (triple-layer: extension + MIME + PIL format)
- ✅ Size limits (10MB max file size, 4096×4096 pixels max)
- ✅ Path traversal protection (local files restricted to config dir and assets dir)
- ✅ SSRF protection (blocks private networks, loopback, link-local, cloud metadata endpoints)
- ✅ URL scheme validation (only http/https for remote, no schemes for local files)
- ✅ Download timeout (30 seconds)
- ✅ Automatic caching with corruption recovery

#### Endpoint Details

-   **Endpoint Path**: `/api/get_gif_frames`

#### Request

-   **Method**: POST
-   **Request Body** (JSON):
    -   `path_url` (String, required): The URL or local file path of the GIF/animated image
        from which frames are to be extracted.
        - **Remote URLs**: Only `http://` or `https://` URLs are allowed. Downloaded and cached automatically.
        - **Local files**: Plain file paths only (no URL schemes). Must be within config directory or LEDFX_ASSETS_PATH.

#### Response

All responses return **Status Code 200** with JSON body (for frontend snackbar compatibility).

-   **Success**:
    -   Body:
        -   `status` (String): `"success"`
        -   `frame_count` (Integer): The number of frames extracted from the image
        -   `frames` (List): A list of base64-encoded strings, each representing a frame in JPEG format

-   **Failure**:
    -   Body:
        -   `status` (String): `"error"` or `"failed"`
        -   `reason` (String): Error description (e.g., "Failed to open gif from: <path_url>")

#### Error Handling

The endpoint returns status code 200 for all responses (success and error) to support frontend snackbar notifications. Check the `status` field in the JSON response to determine success/failure.

**Common error reasons:**
- `"Required attribute "path_url" was not provided"` - Missing required parameter
- `"Failed to open gif from: <path>"` - Image validation failed, file not found, or path traversal blocked
- Invalid JSON body

Error response structure:

``` json
{
  "status": "failed",
  "reason": "<error description>"
}
```

#### Usage Example

##### Requesting GIF Frames from Remote URL

To request frames from a GIF image, send a POST request with JSON body:

``` json
{
  "path_url": "https://example.com/animated.gif"
}
```

**Note:** Remote images are automatically cached. Subsequent requests for the same URL will use the cached version unless explicitly refreshed via the cache API.

##### Requesting GIF Frames from Local File

For a local file (must be within config directory or assets directory):

``` json
{
  "path_url": "/path/to/local/animation.gif"
}
```

Windows example:

``` json
{
  "path_url": "C:\\Users\\username\\.ledfx\\gifs\\custom.gif"
}
```

**Security Note:**

Local file paths are restricted to:
- Config directory (e.g., `~/.ledfx/` or `C:\Users\username\.ledfx\`)
- LEDFX_ASSETS_PATH (built-in preset assets)

Remote URLs are protected against SSRF attacks by blocking:
- Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
- Loopback addresses (127.0.0.0/8, ::1/128)
- Link-local addresses (169.254.0.0/16, fe80::/10)
- Cloud metadata endpoints (169.254.169.254, metadata.google.internal)

URL schemes other than http/https are rejected (file://, ftp://, javascript:, etc.).

Attempts to access blocked resources will return an error response.

##### Sample Success Response

A successful response with two extracted frames:

``` json
{
  "status": "success",
  "frame_count": 2,
  "frames": [
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL...",
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL..."
  ]
}
```

##### Sample Error Response

``` json
{
  "status": "failed",
  "reason": "Failed to open gif from: /invalid/path.gif"
}
```

---

## Cache Workflow

### First Access
1. User requests image via `POST /api/get_image` with JSON body `{"path_url": "https://example.com/image.gif"}`
2. Image not in cache → download from URL
3. Validate file type (extension, MIME, PIL format)
4. Validate size (max 10MB, max 4096×4096 pixels)
5. Store in cache with metadata
6. Return image to user

### Subsequent Access
1. User requests same image
2. Image found in cache → validate cached file
3. If valid: return immediately
4. If corrupted/invalid: delete corrupt entry, re-download, cache fresh copy
5. Update `last_accessed` timestamp
6. Increment `access_count`
7. No expiration check

### Cache Error Handling
1. Cached file corrupted or unreadable
2. Log warning: "Error reading cached image, re-downloading"
3. Delete corrupt cache entry
4. Download fresh copy from original URL
5. Validate and cache new download
6. Return fresh image to user

This ensures the cache is **self-healing** - corruption doesn't break functionality.

### Cache Full (LRU Eviction)
1. New image exceeds cache limits
2. Find least recently accessed item (lowest `last_accessed`)
3. Tiebreaker: lowest `access_count`
4. Evict LRU item
5. Store new image

### Explicit Refresh
1. User calls `POST /api/cache/images/refresh` with URL
2. Cache entry deleted
3. Next access re-downloads from origin
4. New version cached with fresh metadata

---

## Use Cases

### View Most Used Images
```bash
curl http://localhost:8888/api/cache/images
```

Shows which images are accessed most frequently, sorted by `access_count`.

### Clear Old Unused Image
```bash
curl -X DELETE "http://localhost:8888/api/cache/images?url=https://old-domain.com/unused.gif"
```

### Force Refresh Stale Image
```bash
curl -X POST http://localhost:8888/api/cache/images/refresh \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/updated.gif"}'
```

Next access to this URL will download a fresh copy.

### Clear Entire Cache (Fresh Start)
```bash
curl -X DELETE http://localhost:8888/api/cache/images
```

---

## Benefits

- **Performance**: Instant access to frequently used images
- **Bandwidth**: No redundant downloads
- **Reliability**: Works offline once cached
- **Control**: Manual management of cache contents
- **Persistence**: Cache survives LedFx restarts
